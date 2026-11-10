"""Scores, 95 % intervals and paired comparisons.

* Category score = weighted mean over items of the item's mean score over its runs (weights: equal, except honesty,
  which balances the unknowable and the answerable halves).
* 95 % interval: Wilson score interval when every item is pass/fail and has one run with equal weights; otherwise a
  two-stage bootstrap (resample items within their stratum, then each item's runs), 10,000 draws, percentile,
  widened where needed to at least a Wilson interval over the items (so few or all-solved items never give a
  zero-width interval).
* Comparing two labels: item by item on the items both have.  The difference of the category scores, a paired
  bootstrap interval for it, and a sign-flip permutation test (exact up to 2^16 sign patterns, Monte Carlo above).
  "within noise" when the interval contains 0 (p >= 0.05).
"""
from __future__ import annotations

import math
import random
from itertools import product

Z = 1.959963984540054
B = 10000


def wilson(k: float, n: int):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    den = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / den
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def _pct(xs, q):
    xs = sorted(xs)
    i = q * (len(xs) - 1)
    lo, hi = math.floor(i), math.ceil(i)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def category_score(items: dict, seed: int = 1):
    """items: {item_id: {"runs": [scores], "weight": w or None, "stratum": s or None}} -> (score, lo, hi, method)."""
    items = {k: v for k, v in items.items() if v["runs"]}
    if not items:
        return None, None, None, "no data"
    w = {k: (v.get("weight") or 1.0) for k, v in items.items()}
    tw = sum(w.values())
    score = sum(w[k] * (sum(v["runs"]) / len(v["runs"])) for k, v in items.items()) / tw
    binary = all(len(v["runs"]) == 1 and v["runs"][0] in (0, 1) for v in items.values())
    equal_w = len(set(round(x, 12) for x in w.values())) == 1
    if binary and equal_w:
        lo, hi = wilson(sum(v["runs"][0] for v in items.values()), len(items))
        return score, lo, hi, "Wilson"
    rng = random.Random(seed)
    strata = {}
    for k, v in items.items():
        strata.setdefault(v.get("stratum"), []).append(k)
    draws = []
    for _ in range(B):
        num = den = 0.0
        for keys in strata.values():
            for _ in keys:
                k = keys[rng.randrange(len(keys))]
                runs = items[k]["runs"]
                m = sum(runs[rng.randrange(len(runs))] for _ in runs) / len(runs)
                num += w[k] * m
                den += w[k]
        draws.append(num / den)
    # never narrower than a Wilson interval over the items (one observation per item): with few items, or all of
    # them solved, the bootstrap alone collapses to zero width
    wl, wh = wilson(score * len(items), len(items))
    return score, min(_pct(draws, 0.025), wl), max(_pct(draws, 0.975), wh), "bootstrap/Wilson"


def overall_score(cats: dict, seed: int = 2):
    """cats: {cat: items-dict as above}; the unweighted mean of the category scores, bootstrap interval."""
    cats = {c: {k: v for k, v in it.items() if v["runs"]} for c, it in cats.items()}
    cats = {c: it for c, it in cats.items() if it}
    if not cats:
        return None, None, None
    pts = [category_score(it)[0] for it in cats.values()]
    rng = random.Random(seed)
    prepared = {}
    for c, it in cats.items():
        w = {k: (v.get("weight") or 1.0) for k, v in it.items()}
        strata = {}
        for k, v in it.items():
            strata.setdefault(v.get("stratum"), []).append(k)
        prepared[c] = (it, w, strata)
    draws = []
    for _ in range(B // 2):
        tot = 0.0
        for it, w, strata in prepared.values():
            num = den = 0.0
            for keys in strata.values():
                for _ in keys:
                    k = keys[rng.randrange(len(keys))]
                    runs = it[k]["runs"]
                    num += w[k] * sum(runs[rng.randrange(len(runs))] for _ in runs) / len(runs)
                    den += w[k]
            tot += num / den
        draws.append(tot / len(prepared))
    return sum(pts) / len(pts), _pct(draws, 0.025), _pct(draws, 0.975)


def paired(a: dict, b: dict, seed: int = 3):
    """a, b: {item_id: {"runs": [...], "weight": w, "stratum": s}} for the same category.  Item by item on the shared
    items.  Returns a dict: n, diff (b - a), lo, hi, p, verdict."""
    keys = sorted(k for k in a if k in b and a[k]["runs"] and b[k]["runs"])
    if not keys:
        return {"n": 0, "diff": None, "lo": None, "hi": None, "p": None, "verdict": "no shared items"}
    w = {k: (a[k].get("weight") or 1.0) for k in keys}
    tw = sum(w.values())
    d = {k: (sum(b[k]["runs"]) / len(b[k]["runs"]) - sum(a[k]["runs"]) / len(a[k]["runs"])) for k in keys}
    diff = sum(w[k] * d[k] for k in keys) / tw
    rng = random.Random(seed)
    strata = {}
    for k in keys:
        strata.setdefault(a[k].get("stratum"), []).append(k)
    draws = []
    for _ in range(B):
        num = den = 0.0
        for ks in strata.values():
            for _ in ks:
                k = ks[rng.randrange(len(ks))]
                ra, rb = a[k]["runs"], b[k]["runs"]
                ma = sum(ra[rng.randrange(len(ra))] for _ in ra) / len(ra)
                mb = sum(rb[rng.randrange(len(rb))] for _ in rb) / len(rb)
                num += w[k] * (mb - ma)
                den += w[k]
        draws.append(num / den)
    lo, hi = _pct(draws, 0.025), _pct(draws, 0.975)
    # sign-flip permutation test on the weighted item differences
    nz = [k for k in keys if abs(d[k]) > 1e-12]
    obs = abs(sum(w[k] * d[k] for k in nz))
    if not nz:
        p = 1.0
    elif len(nz) <= 16:
        cnt = tot = 0
        for signs in product((1, -1), repeat=len(nz)):
            tot += 1
            if abs(sum(s * w[k] * d[k] for s, k in zip(signs, nz))) >= obs - 1e-12:
                cnt += 1
        p = cnt / tot
    else:
        cnt, M = 0, 20000
        for _ in range(M):
            if abs(sum((1 if rng.random() < 0.5 else -1) * w[k] * d[k] for k in nz)) >= obs - 1e-12:
                cnt += 1
        p = (cnt + 1) / (M + 1)
    noise = (lo <= 0 <= hi) or p >= 0.05
    verdict = "within noise" if noise else ("B higher" if diff > 0 else "A higher")
    return {"n": len(keys), "diff": diff, "lo": lo, "hi": hi, "p": p, "verdict": verdict,
            "items_b_better": sum(1 for k in keys if d[k] > 1e-12), "items_a_better": sum(1 for k in keys if d[k] < -1e-12)}
