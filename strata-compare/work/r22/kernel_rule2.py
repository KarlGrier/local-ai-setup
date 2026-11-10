#!/usr/bin/env python3
"""kernel_rule2.py PFYDIR [PFYDIR ...] [--ref ref --refs unfused,cpushare --cands v2,v2d,v2g] - the kernel rule for the gaps after
gap 8 (the user, 10-22 12:1x), read straight from pf_yardstick.py run dirs (first.<i> logit rows, the ref's index.json;
long prompts only, > 1000 tokens). A variant is rounding-level when, against the same reference build, it sits within
the spread of our own two rounding references:
  KL mean            <= 1.10 x the larger of the two references' means (as in gap 8)
  top-1 (prompts)    at most ONE prompt below the lower reference (as in gap 8)
  KL p90             <= the worse (larger) of the two references' p90 (numpy percentile, linear) - replaces gap 8's
                        single worst-position bound, which a few chaotic prompts decide
  rows with KL > 1   <= the worse reference's count + 1
The int8 attention check: --ref refi8 --refs unfusedi8,cpusharei8 --cands immai8.
Several PFYDIRs (gap 9: gap 8's long40 + gap 9's long80b = 120 prompts) are pooled row by row; each must hold the ref
and every reference and candidate.
"""
import argparse
import json
import pathlib
import sys

import numpy as np

TOL_MEAN, KL_HIGH = 1.10, 1.0


def logp(d, i):
    x = np.fromfile(d / f"first.{i}", dtype=np.float32).astype(np.float64)
    x -= x.max()
    return x - np.log(np.exp(x).sum())


def rows(ref, run, idx):
    kl, hit = [], 0
    for i, rq in enumerate(idx):
        if rq["tokens"] <= 1000 or not (run / f"first.{i}").exists() or not (ref / f"first.{i}").exists():
            continue
        lr, la = logp(ref, i), logp(run, i)
        kl.append(float((np.exp(lr) * (lr - la)).sum()))
        hit += int(lr.argmax() == la.argmax())
    return kl, hit


def stats(parts):
    kl = np.array([x for k, _ in parts for x in k])
    return {"n": len(kl), "hits": sum(h for _, h in parts), "mean": kl.mean(), "p90": float(np.percentile(kl, 90)),
            "high": int((kl > KL_HIGH).sum()), "max": kl.max()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pfy", nargs="+")
    ap.add_argument("--ref", default="ref")
    ap.add_argument("--refs", default="unfused,cpushare")
    ap.add_argument("--cands", default="v2,v2d,v2g")
    a = ap.parse_args()
    roots = [pathlib.Path(d) for d in a.pfy]
    ref = roots[0] / a.ref
    refs, cands = a.refs.split(","), a.cands.split(",")
    s = {}
    for x in refs + cands:
        if all((r / x).is_dir() for r in roots):
            s[x] = stats([rows(r / a.ref, r / x, json.loads((r / a.ref / "index.json").read_text())["requests"]) for r in roots])
    have = [x for x in refs if x in s]
    if len(have) < len(refs):
        print(f"MISSING references: {', '.join(x for x in refs if x not in s)}")
        return 1
    mean_b = TOL_MEAN * max(s[x]["mean"] for x in have)
    hit_b = min(s[x]["hits"] for x in have) - 1
    p90_b = max(s[x]["p90"] for x in have)
    high_b = max(s[x]["high"] for x in have) + 1
    print(f"reference {a.ref} in {', '.join(map(str, roots))} - bounds: top-1 >= {hit_b} prompts, KL mean <= {mean_b:.6f}, KL p90 <= {p90_b:.6f}, "
          f"rows KL > {KL_HIGH:g} <= {high_b}")
    for x in refs + cands:
        if x not in s:
            print(f"{x}: no data")
            continue
        r = s[x]
        line = (f"{x:10s} top-1 {r['hits']}/{r['n']}  KL mean {r['mean']:.6f}  p90 {r['p90']:.6f}  rows > {KL_HIGH:g}: "
                f"{r['high']}  (max {r['max']:.4f}, not judged)")
        if x in cands:
            ok = r["hits"] >= hit_b and r["mean"] <= mean_b and r["p90"] <= p90_b and r["high"] <= high_b
            fails = [w for w, bad in (("top-1", r["hits"] < hit_b), ("mean", r["mean"] > mean_b),
                                      ("p90", r["p90"] > p90_b), ("KL>1 rows", r["high"] > high_b)) if bad]
            line += f"  -> {'PASS' if ok else 'FAIL (' + ', '.join(fails) + ')'}"
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
