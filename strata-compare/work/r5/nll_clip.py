#!/usr/bin/env python3
"""nll_clip.py — round 5, phase 5: the teacher-forced scores again, with the per-token NLL clipped at 5 nats (a few
"flip" tokens - text copied from far back, scored ~0 by one run and 8-14 nats by another - dominate the plain mean on
the long texts) and the top-1 agreement (from the scorers' own output lines). Paired differences vs llama.cpp over the
same tokens. Reads results/tf-<run>-<text>.nll (one NLL per line) and the scorers' logs."""
import math
import re
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
RUNS = [("llama.cpp (6fcaa16, ub 4096)", "L6"), ("llama.cpp (6fcaa16, ub 4096, r5)", "L6x"), ("llama.cpp ub 2048", "L6ub2k"), ("C*3 (r4)", "R4tf-c3"),
        ("C*4 (r4)", "R4tf-up"), ("C*4 + GR v5 (r4)", "R4tf-gr"), ("C*4 (r5, free 5080)", "R5tf-c4"),
        ("v0.1.20 port (r5)", "R5tf-up"), ("v0.1.20 + GR v5 (r5)", "R5tf-gr"), ("v0.1.22 port (r5)", "R5tf-r5c"), ("v0.1.24 port (r5)", "R5tf-r5e"),
        ("v0.1.24 old selection = v0.1.23 (r5)", "R5tf-r5e-old"), ("v0.1.24 + GR v5 (r5)", "R5tf-r5egr")]
TEXTS = ["math", "corpus", "long16k", "long24k", "long28k", "long40k", "long64k"]
CAP = 5.0


def nll(run, text):
    p = WS / f"results/tf-{run}-{text}.nll"
    if not p.exists():
        return None
    return [float(x) for x in p.read_text().split()]


def top1(run, text):
    for lg in (WS / f"logs/r5/tf-{run}-{text}.out", WS / f"logs/r4/tf-{run}-{text}.out"):
        if lg.exists():
            m = re.search(r"top-1 agreement ([\d.]+)", lg.read_text())
            if m:
                return float(m.group(1))
    if run.startswith("L6"):
        for lg in (WS / f"logs/r4/ltf-{run}.out", WS / f"logs/r5/ltf-{run}.out"):
            if lg.exists():
                for ln in lg.read_text().splitlines():
                    if f"tf-{text}.text:" in ln:
                        m = re.search(r"top-1 ([\d.]+) %", ln)
                        if m:
                            return float(m.group(1)) / 100
    return None


def mean(v):
    return sum(v) / len(v)


def se_diff(a, b):
    d = [x - y for x, y in zip(a, b)]
    m = mean(d)
    return m, math.sqrt(sum((x - m) ** 2 for x in d) / (len(d) - 1) / len(d))


def main():
    print("| text | run | mean NLL | clipped NLL (cap 5) | tokens > 5 nats | top-1 | clipped − llama.cpp (paired) |")
    print("|---|---|---|---|---|---|---|")
    for t in TEXTS:
        ref = nll("L6", t) or nll("L6x", t)
        for name, run in RUNS:
            v = nll(run, t)
            if not v:
                continue
            c = [min(x, CAP) for x in v]
            tp = top1(run, t)
            diff = ""
            if ref and run not in ("L6", "L6x") and len(ref) == len(v):
                m, se = se_diff(c, [min(x, CAP) for x in ref])
                diff = f"{m:+.3f} ± {se:.3f}"
            print(f"| {t} | {name} | {mean(v):.4f} | {mean(c):.4f} | {sum(x > CAP for x in v)} | "
                  f"{'–' if tp is None else f'{tp:.3f}'} | {diff} |")


if __name__ == "__main__":
    main()
