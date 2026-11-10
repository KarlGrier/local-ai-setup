#!/usr/bin/env python3
"""resolve.py FILE list | FILE N ours|theirs|both|theirs-then-ours|text — round 14 port helper.

list: print every conflict block of FILE (numbered from 1) with its two sides.
N MODE: replace conflict block N with: ours (HEAD side = upstream v0.1.40.1 while cherry-picking), theirs (the
cherry-picked patch's side), both (ours then theirs), theirs-then-ours, or text (stdin)."""
import re
import sys
from pathlib import Path

PAT = re.compile(r"^<<<<<<< [^\n]*\n(.*?)^(?:\|\|\|\|\|\|\| [^\n]*\n.*?)?^=======\n(.*?)^>>>>>>> [^\n]*\n", re.S | re.M)


def main():
    f = Path(sys.argv[1])
    s = f.read_text()
    blocks = list(PAT.finditer(s))
    if sys.argv[2] == "list":
        for i, m in enumerate(blocks, 1):
            line = s.count("\n", 0, m.start()) + 1
            print(f"### conflict {i} at line {line}\n--- ours (upstream):\n{m.group(1)}--- theirs (patch):\n{m.group(2)}")
        print(f"{len(blocks)} conflict blocks")
        return
    n = int(sys.argv[2]) - 1
    mode = sys.argv[3]
    m = blocks[n]
    rep = {"ours": m.group(1), "theirs": m.group(2), "both": m.group(1) + m.group(2),
           "theirs-then-ours": m.group(2) + m.group(1)}.get(mode)
    if rep is None:
        rep = sys.stdin.read()
    f.write_text(s[:m.start()] + rep + s[m.end():])
    print(f"conflict {n + 1} of {len(blocks)} resolved ({mode})")


if __name__ == "__main__":
    main()
