#!/usr/bin/env python3
"""tf_compare.py — round 6: teacher-forced NLL of the candidate runs vs C*5 (round 5's R5tf-r5egr = the v0.1.24 + GR v5
build = C*5's arithmetic) and vs llama.cpp on the same file (L6 / L6x), clipped at 5 nats (round-5 method), paired over
the same tokens.  Also: tokens bit-identical to C*5."""
import math
import sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
TEXTS = ["math", "corpus", "long16k", "long24k", "long28k", "long40k", "long64k"]
LL = {"long28k": "L6x", "long40k": "L6x"}


def nll(run, text):
    p = WS / f"results/tf-{run}-{text}.nll"
    return [float(x) for x in p.read_text().split()] if p.exists() else None


def diff(a, b, cap=5.0):
    d = [min(x, cap) - min(y, cap) for x, y in zip(a, b)]
    m = sum(d) / len(d)
    sd = math.sqrt(sum((x - m) ** 2 for x in d) / max(1, len(d) - 1))
    return m, sd / math.sqrt(len(d))


runs = sys.argv[1:] or ["R6tf-single", "R6tf-helper", "R6tf-helper-l24", "R6tf-helper-t2"]
print(f"{'run':<18} {'text':<8} {'same as C*5':>12} {'- C*5 (clipped)':>18} {'- llama.cpp (clipped)':>22} {'mean NLL':>9}")
for r in runs:
    for t in TEXTS:
        a = nll(r, t)
        if a is None:
            continue
        c5 = nll("R5tf-r5egr", t)
        ll = nll(LL.get(t, "L6"), t)
        same = f"{sum(1 for x, y in zip(a, c5) if x == y)}/{len(a)}" if c5 else "-"
        d5 = "%+.4f ± %.4f" % diff(a, c5) if c5 else "-"
        dl = "%+.4f ± %.4f" % diff(a, ll) if ll else "-"
        print(f"{r:<18} {t:<8} {same:>12} {d5:>18} {dl:>22} {sum(a) / len(a):9.4f}")
