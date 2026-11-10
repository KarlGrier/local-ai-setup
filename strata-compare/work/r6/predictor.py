#!/usr/bin/env python3
"""predictor.py — round 6, item 7: CAUSAL next-layer expert predictors, scored on real runs.

    predictor.py RUN_PREFIX [RUN_PREFIX ...]      (RUN_PREFIX.route = trace v2, RUN_PREFIX.resid = residual dump)

Predictors of layer L = l+1's routed experts, using only what exists when the prediction is made:
  pre  : router(L) applied to layer l's router input (its pre-MoE residual) — known at layer l's doorbell, so the whole
         DRAM-idle window before L (flag of l -> doorbell of L; measured 187 us into GDN, 222 us into QSA) is lead time
  post : router(L) applied to layer L's attention input (the post-MoE residual of l read by L's hyper-connection) —
         known 67 us (GDN) / 52 us (QSA) into that window, so 120 / 169 us of lead
Per row the top-K logits (K = 10, 14, 20) are taken, united over the window's rows; experts the VRAM tier holds at L
are dropped (the replay of the adaptive tier, cache_replay.py, supplies residency for experts not routed).
Scored against the real CPU experts of L (distinct, kind -1): byte recall (predicted & needed / needed), byte precision
(predicted & needed / predicted), and the NET critical-path saving: the predicted CPU experts are prefetched in score
order within the usable lead (5 us for the prediction GEMV itself subtracted), (a) warmed at 78.8 GB/s or (b) staged to
VRAM at 55 GB/s; only correct ones help, wrong ones use up lead; phase = max(pre + rows, gpu) as in ceiling.py.
"""
import json
import struct
import sys

import numpy as np

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/r6")
from route_parse import load_v2  # noqa: E402
import cache_replay as CR  # noqa: E402

WS = "/home/USER/ai-speed-testing/strata-compare"
BLOB = np.array(json.load(open(f"{WS}/results/r6/blob-bytes.json")))
RATIO = {1: 0.636, 2: 0.786, 3: 0.834, 4: 0.891}
TOUCH, DMA = 78.8, 55.0
ATT_READY = {"gdn": 66.7, "qsa": 52.2}
GPU0, GPU1 = 38.2, 2.23
LAT = 5.0


def router_weights():
    sys.path.insert(0, f"{WS}/strata-v0115/third_party/llama.cpp/gguf-py")
    import gguf
    r = gguf.GGUFReader(f"{WS}/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf")
    T = {t.name: t for t in r.tensors}
    W = []
    for l in range(48):
        u16 = np.ascontiguousarray(T[f"blk.{l}.ffn_gate_inp.weight"].data).view(np.uint16).reshape(512, 2560)
        W.append((u16.astype(np.uint32) << 16).view(np.float32))
    return W


def load_resid(path):
    b = open(path, "rb").read()
    at, rou, att = 0, {}, {}
    while at < len(b):
        m, w, l, n = struct.unpack_from("<Iiii", b, at); at += 16
        x = np.frombuffer(b, "<f4", n * 2560, at).reshape(n, 2560); at += 4 * n * 2560
        (rou if m == 0x554F5258 else att)[(w, l)] = x
    return rou, att


