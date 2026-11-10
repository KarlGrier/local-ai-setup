#!/usr/bin/env python3
"""keep_both.py FILE... - round 19 port: resolve every conflict block in FILE by keeping both sides (ours = the release's
first, then the cherry-picked commit's); prints each block's first lines. Only for blocks read by hand first."""
import re, sys
for p in sys.argv[1:]:
    s = open(p).read()
    n = 0
    def rep(m):
        global n; n += 1
        return m.group(1) + m.group(2)
    s2 = re.sub(r"<<<<<<< [^\n]*\n(.*?)=======\n(.*?)>>>>>>> [^\n]*\n", rep, s, flags=re.S)
    assert "<<<<<<<" not in s2 and ">>>>>>>" not in s2
    open(p, "w").write(s2); print(f"{p}: {n} block(s) kept both")
