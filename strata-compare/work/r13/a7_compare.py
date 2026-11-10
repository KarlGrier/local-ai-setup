#!/usr/bin/env python3
"""a7_compare.py BASE OTHER [OTHER2 ...] — round 13 A7: teacher-forced NLL from Round 4's llama.cpp scorer
(results/r13/a7/tf-LABEL-TEXT.nll, one value per token), clipped at 5 nats, per text: mean NLL of each label and
OTHER - BASE (paired per token: mean and its se = sd / sqrt(n)). Short texts: math, corpus. Long texts: 16K-112K (7).
Long-text verdict at TEXT level (as Round 11's Phase E): the 7 per-text mean differences, their mean and se = sd / sqrt(7)."""
import math
import statistics as st
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
SHORT = ["math", "corpus"]
LONG = ["long16k", "long24k", "long28k", "long40k", "long64k", "long96k", "long112k"]
CLIP = 5.0


def load(lab, t):
    p = WS / f"results/r13/a7/tf-{lab}-{t}.nll"
    if not p.exists():
        return None
    return [min(float(x), CLIP) for x in p.read_text().split()]


base = sys.argv[1]
for other in sys.argv[2:]:
    print(f"\n### {other} vs {base} (NLL nats/token, clipped at {CLIP})")
    print("| text | tokens | " + base + " | " + other + " | diff (paired) | se |\n|---|---|---|---|---|---|")
    dl = []
    for t in SHORT + LONG:
        a, b = load(base, t), load(other, t)
        if a is None or b is None or len(a) != len(b):
            print(f"| {t} | missing or length mismatch |")
            continue
        d = [y - x for x, y in zip(a, b)]
        se = st.pstdev(d) / math.sqrt(len(d))
        print(f"| {t} | {len(a)} | {st.mean(a):.4f} | {st.mean(b):.4f} | {st.mean(d):+.4f} | {se:.4f} |")
        if t in LONG:
            dl.append(st.mean(d))
    if len(dl) >= 2:
        m, se = st.mean(dl), st.stdev(dl) / math.sqrt(len(dl))
        print(f"long texts ({len(dl)}): mean per-text diff {m:+.4f} nats, se {se:.4f} (text level) -> "
              f"{'beats ' + base + ' by > 2 se' if m < -2 * se else 'NOT better by > 2 se'} ({m / se if se else float('nan'):+.1f} se)")
