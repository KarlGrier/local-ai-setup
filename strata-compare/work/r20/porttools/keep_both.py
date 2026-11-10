#!/usr/bin/env python3
"""keep_both.py FILE... - resolve every conflict hunk in FILE by keeping both sides, ours (HEAD) first, then theirs
(only for hunks that are independent additions; check the result)."""
import re
import sys
for f in sys.argv[1:]:
    s = open(f, encoding="utf-8").read()
    pat = re.compile(r"^<<<<<<< [^\n]*\n(.*?)^(?:\|\|\|\|\|\|\| [^\n]*\n.*?)?^=======\n(.*?)^>>>>>>> [^\n]*\n", re.S | re.M)
    n = len(pat.findall(s))
    s = pat.sub(lambda m: m.group(1) + m.group(2), s)
    open(f, "w", encoding="utf-8").write(s)
    print(f, "hunks resolved:", n, "markers left:", s.count("<<<<<<<") + s.count(">>>>>>>"))
