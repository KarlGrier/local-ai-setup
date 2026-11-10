#!/usr/bin/env python3
"""s2_ttft.py NAME=LABEL,... NAME=LABEL,... — round 16 step 2: time to first token per prompt size (8K / 32K / 64K / 120K)
over every speed request of the given labels (the full screen's 32K / 64K / 120K r0 and the TTFT screen's 8K r0, 32K r1-r2,
120K r1), mean and n per arm, B vs A in percent; and the engine's prompt read (ms) beside it."""
import json, os, statistics as st, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
SINCE = os.environ.get("SINCE", "2026-10-08T14:00")
runs = [r for r in (json.loads(l) for l in open(WS / "results/runs.jsonl")) if r.get("started", "") >= SINCE and r.get("scenario") == "speed"]
arms = [(n, ls.split(",")) for n, ls in (a.split("=", 1) for a in sys.argv[1:])]
def vals(ls, size, key):
    return [(r.get("ttft_s") if key == "ttft" else (r.get("engine") or {}).get("prompt_ms", 0) / 1000) for r in runs
            if r["config"] in ls and r["item"] == size and not r.get("error") and r.get("ttft_s")]
print("| size | " + " | ".join(f"{n} TTFT s (n) | {n} engine read s" for n, _ in arms) + " | TTFT B vs A |")
print("|---|" + "---|---|" * len(arms) + "---|")
for size in ("8k", "32k", "64k", "120k"):
    m = []
    cells = []
    for n, ls in arms:
        t, p = vals(ls, size, "ttft"), vals(ls, size, "read")
        m.append(st.mean(t) if t else None)
        cells += [f"{st.mean(t):.2f} ({len(t)})" if t else "–", f"{st.mean(p):.2f}" if p else "–"]
    d = f"{100 * (m[1] / m[0] - 1):+.1f} %" if len(m) == 2 and m[0] and m[1] else "–"
    print(f"| {size} | " + " | ".join(cells) + f" | {d} |")
