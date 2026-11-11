"""Minimal .xlsx reader/writer built on the standard library (zipfile + ElementTree).

Why not openpyxl: no extra dependency to install on every machine and in Docker, and the reader is
deliberately narrow — it only returns cell *values* of one sheet, never evaluates formulas, never follows
external links and rejects anything that looks like a zip bomb or an XML entity trick. The file name and
content type are never consulted; only the bytes are.
"""
import datetime as dt
import re
import zipfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 40 * 1024 * 1024
MAX_PARTS = 200
MAX_COLS = 30

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "pr": "http://schemas.openxmlformats.org/package/2006/relationships"}
_M = "{%s}" % NS["m"]
_EPOCH = dt.date(1899, 12, 30)
_BUILTIN_DATE_FORMATS = set(range(14, 23)) | {45, 46, 47}


class XlsxError(ValueError):
    """The file is not a usable workbook. The message is safe to show to the user."""


class Formula:
    """Marker for a cell that contains a formula (we refuse to read those)."""


# ---------------------------------------------------------------- reading

def _read_part(zf, name, limit=MAX_UNCOMPRESSED_BYTES):
    try:
        data = zf.read(name)
    except KeyError:
        return None
    if len(data) > limit:
        raise XlsxError("The workbook is too large once unpacked.")
    head = data[:4096].lower()
    if b"<!doctype" in head or b"<!entity" in data[:65536].lower():
        raise XlsxError("The workbook contains unsupported XML (DOCTYPE/entities).")
    return data


def _parse(data):
    try:
        return ET.fromstring(data)
    except ET.ParseError:
        raise XlsxError("The workbook XML is damaged.")


def _text_of(si):
    """Text of a shared-string/inline-string element (ignores phonetic runs)."""
    parts = []
    for t in si.iter():
        if t.tag == _M + "t" and not _inside_phonetic(si, t):
            parts.append(t.text or "")
    return "".join(parts)


def _inside_phonetic(root, node):
    for rph in root.findall(_M + "rPh"):
        if node in rph.iter():
            return True
    return False


def _col_index(ref):
    letters = re.match(r"[A-Z]+", ref or "")
    if not letters:
        raise XlsxError("A cell reference in the workbook is invalid.")
    n = 0
    for ch in letters.group():
        n = n * 26 + ord(ch) - 64
    return n - 1


def _date_style_ids(zf):
    data = _read_part(zf, "xl/styles.xml")
    if data is None:
        return set()
    root = _parse(data)
    custom = {}
    for nf in root.iter(_M + "numFmt"):
        code = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", nf.get("formatCode", "")).lower()
        if re.search(r"[ymdhs]", code):
            custom[int(nf.get("numFmtId", "0"))] = True
    ids = set()
    xfs = root.find(_M + "cellXfs")
    if xfs is not None:
        for i, xf in enumerate(xfs.findall(_M + "xf")):
            fmt = int(xf.get("numFmtId", "0"))
            if fmt in _BUILTIN_DATE_FORMATS or custom.get(fmt):
                ids.add(i)
    return ids


def read_rows(fileobj, max_rows=2001, sheet_name="Assets"):
    """Return the rows (lists of str / date / float / Formula / None) of one sheet.

    Reads the sheet called ``sheet_name`` or, failing that, the first sheet. Raises XlsxError on anything
    that is not a plain, reasonably sized workbook. Stops with XlsxError beyond ``max_rows`` rows.
    """
    fileobj.seek(0, 2)
    size = fileobj.tell()
    fileobj.seek(0)
    if size == 0:
        raise XlsxError("The file is empty.")
    if size > MAX_FILE_BYTES:
        raise XlsxError(f"The file is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB.")
    if fileobj.read(4) != b"PK\x03\x04":
        raise XlsxError("This is not an .xlsx workbook (older .xls and .csv files are not supported).")
    fileobj.seek(0)
    try:
        zf = zipfile.ZipFile(fileobj)
    except zipfile.BadZipFile:
        raise XlsxError("The file is damaged or is not a real .xlsx workbook.")
    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_PARTS or sum(i.file_size for i in infos) > MAX_UNCOMPRESSED_BYTES:
            raise XlsxError("The workbook is too large once unpacked.")
        names = {i.filename for i in infos}
        if "xl/workbook.xml" not in names:
            raise XlsxError("This is not an Excel workbook (xl/workbook.xml is missing).")
        sheet_path = _find_sheet(zf, sheet_name)
        shared = []
        data = _read_part(zf, "xl/sharedStrings.xml")
        if data is not None:
            shared = [_text_of(si) for si in _parse(data).findall(_M + "si")]
        date_styles = _date_style_ids(zf)
        data = _read_part(zf, sheet_path)
        if data is None:
            raise XlsxError("The worksheet could not be found in the workbook.")
        return _read_sheet(_parse(data), shared, date_styles, max_rows)


