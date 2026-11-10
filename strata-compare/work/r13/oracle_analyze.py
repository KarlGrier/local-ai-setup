#!/usr/bin/env python3
"""oracle_analyze.py FILE... [--by LABEL=FILE ...] — round 8 A.4: the speculation oracle's records (STRATA_SPEC_ORACLE,
engine-r8o) -> acceptance per drafted position under three proposal rules, and expected tokens per verify window.

Per draft j of a window (paired with the verify row that checks it: counter = pos0 + j, the draft = tokens[j + 1]):
  greedy  (today)  : the drafter proposes argmax q, the verifier's own sample must match -> P(accept) = p(d)
  exact  (Leviathan): propose x ~ q, accept with min(1, p/q), else resample (p - q)+  -> P(accept) = sum min(p, q)
  coupled (0.1.30 STRATA_SPEC_COUPLED): x = F_q^-1(u), target = F_p^-1(u) with the SAME uniform u, both lists in the
                     chain's selection order -> P(accept) = |{u : same token}|
  observed         : today's real sample-and-match outcome (a check on `greedy`)
p and q are the distributions after the full sampler chain (top_k, top_p, min_p, temperature).  q lives on the
drafter's token subset (English/code), so a target token outside it has q = 0.
Window level: E[tokens per window] = 1 + sum_j prod_{i<=j} a_i over the drafts the window really had (their count is
today's --spec-min-p rule on the greedy draft's probability); positions after the first are conditioned on the
greedy drafts' prefix, an approximation for the sampled rules (stated in the report)."""
import argparse
import math
import statistics as st
import sys
from collections import defaultdict


def parse_dist(s):
    out = []
    s = s.strip()
    if not s:
        return out
    for e in s.split(","):
        i, p = e.split(":")
        out.append((int(i), float(p)))
    return out


def load(path):
    """-> list of windows: {pos0, T, toks, outs, p: [dist per row], drafts: [(counter, j, id, prob, q)]}"""
    wins, pending, params = [], [], None
    for ln in open(path, errors="replace"):
        if ln.startswith("P "):
            params = ln.strip()
        elif ln.startswith("D "):
            head, _, dist = ln.partition(" | ")
            f = head.split()
            pending.append((int(f[1]), int(f[2]), int(f[3]), float(f[4]), parse_dist(dist)))
        elif ln.startswith("V ") and ln.endswith("\n"):
            parts = ln.rstrip("\n").split(" | ")
            if len(parts[0].split()) < 5:
                continue
            f = parts[0].split()
            pos0, T = int(f[1]), int(f[2])
            toks = [int(x) for x in f[3].split(",")]
            outs = [int(x) for x in f[4].split(",")]
            p = [parse_dist(x) for x in parts[1:]]
            wins.append({"pos0": pos0, "T": T, "toks": toks, "outs": outs, "p": p, "drafts": pending, "params": params})
            pending = []
    return wins


def coupled(p, q):
    """measure of u in [0,1) where the inverse CDFs of p and q (selection order) pick the same token"""
    def segs(d):
        s, c = [], 0.0
        for i, (tok, pr) in enumerate(d):
            lo, c = c, c + pr
            s.append((lo, c if i + 1 < len(d) else 1.0, tok))   # the last entry takes the rounding remainder
        return s
    a, b = segs(p), segs(q)
    i = j = 0
    tot = 0.0
    while i < len(a) and j < len(b):
        lo = max(a[i][0], b[j][0])
        hi = min(a[i][1], b[j][1])
        if hi > lo and a[i][2] == b[j][2]:
            tot += hi - lo
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return tot


