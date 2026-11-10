#!/usr/bin/env python3
"""wait_table.py RUNS_FOLDER [...] - research vs chat waits (the checkpoint item, the user 10-18 15:30): the table of
10-18 15:20 again, at the chosen thinking levels.

From strata-proxy's call log (logs/llm-calls.jsonl) inside each run's window [ended - wall_s, ended]: call duration
p50 / p90 / max per class, and the wait of a chat message arriving at a random moment of the run - the rest of the
research call in flight (0 between calls), since the gate holds only the NEXT research call. Reported over the whole
run time and over the time a call is in flight (the 10-18 table's basis), with the share of waits over 60 s.

  wait_table.py screen-deep-medium screen-extra-deep-medium hard-screen-deep-medium   (folders under results/bench2/runs)
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")
RUNS = WS / "results" / "bench2" / "runs"


def pct(xs: list[float], p: float) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, int(p * (len(s) - 1) + 0.5))] if s else 0.0


calls = []
for line in open(WS / "logs" / "llm-calls.jsonl", encoding="utf-8"):
    try:
        c = json.loads(line)
    except ValueError:
        continue
    if c.get("path") == "/v1/chat/completions" and c.get("t0") and c.get("t_end"):
        calls.append(c)

by_cls, waits_all, waits_busy, total_s = defaultdict(list), [], [], 0.0
for folder in sys.argv[1:]:
    for b in sorted((RUNS / folder).glob("*/bench.json")):
        d = json.loads(b.read_text())
        end = datetime.fromisoformat(d["ended"]).timestamp()
        start = end - float(d["wall_s"])
        mine = sorted((c for c in calls if start <= c["t0"] <= end), key=lambda c: c["t0"])
        for c in mine:
            by_cls[c.get("cls") or "?"].append(c["t_end"] - c["t0"])
        # sample the run every second: the wait is the rest of the call in flight at that moment
        i, t = 0, start
        while t < end:
            while i < len(mine) and mine[i]["t_end"] < t:
                i += 1
            w = 0.0
            for c in mine[i:i + 3]:
                if c["t0"] <= t <= c["t_end"]:
                    w = max(w, c["t_end"] - t)
            waits_all.append(w)
            if w > 0:
                waits_busy.append(w)
            t += 1.0
        total_s += end - start

print(f"runs: {', '.join(sys.argv[1:])}; {total_s / 3600:.1f} h of research")
print("call duration by class: p50 / p90 / max (n)")
for k in sorted(by_cls, key=lambda k: -sum(by_cls[k])):
    v = by_cls[k]
    print(f"  {k:8s} {pct(v, .5):6.1f} / {pct(v, .9):6.1f} / {max(v):6.1f} s ({len(v)}; {sum(v) / 3600:.1f} h)")
for name, w in (("any moment of the run", waits_all), ("while a call is in flight (10-18 basis)", waits_busy)):
    over = sum(1 for x in w if x > 60) / max(1, len(w))
    print(f"chat wait, {name}: p50 {pct(w, .5):.0f} s, p90 {pct(w, .9):.0f} s, over 60 s {over * 100:.0f} %")
