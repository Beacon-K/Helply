"""Collect translatable strings into locale/fr/LC_MESSAGES/django.po without GNU gettext.

Usage:  python tools/extract_messages.py        (then edit the .po, then: python tools/compile_messages.py)

Reads every template ({% trans %}, {% blocktrans %}, _("...") in filter arguments) and every .py file under apps/ and
config/ (gettext / gettext_lazy / ngettext / _ calls) and merges the result into the existing .po file: new strings are
added with an empty msgstr, existing translations are kept, strings that disappeared are marked obsolete (#~) so nothing
is lost by accident.  Needs Django importable (run it with the project's virtual environment).
"""
import ast
import os
import re
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.template import engines  # noqa: E402
from django.templatetags.i18n import BlockTranslateNode, TranslateNode  # noqa: E402
from django.template.base import Variable  # noqa: E402
from django.template.defaulttags import IfNode  # noqa: E402

LANGS = ["fr"]
found = OrderedDict()  # (msgid, plural) -> set(ref)


def add(msgid, plural, ref):
    if not msgid or not msgid.strip():
        return
    found.setdefault((msgid, plural), set()).add(ref)


def blocktrans_text(tokens):
    out = []
    for tok in tokens:
        if tok.token_type.name == "TEXT":
            out.append(tok.contents.replace("%", "%%"))
        elif tok.token_type.name == "VAR":
            out.append("%%(%s)s" % tok.contents)
    return "".join(out)


def walk(nodes, ref):
    for node in nodes:
        if isinstance(node, TranslateNode):
            fe = node.filter_expression
            if isinstance(fe.var, Variable) and fe.var.literal is not None:
                add(str(fe.var.literal), None, ref)
        elif isinstance(node, BlockTranslateNode):
            singular = blocktrans_text(node.singular)
            plural = blocktrans_text(node.plural) if node.plural else None
            add(singular, plural, ref)
        if isinstance(node, IfNode):
            for cond, nl in node.conditions_nodelists:
                walk(nl, ref)
            continue
        for attr in ("nodelist", "nodelist_true", "nodelist_false", "nodelist_loop", "nodelist_empty"):
            sub = getattr(node, attr, None)
            if sub:
                walk(sub, ref)


# Template filter arguments such as default:_("Unassigned") are found in the raw source below.
TRANSLATED_ARG = re.compile(r'''_\(\s*(?P<q>["'])(?P<s>(?:\\.|(?!(?P=q)).)*)(?P=q)\s*\)''')


def extract_templates():
    engine = engines["django"].engine
    for base in [ROOT / "templates"] + sorted((ROOT / "apps").glob("*/templates")):
        for path in sorted(base.rglob("*.html")):
            rel = path.relative_to(ROOT).as_posix()
            src = path.read_text(encoding="utf-8")
            try:
                tpl = engine.from_string(src)
            except Exception as exc:  # a template that needs a tag library we do not know here
                print("skip %s: %s" % (rel, exc), file=sys.stderr)
                continue
            walk(tpl.nodelist, rel)
            for m in TRANSLATED_ARG.finditer(src):
                add(bytes(m.group("s"), "utf-8").decode("unicode_escape") if "\\" in m.group("s") else m.group("s"), None, rel)


def py_call_name(node):
    f = node.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None


