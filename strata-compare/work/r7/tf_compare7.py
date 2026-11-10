#!/usr/bin/env python3
"""tf_compare7.py — round 7: teacher-forced NLL of the C*7 candidate's twin (R7tf-*) against C*6's (R6tf-*, round 6, same
texts, same flags): tokens bit-identical, and the clipped (5 nats) mean difference with its standard error."""
import math
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
TEXTS = ["math", "corpus", "long16k", "long24k", "long28k", "long40k", "long64k"]
def nll(run, text):
    p = WS / f"results/tf-{run}-{text}.nll"
    return [float(x) for x in p.read_text().split()] if p.exists() else None
for new, old in (("R7tf-single", "R6tf-single"), ("R7tf-helper", "R6tf-helper")):
    for t in TEXTS:
        a, b = nll(new, t), nll(old, t)
        if a is None or b is None:
            print(f"{new:<12} {t:<8} missing"); continue
        n = min(len(a), len(b)); same = sum(1 for x, y in zip(a, b) if x == y)
        d = [min(x, 5) - min(y, 5) for x, y in zip(a[:n], b[:n])]
        m = sum(d) / n; se = math.sqrt(sum((x - m) ** 2 for x in d) / max(1, n - 1)) / math.sqrt(n)
        print(f"{new:<12} vs {old:<12} {t:<8} tokens {n:>5}  identical {same:>5}/{n:<5}  diff {m:+.4f} ± {se:.4f}  mean NLL {sum(a)/len(a):.4f}")
