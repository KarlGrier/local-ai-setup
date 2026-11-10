#!/usr/bin/env python3
"""cache_replay.py — round 6, item 8: replay the VRAM expert tier on real routing traces.

    cache_replay.py TRAIN.bin EVAL.bin [EVAL.bin ...]

* The CURRENT policy, reproduced: the profile's first N ranked (layer, expert) pairs are resident at start (N = what
  fits the measured capacity in per-layer blob bytes: 4,560 here), then the engine's adaptive tier (generate.cpp adapt):
  usage += 1 per routed entry of every verify row, every 4 windows per layer candidates (not resident, usage >= 2)
  replace victims (resident, lowest usage) while cand >= vict + 1.5, all layers' swaps by gain, at most 96, usage *= 0.7;
  a swap is in effect from the next window.  Per-layer slot counts never change (swaps stay in their layer).
  Validated against the trace's own placement (kind 0 = VRAM) before anything else is reported.
* Time model per (window, layer), from this round's measurements: the pool's rows time = a + b x CPU-expert bytes
  + c x CPU entries (least squares on TRAIN's records), its fixed part pre = plan + actq + jobs (measured per record),
  the GPU's work beside it = 38.2 us + 2.23 us per distinct VRAM expert (the nsys per-layer fit); phase = max(pre + rows,
  gpu).  A VRAM hit only saves time while the pool is longer than the GPU work (the cap by the GPU's slack).
* The NEW policy (admission by time saved per byte, per-layer budgets): budgets s_l chosen on TRAIN by moving slots
  between layers while the modelled phase sum drops (greedy, bytes-for-bytes: the same VRAM), each layer's curve from
  the adaptive-tier replay itself; the adaptive tier (with its hysteresis) then runs unchanged inside each layer.
  Evaluated on held-out traces.  ORACLE-free (the budgets come from TRAIN only), but a MODEL (no engine run).
"""
import json
import struct
import sys

import numpy as np

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/r6")
from route_parse import load_v2  # noqa: E402

WS = "/home/USER/ai-speed-testing/strata-compare"
BLOB = np.array(json.load(open(f"{WS}/results/r6/blob-bytes.json")), dtype=np.float64)
GPU0, GPU1 = 38.2, 2.23
L, E = 48, 512


def profile_pairs():
    b = open(f"{WS}/strata-v0115/data/expert-profile.bin", "rb").read()
    n = struct.unpack_from("<I", b, 16)[0]
    a = np.frombuffer(b, "<u2", 2 * n, 24).reshape(n, 2)
    return a.astype(np.int64)


def budgets_from_profile(n_slots):
    pairs = profile_pairs()[:n_slots]
    s = np.bincount(pairs[:, 0], minlength=L)
    return s


_ORDER = None


def initial_resident(budget):
    """per layer: the first budget[l] experts of that layer in the profile's rank order"""
    global _ORDER
    if _ORDER is None:
        pp = profile_pairs()
        _ORDER = [pp[pp[:, 0] == l, 1] for l in range(L)]
    res = np.zeros((L, E), bool)
    for l in range(L):
        res[l, _ORDER[l][:int(budget[l])]] = True
    return res


def replay(W, budget, collect=None, swaps_max=96, every=4):
    """adaptive tier over the windows W; returns per record (hits mask per entry) via callback collect(w, r, resident_row)"""
    res = initial_resident(budget)
    usage = np.zeros((L, E), np.float64)
    pending = None
    for wi, w in enumerate(W):
        if pending is not None:
            for l, ein, eout in pending:
                res[l, eout] = False
                res[l, ein] = True
            pending = None
        for r in w["layers"]:
            l = r["layer"]
            ids = r["ids"].reshape(-1)
            if collect is not None:
                collect(wi, w, r, res[l])
            np.add.at(usage[l], ids, 1.0)
        if (wi + 1) % every == 0:
            swaps = []
            for l in range(L):
                u = usage[l]
                cand = np.where(~res[l] & (u >= 2.0))[0]
                vict = np.where(res[l])[0]
                if len(cand) == 0 or len(vict) == 0:
                    continue
                cand = cand[np.argsort(-u[cand], kind="stable")]
                vict = vict[np.argsort(u[vict], kind="stable")]
                for i in range(min(len(cand), len(vict))):
                    if u[cand[i]] < u[vict[i]] + 1.5:
                        break
                    swaps.append((u[cand[i]] - u[vict[i]], l, cand[i], vict[i]))
            swaps.sort(key=lambda x: -x[0])
            pending = [(l, a, b) for _, l, a, b in swaps[:swaps_max]]
            usage *= 0.7
    return res


def fit_rows_time(W):
    X, y = [], []
    for w in W:
        for r in w["layers"]:
            cpu = r["kind"].reshape(-1) == -1
            ids = r["ids"].reshape(-1)[cpu]
            nb = len(set(ids.tolist()))
            if nb == 0:
                continue
            X.append([1.0, nb * BLOB[r["layer"]] / 1e6, len(ids)])
            y.append(r["run"])
    coef, *_ = np.linalg.lstsq(np.array(X), np.array(y), rcond=None)
    pred = np.array(X) @ coef
    r2 = 1 - ((np.array(y) - pred) ** 2).sum() / ((np.array(y) - np.mean(y)) ** 2).sum()
    return coef, r2