def extract_python():
    names = {"gettext", "gettext_lazy", "_", "ngettext", "ngettext_lazy", "pgettext", "pgettext_lazy"}
    for folder in ("apps", "config"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            if "migrations" in path.parts or path.name.startswith("test"):
                continue
            rel = path.relative_to(ROOT).as_posix()
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and py_call_name(node) in names and node.args:
                    name = py_call_name(node)
                    if name.startswith("ngettext") and len(node.args) >= 2:
                        a, b = node.args[0], node.args[1]
                        if all(isinstance(x, ast.Constant) and isinstance(x.value, str) for x in (a, b)):
                            add(a.value, b.value, rel)
                    elif name.startswith("pgettext"):
                        continue
                    elif isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        add(node.args[0].value, None, rel)


def esc(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def po_block(key, refs, msgstr):
    msgid, plural = key
    lines = ["#: " + " ".join(sorted(refs)[:3])]
    if "%(" in msgid or "%%" in msgid or (plural and "%(" in plural):
        lines.append("#, python-format")
    lines.append("msgid " + esc(msgid))
    if plural is not None:
        lines.append("msgid_plural " + esc(plural))
        strs = msgstr if isinstance(msgstr, list) else ["", ""]
        for i, s in enumerate(strs):
            lines.append("msgstr[%d] %s" % (i, esc(s)))
    else:
        lines.append("msgstr " + esc(msgstr if isinstance(msgstr, str) else ""))
    return "\n".join(lines)


def read_existing(path):
    """Return {(msgid, plural): msgstr or [msgstr0, msgstr1]} from an existing .po (fuzzy ones are kept as-is)."""
    out = {}
    if not path.exists():
        return out
    cur, field = {}, None

    def flush():
        nonlocal cur
        if "msgid" in cur:
            key = (cur["msgid"], cur.get("msgid_plural"))
            if "msgid_plural" in cur:
                out[key] = [cur.get("msgstr", {}).get(i, "") for i in (0, 1)]
            else:
                out[key] = cur.get("msgstr", {}).get(0, "")
        cur = {}

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            flush()
            field = None
            continue
        if line.startswith("#"):
            continue
        if line.startswith("msgid_plural "):
            cur["msgid_plural"] = ast.literal_eval(line[13:])
            field = "msgid_plural"
        elif line.startswith("msgid "):
            if "msgid" in cur:
                flush()
            cur["msgid"] = ast.literal_eval(line[6:])
            field = "msgid"
        elif line.startswith("msgstr["):
            i = int(line[7:line.index("]")])
            cur.setdefault("msgstr", {})[i] = ast.literal_eval(line[line.index("]") + 1:].strip())
            field = ("msgstr", i)
        elif line.startswith("msgstr "):
            cur.setdefault("msgstr", {})[0] = ast.literal_eval(line[7:])
            field = ("msgstr", 0)
        elif line.startswith('"'):
            t = ast.literal_eval(line)
            if isinstance(field, tuple):
                cur["msgstr"][field[1]] += t
            else:
                cur[field] += t
    flush()
    return out


HEADER = {
    "fr": 'msgid ""\nmsgstr ""\n"Project-Id-Version: Helply\\n"\n"Language: fr\\n"\n"MIME-Version: 1.0\\n"\n"Content-Type: text/plain; charset=UTF-8\\n"\n"Content-Transfer-Encoding: 8bit\\n"\n"Plural-Forms: nplurals=2; plural=(n > 1);\\n"\n',
}


def main():
    extract_templates()
    extract_python()
    for lang in LANGS:
        path = ROOT / "locale" / lang / "LC_MESSAGES" / "django.po"
        path.parent.mkdir(parents=True, exist_ok=True)
        old = read_existing(path)
        blocks, kept, new = [HEADER[lang]], 0, 0
        for key, refs in found.items():
            if key in old and old[key] not in ("", ["", ""]):
                kept += 1
            else:
                new += 1
            blocks.append(po_block(key, refs, old.get(key, "")))
        gone = [k for k in old if k not in found and k != ("", None) and any(old[k] if isinstance(old[k], list) else [old[k]])]
        for key in gone:
            blocks.append("\n".join("#~ " + l for l in po_block(key, set(), old[key]).splitlines() if not l.startswith("#:")))
        path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
        print("%s: %d strings (%d translated, %d to translate, %d obsolete)" % (path.relative_to(ROOT), len(found), kept, new, len(gone)))


if __name__ == "__main__":
    main()
