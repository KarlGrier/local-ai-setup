#!/usr/bin/env python3
"""s1_table.py NAME=LABEL,LABEL NAME=LABEL,LABEL — round 16 step 1: per prompt size (512 / 1000, prompts/r16/ttft-short.json)
the client's time to first token and the engine's prompt read (ms) per arm: mean, the two arms' means, B vs A in percent."""
import json, os, statistics as st, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
SINCE = os.environ.get("SINCE", "2026-10-08T14:00")
runs = [r for r in (json.loads(l) for l in open(WS / "results/runs.jsonl")) if r.get("started", "") >= SINCE and r.get("scenario") == "speed"]
arms = [(n, ls.split(",")) for n, ls in (a.split("=", 1) for a in sys.argv[1:])]
def vals(lab, size, key):
    out = []
    for r in runs:
        if r["config"] == lab and r["item"] == size and not r.get("error"):
            v = r.get("ttft_s") if key == "ttft" else (r.get("engine") or {}).get("prompt_ms")
            if v: out.append(v * (1000 if key == "ttft" else 1))
    return out
print("| size | " + " | ".join(f"{n}: TTFT ms (arm a / arm b) | {n}: engine read ms" for n, _ in arms) + " | TTFT B vs A | read B vs A |")
print("|---|" + "---|---|" * len(arms) + "---|---|")
for size in ("512", "1000"):
    cells, means = [], []
    for n, ls in arms:
        t = [vals(l, size, "ttft") for l in ls]; p = [v for l in ls for v in vals(l, size, "read")]
        tm = st.mean([v for x in t for v in x]) if any(t) else None; pm = st.mean(p) if p else None
        cells.append(f"{tm:.0f} ({' / '.join(f'{st.mean(x):.0f}' if x else '–' for x in t)}; n={sum(len(x) for x in t)})" if tm else "–")
        cells.append(f"{pm:.0f}" if pm else "–"); means.append((tm, pm))
    d = [f"{100 * (means[1][i] / means[0][i] - 1):+.1f} %" if means[0][i] and means[1][i] else "–" for i in (0, 1)]
    print(f"| {size} | " + " | ".join(cells) + f" | {d[0]} | {d[1]} |")
