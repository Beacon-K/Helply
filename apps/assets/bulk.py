"""Bulk Excel export / import for the asset register.

Rules that keep the database the single source of truth:
* assets are matched on ``asset_tag`` (the only unique field) and only matched rows are ever changed;
* nothing is deleted, whatever is missing from the file;
* an empty cell on an existing asset means "leave as it is" (never "clear it");
* cell contents are values only: formulas are refused, text is never evaluated.
"""
import datetime as dt
import re
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.accounts.models import Department

from . import xlsx
from .models import Asset

MAX_ROWS = 2000
SHEET = "Assets"

# (header, model attribute, width). The header text is what users see and what the import checks.
COLUMNS = [
    ("Asset tag", "asset_tag", 14),
    ("Name", "name", 30),
    ("Type", "type", 18),
    ("Status", "status", 12),
    ("Serial number", "serial_number", 20),
    ("Owner (username or email)", "owner", 26),
    ("Department", "department", 18),
    ("Location", "location", 20),
    ("Supplier", "supplier", 20),
    ("Purchase date", "purchase_date", 14),
    ("Purchase cost (CAD)", "purchase_cost", 16),
    ("Warranty / renewal date", "warranty_expiry", 20),
    ("Notes", "notes", 40),
]
HEADERS = [c[0] for c in COLUMNS]
KEYS = [c[1] for c in COLUMNS]
LABELS = dict(zip(KEYS, HEADERS))
TEXT_LIMITS = {"asset_tag": 30, "name": 150, "serial_number": 100, "location": 100, "supplier": 100}

_FORMULA_START = "=+-@\t\r"
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def safe_text(value):
    """Exported text must never start like a formula: Excel would run it when the file is opened."""
    text = "" if value is None else str(value)
    stripped = text.lstrip()
    if stripped[:1] in tuple(_FORMULA_START):
        return stripped.lstrip(_FORMULA_START + " ")
    return text


# ---------------------------------------------------------------- export / template

def export_bytes(assets):
    rows = [HEADERS]
    for a in assets:
        rows.append([
            safe_text(a.asset_tag), safe_text(a.name), a.type, a.status, safe_text(a.serial_number),
            safe_text(a.owner.username if a.owner else ""), safe_text(a.department.name if a.department else ""),
            safe_text(a.location), safe_text(a.supplier), a.purchase_date, a.purchase_cost, a.warranty_expiry,
            safe_text(a.notes),
        ])
    return xlsx.write_workbook([(SHEET, rows, [c[2] for c in COLUMNS])])


def template_bytes():
    types = ", ".join(f"{v} ({l})" for v, l in Asset.Type.choices)
    statuses = ", ".join(f"{v} ({l})" for v, l in Asset.Status.choices)
    help_rows = [
        ["How to import assets into Helply"],
        [""],
        ["1. Fill in the 'Assets' sheet: one row per asset, keep the header row exactly as it is."],
        ["2. Upload the file on the Assets page. You will see a preview first; nothing changes until you confirm."],
        ["3. Rows whose Asset tag already exists UPDATE that asset; other rows create a new asset."],
        ["4. On existing assets an empty cell leaves the current value alone. Assets missing from the file are never deleted."],
        [""],
        ["Required for new assets: Asset tag, Name, Type."],
        [f"Type: {types}"],
        [f"Status (default in_stock): {statuses}"],
        ["Owner: the username or email of an existing Helply user. Leave empty for a shared asset."],
        ["Department: the exact name of an existing department."],
        ["Dates: YYYY-MM-DD (or an Excel date). Cost: a plain number in CAD, no currency symbol."],
        [f"Limits: {MAX_ROWS} rows, 5 MB, .xlsx only. Formulas are not accepted: paste values instead."],
    ]
    return xlsx.write_workbook([(SHEET, [HEADERS], [c[2] for c in COLUMNS]),
                                ("Instructions", help_rows, [120])])


# ---------------------------------------------------------------- reading the upload

class SheetError(ValueError):
    pass


