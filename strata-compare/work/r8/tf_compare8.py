#!/usr/bin/env python3
"""tf_compare8.py — round 8: teacher-forced NLL of the v0.1.30 port twin (R8mtf3500-*) against C*7 twin (R7mtf3500-*), binding fixed cache 3500, same
texts, same flags): tokens bit-identical, and the clipped (5 nats) mean difference with its standard error."""
import math
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
TEXTS = ["math", "corpus", "long16k", "long24k", "long28k", "long40k", "long64k"]
def nll(run, text):
    p = WS / f"results/tf-{run}-{text}.nll"
    return [float(x) for x in p.read_text().split()] if p.exists() else None
for new, old in (("R8mtf3500-single", "R7mtf3500-single"), ("R8mtf3500-helper", "R7mtf3500-helper")):
    for t in TEXTS:
        a, b = nll(new, t), nll(old, t)
        if a is None or b is None:
            print(f"{new:<17} {t:<8} missing"); continue
        n = min(len(a), len(b)); same = sum(1 for x, y in zip(a, b) if x == y)
        d = [min(x, 5) - min(y, 5) for x, y in zip(a[:n], b[:n])]
        m = sum(d) / n; se = math.sqrt(sum((x - m) ** 2 for x in d) / max(1, n - 1)) / math.sqrt(n)
        print(f"{new:<17} vs {old:<17} {t:<8} tokens {n:>5}  identical {same:>5}/{n:<5}  diff {m:+.4f} ± {se:.4f}  mean NLL {sum(a)/len(a):.4f}")
