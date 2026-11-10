#!/usr/bin/env python3
"""strata-idle.py CALLS.jsonl [T_START T_END] — how busy Strata was during a run, from strata-proxy's call log:
the union of the calls' [start, end] intervals vs. the wall time. With one subagent worker, the idle share is the
most a second worker could win back by overlapping one agent's tool time with another's model calls."""
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
rows = [r for r in rows if r.get("path", "").endswith("/chat/completions") and r.get("t_end")]
t0 = float(sys.argv[2]) if len(sys.argv) > 2 else min(r["t0"] for r in rows)
t1 = float(sys.argv[3]) if len(sys.argv) > 3 else max(r["t_end"] for r in rows)
iv = sorted((max(r["t0"], t0), min(r["t_end"], t1)) for r in rows if r["t_end"] > t0 and r["t0"] < t1)
busy, cur = 0.0, None
for a, b in iv:
    if cur is None or a > cur[1]:
        if cur: busy += cur[1] - cur[0]
        cur = [a, b]
    else:
        cur[1] = max(cur[1], b)
if cur: busy += cur[1] - cur[0]
gaps = []
last = None
for a, b in iv:
    if last is not None and a > last:
        gaps.append(a - last)
    last = b if last is None else max(last, b)
wall = t1 - t0
print(json.dumps({"wall_s": round(wall, 1), "busy_s": round(busy, 1), "idle_s": round(wall - busy, 1),
                  "idle_share": round((wall - busy) / wall, 3) if wall else None, "calls": len(iv),
                  "gaps": len(gaps), "median_gap_s": round(sorted(gaps)[len(gaps)//2], 2) if gaps else None,
                  "gaps_over_10s": sum(1 for g in gaps if g > 10)}))
