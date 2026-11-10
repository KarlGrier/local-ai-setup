#!/usr/bin/env python3
"""ttft_table.py NAME=LABEL,LABEL NAME=LABEL,LABEL — round 10: per prompt size (1K / 4K / 32K / 120K, speed set) the TTFT
and the engine's decode tok/s of the 768 tokens after it, per arm (mean over its runs and reps), B vs A in percent."""
import json, os, statistics, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
SINCE = os.environ.get("SINCE", "2026-10-02T07:25")
runs = [r for r in (json.loads(l) for l in open(WS / "results/runs.jsonl")) if r.get("started", "") >= SINCE and r.get("scenario") == "speed"]
arms = [(n, ls.split(",")) for n, ls in (a.split("=", 1) for a in sys.argv[1:])]
def vals(ls, size, key):
    out = []
    for r in runs:
        if r["config"] in ls and r["item"] == size and not r.get("error"):
            v = (r.get("engine") or {}).get("decode_tps") if key == "dec" else r.get("ttft_s")
            if v: out.append(v)
    return out
print("| size | " + " | ".join(f"{n} TTFT s / decode tok/s" for n, _ in arms) + (" | TTFT B vs A | decode B vs A |" if len(arms) == 2 else " |"))
print("|---|" + "---|" * len(arms) + ("---|---|" if len(arms) == 2 else ""))
for size in ("1k", "4k", "32k", "120k"):
    m = [(statistics.mean(vals(ls, size, "ttft")) if vals(ls, size, "ttft") else None,
          statistics.mean(vals(ls, size, "dec")) if vals(ls, size, "dec") else None) for _, ls in arms]
    cells = [f"{a:.2f} / {b:.1f}" if a and b else "–" for a, b in m]
    extra = ""
    if len(arms) == 2 and all(x[0] and x[1] for x in m):
        extra = f" {100 * (m[1][0] / m[0][0] - 1):+.1f} % | {100 * (m[1][1] / m[0][1] - 1):+.1f} % |"
    print(f"| {size} ({len(vals(arms[0][1], size, 'ttft'))} per arm) | " + " | ".join(cells) + (" |" + extra if extra else " |"))
