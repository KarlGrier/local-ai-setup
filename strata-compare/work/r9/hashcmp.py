#!/usr/bin/env python3
"""hashcmp.py A B [WHAT] — round 9: the 7 fixed-computation output hashes of exact7 run A against run B (batch log)."""
import re, sys
L = open("/home/USER/ai-speed-testing/strata-compare/logs/r9/batch.log").read()
def h(lab, k):
    m = re.findall(rf"^{re.escape(lab)}-{k}\s+out (\w+)", L, re.M)
    return m[-1] if m else None
K = ["x-math", "s-math", "x-code", "s-code", "x-p2000", "x-32k", "x-112k"]
a, b = sys.argv[1], sys.argv[2]
same = [k for k in K if h(a, k) and h(a, k) == h(b, k)]
print(f"{a} vs {b} ({' '.join(sys.argv[3:])}): {len(same)}/{len(K)} identical  " + " ".join(f"{k}:{h(a,k)}/{h(b,k)}" for k in K))
