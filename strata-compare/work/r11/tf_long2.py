#!/usr/bin/env python3
"""tf_long2.py V5 V3 OLD — round 9 track 5 gate: the two extra long texts (long96k, long112k) for the three hyper-connection
reads (clipped at 5 nats, mean difference ± its standard error), then the per-text mean over all 7 long texts."""
import math, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
def nll(r, t):
    p = WS / f"results/tf-{r}-{t}.nll"
    return [float(x) for x in p.read_text().split()] if p.exists() else None
def diff(a, b):
    n = min(len(a), len(b)); d = [min(x, 5) - min(y, 5) for x, y in zip(a[:n], b[:n])]
    m = sum(d) / n; se = math.sqrt(sum((x - m) ** 2 for x in d) / max(1, n - 1)) / math.sqrt(n)
    return m, se
v5, v3, old = sys.argv[1:4]
LONG = ["long16k", "long24k", "long28k", "long40k", "long64k", "long96k", "long112k"]
for name, a, b in [("v3 - v5", v3, v5), ("old - v5", old, v5), ("v3 - old", v3, old)]:
    ds = []
    for t in LONG:
        x, y = nll(a, t), nll(b, t)
        if x is None or y is None:
            print(f"{name} {t}: missing"); continue
        m, se = diff(x, y); ds.append(m)
        print(f"{name:<9} {t:<9} {m:+.4f} ± {se:.4f}   (NLL {sum(min(v,5) for v in y)/len(y):.4f} -> {sum(min(v,5) for v in x)/len(x):.4f})")
    if ds:
        mu = sum(ds) / len(ds); sd = math.sqrt(sum((d - mu) ** 2 for d in ds) / max(1, len(ds) - 1))
        print(f"{name:<9} mean over {len(ds)} long texts {mu:+.4f} (spread between texts sd {sd:.4f}, se {sd / math.sqrt(len(ds)):.4f})\n")
