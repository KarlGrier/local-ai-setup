#!/usr/bin/env python3
"""sp_table.py LABEL... — round 8 Phase 0: short-prompt A/B table from results/r8/shortprompt.jsonl (work/r8/shortprompt.py):
per kind and size, the engine's prompt_ms (median over the reps / runs of each arm) and the client TTFT; arms are the
labels with their trailing run letter removed (SP-R8c-helper-a + SP-R8c-helper-b = one arm)."""
import collections
import json
import statistics as st
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
rows = [json.loads(l) for l in open(WS / "results/r8/shortprompt.jsonl")]
labels = sys.argv[1:]
arms = collections.OrderedDict()
for L in labels:
    arms.setdefault(L.rsplit("-", 1)[0], []).append(L)
cells = collections.defaultdict(list)          # (arm, kind, size) -> [(prompt_ms, ttft, read)]
for r in rows:
    if r["label"] not in labels or r.get("error"):
        continue
    arm = r["label"].rsplit("-", 1)[0]
    cells[(arm, r["kind"], r["size"])].append((r["prompt_ms"], r["ttft_s"], r["prompt_n"]))
keys = sorted({(k, s) for (_, k, s) in cells}, key=lambda x: (["fresh", "follow", "tool"].index(x[0]), x[1]))
print("| kind | size | tokens read | " + " | ".join(f"{a} prompt ms (TTFT s)" for a in arms) + " |")
print("|---|---|---|" + "---|" * len(arms))
for k, s in keys:
    reads = [x[2] for a in arms for x in cells[(a, k, s)] if x[2] is not None]
    out = []
    for a in arms:
        v = cells.get((a, k, s), [])
        pm = [x[0] for x in v if x[0] is not None]
        tt = [x[1] for x in v if x[1] is not None]
        out.append(f"{st.median(pm):.0f} ({st.median(tt):.2f}) n={len(v)}" if pm else "–")
    print(f"| {k} | {s} | {int(st.median(reads)) if reads else '–'} | " + " | ".join(out) + " |")
