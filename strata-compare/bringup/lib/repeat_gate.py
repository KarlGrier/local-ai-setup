#!/usr/bin/env python3
"""repeat_gate.py REF_A REF_B CAND_A CAND_B — the patched-off check for a placement whose stock run does not repeat
itself (Rehearsal B: a file whose experts are partly read from the files; stock v0.1.39 vs itself 5/7). Bit identity
cannot be the criterion there, so per exact7 item: W = the token where the two stock runs first differ (the full length
if they do not), C = the first difference of each candidate run from each stock run (4 values). An exact build lands on
the same near-tie alternatives as stock, so C behaves like W; a build that computes something else differs early in
every pair. PASS per item: median(C) >= W / 2 (W = full length: median(C) >= full / 2). A smoke test, not a proof:
the per-switch gates then use teacher-forced NLL, and the kernels' bitwise parity tests hold whatever the placement."""
import re
import statistics as st
import sys
from pathlib import Path

P = Path("/home/USER/ai-speed-testing/strata-compare/bringup/out/logs/prof")
ITEMS = ("x-math", "s-math", "x-code", "s-code", "x-p2000", "x-32k", "x-112k")


def toks(label):
    f = P / f"{label}.out"
    m = re.search(r"^output\s*:\s*(.*)$", f.read_text(errors="replace"), re.M) if f.exists() else None
    return m[1].split() if m else None


def fd(a, b):
    i = next((k for k, (x, y) in enumerate(zip(a, b)) if x != y), None)
    return min(len(a), len(b)) if i is None else i


ra, rb, ca, cb = sys.argv[1:5]
ok_all, rows = True, []
for it in ITEMS:
    s = [toks(f"{ra}-{it}"), toks(f"{rb}-{it}")]
    c = [toks(f"{ca}-{it}"), toks(f"{cb}-{it}")]
    if None in s or None in c:
        ok_all = False; rows.append(f"{it}: missing"); continue
    w = fd(*s)
    cs = [fd(x, y) for x in c for y in s]
    ok = st.median(cs) >= w / 2
    ok_all &= ok
    rows.append(f"{it}: stock/stock {w}, cand/stock {cs} {'ok' if ok else 'EARLY'}")
print("\n".join(rows))
print(f"repeat gate: {'PASS' if ok_all else 'FAIL'} (first differing token: candidate vs stock no earlier than half of stock vs stock)")
