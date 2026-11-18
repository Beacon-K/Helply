"""Merge a {msgid: french} dict (Python file) into locale/fr/LC_MESSAGES/django.po.  Usage: python tools/fill_translations.py <dict.py>"""
import ast, importlib.util, re, sys
from pathlib import Path

NB = "\u00a0"


def typo(s):
    # French typography: a (non-breaking) space before ? ! : ; and inside « » -- but not inside HTML tags or placeholders
    s = re.sub(r"(?<=[^\s\u00a0%]) ([?!:;»])", NB + r"\1", s)
    s = s.replace("« ", "«" + NB)
    return s


def esc(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\n") + '"'


def main(dict_path):
    spec = importlib.util.spec_from_file_location("frdict", dict_path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    fr = mod.FR
    po = Path(__file__).resolve().parent.parent / "locale/fr/LC_MESSAGES/django.po"
    blocks = po.read_text(encoding="utf-8").split("\n\n")
    out, missing = [blocks[0]], []
    for b in blocks[1:]:
        m = re.search(r'^msgid (".*")$', b, re.M)
        if not m:
            out.append(b); continue
        mid = ast.literal_eval(m.group(1))
        have = re.search(r'^msgstr(?:\[0\])? (".+")$', b, re.M)
        if mid not in fr or have:
            if not have: missing.append(mid)
            out.append(b); continue
        val = fr[mid]
        head = [l for l in b.split("\n") if not l.startswith("msgstr")]
        if isinstance(val, tuple):
            body = head + ["msgstr[%d] %s" % (i, esc(typo(v))) for i, v in enumerate(val)]
        else:
            body = head + ["msgstr " + esc(typo(val))]
        out.append("\n".join(body))
    po.write_text("\n\n".join(out), encoding="utf-8")
    print("untranslated:", len(missing))
    for m in missing: print("  ", repr(m)[:110])


main(sys.argv[1])