def _find_sheet(zf, wanted):
    wb = _parse(_read_part(zf, "xl/workbook.xml"))
    sheets = wb.find(_M + "sheets")
    entries = sheets.findall(_M + "sheet") if sheets is not None else []
    if not entries:
        raise XlsxError("The workbook has no worksheets.")
    chosen = next((s for s in entries if (s.get("name") or "").lower() == wanted.lower()), entries[0])
    rid = chosen.get("{%s}id" % NS["r"])
    rels = _read_part(zf, "xl/_rels/workbook.xml.rels")
    if rid and rels is not None:
        for rel in _parse(rels):
            if rel.get("Id") == rid:
                target = rel.get("Target", "")
                if rel.get("TargetMode") == "External":
                    break
                path = target.lstrip("/") if target.startswith("/") else "xl/" + target
                return re.sub(r"[^/]+/\.\./", "", path)
    return "xl/worksheets/sheet1.xml"


def _read_sheet(root, shared, date_styles, max_rows):
    rows = []
    data = root.find(_M + "sheetData")
    if data is None:
        return rows
    for row in data.findall(_M + "row"):
        values = {}
        for c in row.findall(_M + "c"):
            col = _col_index(c.get("r"))
            if col >= MAX_COLS:
                if _cell_value(c, shared, date_styles) not in (None, ""):
                    raise XlsxError(f"There are more than {MAX_COLS} columns with data.")
                continue
            values[col] = _cell_value(c, shared, date_styles)
        r = int(row.get("r") or len(rows) + 1)
        if not any(v not in (None, "") for v in values.values()):
            continue
        if r > max_rows:
            raise XlsxError(f"The sheet has more than {max_rows - 1} rows of data.")
        width = max(values) + 1
        rows.append((r, [values.get(i) for i in range(width)]))
    return rows


def _cell_value(c, shared, date_styles):
    if c.find(_M + "f") is not None:
        return Formula()
    t = c.get("t", "n")
    v = c.find(_M + "v")
    if t == "inlineStr":
        is_ = c.find(_M + "is")
        return _text_of(is_) if is_ is not None else None
    if v is None or v.text is None:
        return None
    raw = v.text
    if t == "s":
        try:
            return shared[int(raw)]
        except (ValueError, IndexError):
            raise XlsxError("A shared string reference in the workbook is invalid.")
    if t in ("str", "e"):
        return raw
    if t == "b":
        return raw == "1"
    if t == "d":
        try:
            return dt.date.fromisoformat(raw[:10])
        except ValueError:
            return raw
    try:
        number = float(raw)
    except ValueError:
        return raw
    if int(c.get("s", "0") or 0) in date_styles:
        try:
            return _EPOCH + dt.timedelta(days=int(number))
        except (OverflowError, ValueError):
            return raw
    return number


# ---------------------------------------------------------------- writing

def _col_letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _clean_xml(text):
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]", "", text)


def write_workbook(sheets):
    """sheets: list of (name, rows, col_widths). A cell is str, int/float/Decimal, date or None.

    Row 0 of the first sheet is styled as the header. Dates get a yyyy-mm-dd format. Returns bytes.
    """
    import io
    from decimal import Decimal

    parts = {}
    sheet_xml = []
    for idx, (name, rows, widths) in enumerate(sheets, start=1):
        out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
               f'<worksheet xmlns="{NS["m"]}">']
        if rows and idx == 1:
            out.append('<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
                       'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>')
        if widths:
            out.append("<cols>" + "".join(f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>'
                                          for i, w in enumerate(widths, start=1)) + "</cols>")
        out.append("<sheetData>")
        for r, row in enumerate(rows, start=1):
            out.append(f'<row r="{r}">')
            for c, value in enumerate(row):
                ref = f"{_col_letter(c)}{r}"
                style = 1 if (idx == 1 and r == 1) else 0
                if value is None or value == "":
                    continue
                if isinstance(value, dt.date):
                    out.append(f'<c r="{ref}" s="2"><v>{(value - _EPOCH).days}</v></c>')
                elif isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
                    out.append(f'<c r="{ref}" s="{3 if isinstance(value, Decimal) else style}"><v>{value}</v></c>')
                else:
                    out.append(f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">'
                               f'{escape(_clean_xml(str(value)))}</t></is></c>')
            out.append("</row>")
        out.append("</sheetData></worksheet>")
        sheet_xml.append((name, "".join(out)))
    for i, (_, xml) in enumerate(sheet_xml, start=1):
        parts[f"xl/worksheets/sheet{i}.xml"] = xml
    n = len(sheet_xml)
    parts["[Content_Types].xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                  for i in range(1, n + 1)) + "</Types>")
    parts["_rels/.rels"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>')
    parts["xl/workbook.xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{NS["m"]}" xmlns:r="{NS["r"]}"><sheets>'
        + "".join(f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
                  for i, (name, _) in enumerate(sheet_xml, start=1)) + "</sheets></workbook>")
    parts["xl/_rels/workbook.xml.rels"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                  for i in range(1, n + 1))
        + f'<Relationship Id="rId{n + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '</Relationships>')
    parts["xl/styles.xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<styleSheet xmlns="{NS["m"]}">'
        '<numFmts count="1"><numFmt numFmtId="164" formatCode="yyyy\\-mm\\-dd"/></numFmts>'
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
        '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
        '<xf numFmtId="2" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>'
        '</styleSheet>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, xml in parts.items():
            zf.writestr(name, xml)
    return buf.getvalue()
