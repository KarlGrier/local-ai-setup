#!/usr/bin/env python3
"""policy4.py (policy3 with C*10's W(T) from Phase 0.5) (round 9 copy of policy2.py: the exact-sampling arm gated BOTH ways - on the raw top probability (index 3, today's gate, what r9-ess implements) and on the post-chain max q (index 2, round 8's policy2)) — — round 8 A.4 policy model, CORRECTED to the engine's real draft-length rule (generate.cpp:5044):
T starts at 1 and draft j is in the window while the previous draft's probability >= --spec-min-p... precisely:
    T = 1; while T < S and dprob[T-1] >= floor: ++T        (dprob[j] = draft j's probability = max q for greedy drafts)
so the floor gates draft 1 too (a window can have NO draft).  The first model (oracle_analyze.policy_table) always kept
draft 1, which flattered high floors.  Window times W(T) are the A.4 CLI table (ms per round incl. commit + drafting,
mean of math / code); W(1) is NOT measured: W(2) - 3.9 ms (the T1 -> T2 step in the A.1 served trace is +4.0 ms).
Data: the deep oracle arm (every window drafted to 7 with no floor), later positions conditioned on the greedy prefix."""
import sys
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/r8")   # oracle_analyze + the round-8 oracle data
from oracle_analyze import load, coupled

W = {1: 11.9, 2: 15.33, 3: 18.76, 4: 22.35, 5: 25.53, 6: 29.29, 7: 32.81, 8: 35.78}   # round 9 Phase 0.5 (C*10, mean of math / code; W(1) = W(2) - 3.4, estimated)


def chains(wins):
    out = []
    for w in wins:
        dr = sorted(w["drafts"], key=lambda d: d[1])
        if not dr or len(w["toks"]) < 2:
            continue
        ch = []
        for j, (ctr, jj, did, dprob, q) in enumerate(dr):
            if j + 1 >= w["T"] or ctr != w["pos0"] + j or w["toks"][j + 1] != did:
                break
            p = dict(w["p"][j]); qd = dict(q)
            ch.append((p.get(did, 0.0), sum(min(pp, qd.get(t, 0.0)) for t, pp in p.items()), q[0][1] if q else 0.0, dprob))
        if len(ch) >= 7:
            out.append(ch)
    return out


def run(chs, S, th, k, w1=W[1], gate=None):
    toks = ms = 0.0
    Ts = []
    for ch in chs:
        T = 1
        gi = gate if gate is not None else (3 if k == 0 else 2)
        while T < S and ch[T - 1][gi] >= th:   # 3 = the raw top probability (today's gate), 2 = the post-chain max q
            T += 1
        n = T - 1
        e, pr = 1.0, 1.0
        for a in ch[:n]:
            pr *= a[k]
            e += pr
        toks += e
        ms += w1 if T == 1 else W[T]
        Ts.append(T)
    return toks / len(chs), toks / ms, sum(Ts) / len(Ts)


def main():
    wins = load("/home/USER/ai-speed-testing/strata-compare/results/r8/oracle/R8o-deep.txt")
    chs = chains(wins)
    base = run(chs, 4, 0.5, 0)[1]
    print(f"{len(chs)} windows with 7 drafts; W(1) = {W[1]} ms (estimated)")
    print("| --spec | floor | greedy: tokens/round, mean T, tokens/ms vs today | exact, raw-top gate (r9-ess) | exact, post-chain max-q gate (r8 policy2) |")
    print("|---|---|---|---|---|")
    for S in (3, 4, 5, 6, 8):
        for th in (0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
            g = run(chs, S, th, 0); x = run(chs, S, th, 1, gate=3); y = run(chs, S, th, 1, gate=2)
            print(f"| {S} | {th} | {g[0]:.3f}, {g[2]:.2f}, {(g[1] / base - 1) * 100:+.1f} % | {x[0]:.3f}, {x[2]:.2f}, "
                  f"{(x[1] / base - 1) * 100:+.1f} % | {y[0]:.3f}, {y[2]:.2f}, {(y[1] / base - 1) * 100:+.1f} % |")
    for w1 in (11.1, 13.1):
        b = run(chs, 4, 0.5, 0, w1)[1]
        print(f"sensitivity W(1) = {w1}: greedy s4 floor 0.7 {(run(chs, 4, 0.7, 0, w1)[1] / b - 1) * 100:+.1f} %, "
              f"exact s4 floor 0.5 {(run(chs, 4, 0.5, 1, w1)[1] / b - 1) * 100:+.1f} %, "
              f"exact best s5 floor 0.5 {(run(chs, 5, 0.5, 1, w1)[1] / b - 1) * 100:+.1f} %")


if __name__ == "__main__":
    main()
