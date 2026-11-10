#!/usr/bin/env python3
"""a1_analyze.py — round 13 A1 (the drafter), from the oracle recordings results/r13/oracle/LABEL.txt (engine-r12o).

load(label) -> one record per MTP-drafted position of an MTP window (V12 kind M), paired with the D12 line of the draft
round that proposed it (same request, same counter = pos0 + j, same draft token):
  req (oracle request index), j (draft step 0..), gate (the drafter's raw top probability: today's length gate),
  p (target after the full chain: dict id -> prob), q (the ESS q list the verify used: dict id -> count / 2^24),
  L (the raw draft logits' top 64: ids, logits), acc (accepted), reached (every earlier draft of the window accepted),
  hrec (index of the hidden vector in LABEL.txt.h), pos0, n_mtp.
Request kinds come from results/runs.jsonl (session LABEL-*), matched by prompt length (first window pos0 = prompt - 1).

The sampler chain (spec_oracle_chain, = sampled_tail_warp): top-k on the raw logits, top-p on softmax(raw top-k),
min-p on the raw logits (top + log min_p), THEN temperature over what is kept."""
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

WS = Path("/home/USER/ai-speed-testing/strata-compare")
DVOCAB = set(np.fromfile(WS / "strata-v0115/mtp/rt/draft_vocab.bin", dtype=np.int32).tolist())
TOPK, TOPP, MINP, TEMP = 20, 0.95, 0.05, 1.0


def pdist(s):
    out = {}
    if not s.strip():
        return out
    for kv in s.split(","):
        k, v = kv.split(":")
        out[int(k)] = float(v)
    return out


def load(label):
    f = WS / f"results/r13/oracle/{label}.txt"
    reqs = []          # per request: {"windows": [...], "first_pos0": int}
    cur = None
    pending = []       # D12 records since the last V12 line
    for ln in open(f, errors="replace"):
        if ln.startswith("R "):
            cur = {"idx": int(ln.split()[1]), "windows": [], "first_pos0": None, "params": {}}
            reqs.append(cur)
            pending = []
            continue
        if cur is None:
            continue
        if ln.startswith("P "):
            cur["params"] = {k: float(v) for k, v in (kv.split("=") for kv in ln.split()[1:])}
            continue
        if ln.startswith("D12 "):
            head, chain, q, L = ln.rstrip("\n").split(" | ")
            h = head.split()
            qd = {}
            qs = q[2:].strip()
            if qs:
                for kv in qs.split(","):
                    k, v = kv.split(":")
                    qd[int(k)] = int(v) / float(1 << 24)
            ids, lg = [], []
            for kv in L[2:].strip().split(","):
                k, v = kv.split(":")
                ids.append(int(k)); lg.append(float(v))
            pending.append({"counter": int(h[1]), "j": int(h[2]), "draft": int(h[3]), "gate": float(h[4]),
                            "nv": int(h[5]), "hrec": int(h[6]), "chain": pdist(chain), "q": qd,
                            "Lids": np.array(ids, dtype=np.int64), "L": np.array(lg, dtype=np.float64)})
            continue
        if ln.startswith("V12 "):
            parts = ln.rstrip("\n").split(" | ")
            h = parts[0].split()
            pos0, T, kind, nm = int(h[1]), int(h[2]), h[3], int(h[4])
            toks = [int(x) for x in h[5].split(",")]
            outs = [int(x) for x in h[6].split(",")]
            rows = [pdist(s) for s in parts[1:]]
            if cur["first_pos0"] is None:
                cur["first_pos0"] = pos0
            cur["windows"].append({"pos0": pos0, "T": T, "kind": kind, "n_mtp": nm, "toks": toks, "outs": outs,
                                   "rows": rows, "drafts": pending})
            pending = []
    return reqs


def positions(reqs):
    """MTP-drafted positions of MTP windows, paired with their drafts."""
    out = []
    unpaired = 0
    for r in reqs:
        for w in r["windows"]:
            if w["kind"] != "M" or w["T"] < 2:
                continue
            bykey = {}
            for d in w["drafts"]:
                bykey[(d["counter"], d["j"])] = d      # the latest wins
            reached = True
            for j in range(min(w["n_mtp"], w["T"] - 1)):
                d = bykey.get((w["pos0"] + j, j))
                if d is None or d["draft"] != w["toks"][j + 1]:
                    unpaired += 1
                    break
                acc = w["outs"][j] == w["toks"][j + 1]
                out.append({"params": r["params"], "req": r["idx"], "j": j, "gate": d["gate"], "p": w["rows"][j], "q": d["q"] or d["chain"],
                            "qchain": d["chain"], "Lids": d["Lids"], "L": d["L"], "acc": acc, "reached": reached,
                            "hrec": d["hrec"], "pos0": w["pos0"], "n_mtp": w["n_mtp"], "T": w["T"]})
                reached = reached and acc
    return out, unpaired


