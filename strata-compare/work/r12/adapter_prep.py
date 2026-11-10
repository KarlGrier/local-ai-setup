#!/usr/bin/env python3
"""adapter_prep.py LABEL — round 12 A1 adapter pilot, step 1: the recording's MTP-drafted positions as compact arrays
(results/r12/adapter-LABEL.npz): hidden-vector record index (into results/r12/oracle/LABEL.txt.h, fp32 x 2560), draft
step, task (LDR topic / decode item) and its index, request kind, the target's post-chain distribution (<= 20 ids +
probs), the recorded raw draft logits' top 64 (ids + logits, to check the head emulation), the ESS q list."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/r12")
import a1_analyze as A  # noqa: E402

WS = Path("/home/USER/ai-speed-testing/strata-compare")
label = sys.argv[1]
reqs = A.load(label)
km = A.kinds_for(label, reqs)
pos, _ = A.positions(reqs)
pos = [p for p in pos if p["req"] in km and p["hrec"] >= 0]
tasks = sorted({km[p["req"]][3] for p in pos})
tid = {t: i for i, t in enumerate(tasks)}
n = len(pos)
P_ids = np.full((n, 20), -1, np.int32); P_pr = np.zeros((n, 20), np.float32)
Q_ids = np.full((n, 20), -1, np.int32); Q_pr = np.zeros((n, 20), np.float32)
L_ids = np.full((n, 64), -1, np.int32); L_lg = np.zeros((n, 64), np.float32)
for i, p in enumerate(pos):
    for k, (t, v) in enumerate(sorted(p["p"].items(), key=lambda kv: -kv[1])[:20]):
        P_ids[i, k] = t; P_pr[i, k] = v
    for k, (t, v) in enumerate(sorted(p["q"].items(), key=lambda kv: -kv[1])[:20]):
        Q_ids[i, k] = t; Q_pr[i, k] = v
    m = len(p["Lids"])
    L_ids[i, :m] = p["Lids"]; L_lg[i, :m] = p["L"]
np.savez_compressed(WS / f"results/r12/adapter-{label}.npz", hrec=np.array([p["hrec"] for p in pos], np.int64),
                    j=np.array([p["j"] for p in pos], np.int8), task=np.array([tid[km[p["req"]][3]] for p in pos], np.int16),
                    ldr=np.array([km[p["req"]][0].startswith("ldr-") for p in pos]), gate=np.array([p["gate"] for p in pos], np.float32),
                    P_ids=P_ids, P_pr=P_pr, Q_ids=Q_ids, Q_pr=Q_pr, L_ids=L_ids, L_lg=L_lg, tasks=np.array(tasks))
print(f"{label}: {n} positions, {len(tasks)} tasks -> results/r12/adapter-{label}.npz")
