#!/usr/bin/env python3
"""rel_table.py - r17 release A/B (A B C C B A = stock v0.1.40.1 / v0.1.40.2 / v0.1.41 with the share off; the same flags):
per item, each arm's output hash, ms per verify round, tokens per round, decode tok/s; per release the mean of its two arms
and the change vs the previous release. x- = exact7's fixed computation (--expert-cache 3500 --adapt-swaps 0
--suffix-draft 0), a- = the served flags (adaptive tier live). Greedy, 1,024 tokens, cold page cache per run."""
import sys
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/bringup/lib")
from p0_table import parse

V = [("v0401", "0.1.40.1"), ("v0402", "0.1.40.2"), ("v041", "0.1.41")]
items = ["x-math", "x-code", "a-math", "a-code"]
print("# r17 release A/B — stock builds, IQ3_S, CLI `strata generate --stats`, greedy 1,024 tokens, A B C C B A\n")
print("| item | release | arm a: out / ms per round / tok per round / tok/s | arm b | mean ms per round | vs previous |")
print("|---|---|---|---|---|---|")
summ = {}
for it in items:
    prev = None
    for v, name in V:
        arms = []
        for s in ("a", "b"):
            try:
                arms.append(parse(f"r17-rel-{v}-{s}-{it}"))
            except FileNotFoundError:
                arms.append(None)
        cell = lambda d: "–" if not d or "ms_round" not in d else f"{d['out']} / {d['ms_round']:.2f} / {d.get('tpr', 0):.3f} / {d.get('tps', 0):.1f}"
        ms = [d["ms_round"] for d in arms if d and "ms_round" in d]
        m = sum(ms) / len(ms) if ms else None
        ch = f"{100 * (m / prev - 1):+.1f} %" if m and prev else "–"
        print(f"| {it} | {name} | {cell(arms[0])} | {cell(arms[1])} | {m:.2f} |" if m else f"| {it} | {name} | – | – | – |", ch, "|")
        summ.setdefault(name, []).append(m)
        prev = m
print("\nOutputs: an item's hashes must match across releases for its ms per round to compare like for like.")