def _as_text(value):
    if value is None:
        return ""
    if isinstance(value, xlsx.Formula):
        raise SheetError("formula")
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float):
        return str(int(value)) if value == int(value) else repr(value)
    return _CONTROL.sub("", str(value)).strip()


def read_upload(fileobj):
    """Parse an uploaded workbook into ``[(row_number, {key: str}, [errors])]``. Raises SheetError."""
    try:
        rows = xlsx.read_rows(fileobj, max_rows=MAX_ROWS + 1, sheet_name=SHEET)
    except xlsx.XlsxError as exc:
        raise SheetError(str(exc))
    if not rows:
        raise SheetError("The sheet is empty. The first row must contain the column headers.")
    _, header = rows[0]
    names = [_as_text(h).casefold() if not isinstance(h, xlsx.Formula) else "" for h in header]
    expected = {h.casefold(): k for h, k in zip(HEADERS, KEYS)}
    missing = [h for h in HEADERS if h.casefold() not in names]
    unknown = [header[i] for i, n in enumerate(names) if n and n not in expected]
    if missing:
        raise SheetError("Missing column(s): " + ", ".join(missing) + ". Download the template to get the exact headers.")
    if unknown:
        raise SheetError("Unknown column(s): " + ", ".join(_as_text(u) for u in unknown) + ".")
    if len({n for n in names if n}) != len([n for n in names if n]):
        raise SheetError("A column header appears twice.")
    index = {expected[n]: i for i, n in enumerate(names) if n}
    out = []
    for number, cells in rows[1:]:
        data, errors = {}, []
        for key in KEYS:
            i = index[key]
            try:
                data[key] = _as_text(cells[i]) if i < len(cells) else ""
            except SheetError:
                data[key] = ""
                errors.append(f"{LABELS[key]}: formulas are not accepted, paste the value instead")
        out.append((number, data, errors))
    if not out:
        raise SheetError("The sheet has a header row but no assets.")
    return out


# ---------------------------------------------------------------- validation / classification

def _choice(value, choices, label):
    folded = value.casefold()
    for v, l in choices:
        if folded in (v.casefold(), l.casefold()):
            return v
    raise ValueError(f"{label} '{value}' is not valid (use one of: {', '.join(v for v, _ in choices)})")


def _date(value, label):
    try:
        d = dt.date.fromisoformat(value[:10]) if re.fullmatch(r"\d{4}-\d{2}-\d{2}([ T].*)?", value) else None
    except ValueError:
        d = None
    if d is None or not (1980 <= d.year <= 2100):
        raise ValueError(f"{label} '{value}' is not a date (use YYYY-MM-DD)")
    return d


def _cost(value):
    try:
        d = Decimal(value.replace(",", "").lstrip("$"))
    except InvalidOperation:
        raise ValueError(f"Purchase cost '{value}' is not a number")
    if not d.is_finite() or d < 0 or d >= Decimal("100000000"):
        raise ValueError("Purchase cost must be between 0 and 99,999,999.99")
    if d != d.quantize(Decimal("0.01")):
        raise ValueError("Purchase cost can have at most 2 decimals")
    return d.quantize(Decimal("0.01"))


class Lookups:
    def __init__(self):
        User = get_user_model()
        self.assets = {}
        for a in Asset.objects.select_related("owner", "department"):
            self.assets.setdefault(a.asset_tag.casefold(), []).append(a)
        self.users = {}
        self.emails = {}
        for u in User.objects.filter(is_active=True):
            self.users[u.username.casefold()] = u
            if u.email:
                self.emails.setdefault(u.email.casefold(), []).append(u)
        self.departments = {d.name.casefold(): d for d in Department.objects.all()}

    def find_asset(self, tag):
        found = self.assets.get(tag.casefold(), [])
        return next((a for a in found if a.asset_tag == tag), found[0] if len(found) == 1 else None)

    def find_user(self, ident):
        user = self.users.get(ident.casefold())
        if user:
            return user
        by_email = self.emails.get(ident.casefold(), [])
        if len(by_email) > 1:
            raise ValueError(f"Owner '{ident}' matches several users, use the username")
        if by_email:
            return by_email[0]
        raise ValueError(f"Owner '{ident}' is not an active Helply user")


