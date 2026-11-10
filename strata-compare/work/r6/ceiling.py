#!/usr/bin/env python3
"""ceiling.py — round 6, item 6: ORACLE ESTIMATES of what next-layer expert prefetch could save, per window.

    ceiling.py ROUTE_V2.bin NSYS_TABLE.txt [--vram-slots-cost N]

Inputs (all measured this round):
  * the routing trace v2 of a real decode run (work/r6/route_parse.py): per window and layer the routed ids, where each
    entry ran (VRAM / CPU), the pool's row time (run_us), its fixed overhead (plan + actq + jobs), and the host's spin
    for the doorbell (wait_us) = the time the CPU and DRAM sit idle while the GPU runs the previous layer's tail and this
    layer's mixer (the LEAD TIME a prefetch of this layer's experts can use, if the experts were known at its start);
  * results/r6/blob-bytes.json (bytes of one expert per layer);
  * the nsys decode trace's per-layer "GPU working inside the pool interval" (VRAM-hit experts + shared expert):
    the pool cannot hide below it (the GPU becomes the critical path);
  * the cache-warming microbenchmark: warm/cold time ratio by tokens per expert 0.636 / 0.786 / 0.834 / 0.891 (T=1..4),
    touch rate 78.8 GB/s (15.2 MB in 193 us); PCIe H2D 57.8 GB/s (round 5), capped at 55 GB/s here for DRAM sharing.

Per (window, layer): phase_before = max(pre + run, gpu); the pool's rows are DRAM-bound, so its time scales with the
CPU experts' bytes.  (a) WARM: min(bytes, lead x 78.8 GB/s) of the CPU experts' bytes are warmed (whole experts in
routing order), their share of run shrinks by their ratio.  (b) STAGE: whole experts copied to VRAM staging within the
lead at 55 GB/s become GPU work (gpu_per_expert x their distinct count) and leave the pool.  (a+b): stage while the
GPU's added work stays below the remaining pool, warm the rest of the lead window.  Saving = phase_before - phase_after.
Everything is an ORACLE (the next layer's experts known at the start of its lead window) and a model (no engine run).
"""
import json
import re
import sys

import numpy as np

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/r6")
from route_parse import load_v2  # noqa: E402

WS = "/home/USER/ai-speed-testing/strata-compare"
RATIO = {1: 0.636, 2: 0.786, 3: 0.834, 4: 0.891}
TOUCH_GBS, DMA_GBS = 78.8, 55.0


def gpu_overlap(path):
    t = open(path).read()
    ov = {}
    for m in re.finditer(r"^\s+(\d+)\s+\d+\s+([\d.]+)\s+([\d.]+)\s+([\d.-]+)$", t, re.M):
        ov[int(m.group(1))] = float(m.group(3))
    return ov


def main():
    W = [w for w in load_v2(sys.argv[1]) if w["kind"] == 0]
    ov = gpu_overlap(sys.argv[2])
    blob = json.load(open(f"{WS}/results/r6/blob-bytes.json"))
    # GPU cost of one more distinct expert in a layer's VRAM groups: the nsys per-layer overlap regressed on the
    # distinct VRAM experts of that layer in the trace (the shared expert and fixed launches are the intercept)
    dist_hits = np.zeros(48); cnt = np.zeros(48)
    for w in W:
        for r in w["layers"]:
            dist_hits[r["layer"]] += len(set(r["ids"][r["kind"] == 0].tolist())); cnt[r["layer"]] += 1
    dh = dist_hits / np.maximum(cnt, 1)
    ovv = np.array([ov.get(l, 70.0) for l in range(48)])
    A = np.vstack([dh, np.ones(48)]).T
    slope, icpt = np.linalg.lstsq(A, ovv, rcond=None)[0]
    print(f"GPU work in the pool phase ~ {icpt:.1f} us + {slope:.2f} us per distinct VRAM expert (fit over 48 layers)")
    tot = dict(before=0.0, warm=0.0, stage=0.0, both=0.0, warm_nolead=0.0, stage_nolead=0.0)
    win_ms = []
    lay_sav = np.zeros((48, 3))
    for i, w in enumerate(W):
        if i + 1 < len(W):
            win_ms.append((W[i + 1]["t_commit_ns"] - w["t_commit_ns"]) / 1e6)
        for r in w["layers"]:
            l = r["layer"]
            pre = r["plan"] + r["actq"] + r["jobs"]
            run = r["run"]
            cpu_ids = r["ids"][r["kind"] == -1].tolist()
            # distinct CPU experts in routing order, with their token counts
            order, nt = [], {}
            for e in cpu_ids:
                if e not in nt:
                    order.append(e); nt[e] = 0
                nt[e] += 1
            nb = len(order)
            gpu = ovv[l]
            before = max(pre + run, gpu) if nb else gpu
            tot["before"] += before
            if nb == 0:
                continue
            B = blob[l]
            per_us = run / nb                      # the pool's time per CPU expert (DRAM-bound: bytes-proportional)
            lead = r["wait"]

            def warm_phase(experts, budget_bytes):
                left, t = budget_bytes, 0.0
                for e in experts:
                    f = min(1.0, max(0.0, left / B)); left -= f * B
                    t += per_us * (1 - f * (1 - RATIO[min(4, nt[e])]))
                return t

            # (a) warm within the lead
            a_run = warm_phase(order, lead * TOUCH_GBS * 1e3)
            a = max(pre + a_run, gpu)
            # (b) stage whole experts within the lead
            ns = min(nb, int(lead * DMA_GBS * 1e3 // B))
            b_run = per_us * (nb - ns)
            b = max(pre + b_run if nb - ns else 0.0, gpu + slope * ns)
            # (a+b): stage k experts (best k), warm the rest with the lead's remaining DRAM time
            best = min(a, b)
            for k in range(0, ns + 1):
                rem_lead_bytes = max(0.0, lead * 1e3 * TOUCH_GBS - k * B * TOUCH_GBS / DMA_GBS)
                rr = warm_phase(order[k:], rem_lead_bytes)
                best = min(best, max(pre + rr if nb - k else 0.0, gpu + slope * k))
            # no lead limit (the prefetch could run anywhere): the bound of the method itself
            a_nl = max(pre + warm_phase(order, 1e18), gpu)
            b_nl = max(pre if 0 else 0.0, gpu + slope * nb)
            tot["warm"] += before - a; tot["stage"] += before - b; tot["both"] += before - best
            tot["warm_nolead"] += before - a_nl; tot["stage_nolead"] += before - b_nl
            lay_sav[l] += (before - a, before - b, before - best)
    nwin = len(W)
    wm = float(np.mean(win_ms))
    print(f"{nwin} decode windows, mean window (commit to commit) {wm:.2f} ms")
    exposed = sum(max(0.0, 0) for _ in [0])
    for k, label in (("warm", "(a) CPU-cache warming within the lead"), ("stage", "(b) PCIe staging within the lead"),
                     ("both", "(a+b) best split of the lead"), ("warm_nolead", "(a) no lead limit"),
                     ("stage_nolead", "(b) no lead limit")):
        ms = tot[k] / 1e3 / nwin
        print(f"  ORACLE {label:<40} saves {ms:6.3f} ms per window = {100 * ms / wm:5.1f} % of window time")
    print("per layer, us per window saved (a / b / a+b), top 12 by a+b:")
    for l in np.argsort(-lay_sav[:, 2])[:12]:
        print(f"  layer {l:2d}: {lay_sav[l, 0] / nwin:6.1f} / {lay_sav[l, 1] / nwin:6.1f} / {lay_sav[l, 2] / nwin:6.1f}")


if __name__ == "__main__":
    main()
