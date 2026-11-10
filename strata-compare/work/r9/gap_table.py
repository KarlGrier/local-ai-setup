#!/usr/bin/env python3
"""gap_table.py A=l1,l2 B=l3,l4 — TTFT by idle gap from results/r9/gaptest.jsonl (mean of the runs per gap)."""
import json, sys, statistics as st
recs = [json.loads(l) for l in open("/home/USER/ai-speed-testing/strata-compare/results/r9/gaptest.jsonl")]
arms = [(a.split("=")[0], a.split("=")[1].split(",")) for a in sys.argv[1:]]
gaps = sorted({r["gap_s"] for r in recs})
print("| gap (s) | " + " | ".join(f"{n} TTFT ms (n)" for n, _ in arms) + " | B vs A |"); print("|---" * (len(arms) + 2) + "|")
for g in gaps:
    m = []
    for n, ls in arms:
        v = [r["ttft"] * 1000 for r in recs if r["label"] in ls and r["gap_s"] == g and r["ttft"]]
        m.append((st.mean(v) if v else float("nan"), len(v)))
    d = (m[1][0] / m[0][0] - 1) * 100 if len(m) > 1 else 0
    print(f"| {g} | " + " | ".join(f"{x:.0f} ({k})" for x, k in m) + f" | {d:+.1f} % |")