def analyze(wins):
    rows = []          # per paired draft
    wstats = []        # per window: list of (a_greedy, a_exact, a_coupled, observed) for its drafts
    unpaired = 0
    for w in wins:
        if not w["drafts"]:
            continue
        # the drafts that fed THIS window: its tokens[1..] must equal them (else it was a prompt-lookup window)
        dr = sorted(w["drafts"], key=lambda d: d[1])
        if len(w["toks"]) < 2 or any(j + 1 >= len(w["toks"]) or w["toks"][j + 1] != d[2]
                                     for j, d in enumerate(dr[:len(w["toks"]) - 1])):
            unpaired += 1
            continue
        chain = []
        alive = True
        for j, (ctr, jj, did, dprob, q) in enumerate(dr):
            if j + 1 >= w["T"]:
                break
            if ctr != w["pos0"] + j:
                unpaired += 1
                break
            p = dict(w["p"][j])
            qd = dict(q)
            ag = p.get(did, 0.0)
            ax = sum(min(pp, qd.get(t, 0.0)) for t, pp in p.items())
            ac = coupled(w["p"][j], q)
            obs = alive and w["outs"][j] == did
            if alive:
                rows.append({"j": j, "a_g": ag, "a_x": ax, "a_c": ac, "obs": obs, "pmax": w["p"][j][0][1] if w["p"][j] else 0,
                             "qmax": q[0][1] if q else 0, "dprob": dprob, "p_n": len(p), "q_n": len(q),
                             "p_out_of_subset": 0.0, "pos0": w["pos0"]})
            chain.append((ag, ax, ac, obs))
            alive = obs
        if chain:
            wstats.append(chain)
    return rows, wstats, unpaired


def expected_tokens(wstats, k):
    """E[tokens per window] = 1 + sum_j prod_{i<=j} a_i (k: 0 greedy, 1 exact, 2 coupled)"""
    out = []
    for ch in wstats:
        e, pr = 1.0, 1.0
        for a in ch:
            pr *= a[k]
            e += pr
        out.append(e)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()
    print("| set | windows w/ MTP drafts | paired drafts | draft 1 accept: observed / greedy p(d) / exact Σmin / coupled | "
          "all drafts: greedy / exact / coupled | E[tokens/window] greedy → exact (Δ) / coupled (Δ) | pmax / qmax (draft 1) |")
    print("|---|---|---|---|---|---|---|")
    for spec in a.files:
        label, _, path = spec.rpartition("=")
        label = label or path
        wins = load(path)
        rows, wstats, unp = analyze(wins)
        if not rows:
            print(f"| {label} | {len(wins)} | 0 | – | – | – | – |")
            continue
        r1 = [r for r in rows if r["j"] == 0]
        m = lambda xs: sum(xs) / len(xs) if xs else float("nan")
        eg, ex, ec = (m(expected_tokens(wstats, k)) for k in (0, 1, 2))
        print(f"| {label} | {len(wstats)} (+{unp} lookup/unpaired) | {len(rows)} | "
              f"{m([r['obs'] for r in r1]):.3f} / {m([r['a_g'] for r in r1]):.3f} / {m([r['a_x'] for r in r1]):.3f} / "
              f"{m([r['a_c'] for r in r1]):.3f} | {m([r['a_g'] for r in rows]):.3f} / {m([r['a_x'] for r in rows]):.3f} / "
              f"{m([r['a_c'] for r in rows]):.3f} | {eg:.3f} → {ex:.3f} ({(ex / eg - 1) * 100:+.1f} %) / {ec:.3f} "
              f"({(ec / eg - 1) * 100:+.1f} %) | {m([r['pmax'] for r in r1]):.3f} / {m([r['qmax'] for r in r1]):.3f} |")


if __name__ == "__main__":
    main()


