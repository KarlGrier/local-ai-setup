#!/usr/bin/env python3
"""ttft567_table.py NEW=label,label OLD=label,label — round 11 Phase 0.4: follow-up TTFT per chat size and arm."""
import json
import statistics as S
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
arms = {a.split("=")[0]: a.split("=")[1].split(",") for a in sys.argv[1:]}
rows = {}
for arm, labels in arms.items():
    for lab in labels:
        for line in open(WS / f"results/r18/ttft567-{lab}.jsonl"):
            r = json.loads(line)
            rows.setdefault((arm, r["chat"]), []).append(r)
print("| chat | arm | follow-ups | TTFT median (s) | TTFT mean | server prompt_ms median | reused / prompt (median) |")
print("|---|---|---|---|---|---|---|")
for chat in ("31K", "98K"):
    for arm in arms:
        rs = rows.get((arm, chat), [])
        if not rs:
            continue
        t = [r["ttft_s"] for r in rs]
        pm = [r["prompt_ms"] or 0 for r in rs]
        print(f"| {chat} | {arm} | {len(rs)} | {S.median(t):.3f} | {S.mean(t):.3f} | {S.median(pm):.0f} | "
              f"{S.median([r['reused'] or 0 for r in rs]):.0f} / {S.median([r['prompt_total'] for r in rs]):.0f} |")
