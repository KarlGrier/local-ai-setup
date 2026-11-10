#!/usr/bin/env python3
"""tf_vs_ref.py REF ARM ARM ... — round 10: per text, the clipped (5 nats) mean NLL difference of each ARM against a
higher-precision reference REF (results/tf-LABEL-TEXT.nll), and over the long texts: the mean signed difference and the
mean absolute difference, with the between-text sd. Which arm sits closer to the reference?"""
import math, os, statistics as st, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
TEXTS = os.environ.get("TEXTS", "long16k long24k long28k long40k long64k long96k long112k").split()
def nll(run, t):
    p = WS / f"results/tf-{run}-{t}.nll"
    return [float(x) for x in p.read_text().split()] if p.exists() else None
ref, arms = sys.argv[1], sys.argv[2:]
print(f"| text | " + " | ".join(f"{a} − {ref}" for a in arms) + " |\n|---|" + "---|" * len(arms))
diffs = {a: [] for a in arms}
for t in TEXTS:
    r = nll(ref, t); cells = []
    for a in arms:
        x = nll(a, t)
        if r is None or x is None: cells.append("missing"); continue
        n = min(len(r), len(x)); d = [min(p, 5) - min(q, 5) for p, q in zip(x[:n], r[:n])]
        m = sum(d) / n; se = st.pstdev(d) / math.sqrt(n); diffs[a].append(m); cells.append(f"{m:+.4f} ± {se:.4f}")
    print(f"| {t} | " + " | ".join(cells) + " |")
for a in arms:
    v = diffs[a]
    if len(v) > 1:
        print(f"- {a}: mean signed {st.mean(v):+.4f} (between-text sd {st.stdev(v):.4f}, se {st.stdev(v) / math.sqrt(len(v)):.4f}); "
              f"mean |diff| {st.mean(abs(x) for x in v):.4f}  ({len(v)} texts)")