# ---- round 8 A.4 part 2: tokens per millisecond (needs the window-time table W(T) from the A4-W* CLI runs)
def policy_table(wins, W, extra_ms=0.0):
    """From DEEP records (every window drafted to K = 7 with no floor): for fixed K and for a floor theta on max q
    (decided before sampling), expected tokens per window under greedy / exact / coupled rules, and tokens per ms
    = E[tokens] / E[W(T)] (+ extra_ms per window for the sampled rules' drafter sampling)."""
    rows = []
    chains = []
    for w in wins:
        dr = sorted(w["drafts"], key=lambda d: d[1])
        if not dr or len(w["toks"]) < 2:
            continue
        ch = []
        for j, (ctr, jj, did, dprob, q) in enumerate(dr):
            if j + 1 >= w["T"] or ctr != w["pos0"] + j or w["toks"][j + 1] != did:
                break
            p = dict(w["p"][j]); qd = dict(q)
            ch.append((p.get(did, 0.0), sum(min(pp, qd.get(t, 0.0)) for t, pp in p.items()), coupled(w["p"][j], q),
                       q[0][1] if q else 0.0))
        if ch:
            chains.append(ch)
    def run(select):
        out = {}
        for k, name in ((0, "greedy"), (1, "exact"), (2, "coupled")):
            toks, ms = [], []
            for ch in chains:
                n = select(ch)
                e, pr = 1.0, 1.0
                for a in ch[:n]:
                    pr *= a[k]
                    e += pr
                toks.append(e)
                ms.append(W.get(n + 1, W[max(W)]) + (extra_ms if k else 0.0))
            out[name] = (sum(toks) / len(toks), sum(toks) / sum(ms))
        return out
    for K in range(1, 8):
        r = run(lambda ch, K=K: min(K, len(ch)))
        rows.append((f"K = {K}", r))
    for th in (0.3, 0.5, 0.7):
        def sel(ch, th=th):   # the engine's rule: draft 1 always, draft j+1 while draft j's max q >= the floor
            n = 1
            while n < len(ch) and n < 7 and ch[n - 1][3] >= th:
                n += 1
            return n
        rows.append((f"floor max q >= {th}", run(sel)))
    return rows, len(chains)


def load_split(path, ranges_path):
    """the oracle file split into scenarios by work/r8/oracle_run.py's byte ranges (a line belongs to the scenario
    whose [from, to) holds its first byte; ranges are exact to one 4 KiB stdio buffer)"""
    import json as _j
    rg = _j.load(open(ranges_path))
    data = open(path, "rb").read()
    out = {}
    for name, r in rg.items():
        a, b = r["from"], r["to"]
        # widen to whole lines: start at the first line beginning at or after a, stop at the last line beginning before b
        if a > 0:
            nl = data.rfind(b"\n", 0, a)
            a = nl + 1
        nl = data.rfind(b"\n", 0, b)
        chunk = data[a:nl + 1] if nl + 1 > a else b""
        tmp = path + f".{name}.part"
        open(tmp, "wb").write(chunk)
        out[name] = load(tmp)
        import os as _o
        _o.remove(tmp)
    return out


def report_split(label, path, ranges_path):
    parts = load_split(path, ranges_path)
    print(f"\n### {label}: per scenario")
    print("| scenario | windows w/ MTP drafts | paired drafts | draft 1: observed / greedy / exact / coupled | all drafts: greedy / exact / coupled | E[tokens/window] greedy → exact / coupled | pmax / qmax (draft 1) |")
    print("|---|---|---|---|---|---|---|")
    allw = []
    for name, wins in parts.items():
        allw += wins
        _row(name, wins)
    _row("ALL", allw)


def _row(name, wins):
    rows, wstats, unp = analyze(wins)
    if not rows:
        print(f"| {name} | 0 | 0 | – | – | – | – |")
        return
    r1 = [r for r in rows if r["j"] == 0]
    m = lambda xs: sum(xs) / len(xs) if xs else float("nan")
    eg, ex, ec = (m(expected_tokens(wstats, k)) for k in (0, 1, 2))
    print(f"| {name} | {len(wstats)} (+{unp}) | {len(rows)} | {m([r['obs'] for r in r1]):.3f} / {m([r['a_g'] for r in r1]):.3f} / "
          f"{m([r['a_x'] for r in r1]):.3f} / {m([r['a_c'] for r in r1]):.3f} | {m([r['a_g'] for r in rows]):.3f} / "
          f"{m([r['a_x'] for r in rows]):.3f} / {m([r['a_c'] for r in rows]):.3f} | {eg:.3f} → {ex:.3f} ({(ex / eg - 1) * 100:+.1f} %) / "
          f"{ec:.3f} ({(ec / eg - 1) * 100:+.1f} %) | {m([r['pmax'] for r in r1]):.3f} / {m([r['qmax'] for r in r1]):.3f} |")
