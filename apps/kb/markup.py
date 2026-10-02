"""Tiny, safe markup renderer for KB articles.

Supports the subset authors actually need:

    ## Heading / ### Sub-heading
    - bullet            1. numbered step
    **bold**            `code or keys`
    > Tip / warning callout

All input is HTML-escaped first, so article text can never inject markup.
"""
import re

from django.utils.html import escape
from django.utils.safestring import mark_safe

HEADING = re.compile(r"^(#{2,3})\s+(.*)$")
BULLET = re.compile(r"^[-*]\s+(.*)$")
NUMBERED = re.compile(r"^\d+[.)]\s+(.*)$")
CALLOUT = re.compile(r"^>\s?(.*)$")
CODE = re.compile(r"`([^`]+)`")
BOLD = re.compile(r"\*\*(.+?)\*\*")


def _inline(text):
    text = escape(text)
    text = CODE.sub(r"<code>\1</code>", text)
    return BOLD.sub(r"<strong>\1</strong>", text)


def render(text):
    out, para, items, callout = [], [], [], []
    list_tag = None

    def flush_para():
        if para:
            out.append(f"<p>{_inline(' '.join(para))}</p>")
            para.clear()

    def flush_list():
        nonlocal list_tag
        if items:
            out.append(f"<{list_tag}>" + "".join(f"<li>{_inline(i)}</li>" for i in items) + f"</{list_tag}>")
            items.clear()
        list_tag = None

    def flush_callout():
        if callout:
            out.append(f'<div class="callout">{_inline(" ".join(callout))}</div>')
            callout.clear()

    def flush_all():
        flush_para()
        flush_list()
        flush_callout()

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush_all()
            continue
        if m := HEADING.match(line):
            flush_all()
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
        elif m := CALLOUT.match(line):
            flush_para()
            flush_list()
            callout.append(m.group(1))
        elif (m := BULLET.match(line)) or (m := NUMBERED.match(line)):
            tag = "ul" if BULLET.match(line) else "ol"
            flush_para()
            flush_callout()
            if list_tag != tag:
                flush_list()
                list_tag = tag
            items.append(m.group(1))
        elif items and raw[:1].isspace():
            items[-1] += " " + line  # indented continuation of a list item
        else:
            flush_list()
            flush_callout()
            para.append(line)
    flush_all()
    return mark_safe("\n".join(out))
