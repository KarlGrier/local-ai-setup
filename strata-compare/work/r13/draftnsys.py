#!/usr/bin/env python3
"""draftnsys.py LABEL — round 13 Phase 0 item 5: where the draft round's GPU time goes, from a whole-run nsys trace
(logs/r13/prof/LABEL.sqlite, --cuda-graph-trace=node). The drafter runs its round / step graphs on its own stream: the
stream on which the kernels whose names contain "mtp_select" run. Decode-time draft graphs = graph launches on that
stream after the prompt (consecutive kernels on the stream separated by > 0.2 ms of idle form one graph run). Per graph
run: kernels, GPU busy time, span; per kernel name: time per run and share."""
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
db = sqlite3.connect(WS / f"logs/r13/prof/{sys.argv[1]}.sqlite")
c = db.cursor()
names = dict(c.execute("SELECT id, value FROM StringIds"))
rows = c.execute("SELECT start, end, streamId, shortName, graphId FROM CUPTI_ACTIVITY_KIND_KERNEL ORDER BY start").fetchall()
sel = [r for r in rows if "mtp_select" in names.get(r[3], "")]
if not sel:
    print("no mtp_select kernels found; kernel names containing 'mtp':", sorted({names[r[3]] for r in rows if "mtp" in names.get(r[3], "").lower()})[:20])
    sys.exit(1)
stream = max(set(r[2] for r in sel), key=lambda s: sum(1 for r in sel if r[2] == s))
ks = [r for r in rows if r[2] == stream]
runs, cur = [], []
for r in ks:
    if cur and r[0] - cur[-1][1] > 200_000:
        runs.append(cur); cur = []
    cur.append(r)
if cur:
    runs.append(cur)
# decode runs: those containing mtp_select (the round and step graphs end with it); skip the first few (warm-up / prompt)
dec = [g for g in runs if any("mtp_select" in names[k[3]] for k in g)]
print(f"stream {stream}: {len(ks)} kernels, {len(runs)} runs, {len(dec)} with mtp_select")
by_len = defaultdict(list)
for g in dec:
    by_len[len(g)].append(g)
for n, gs in sorted(by_len.items(), key=lambda kv: -len(kv[1]))[:4]:
    busy = sum(sum(k[1] - k[0] for k in g) for g in gs) / len(gs) / 1e6
    span = sum(g[-1][1] - g[0][0] for g in gs) / len(gs) / 1e6
    print(f"\n### graph runs with {n} kernels: {len(gs)} runs, GPU busy {busy:.3f} ms, span {span:.3f} ms (idle inside {span - busy:.3f})")
    agg = defaultdict(float)
    cnt = defaultdict(int)
    for g in gs:
        for k in g:
            agg[names[k[3]]] += (k[1] - k[0]) / 1e6
            cnt[names[k[3]]] += 1
    tot = sum(agg.values())
    print("| kernel | launches per run | ms per run | share |\n|---|---|---|---|")
    for nm, v in sorted(agg.items(), key=lambda kv: -kv[1])[:18]:
        print(f"| {nm[:70]} | {cnt[nm]/len(gs):.1f} | {v/len(gs):.4f} | {100*v/tot:.1f} % |")