def main():
    W = router_weights()
    Ks = (10, 14, 20)
    for prefix in sys.argv[1:]:
        wins = [w for w in load_v2(prefix + ".route") if w["kind"] == 0]
        rou, att = load_resid(prefix + ".resid")
        # residency per (window, layer) from the validated replay of the adaptive tier
        resid_rows = {}

        def col(wi, w, r, resrow):
            resid_rows[(w["id"], r["layer"])] = resrow.copy()

        CR.replay(wins, CR.budgets_from_profile(4560), col)
        acc = {(p, K): dict(need=0.0, hit=0.0, pred=0.0, sav_a=0.0, sav_b=0.0) for p in ("pre", "post", "oracle") for K in Ks}
        per_layer = {(p, K): np.zeros((48, 3)) for p in ("pre", "post") for K in Ks}
        before_tot, nwin = 0.0, 0
        wms = np.mean([(wins[i + 1]["t_commit_ns"] - wins[i]["t_commit_ns"]) / 1e6 for i in range(len(wins) - 1)])
        for w in wins:
            nwin += 1
            for rL in w["layers"][1:]:
                L = rL["layer"]; l = L - 1
                kind = "qsa" if L % 4 == 3 else "gdn"
                ids = rL["ids"].reshape(-1); kd = rL["kind"].reshape(-1)
                cpu_ids = ids[kd == -1]
                nt = {}
                for e in cpu_ids.tolist():
                    nt[e] = nt.get(e, 0) + 1
                A = set(nt)
                resrow = resid_rows[(w["id"], L)]
                nh = len(set(ids[kd == 0].tolist()))
                pre_t = rL["plan"] + rL["actq"] + rL["jobs"]
                run = rL["run"]
                gpu = GPU0 + GPU1 * nh
                before = max(pre_t + run, gpu) if A else gpu
                before_tot += before
                if not A:
                    continue
                per_us = run / len(A)
                lead_full = rL["wait"]

                def score(P_order, lead):
                    """net saving for (a) warming and (b) staging the ordered prediction within `lead` us"""
                    B = BLOB[L]
                    # (a)
                    budget = max(0.0, lead - LAT) * TOUCH * 1e3
                    t_rows = 0.0
                    warmed = {}
                    for e in P_order:
                        if budget <= 0:
                            break
                        f = min(1.0, budget / B); budget -= f * B
                        if e in A:
                            warmed[e] = f
                    for e in A:
                        f = warmed.get(e, 0.0)
                        t_rows += per_us * (1 - f * (1 - RATIO[min(4, nt[e])]))
                    a = max(pre_t + t_rows, gpu)
                    # (b)
                    nfit = int(max(0.0, lead - LAT) * DMA * 1e3 // B)
                    staged = [e for e in P_order[:nfit] if e in A]
                    left = len(A) - len(staged)
                    b = max(pre_t + per_us * left if left else 0.0, gpu + GPU1 * len(staged))
                    return before - a, before - b

                preds = {}
                for K in Ks:
                    for p, X, lead in (("pre", rou.get((w["id"], l)), lead_full),
                                       ("post", att.get((w["id"], L)), lead_full - ATT_READY[kind])):
                        if X is None:
                            continue
                        lg = X @ W[L].T
                        top = np.argpartition(-lg, K - 1, axis=1)[:, :K]
                        best = {}
                        for row in range(top.shape[0]):
                            for e in top[row]:
                                v = lg[row, e]
                                if e not in best or v > best[e]:
                                    best[e] = v
                        cand = [e for e in sorted(best, key=lambda e: -best[e]) if not resrow[e] or e in A]
                        cand = [e for e in cand if e in A or not resrow[e]]
                        P = set(cand)
                        s_a, s_b = score(cand, lead)
                        d = acc[(p, K)]
                        d["need"] += len(A) * BLOB[L]; d["hit"] += len(P & A) * BLOB[L]; d["pred"] += len(P) * BLOB[L]
                        d["sav_a"] += s_a; d["sav_b"] += s_b
                        per_layer[(p, K)][L] += (len(A), len(P & A), len(P))
                    # the oracle within the same (full) lead, for reference
                    s_a, s_b = score(sorted(A), lead_full)
                    d = acc[("oracle", K)]
                    d["need"] += len(A) * BLOB[L]; d["hit"] += len(A) * BLOB[L]; d["pred"] += len(A) * BLOB[L]
                    d["sav_a"] += s_a; d["sav_b"] += s_b
        print(f"== {prefix.split('/')[-1]}: {nwin} decode windows, mean window {wms:.2f} ms")
        print(f"   {'predictor':<10} {'K':>3} {'byte recall':>11} {'byte precision':>14} {'(a) warm saving':>18} {'(b) stage saving':>18}")
        for p in ("oracle", "pre", "post"):
            for K in Ks:
                d = acc[(p, K)]
                if d["need"] == 0 or (p == "oracle" and K != 10):
                    continue
                sa = d["sav_a"] / 1e3 / nwin; sb = d["sav_b"] / 1e3 / nwin
                print(f"   {p:<10} {K:>3} {d['hit'] / d['need']:11.3f} {d['hit'] / max(1, d['pred']):14.3f} "
                      f"{sa:7.3f} ms {100 * sa / wms:5.1f}% {sb:7.3f} ms {100 * sb / wms:5.1f}%")
        for p in ("pre", "post"):
            pl = per_layer[(p, 14)]
            rec = pl[:, 1] / np.maximum(pl[:, 0], 1)
            print(f"   {p} K=14 recall by layer (1..47): " + " ".join(f"{rec[L]:.2f}" for L in range(1, 48)))


if __name__ == "__main__":
    main()