def phase_sums(W, budget, coef):
    """modelled per-layer phase sums (us) and hits for a budget; also the model's per-record detail"""
    ph = np.zeros(L)
    hits = [0, 0]

    def col(wi, w, r, resrow):
        ids = r["ids"].reshape(-1)
        hit = resrow[ids]
        hits[0] += int(hit.sum()); hits[1] += len(ids)
        cpu_ids = ids[~hit]
        nb = len(set(cpu_ids.tolist()))
        nh = len(set(ids[hit].tolist()))
        pre = r["plan"] + r["actq"] + r["jobs"]
        rows = coef[0] + coef[1] * nb * BLOB[r["layer"]] / 1e6 + coef[2] * len(cpu_ids) if nb else 0.0
        gpu = GPU0 + GPU1 * nh
        ph[r["layer"]] += max(pre + rows, gpu)

    replay(W, budget, col)
    return ph, hits


def main():
    train = [w for w in load_v2(sys.argv[1]) if w["kind"] == 0]
    evals = [(p, [w for w in load_v2(p) if w["kind"] == 0]) for p in sys.argv[2:]]
    coef, r2 = fit_rows_time(train)
    print(f"pool rows time = {coef[0]:.1f} us + {coef[1]:.2f} us/MB of CPU experts ({1e3 / coef[1]:.1f} GB/s) "
          f"+ {coef[2]:.2f} us per CPU entry  (R^2 {r2:.3f}, {sum(len(w['layers']) for w in train)} records)")
    base = budgets_from_profile(4560)
    cap = float((base * BLOB).sum())
    print(f"current budgets: {int(base.sum())} slots, {cap / 2**30:.2f} GiB; per layer min {base.min()} max {base.max()}")
    # 1. validate the replay against the trace's own placement
    agree = [0, 0]

    def chk(wi, w, r, resrow):
        ids = r["ids"].reshape(-1)
        k = r["kind"].reshape(-1)
        agree[0] += int(((k == 0) == resrow[ids]).sum()); agree[1] += len(ids)

    replay(train, base, chk)
    true_hits = sum(int((r["kind"] == 0).sum()) for w in train for r in w["layers"])
    ph, hits = phase_sums(train, base, coef)
    print(f"VALIDATION on TRAIN: replayed placement agrees with the engine's on {100 * agree[0] / agree[1]:.2f} % of "
          f"entries; hits replayed {hits[0]} vs engine {true_hits} of {hits[1]}")
    act = sum(r["wait"] + r["plan"] + r["actq"] + r["jobs"] + r["run"] for w in train for r in w["layers"]) / len(train) / 1e3
    print(f"   modelled pool-phase sum {ph.sum() / len(train) / 1e3:.2f} ms/window (measured wait+pool {act:.2f}; the "
          f"wait also holds the GPU's mixer)")
    # 2. per-layer budgets by time saved per byte (greedy moves on TRAIN)
    cur = base.copy()
    cache_ph = {}

    def layer_curve(l, s):
        key = (l, s)
        if key not in cache_ph:
            b = cur.copy(); b[l] = s
            p, _ = phase_sums_layer(train, b, coef, l)
            cache_ph[key] = p
        return cache_ph[key]

    def phase_sums_layer(W, budget, coef, l):
        # only layer l's replay matters for its own curve (swaps are per layer; the 96-swap global cap couples them
        # weakly and is ignored here)
        ph_l = 0.0
        sub = [dict(w, layers=[w["layers"][l]]) for w in W]
        ph, h = phase_sums(sub, budget, coef)
        return ph[l], h

    step = 16
    base_total = sum(layer_curve(l, cur[l]) for l in range(L))
    for it in range(400):
        gains, losses = [], []
        for l in range(L):
            g = layer_curve(l, cur[l]) - layer_curve(l, cur[l] + step)
            gains.append((g / (step * BLOB[l]), l, g))
            if cur[l] >= step:
                lo = layer_curve(l, cur[l] - step) - layer_curve(l, cur[l])
                losses.append((lo / (step * BLOB[l]), l, lo))
        gains.sort(reverse=True); losses.sort()
        gpb, gl, gv = gains[0]
        lpb, ll, lv = losses[0]
        if gl == ll or gpb <= lpb * 1.02:
            break
        # bytes-for-bytes: give `step` slots to gl, take the same bytes from ll
        take = int(round(step * BLOB[gl] / BLOB[ll]))
        if cur[ll] < take:
            break
        cur[gl] += step; cur[ll] -= take
    new = cur
    print(f"new budgets: {int(new.sum())} slots, {(new * BLOB).sum() / 2**30:.2f} GiB (cap {cap / 2**30:.2f})")
    print("   layer: current -> new  " + "  ".join(f"{l}:{base[l]}->{new[l]}" for l in range(L) if base[l] != new[l]))
    # 3. evaluate current vs new budgets on every trace (TRAIN first, then held-out), modelled
    for name, W in [(sys.argv[1] + " (TRAIN)", train)] + evals:
        p0, h0 = phase_sums(W, base, coef)
        p1, h1 = phase_sums(W, new, coef)
        wms = np.mean([(W[i + 1]["t_commit_ns"] - W[i]["t_commit_ns"]) / 1e6 for i in range(len(W) - 1)])
        d = (p0.sum() - p1.sum()) / len(W) / 1e3
        print(f"{name.split('/')[-1]}: hit rate {h0[0] / h0[1]:.3f} -> {h1[0] / h1[1]:.3f}; modelled saving {d:+.3f} ms "
              f"per window = {100 * d / wms:+.1f} % of {wms:.2f} ms")
    json.dump({"base": base.tolist(), "new": new.tolist()}, open(f"{WS}/results/r6/budgets.json", "w"))


if __name__ == "__main__":
    main()