def overlap(p, q):
    return sum(min(pp, q.get(t, 0.0)) for t, pp in p.items())


def chain_np(ids, z, top_k=TOPK, top_p=TOPP, min_p=MINP, temp=TEMP):
    """spec_oracle_chain on (ids, logits) already holding the top 64: returns dict id -> prob."""
    o = np.lexsort((ids, -z))          # logit descending, then id ascending (ids stand in for the subset index)
    k = min(top_k, len(z))
    sl = z[o[:k]]
    sid = ids[o[:k]]
    n_keep = k
    if top_p < 1.0:
        ex = np.exp(sl - sl.max())
        ex /= ex.sum()
        cum = np.cumsum(ex)
        hit = np.nonzero(cum >= top_p)[0]
        n_keep = int(hit[0]) + 1 if len(hit) else k
        n_keep = max(n_keep, 1)
    if min_p > 0:
        th = sl[0] + math.log(min_p)
        below = np.nonzero(sl[:n_keep] < th)[0]
        if len(below):
            n_keep = int(below[0])
    if n_keep <= 0:
        return {int(sid[0]): 1.0}
    s = sl[:n_keep] / temp
    ex = np.exp(s - s.max())
    ex /= ex.sum()
    return {int(i): float(v) for i, v in zip(sid[:n_keep], ex)}


def corrected_q(pos, tau=1.0, beta=0.0):
    """the drafter's q after a correction of its raw logits (z / tau, + beta on the top token), through the
    request's own chain (its P line: top_k / top_p / min_p / temperature)"""
    z = pos["L"] / tau
    if beta != 0.0:
        z = z.copy()
        z[int(np.argmax(pos["L"]))] += beta
    pr = pos.get("params") or {}
    return chain_np(pos["Lids"], z, top_k=int(pr.get("top_k", TOPK)), top_p=pr.get("top_p", TOPP),
                    min_p=pr.get("min_p", MINP), temp=pr.get("temp", TEMP))


def kinds_for(label, reqs):
    """oracle request index -> (scenario, item, kind) from results/runs.jsonl, matched by prompt length."""
    recs = [json.loads(l) for l in open(WS / "results/runs.jsonl") if f'"session": "{label.replace('part','')}-' in l]
    m = {}
    i = 0
    for r in reqs:
        if r["first_pos0"] is None:
            continue
        n = r["first_pos0"] + 1
        k = i
        while k < len(recs) and recs[k].get("prompt_tokens") != n:
            k += 1
        if k < len(recs):
            rec = recs[k]
            sc = rec["scenario"]
            kind = (rec.get("note") or rec["item"].split("-")[-1]) if sc.startswith("ldr-") else f"{sc}:{rec['item']}"
            topic = rec["item"].split("-")[0] if sc.startswith("ldr-") else f"{sc}:{rec['item']}"
            m[r["idx"]] = (sc, rec["item"], kind, topic)
            i = k + 1
    return m




# ---------------------------------------------------------------- the policy model (round 13)
def deep_chains(pos):
    """the deep arm (every round drafted to its last step, no lookup): per MTP window the drafts in order,
    (gate, alpha = sum min(p, q)) for every drafted position; only windows whose positions all paired"""
    by = defaultdict(dict)
    for p in pos:
        by[(p["req"], p["pos0"])][p["j"]] = (p["gate"], overlap(p["p"], p["q"]))
    out = []
    for k, d in by.items():
        if not d or sorted(d) != list(range(len(d))):
            continue
        out.append([d[j] for j in range(len(d))])
    return out


def served_T(ch, S=4, floor=0.5):
    T = 1
    while T < S and T - 1 < len(ch) and ch[T - 1][0] >= floor:
        T += 1
    return T


def exp_tokens(alphas):
    e, pr = 1.0, 1.0
    for a in alphas:
        pr *= a
        e += pr
    return e


