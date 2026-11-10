#!/usr/bin/env python3
"""issue_body.py DRAFT.md OUT_BODY.md - the post-ready body of an issue draft: the text after the **Title:** line, with
the form fields as the form renders them (### Label) and the 120-column hard wraps joined (GitHub shows every single
line break in an issue body); code blocks are copied unchanged."""
import re
import sys

src, out = sys.argv[1:]
lines = open(src, encoding="utf-8").read().splitlines()
i = next(k for k, l in enumerate(lines) if l.startswith("**Title:**"))
title = lines[i][len("**Title:**"):].strip()
body, fence, para = [], None, []


def flush():
    if para:
        body.append(" ".join(para))
        para.clear()


for l in lines[i + 1:]:
    m = re.match(r"^(`{3,}|~{3,})", l)
    if fence:
        body.append(l)
        if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and l.strip() == m.group(1):
            fence = None
        continue
    if m:
        flush()
        fence = m.group(1)
        body.append(l)
        continue
    f = re.match(r"^\*\*(.+?)\*\* \(form field, (required|optional)\)$", l)
    if f:
        flush()
        body.append("### " + f.group(1))
        continue
    if not l.strip():
        flush()
        body.append("")
        continue
    if l.startswith("- "):
        flush()
        para.append(l)
        continue
    if para and l.startswith("  "):
        para.append(l.strip())
        continue
    para.append(l)
flush()
text = re.sub(r"\n{3,}", "\n\n", "\n".join(body).strip()) + "\n"
open(out, "w", encoding="utf-8").write(text)
print("title:", title)
print("body:", out, len(text), "chars,", text.count("\n"), "lines")
