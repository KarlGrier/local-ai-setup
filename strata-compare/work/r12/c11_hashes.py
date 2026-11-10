#!/usr/bin/env python3
"""c11_hashes.py — round 9 Phase C: the candidate's fixed-computation hashes against the arms they must equal
(switches off = C*10; v3 only = R10 + STRATA_GR_V3 (e10-v3); all on, run twice = itself)."""
import re
L = open("/home/USER/ai-speed-testing/strata-compare/logs/r12/batch.log").read()
def h(lab, k):
    m = re.findall(rf"^{lab}-{k}\s+out (\w+)", L, re.M)
    return m[-1] if m else None
K = ["x-math", "s-math", "x-code", "s-code", "x-p2000", "x-32k", "x-112k"]
for a, b, what in [("c11v3", "e11-v3", "v3 only = the .34 port with STRATA_GR_V3=1"), ("c11", "c11b", "all on, twice")]:
    same = [k for k in K if h(a, k) and h(a, k) == h(b, k)]
    print(f"{a} vs {b} ({what}): {len(same)}/{len(K)} identical  " + " ".join(f"{k}:{h(a,k)}/{h(b,k)}" for k in K))