def model_rate(chs, W, lk_tokens=0.0, lk_ms=0.0, rule=None, alpha=None, S=4):
    """decode tokens per ms: the MTP windows of `chs` (T from `rule`, expected tokens from the conditional acceptance
    probabilities, possibly changed by `alpha`) plus fixed lookup windows (their tokens and ms per MTP window, so the
    lookup share stays what it was measured to be). W[T] = ms per MTP window of size T (whole round)."""
    rule = rule or (lambda ch: served_T(ch, S))
    tok = ms = 0.0
    Ts = []
    for ch in chs:
        T = rule(ch)
        al = [alpha(a) if alpha else a for (_, a) in ch[:T - 1]]
        tok += exp_tokens(al)
        ms += W[T]
        Ts.append(T)
    n = len(chs)
    return (tok + lk_tokens * n) / (ms + lk_ms * n), tok / n, sum(Ts) / n


def best_T_rule(chs, W, lk_tokens, lk_ms, S=4, alpha=None):
    """every draft gated on its TRUE acceptance probability: per window the T that maximizes the global rate
    (Dinkelbach: T = argmax E[tokens](T) - lambda W(T), iterate lambda = rate)"""
    lam = model_rate(chs, W, lk_tokens, lk_ms, alpha=alpha, S=S)[0]
    for _ in range(30):
        def rule(ch, lam=lam):
            best, bT = -1e9, 1
            for T in range(1, min(S, len(ch) + 1) + 1):
                al = [alpha(a) if alpha else a for (_, a) in ch[:T - 1]]
                v = exp_tokens(al) - lam * W[T]
                if v > best:
                    best, bT = v, T
            return bT
        new = model_rate(chs, W, lk_tokens, lk_ms, rule=rule, alpha=alpha, S=S)[0]
        if abs(new - lam) < 1e-9:
            break
        lam = new
    return new, rule


# ---------------------------------------------------------------- vectorized chain + corrections (round 13)
class Pack:
    """positions as arrays: Z (n x 64 raw draft logits, descending), P (n x 64: the target's p at those ids),
    pout (target mass outside the draft vocabulary), j (step), params (top_k / top_p / min_p / temp per row)"""
    def __init__(self, pos):
        n = len(pos)
        self.n = n
        self.Z = np.full((n, 64), -1e30)
        self.P = np.zeros((n, 64))
        self.j = np.array([p["j"] for p in pos])
        self.pout = np.zeros(n)
        self.topk = np.array([int((p.get("params") or {}).get("top_k", TOPK)) for p in pos])
        self.topp = np.array([(p.get("params") or {}).get("top_p", TOPP) for p in pos])
        self.minp = np.array([(p.get("params") or {}).get("min_p", MINP) for p in pos])
        self.temp = np.array([(p.get("params") or {}).get("temp", TEMP) for p in pos])
        for i, p in enumerate(pos):
            o = np.lexsort((p["Lids"], -p["L"]))
            m = len(o)
            self.Z[i, :m] = p["L"][o]
            ids = p["Lids"][o]
            pp = p["p"]
            self.P[i, :m] = [pp.get(int(t), 0.0) for t in ids]
            self.pout[i] = sum(v for t, v in pp.items() if t not in DVOCAB)

    def q(self, tau=1.0, beta=0.0):
        """the chain on corrected logits z / tau (+ beta on the top token), vectorized; returns q aligned with Z
        AFTER re-sorting (and the matching P)"""
        tau = np.broadcast_to(np.asarray(tau, dtype=float), (self.n,))[:, None]
        Z = self.Z / tau
        if np.any(np.asarray(beta) != 0):
            Z = Z.copy()
            Z[:, 0] += np.broadcast_to(np.asarray(beta, dtype=float), (self.n,))
        o = np.argsort(-Z, axis=1, kind="stable")
        Z = np.take_along_axis(Z, o, 1)
        P = np.take_along_axis(self.P, o, 1)
        K = 20
        z = Z[:, :K]
        col = np.arange(K)[None, :]
        keep = col < self.topk[:, None]
        e = np.exp(z - z[:, :1]) * keep
        e /= e.sum(1, keepdims=True)
        cum = np.cumsum(e, 1)
        hit = (cum >= self.topp[:, None]) & keep
        cut_p = np.where(hit.any(1), hit.argmax(1) + 1, keep.sum(1))
        th = z[:, :1] + np.log(np.maximum(self.minp, 1e-30))[:, None]
        below = (z < th) & (col < cut_p[:, None])
        cut = np.where(below.any(1), below.argmax(1), cut_p)
        cut = np.maximum(cut, 1)
        mask = col < cut[:, None]
        s = z / self.temp[:, None]
        ex = np.exp(s - s[:, :1]) * mask
        q = ex / ex.sum(1, keepdims=True)
        return q, P[:, :K]

    def overlap(self, tau=1.0, beta=0.0, idx=None):
        q, P = self.q(tau, beta)
        ov = np.minimum(q, P).sum(1)
        return ov if idx is None else ov[idx]


