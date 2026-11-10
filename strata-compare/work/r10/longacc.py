#!/usr/bin/env python3
"""longacc.py NAME=LABEL,LABEL ... — round 10 B.1: draft acceptance, tokens per round and decode tok/s of the answers
after the long prompts (speed set: 32k / 64k / 120k) per arm, pooled over the arm's screens (results/runs.jsonl)."""
import json, os, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
SINCE = os.environ.get("SINCE", "2026-10-02T07:25")
runs = [r for r in (json.loads(l) for l in open(WS / "results/runs.jsonl")) if r.get("started", "") >= SINCE and r.get("scenario") == "speed"]
arms = [(n, ls.split(",")) for n, ls in (a.split("=", 1) for a in sys.argv[1:])]
print("| prompt | " + " | ".join(f"{n}: acceptance / tokens per round / decode tok/s (n)" for n, _ in arms) + " |\n|---|" + "---|" * len(arms))
for size in ("32k", "64k", "120k"):
    cells = []
    for n, ls in arms:
        e = [r["engine"] for r in runs if r["config"] in ls and r["item"] == size and r.get("engine") and not r.get("error")]
        if not e: cells.append("–"); continue
        acc = sum(x["drafts_accepted"] for x in e) / max(1, sum(x["drafts_offered"] for x in e))
        rounds = sum(x["generated"] - x["drafts_accepted"] for x in e); g = sum(x["generated"] for x in e)
        cells.append(f"{acc:.3f} / {g / max(1, rounds):.3f} / {g / (sum(x['decode_ms'] for x in e) / 1000):.1f} ({len(e)})")
    print(f"| {size} | " + " | ".join(cells) + " |")
