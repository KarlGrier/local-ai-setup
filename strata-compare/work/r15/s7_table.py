#!/usr/bin/env python3
"""s7_table.py — round 15 step 7's table: per text the teacher-forced mean NLL (nats) of IQ3_S, UD-Q4_K_XL and the two
stand-ins (bringup/out/results/tf-s7-LABEL-TEXT.nll), each minus IQ3_S with its per-token standard error (paired tokens:
the same forced ids), and the summaries the acceptance suite uses: short (math, corpus), long clipped at 5 nats (mean of
7), long unclipped (mean of 7, its text-level se)."""
import math
import statistics as st
from pathlib import Path

R = Path("/home/USER/ai-speed-testing/strata-compare/bringup/out/results")
TEXTS = ["math", "corpus", "long16k", "long24k", "long28k", "long40k", "long64k", "long96k", "long112k"]
LONG = TEXTS[2:]
MODELS = [("iq3", "IQ3_S (served)"), ("q4", "UD-Q4_K_XL"), ("q5s", "UD-Q5_K_XL experts (splice; 6.5 bpw)"),
          ("q8", "Q8_0 (8.5 bpw)")]


def vals(lab, t, clip=None):
    p = R / f"tf-s7-{lab}-{t}.nll"
    if not p.exists():
        return None
    v = [float(x) for x in p.read_text().split() if x.strip()]
    return [min(x, clip) for x in v] if clip else v


def mean(v):
    return sum(v) / len(v) if v else None


def f(v, n=4):
    return "–" if v is None else f"{v:.{n}f}"


print("# Round 15 step 7 — teacher-forced NLL on the 9 texts (nats per token, lower is better; v0.1.40.2 + r15p27's twin)\n")
print("| text | " + " | ".join(n for _, n in MODELS) + " | " + " | ".join(f"{n.split(' ')[0]} − IQ3_S (± se)" for _, n in MODELS[1:]) + " |")
print("|---|" + "---|" * (2 * len(MODELS) - 1))
for t in TEXTS:
    base = vals("iq3", t)
    cells, diffs = [], []
    for lab, _ in MODELS:
        v = vals(lab, t)
        cells.append(f(mean(v)))
        if lab != "iq3":
            if v and base and len(v) == len(base):
                d = [a - b for a, b in zip(v, base)]
                se = st.pstdev(d) / math.sqrt(len(d))
                diffs.append(f"{mean(d):+.4f} ± {se:.4f}")
            else:
                diffs.append("–")
    print(f"| {t} | " + " | ".join(cells) + " | " + " | ".join(diffs) + " |")
print("\n| summary | " + " | ".join(n for _, n in MODELS) + " |\n|---|" + "---|" * len(MODELS))
for name, ts, clip in (("short (math, corpus), mean", TEXTS[:2], None), ("long 16K–112K, clipped at 5, mean of 7", LONG, 5),
                       ("long 16K–112K, unclipped, mean of 7", LONG, None)):
    row = []
    for lab, _ in MODELS:
        m = [mean(vals(lab, t, clip)) for t in ts]
        if any(x is None for x in m):
            row.append("–")
            continue
        se = st.stdev(m) / math.sqrt(len(m)) if len(m) > 2 else None
        row.append(f"{mean(m):.4f}" + (f" (text se {se:.3f})" if se else ""))
    print(f"| {name} | " + " | ".join(row) + " |")
# the paired long-text shift vs IQ3_S: mean over texts of (model - IQ3_S), clipped at 5, with the text-level se
print("\n| long 16K–112K, clipped at 5: shift vs IQ3_S (mean over the 7 texts ± text-level se) | value |\n|---|---|")
for lab, n in MODELS[1:]:
    d = []
    for t in LONG:
        a, b = vals(lab, t, 5), vals("iq3", t, 5)
        if a and b:
            d.append(mean(a) - mean(b))
    if len(d) == 7:
        print(f"| {n} | {mean(d):+.4f} ± {st.stdev(d) / math.sqrt(7):.4f} |")
