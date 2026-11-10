#!/usr/bin/env python3
"""a8_reuse.py ROUTE_LABEL — round 13 A8-3: could an L3-resident hot set of CPU-side experts serve part of each window
from cache? From the R12 routing dump (every verified row; who computed each expert): per decode window, the distinct
CPU-side (layer, expert) pairs the pool computes (all rows: the pool computes rejected rows too). Two hot sets, both
limited to BUDGET bytes (default 96 MB, the V-cache CCD's L3; expert bytes per layer from the GGUF):
  * previous-window: the CPU-side experts of the previous window (most recent first) that fit the budget;
  * frequency: the CPU-side experts with the highest decayed use (x 0.9 per window) that fit the budget.
Reports the share of each window's CPU-side BYTES that the hot set held (mean over decode windows)."""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/r13")
from replay12 import windows  # noqa: E402

WS = Path("/home/USER/ai-speed-testing/strata-compare")
EB = {int(k): v for k, v in json.loads((WS / "results/r13/expert_bytes.json").read_text()).items()}
label = sys.argv[1]
BUDGET = float(sys.argv[2]) * 1e6 if len(sys.argv) > 2 else 96e6
prev = []                   # list of (layer, expert) of the previous window, in routing order
use = defaultdict(float)
tot_b = hit_prev = hit_freq = 0.0
nwin = 0
for w in windows(label):
    if w["sfx"] < 0:
        continue
    cur = {}
    for layer, row, ids, kinds in w["rows"]:
        for e, k in zip(ids.tolist(), kinds.tolist()):
            if k in (1, 3):
                cur[(layer, e)] = EB[layer]
    if not cur:
        continue
    # hot sets as they stand BEFORE this window
    hp, b = set(), 0.0
    for key in reversed(prev):
        if b + EB[key[0]] > BUDGET:
            break
        hp.add(key); b += EB[key[0]]
    hf, b = set(), 0.0
    for key, _ in sorted(use.items(), key=lambda kv: -kv[1]):
        if b + EB[key[0]] > BUDGET:
            break
        hf.add(key); b += EB[key[0]]
    cb = sum(cur.values())
    tot_b += cb
    hit_prev += sum(v for k, v in cur.items() if k in hp)
    hit_freq += sum(v for k, v in cur.items() if k in hf)
    nwin += 1
    for k in list(use):
        use[k] *= 0.9
        if use[k] < 0.01:
            del use[k]
    for k in cur:
        use[k] += 1.0
    prev = list(cur)
print(f"route-{label}: {nwin} decode windows, CPU-side bytes per window {tot_b / max(nwin, 1) / 1e6:.0f} MB; hot set {BUDGET / 1e6:.0f} MB: "
      f"previous window's experts hold {100 * hit_prev / tot_b:.1f} % of the bytes, the most-used {100 * hit_freq / tot_b:.1f} %")