def fit_corrections(pk, fit, held, steps=(0, 1, 2)):
    """(ii): one temperature; one per draft step; a small logit-affine fit per step (scale + a bias on the top
    token). Fitted on `fit` rows (maximize mean overlap), reported on `held` rows."""
    taus = np.round(np.arange(0.50, 2.001, 0.02), 3)
    betas = np.round(np.arange(-1.5, 1.501, 0.1), 2)
    base_f, base_h = pk.overlap()[fit].mean(), pk.overlap()[held].mean()
    # one temperature
    best = max(taus, key=lambda t: pk.overlap(t)[fit].mean())
    one = (best, pk.overlap(best)[held].mean())
    # per step
    tau_j = {}
    for s in steps:
        fs = fit[pk.j[fit] == s]
        tau_j[s] = max(taus, key=lambda t: pk.overlap(t)[fs].mean())
    tv = np.array([tau_j.get(int(s), 1.0) for s in pk.j])
    per = (tau_j, pk.overlap(tv)[held].mean())
    # affine per step: coarse grid
    ab = {}
    for s in steps:
        fs = fit[pk.j[fit] == s]
        bestv, bestp = -1, (1.0, 0.0)
        for t in taus[::3]:
            ovs = [(pk.overlap(t, b)[fs].mean(), b) for b in betas]
            v, b = max(ovs)
            if v > bestv:
                bestv, bestp = v, (t, b)
        ab[s] = bestp
    tv = np.array([ab.get(int(s), (1.0, 0.0))[0] for s in pk.j])
    bv = np.array([ab.get(int(s), (1.0, 0.0))[1] for s in pk.j])
    aff = (ab, pk.overlap(tv, bv)[held].mean())
    return base_f, base_h, one, per, aff


def report(label):
    """A1 tables on one recording: positions, acceptance vs overlap per step and kind, the missing overlap split
    (i) outside the draft vocabulary, (ii) fitted corrections on held-out TASKS, (iii) the rest."""
    import statistics as st
    reqs = load(label)
    pos, unp = positions(reqs)
    km = kinds_for(label, reqs)
    pos = [p for p in pos if p["req"] in km and (p.get("params") or {}).get("greedy", 0) == 0]
    for p in pos:
        sc, item, kind, topic = km[p["req"]]
        p["kind"], p["topic"] = kind, topic
        p["grp"] = "LDR" if sc.startswith("ldr-") else "decode"
    print(f"## A1 on {label}: {len(reqs)} requests, {len(pos)} MTP-drafted positions of MTP windows ({unp} unpaired), "
          f"{len(km)} requests matched")
    pk = Pack(pos)
    ov = pk.overlap()
    acc = np.array([p["acc"] for p in pos]); rch = np.array([p["reached"] for p in pos])
    print("\n### overlap sum min(p, q) vs observed acceptance (reached positions), per draft step")
    print("| group | step | positions | overlap | observed acceptance | target mass outside the draft vocabulary |\n|---|---|---|---|---|---|")
    for g in ("LDR", "decode", "all"):
        for j in range(4):
            sel = np.array([(g == "all" or p["grp"] == g) and p["j"] == j for p in pos])
            if sel.sum() == 0:
                continue
            r = sel & rch
            print(f"| {g} | {j+1} | {sel.sum()} | {ov[sel].mean():.4f} | {acc[r].mean():.4f} (n {r.sum()}) | {pk.pout[sel].mean():.4f} |")
    print("\n### per request kind (all steps)")
    print("| kind | positions | overlap | acceptance | step 1 / 2 / 3 overlap |\n|---|---|---|---|---|")
    for k in sorted({p["kind"] for p in pos}):
        sel = np.array([p["kind"] == k for p in pos])
        r = sel & rch
        sj = " / ".join(f"{ov[sel & (pk.j == j)].mean():.3f}" if (sel & (pk.j == j)).any() else "-" for j in range(3))
        print(f"| {k} | {sel.sum()} | {ov[sel].mean():.4f} | {acc[r].mean():.4f} | {sj} |")
    # fit / held-out by whole task: topics (LDR) and decode items, alternating in sorted order
    tasks = sorted({p["topic"] for p in pos})
    fit_t = set(tasks[0::2])
    idx = np.arange(len(pos))
    isfit = np.array([p["topic"] in fit_t for p in pos])
    fit, held = idx[isfit], idx[~isfit]
    print(f"\n### missing overlap split (tasks: {len(tasks)}; fit {len(fit_t)} tasks / {len(fit)} positions, held-out {len(tasks)-len(fit_t)} / {len(held)})")
    for g in ("LDR", "all"):
        gsel = np.array([g == "all" or p["grp"] == g for p in pos])
        f, h = fit[gsel[fit]], held[gsel[held]]
        bf, bh, one, per, aff = fit_corrections(pk, f, h)
        gap = 1 - bh
        out_v = pk.pout[h].mean()
        best = max(one[1], per[1], aff[1])
        print(f"{g}: held-out overlap {bh:.4f} -> gap {gap:.4f}; (i) target mass outside the draft vocabulary {out_v:.4f} "
              f"({100*out_v/gap:.0f} % of the gap); (ii) corrections on held-out: one temperature {one[0]} -> {one[1]:.4f} "
              f"({100*(one[1]-bh):+.2f} points), per step {dict((k+1, float(v)) for k, v in per[0].items())} -> {per[1]:.4f} "
              f"({100*(per[1]-bh):+.2f}), affine per step {dict((k+1, (float(a), float(b))) for k, (a, b) in aff[0].items())} -> {aff[1]:.4f} "
              f"({100*(aff[1]-bh):+.2f}); (iii) the rest {gap - out_v - max(0.0, best - bh):.4f} "
              f"({100*(gap - out_v - max(0.0, best - bh))/gap:.0f} % of the gap)")
    return pos, pk


