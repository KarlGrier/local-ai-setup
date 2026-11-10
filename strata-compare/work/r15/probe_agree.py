#!/usr/bin/env python3
"""probe_agree.py LABEL_A LABEL_B — round 15 step 3 (your rules 10-07: ~08:50 two consecutive probes that agree; ~14:10
the rule itself): two consecutive warm probes agree when their decode tok/s are within 3 % of each other. The output's
first differing token is reported beside it but does not gate: with the adaptive tier live (as served), two greedy
probes of an unchanged build split early (Q8_0 placement A: tokens 97-279 of 1,024), so Round 13's output rule (first
difference >= half) cannot pass there. Prints AGREE / DIFFER and the values."""
import re
import sys
from pathlib import Path

P = Path("/home/USER/ai-speed-testing/strata-compare/bringup/out/logs/prof")


def get(label):
    t = (P / f"{label}.out").read_text(errors="replace") if (P / f"{label}.out").exists() else ""
    m = re.search(r"^output\s*:\s*(.*)$", t, re.M)
    d = re.search(r"^decode\s+(\d+) tokens in ([\d.]+) ms\s+->\s+([\d.]+) tok/s", t, re.M)
    return (m[1].split() if m else None), (float(d[3]) if d else None)


(ta, sa), (tb, sb) = get(sys.argv[1]), get(sys.argv[2])
if not ta or not tb or not sa or not sb:
    print(f"DIFFER (missing output or decode line: {sys.argv[1]} / {sys.argv[2]})")
    sys.exit(1)
i = next((k for k, (x, y) in enumerate(zip(ta, tb)) if x != y), None)
fd = min(len(ta), len(tb)) if i is None else i
n = min(len(ta), len(tb))
dv = abs(sa / sb - 1)
ok = dv <= 0.03
print(f"{'AGREE' if ok else 'DIFFER'}: decode {sa:.2f} vs {sb:.2f} tok/s ({100 * dv:.1f} %, gate: <= 3 %); first differing "
      f"output token {fd} of {n} (reported, not gating)")
sys.exit(0 if ok else 1)
