#!/usr/bin/env python3
"""needle2_table.py — round 5: the harder needle set per engine and document size (results/r5/needle2.jsonl):
correct answers per question type over the runs, time to first token, errors / cut answers."""
import collections
import json
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
rows = [json.loads(l) for l in open(WS / "results/r5/needle2.jsonl")]
Q = {"1": "3-hop (device → technician → lab → door code)", "2": "2-hop (project → budget holder → extension)",
     "3": "one-digit twin: serial of a unit", "4": "one-digit twin: unit of a serial",
     "5": "which sentence is in it (memo, one digit changed)", "6": "which line is in it (corpus line, one digit changed)"}
labels = sorted({r["label"] for r in rows})
sizes = ["32k", "64k", "120k"]
print("| question | " + " | ".join(f"{l} {s}" for l in labels for s in sizes) + " | " +
      " | ".join(f"{l} all" for l in labels) + " |")
print("|---|" + "---|" * (len(labels) * (len(sizes) + 1)))
for q, name in Q.items():
    cells, tot = [], []
    for l in labels:
        a = b = 0
        for s in sizes:
            rs = [r for r in rows if r["label"] == l and r["size"] == s]
            ok = sum(1 for r in rs if r["per_q"].get(q))
            cells.append(f"{ok}/{len(rs)}")
            a += ok
            b += len(rs)
        tot.append(f"**{a}/{b}**")
    print(f"| {q}. {name} | " + " | ".join(cells) + " | " + " | ".join(tot) + " |")
cells, tot = [], []
for l in labels:
    a = b = 0
    for s in sizes:
        rs = [r for r in rows if r["label"] == l and r["size"] == s]
        sc = sum(r["score"] for r in rs)
        cells.append(f"{sc}/{6 * len(rs)}")
        a += sc
        b += 6 * len(rs)
    tot.append(f"**{a}/{b}**")
print("| all six | " + " | ".join(cells) + " | " + " | ".join(tot) + " |")
cells = []
for l in labels:
    for s in sizes:
        rs = [r for r in rows if r["label"] == l and r["size"] == s and r.get("ttft_s")]
        cells.append(f"{sum(r['ttft_s'] for r in rs) / len(rs):.0f} s" if rs else "–")
print("| time to first token (mean) | " + " | ".join(cells) + " | " + " | ".join("" for _ in labels) + " |")
bad = [(r["label"], r["size"], r["run"], r.get("finish"), r.get("error")) for r in rows
       if r.get("error") or r.get("finish") not in ("stop",)]
print("\nnot finished normally:", bad or "none")