def policy_report(deep, served, p0sesp="P0PROF-1005", p0log="P0PROF"):
    """the policy model: W(T) and the lookup windows from the Phase 0 profile (per group), the MTP windows' conditional
    acceptance chains from the deep arm (every round drafted to its last step); validated against the served MTP
    tokens per window and decode rates; then the three ceilings for LDR decode."""
    sys.path.insert(0, str(WS / "work/r13"))
    import p12_table as P
    _, _, m = P.load_matched(p0log, p0sesp)
    dreqs = load(deep)
    dpos, _ = positions(dreqs)
    dkm = kinds_for(deep, dreqs)
    sreqs = load(served)
    spos, _ = positions(sreqs)
    skm = kinds_for(served, sreqs)
    print(f"\n## policy model (W from {p0sesp}; acceptance chains from {deep}; served check from {served})")
    for grp in ("LDR", "decode"):
        Wt = P.W_table(m, grp)
        W = {T: Wt[("mtp", T)]["ms"] / Wt[("mtp", T)]["n"] for T in range(1, 5) if Wt[("mtp", T)]["n"] > 0}
        n_mtp = sum(Wt[("mtp", T)]["n"] for T in range(1, 9))
        lk_n = sum(v["n"] for k, v in Wt.items() if k[0] == "lookup")
        lk_tok = sum(v["n"] + v["acc"] for k, v in Wt.items() if k[0] == "lookup")
        lk_ms = sum(v["ms"] for k, v in Wt.items() if k[0] == "lookup")
        mtp_tok = sum(Wt[("mtp", T)]["n"] + Wt[("mtp", T)]["acc"] for T in range(1, 9))
        mtp_ms = sum(Wt[("mtp", T)]["ms"] for T in range(1, 9))
        meas = (mtp_tok + lk_tok) / (mtp_ms + lk_ms)
        isg = (lambda r: dkm.get(r, ("",))[0].startswith("ldr-")) if grp == "LDR" else (lambda r: r in dkm and not dkm[r][0].startswith("ldr-"))
        chs = deep_chains([p for p in dpos if isg(p["req"])])
        chs = [c for c in chs if len(c) >= 3]
        if not chs:
            print(f"\n### {grp}: no fully drafted deep-arm windows recorded - skipped")
            continue
        lt, lm = lk_tok / n_mtp, lk_ms / n_mtp
        base, etok, mT = model_rate(chs, W, lt, lm)
        print(f"\n### {grp}: W(T) ms per MTP window {', '.join(f'T{T} {W[T]:.2f}' for T in sorted(W))}; lookup windows "
              f"{lk_n} ({100*lk_n/(lk_n+n_mtp):.1f} % of decode windows); deep-arm windows {len(chs)}")
        # served check: the served recording's MTP windows (served gate)
        sg = (lambda r: skm.get(r, ("",))[0].startswith("ldr-")) if grp == "LDR" else (lambda r: r in skm and not skm[r][0].startswith("ldr-"))
        sw = [w for r in sreqs if sg(r["idx"]) for w in r["windows"] if w["kind"] in ("M", "L") and w["T"] >= 1]
        sw_m = [w for w in sw if w["kind"] == "M" or w["T"] == 1]   # a T = 1 window (no draft) is tagged L by the oracle
        s_tok = sum(1 + next((k for k in range(w["T"] - 1) if w["outs"][k] != w["toks"][k + 1]), w["T"] - 1) for w in sw_m) / max(len(sw_m), 1)
        p_tok = mtp_tok / max(n_mtp, 1)
        print(f"MTP tokens per window: model {etok:.3f} (mean T {mT:.2f}) | served recording {served} {s_tok:.3f} | Phase 0 profile {p_tok:.3f}")
        print(f"decode rate: model {1000*base:.1f} tok/s vs the profile pass measured {1000*meas:.1f} tok/s ({100*(base/meas-1):+.1f} %)")
        g_rate, _ = best_T_rule(chs, W, lt, lm)
        p10 = model_rate(chs, W, lt, lm, alpha=lambda a: min(1.0, a + 0.10))[0]
        g10, _ = best_T_rule(chs, W, lt, lm, alpha=lambda a: min(1.0, a + 0.10))
        perf = (4.0 * len(chs) + lt * len(chs)) / (W[4] * len(chs) + lm * len(chs))
        perf_all = 4.0 / W[4]
        print(f"ceilings vs the model's own baseline: (1) every draft gated on its true acceptance {100*(g_rate/base-1):+.2f} %; "
              f"(2) +10 points of overlap at every step {100*(p10/base-1):+.2f} % (gated on the true acceptance too: "
              f"{100*(g10/base-1):+.2f} %); (3) a perfect drafter (MTP windows at T 4, all accepted) {100*(perf/base-1):+.1f} % "
              f"(lookup windows too: {100*(perf_all/base-1):+.1f} %)")
        for d in (0.03, 0.05):
            v = model_rate(chs, W, lt, lm, alpha=lambda a, d=d: min(1.0, a + d))[0]
            print(f"   +{int(100*d)} points everywhere: {100*(v/base-1):+.2f} %")


