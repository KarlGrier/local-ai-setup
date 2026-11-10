#!/usr/bin/env python3
"""a4_table.py [SINCE_EPOCH] — round 13 A4: results/r13/a4pairs.jsonl by arm: pair completion time (later end - earlier
start), total tok/s (both answers' tokens / completion), per-request latency (total and TTFT), over the 6 pairs and
both passes of each arm."""
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
since = float(sys.argv[1]) if len(sys.argv) > 1 else 0
recs = [json.loads(l) for l in open(WS / "results/r13/a4pairs.jsonl")]
recs = [r for r in recs if r["start"] >= since]
by = defaultdict(lambda: defaultdict(list))
for r in recs:
    by[r["arm"]][(r["config"], r["pair"])].append(r)
names = {"arm1": "1 one slot, both sent (queued: sequential)", "arm2": "2 two slots configured, one active",
         "arm3": "3 two slots, both active"}
print("| arm | pairs | pair completion (s, sum over the 6 pairs) | total tok/s | per-request total s (mean) | TTFT s (mean) | tokens |")
print("|---|---|---|---|---|---|---|")
res = {}
for arm in sorted(by):
    comp, toks, lat, ttft = [], [], [], []
    for key, rs in by[arm].items():
        if len(rs) != 2:
            continue
        s = min(r["start"] for r in rs); e = max(r["end"] for r in rs)
        comp.append(e - s); toks.append(sum(r["completion_tokens"] or 0 for r in rs))
        lat += [r["total_s"] for r in rs]; ttft += [r["ttft_s"] or 0 for r in rs]
    passes = len({k[0] for k in by[arm]})
    res[arm] = (sum(comp) / passes, sum(toks) / sum(comp))
    print(f"| {names.get(arm, arm)} | {len(comp)} ({passes} passes) | {sum(comp)/passes:.1f} | {sum(toks)/sum(comp):.1f} | "
          f"{st.mean(lat):.1f} | {st.mean(ttft):.2f} | {sum(toks)/passes:.0f} per pass |")
if "arm1" in res and "arm3" in res:
    print(f"arm 3 vs arm 1: pair completion {100 * (res['arm3'][0] / res['arm1'][0] - 1):+.1f} %, total tok/s "
          f"{100 * (res['arm3'][1] / res['arm1'][1] - 1):+.1f} % (Phase B candidate only if arm 3 beats arm 1 by >= 10 % on completion)")
if "arm1" in res and "arm2" in res:
    print(f"arm 2 vs arm 1 (the cost of the second slot for a request alone): total tok/s {100 * (res['arm2'][1] / res['arm1'][1] - 1):+.1f} %")
