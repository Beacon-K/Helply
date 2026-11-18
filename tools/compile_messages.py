"""Compile locale/<lang>/LC_MESSAGES/django.po into django.mo with no GNU gettext installed.

Usage:  python tools/compile_messages.py
Handles the subset of .po syntax Helply uses: msgid / msgstr (multi-line strings), msgctxt, plural forms, comments,
fuzzy entries are skipped.  Run it after editing a .po file and commit the .mo next to it (Windows servers have no msgfmt).
"""
import ast
import struct
import sys
from pathlib import Path


def parse(path):
    entries, cur, field, fuzzy = {}, {}, None, False

    def flush():
        nonlocal cur, fuzzy
        if "msgid" in cur and not fuzzy:
            key = cur["msgid"] if "msgctxt" not in cur else cur["msgctxt"] + "\x04" + cur["msgid"]
            if "msgid_plural" in cur:
                key += "\x00" + cur["msgid_plural"]
                val = "\x00".join(cur["msgstr"][i] for i in sorted(cur["msgstr"]))
            else:
                val = cur.get("msgstr", {}).get(0, "")
            if val and (key or True):
                entries[key] = val
        cur, fuzzy = {}, False

    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            flush(); field = None; continue
        if line.startswith("#,") and "fuzzy" in line:
            fuzzy = True; continue
        if line.startswith("#"):
            continue
        if line.startswith("msgctxt "):
            if "msgid" in cur: flush()
            cur["msgctxt"] = ast.literal_eval(line[8:]); field = "msgctxt"
        elif line.startswith("msgid_plural "):
            cur["msgid_plural"] = ast.literal_eval(line[13:]); field = "msgid_plural"
        elif line.startswith("msgid "):
            if "msgid" in cur: flush()
            cur["msgid"] = ast.literal_eval(line[6:]); field = "msgid"
        elif line.startswith("msgstr["):
            idx = int(line[7:line.index("]")]); cur.setdefault("msgstr", {})[idx] = ast.literal_eval(line[line.index("]") + 1:].strip()); field = ("msgstr", idx)
        elif line.startswith("msgstr "):
            cur.setdefault("msgstr", {})[0] = ast.literal_eval(line[7:]); field = ("msgstr", 0)
        elif line.startswith('"'):
            text = ast.literal_eval(line)
            if isinstance(field, tuple): cur["msgstr"][field[1]] += text
            else: cur[field] += text
    flush()
    return entries


def write_mo(entries, out):
    keys = sorted(entries)
    ids = strs = b""
    offsets = []
    for k in keys:
        kb, vb = k.encode("utf-8"), entries[k].encode("utf-8")
        offsets.append((len(ids), len(kb), len(strs), len(vb)))
        ids += kb + b"\0"; strs += vb + b"\0"
    keystart = 7 * 4 + 16 * len(keys)
    valuestart = keystart + len(ids)
    koffsets, voffsets = [], []
    for o1, l1, o2, l2 in offsets:
        koffsets += [l1, o1 + keystart]; voffsets += [l2, o2 + valuestart]
    data = struct.pack("Iiiiiii", 0x950412DE, 0, len(keys), 7 * 4, 7 * 4 + len(keys) * 8, 0, 0)
    data += struct.pack("%di" % len(koffsets), *koffsets) + struct.pack("%di" % len(voffsets), *voffsets) + ids + strs
    Path(out).write_bytes(data)


def main():
    root = Path(__file__).resolve().parent.parent / "locale"
    n = 0
    for po in sorted(root.glob("*/LC_MESSAGES/django.po")):
        entries = parse(po)
        if "" not in entries:
            print("warning: %s has no header entry (Content-Type / Plural-Forms)" % po, file=sys.stderr)
        write_mo(entries, po.with_suffix(".mo"))
        print("%s: %d messages" % (po.relative_to(root.parent), len(entries) - ("" in entries))); n += 1
    if not n:
        print("no .po files found", file=sys.stderr); sys.exit(1)


if __name__ == "__main__":
    main()