if __name__ == "__main__":
    if len(sys.argv) > 2:
        policy_report(sys.argv[1], sys.argv[2])
    else:
        report(sys.argv[1])


def tree_estimate(pos):
    """A6 tree drafting: at step 1, a SECOND candidate verified by recursive rejection (multi-draft speculative
    sampling: the first draft x ~ q is rejected with prob 1 - min(1, p(x)/q(x)); then y ~ q' = q without x
    renormalised is accepted against the residual r = normalize((p - q)+) with prob min(1, r(y)/q'(y))).
    Returns: P(step 1 rejected), E[P(y accepted) | rejected], E over positions of P(rej) * P2 (expected extra tokens per
    window from the extra row)."""
    out = []
    for p in pos:
        if p["j"] != 0:
            continue
        P, Q = p["p"], p["q"]
        ov = overlap(P, Q)
        rej = 1.0 - ov
        if rej <= 1e-12:
            out.append((0.0, 0.0)); continue
        r = {t: max(P.get(t, 0.0) - Q.get(t, 0.0), 0.0) for t in set(P) | set(Q)}
        rs = sum(r.values())
        if rs <= 0:
            out.append((rej, 0.0)); continue
        r = {t: v / rs for t, v in r.items()}
        # x ~ q given rejection is not q itself; for the estimate take y ~ q' over q's support (excluding the
        # x drawn), averaged over x ~ q weighted by its rejection probability
        p2 = 0.0; wsum = 0.0
        for x, qx in Q.items():
            w = qx * (1.0 - min(1.0, P.get(x, 0.0) / qx))
            if w <= 0:
                continue
            rest = 1.0 - qx
            if rest <= 1e-12:
                continue
            acc = sum(min(r.get(y, 0.0), qy / rest) for y, qy in Q.items() if y != x)
            p2 += w * acc; wsum += w
        out.append((rej, p2 / wsum if wsum > 0 else 0.0))
    n = len(out)
    pr = sum(o[0] for o in out) / n
    p2 = sum(o[0] * o[1] for o in out) / max(sum(o[0] for o in out), 1e-12)
    gain = sum(o[0] * o[1] for o in out) / n
    return pr, p2, gain, n
