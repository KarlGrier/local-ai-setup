#!/usr/bin/env python3
"""specsamp_ref.py [--n N] — round 8 A.4 / B: a host reference of EXACT speculative sampling for one verify window, and
the tiny-vocabulary tests it must pass (the same tests a GPU implementation will have to pass bit-for-bit in its
decisions).  The rule (Leviathan et al. 2023 / Chen et al. 2023):
  for j = 1..K: draft x_j ~ q_j (independent proposal stream); accept with prob min(1, p_j(x_j) / q_j(x_j))
                (acceptance stream); on the first rejection draw the next token from normalize((p_j - q_j)+) (residual
                stream) and stop;  if all K are accepted, draw the bonus token from p_{K+1} (the target's own stream).
Whether position j is drafted is decided BEFORE x_j is drawn (here: a fixed K, or a rule on q_j alone - never on x_j).
q_j may have zero mass where p_j has mass (the draft vocabulary is a subset): the residual keeps those tokens.

Tests (each: the empirical distribution of the FIRST emitted token and of the first TWO emitted tokens vs the exact
target distribution, chi-square; plus the analytic acceptance sum(min(p, q)) vs the observed):
  identical (q = p), disjoint supports, swapped ranks, zero draft support for most of the target's mass, extreme logits
  (+-80, near-ties), a penalty applied to both (the SAME penalized distributions), a q decided from q only (variable K).
The second token is conditioned on the first (a toy 'model' where p and q depend on the previous token)."""
import argparse
import math
import random

import numpy as np

V = 6   # tiny vocabulary


def softmax(l):
    m = max(l)
    e = [math.exp(x - m) for x in l]
    s = sum(e)
    return [x / s for x in e]


def draw(dist, u):
    c = 0.0
    for i, p in enumerate(dist):
        c += p
        if u < c:
            return i
    return max(i for i, p in enumerate(dist) if p > 0)


def residual(p, q):
    r = [max(0.0, a - b) for a, b in zip(p, q)]
    s = sum(r)
    return [x / s for x in r] if s > 0 else list(p)


def window(ctx, P, Q, K, rng_prop, rng_acc, rng_res, rng_bonus, k_rule=None):
    """emit tokens for one window starting after context `ctx` (a tuple); P(ctx) / Q(ctx) give distributions"""
    out = []
    c = ctx
    k = 0
    while True:
        q = Q(c)
        if k_rule is not None and not k_rule(q, k):   # decided from q alone, BEFORE drawing
            break
        if k >= K:
            break
        x = draw(q, rng_prop.random())
        p = P(c)
        if q[x] > 0 and rng_acc.random() < min(1.0, p[x] / q[x]):
            out.append(x)
            c = c + (x,)
            k += 1
            continue
        out.append(draw(residual(p, q), rng_res.random()))
        return out
    out.append(draw(P(c), rng_bonus.random()))
    return out


def chi2(counts, probs, n):
    exp = [p * n for p in probs]
    stat, dof = 0.0, 0
    for o, e in zip(counts, exp):
        if e > 0:
            stat += (o - e) ** 2 / e
            dof += 1
        elif o > 0:
            return float("inf"), dof
    return stat, max(1, dof - 1)


def pval(stat, dof):
    if stat == float("inf"):
        return 0.0
    try:
        from scipy.stats import chi2 as C
        return float(C.sf(stat, dof))
    except Exception:   # Wilson-Hilferty approximation
        z = ((stat / dof) ** (1 / 3) - (1 - 2 / (9 * dof))) / math.sqrt(2 / (9 * dof))
        return 0.5 * math.erfc(z / math.sqrt(2))