def _display(field, value):
    if field == "owner":
        return value.username if value else "Shared"
    if field == "department":
        return value.name if value else "–"
    if value in (None, ""):
        return "–"
    return str(value)


def classify(parsed):
    """Turn parsed rows into a plan.

    Returns dict(create=[...], update=[...], unchanged=[...], errors=[...]); each item has ``row``, ``tag``,
    ``name`` and (create/update) ``values`` — the cleaned model values — plus ``changes`` for updates.
    """
    lk = Lookups()
    plan = {"create": [], "update": [], "unchanged": [], "errors": []}
    seen = {}
    for number, data, errors in parsed:
        errors = list(errors)
        tag = data["asset_tag"]
        if not any(data.values()) and not errors:
            continue
        values = {}
        existing = None
        if not tag:
            errors.append("Asset tag is required")
        elif len(tag) > TEXT_LIMITS["asset_tag"]:
            errors.append(f"Asset tag is longer than {TEXT_LIMITS['asset_tag']} characters")
        else:
            if tag.casefold() in seen:
                errors.append(f"Duplicate of row {seen[tag.casefold()]} in this file")
            else:
                seen[tag.casefold()] = number
            existing = lk.find_asset(tag)
            if existing is None and len(lk.assets.get(tag.casefold(), [])) > 1:
                errors.append("Matches several existing assets that differ only by upper/lower case")
        for key in ("name", "serial_number", "location", "supplier"):
            if len(data[key]) > TEXT_LIMITS[key]:
                errors.append(f"{LABELS[key]} is longer than {TEXT_LIMITS[key]} characters")
            elif data[key]:
                values[key] = data[key]
        if data["notes"]:
            if len(data["notes"]) > 5000:
                errors.append("Notes are longer than 5000 characters")
            else:
                values["notes"] = data["notes"]
        converters = (
            ("type", lambda v: _choice(v, Asset.Type.choices, "Type")),
            ("status", lambda v: _choice(v, Asset.Status.choices, "Status")),
            ("owner", lk.find_user),
            ("department", None),
            ("purchase_date", lambda v: _date(v, "Purchase date")),
            ("warranty_expiry", lambda v: _date(v, "Warranty / renewal date")),
            ("purchase_cost", _cost),
        )
        for key, fn in converters:
            if not data[key]:
                continue
            try:
                if key == "department":
                    dept = lk.departments.get(data[key].casefold())
                    if dept is None:
                        raise ValueError(f"Department '{data[key]}' does not exist")
                    values[key] = dept
                else:
                    values[key] = fn(data[key])
            except ValueError as exc:
                errors.append(str(exc))
        if existing is None and not errors:
            for key in ("name", "type"):
                if key not in values:
                    errors.append(f"{LABELS[key]} is required for a new asset")
        item = {"row": number, "tag": tag, "name": values.get("name") or (existing.name if existing else ""),
                "values": values}
        if errors:
            item["errors"] = errors
            plan["errors"].append(item)
        elif existing is None:
            plan["create"].append(item)
        else:
            changes = [(LABELS[k], _display(k, getattr(existing, k)), _display(k, v))
                       for k, v in values.items() if getattr(existing, k) != v]
            item["asset"] = existing
            item["changes"] = changes
            plan["update"].append(item) if changes else plan["unchanged"].append(item)
    return plan


def apply_plan(plan):
    """Write creates and updates in one transaction. Returns (created, updated)."""
    with transaction.atomic():
        for item in plan["create"]:
            vals = dict(item["values"])
            Asset.objects.create(asset_tag=item["tag"], **vals)
        for item in plan["update"]:
            asset = item["asset"]
            for key, value in item["values"].items():
                setattr(asset, key, value)
            asset.save()
    return len(plan["create"]), len(plan["update"])
