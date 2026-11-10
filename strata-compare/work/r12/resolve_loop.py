#!/usr/bin/env python3
"""resolve_loop.py FILE — v0.1.39 port helper: a conflict where OUR side adds definitions that end with the old request
loop's `while (next_line(line)) {` and upstream's side is (or contains) its new `for (;;) {` loop: keep upstream's side
and insert ours (minus the old loop line) right before the new loop. Every such hunk in FILE; others are left."""
import sys
from pathlib import Path
p = Path(sys.argv[1]); s = p.read_text()
anchor = "        for (;;) {\n            if (batch_on() || (piped && pipe_inflight())) {"
n = 0
pos = 0
while True:
    a = s.find("<<<<<<< HEAD\n", pos)
    if a < 0: break
    m = s.index("=======\n", a); b = s.index(">>>>>>> ", m); be = s.index("\n", b) + 1
    head, ours = s[a + 13:m], s[m + 8:b]
    if ours.rstrip().endswith("while (next_line(line)) {") and anchor in head:
        ours = ours.rstrip()[: -len("while (next_line(line)) {")].rstrip() + "\n"
        head = head.replace(anchor, ours + anchor, 1)
        s = s[:a] + head + s[be:]
        n += 1
        pos = a
    else:
        pos = be
p.write_text(s)
print(f"resolved {n} hunk(s); conflicts left: {s.count('<<<<<<< HEAD')}")