def case(name, Pl, Ql, K, n, seed, k_rule=None):
    P = lambda c: softmax(Pl(c))
    Q = lambda c: (lambda d: d)(Ql(c))
    rs = [random.Random(seed * 10 + i) for i in range(4)]
    first = [0] * V
    pair = np.zeros((V, V))
    acc_obs = 0
    for _ in range(n):
        out = window((), P, Q, K, *rs, k_rule=k_rule)
        first[out[0]] += 1
        if len(out) >= 2:
            pair[out[0], out[1]] += 1
        else:   # the window ended after 1 token: the next token comes from the next window at context (out[0],)
            nxt = window((out[0],), P, Q, K, *rs, k_rule=k_rule)
            pair[out[0], nxt[0]] += 1
        acc_obs += 0   # (acceptance measured separately below)
    p1 = P(())
    s1, d1 = chi2(first, p1, n)
    pp = [p1[a] * P((a,))[b] for a in range(V) for b in range(V)]
    s2, d2 = chi2(pair.flatten().tolist(), pp, n)
    q1 = Q(())
    amin = sum(min(a, b) for a, b in zip(p1, q1))
    # observed first-draft acceptance (fresh streams)
    ra, rb = random.Random(seed + 7), random.Random(seed + 8)
    m = 200000
    acc = sum(1 for _ in range(m) if (lambda x: q1[x] > 0 and rb.random() < min(1, p1[x] / q1[x]))(draw(q1, ra.random())))
    print(f"{name:34s} first token chi2 {s1:7.2f} (dof {d1}) p={pval(s1, d1):.3f} | first two chi2 {s2:7.2f} (dof {d2}) "
          f"p={pval(s2, d2):.3f} | accept sum(min) {amin:.4f} observed {acc / m:.4f}")
    return pval(s1, d1), pval(s2, d2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200000)
    a = ap.parse_args()
    base = [2.0, 1.2, 0.3, 0.0, -0.5, -1.0]
    dep = lambda c: [x + (0.8 if c and i == (c[-1] + 1) % V else 0.0) for i, x in enumerate(base)]   # context-dependent
    sm = softmax
    cases = [
        ("identical q = p", lambda c: dep(c), lambda c: sm(dep(c)), 3),
        ("disjoint supports", lambda c: dep(c), lambda c: [0, 0, 0, 0.5, 0.5, 0] if True else None, 3),
        ("swapped ranks", lambda c: dep(c), lambda c: sm(list(reversed(dep(c)))), 3),
        ("zero draft support (subset vocab)", lambda c: dep(c), lambda c: (lambda d: [x / sum(d[2:]) if i >= 2 else 0.0 for i, x in enumerate(d)])(sm(dep(c))), 4),
        ("extreme logits (+-80, near-tie)", lambda c: [80.0, 79.999, -80, -80, 0, 1e-3], lambda c: sm([80.0, 80.0, -80, -80, 0, 0]), 2),
        ("penalized (same penalty in p and q)", lambda c: [x - (1.5 if c and i == c[-1] else 0.0) for i, x in enumerate(dep(c))],
         lambda c: sm([x * 0.8 - (1.5 if c and i == c[-1] else 0.0) for i, x in enumerate(dep(c))]), 3),
        ("q close to p (temperature 0.8 draft)", lambda c: dep(c), lambda c: sm([x / 0.8 for x in dep(c)]), 4),
    ]
    bad = 0
    for i, (name, Pl, Ql, K) in enumerate(cases):
        p1, p2 = case(name, Pl, Ql, K, a.n, 100 + i)
        bad += (p1 < 0.001) + (p2 < 0.001)
    p1, p2 = case("K from q alone (stop if max q < 0.5)", cases[6][1], cases[6][2], 6, a.n, 99,
                  k_rule=lambda q, k: max(q) >= 0.5)
    bad += (p1 < 0.001) + (p2 < 0.001)
    # the NEGATIVE control: deciding from the SAMPLED draft (drop x_j when q(x_j) < 0.3 and emit from p instead - the
    # coupled rule "gate on the sampled draft's probability" applied to exact sampling) biases the output
    def biased(ctx, P, Q, K, rp, ra, rr, rb, k_rule=None):
        out, c = [], ctx
        for _ in range(K):
            q = Q(c); x = draw(q, rp.random()); p = P(c)
            if q[x] < 0.3:                                   # the decision reads the sampled x
                out.append(draw(p, rb.random())); return out
            if q[x] > 0 and ra.random() < min(1.0, p[x] / q[x]):
                out.append(x); c = c + (x,); continue
            out.append(draw(residual(p, q), rr.random())); return out
        out.append(draw(P(c), rb.random())); return out
    global window
    keep = window
    window = biased
    p1, p2 = case("NEGATIVE CONTROL (K from sampled x)", cases[6][1], cases[6][2], 3, a.n, 98)
    window = keep
    print(f"\n{bad} failures at p < 0.001 in the exact cases; negative control p(first two) = {p2:.2e} "
          f"({'caught' if p2 < 0.001 else 'NOT caught: the test is too weak'})")


if __name__ == "__main__":
    main()
