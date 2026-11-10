#!/usr/bin/env python3
"""helper_table.py TRACE... — round 6 item 3: per trace, window time by window size T (commit to commit, ms) and per
layer the helper's launch overhead (remote begin), the CPU pool's rows, the remaining wait for the helper, and
how many entries the helper computed."""
import sys
import numpy as np
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/r6")
from route_parse import load_v2
for p in sys.argv[1:]:
    W = [w for w in load_v2(p) if w["kind"] == 0]
    byT = {}
    for i in range(1, len(W)):
        byT.setdefault(W[i]["T"], []).append((W[i]["t_commit_ns"] - W[i - 1]["t_commit_ns"]) / 1e6)
    rb = np.array([[r["rbegin"], r["run"], r["rwait"], r["plan"] + r["actq"] + r["jobs"], r["wait"],
                    int((r["kind"] == 2).sum()), int((r["kind"] == 0).sum()), r["kind"].size, r["n_tok"]]
                   for w in W for r in w["layers"]])
    print(f"== {p.split('/')[-1]}: {len(W)} windows; window ms by T: " +
          "  ".join(f"T{t}: {np.mean(v):.2f} (n={len(v)})" for t, v in sorted(byT.items()) if len(v) >= 5))
    print(f"   per layer (us): helper launch {rb[:,0].mean():.1f}, pool rows {rb[:,1].mean():.1f}, wait for helper after "
          f"the pool {rb[:,2].mean():.1f}, plan+actq+jobs {rb[:,3].mean():.1f}, doorbell wait {rb[:,4].mean():.1f}; "
          f"entries helper {rb[:,5].sum()/rb[:,7].sum():.3f} VRAM {rb[:,6].sum()/rb[:,7].sum():.3f}")
    for T in (1, 2, 3, 4):
        s = rb[rb[:, 8] == T]
        if len(s):
            print(f"   T={T}: launch {s[:,0].mean():5.1f}  pool {s[:,1].mean():6.1f}  helper wait {s[:,2].mean():5.1f}  "
                  f"helper entries/layer {s[:,5].mean():4.2f}  records {len(s)}")
