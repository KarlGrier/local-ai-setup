#!/usr/bin/env python3
"""ldrbench.py --config LABEL --base URL --engine-log LOG --set screen|holdout|pool [--loop-min M] [--ids a,b] —
round 10: sends prompts/r10/ldr-SET.json through scripts/bench.py's Runner (same streaming client, same records in
results/runs.jsonl, scenario "ldr-SET", item = the request id), in file order.  No sampling fields: the config's shared
settings apply (yours: T 1.0, top-p 0.95, top-k 20, min-p 0.05, xhigh).  --loop-min M repeats the set (shuffled with a
fixed seed per pass) until M minutes have passed (the aging traffic)."""
import argparse
import json
import random
import sys
import time
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "scripts"))
from bench import Runner  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--config", required=True)
ap.add_argument("--base", default="http://127.0.0.1:8081")
ap.add_argument("--engine-log", default="")
ap.add_argument("--set", required=True)
ap.add_argument("--file", default="", help="another request file of the same form (scenario ldr-SET)")
ap.add_argument("--loop-min", type=float, default=0)
ap.add_argument("--ids", default="")
ap.add_argument("--session", default="")
a = ap.parse_args()
a.model, a.extra = "x", ""
reqs = json.loads((Path(a.file) if a.file else WS / f"prompts/r10/ldr-{a.set}.json").read_text(encoding="utf-8"))
if a.ids:
    keep = set(a.ids.split(","))
    reqs = [r for r in reqs if r["id"] in keep]
R = Runner(a)
t0 = time.time()
npass = 0
while True:
    order = list(reqs)
    if a.loop_min:
        random.Random(1000 + npass).shuffle(order)
    for r in order:
        if r.get("tools"):
            R.extra = {"tools": r["tools"]}
        else:
            R.extra = {}
        R.call(f"ldr-{a.set}", r["id"], npass, r["messages"], r["max_tokens"], save_text=(a.set != "pool"),
               note=r["kind"])
        if a.loop_min and time.time() - t0 > a.loop_min * 60:
            break
    npass += 1
    if not a.loop_min or time.time() - t0 > a.loop_min * 60:
        break
print(f"ldrbench {a.set}: {npass} pass(es), {time.time() - t0:.0f} s")
