#!/usr/bin/env python3
"""kernel_rule3.py PFYDIR [--ref ref --refs unfused,cpushare --cands x28h,x28h-nov2] - round 22 gap 16 (Karl 10-30, condition 4:
"KL mean, p90, KL>1 count, top-1 and NLL stay exactly as they are"): the rounding-level rule in its CURRENT form
(yardstick-kernel-rule, the 10-26 changes; work/ds41/tune/skipcheck.py rounding_checks) on pf_yardstick.py long40 dirs.
kernel_rule2.py (gaps 12-15) is the 10-22 form and has no NLL check; gap 16 runs both and a switch needs both.
Against the same reference build (ref), a candidate passes when, with R1 / R2 = our two rounding references:
  mean   KL mean <= 1.10 x the larger reference's
  p90    KL p90 <= 1.10 x the larger reference's (numpy percentile, linear, as kernel_rule2)
  gt1    prompts with KL > 1 <= the worse reference's + 1
  top1   changed top-1 picks vs ref <= 1.10 x the larger reference's
  nll    mean NLL of the text's own next token (the token after each cut, from each run's own logit row): the candidate's
         may exceed ref's by at most 1.10 x the larger reference's distance from ref
Rows as kernel_rule2: long prompts only (> 1000 tokens), present in both dirs; the NLL rows are the same prompts where the
text goes on after the cut. Exit 0 = every candidate passes, 1 = a candidate fails, 2 = could not run.
"""
import argparse
import importlib.util
import json
import pathlib
import sys

import numpy as np

SC = pathlib.Path("/home/USER/ai-speed-testing/strata-compare")
TOL, KL_HIGH = 1.10, 1.0


def pfy_module():
    spec = importlib.util.spec_from_file_location("pf_yardstick", SC / "work/r22/pf_yardstick.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def next_tokens(n_req):
    """the text's next token after each long40 cut (None where the text ends at the cut), in pf_yardstick's order"""
    py = pfy_module()
    out = []
    for f, cuts in py.LONG40:
        ids = [int(x) for x in (py.PR / f).read_text().replace("\n", ",").split(",") if x.strip()]
        for n in cuts:
            out.append((n or len(ids), ids[n] if n and n < len(ids) else None))
    if len(out) != n_req:
        raise SystemExit(f"index.json has {n_req} requests, long40 has {len(out)} - not a long40 dir")
    return out


def logp(d, i):
    x = np.fromfile(d / f"first.{i}", dtype=np.float32).astype(np.float64)
    x -= x.max()
    return x - np.log(np.exp(x).sum())


def run_rows(ref, run, idx, nxt):
    kl, flips, nll = [], 0, []
    for i, rq in enumerate(idx):
        if rq["tokens"] <= 1000 or not (run / f"first.{i}").exists() or not (ref / f"first.{i}").exists():
            continue
        if rq["tokens"] != nxt[i][0]:
            raise SystemExit(f"request {i}: {rq['tokens']} tokens, long40 cut {nxt[i][0]} - order differs")
        lr, la = logp(ref, i), logp(run, i)
        kl.append(float((np.exp(lr) * (lr - la)).sum()))
        flips += int(lr.argmax() != la.argmax())
        if nxt[i][1] is not None:
            nll.append((i, -float(la[nxt[i][1]]), -float(lr[nxt[i][1]])))
    kl = np.array(kl)
    return {"n": len(kl), "flips": flips, "mean": kl.mean(), "p90": float(np.percentile(kl, 90)),
            "high": int((kl > KL_HIGH).sum()), "max": kl.max(), "nll_rows": nll}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pfy")
    ap.add_argument("--ref", default="ref")
    ap.add_argument("--refs", default="unfused,cpushare")
    ap.add_argument("--cands", default="x28h,x28h-nov2")
    a = ap.parse_args()
    root = pathlib.Path(a.pfy)
    idx = json.loads((root / a.ref / "index.json").read_text())["requests"]
    nxt = next_tokens(len(idx))
    refs, cands = a.refs.split(","), a.cands.split(",")
    s = {x: run_rows(root / a.ref, root / x, idx, nxt) for x in refs + cands if (root / x).is_dir()}
    if any(x not in s for x in refs):
        print(f"MISSING references: {', '.join(x for x in refs if x not in s)}")
        return 2
    # NLL on the prompts every run has (the same rows for all)
    common = set.intersection(*[{i for i, _, _ in s[x]["nll_rows"]} for x in s])
    for x in s:
        rows = [(c, b) for i, c, b in s[x]["nll_rows"] if i in common]
        s[x]["nll"], s[x]["nll_base"] = np.mean([c for c, _ in rows]), np.mean([b for _, b in rows])
    base = s[refs[0]]["nll_base"]
    mean_b = TOL * max(s[x]["mean"] for x in refs)
    p90_b = TOL * max(s[x]["p90"] for x in refs)
    high_b = max(s[x]["high"] for x in refs) + 1
    flip_b = TOL * max(s[x]["flips"] for x in refs)
    nll_b = TOL * max(abs(s[x]["nll"] - base) for x in refs)
    print(f"reference {a.ref} in {root} (10-26 rule, {s[refs[0]]['n']} prompts, NLL on {len(common)}) - bounds: KL mean <= "
          f"{mean_b:.6f}, KL p90 <= {p90_b:.6f}, rows KL > {KL_HIGH:g} <= {high_b}, changed top-1 <= {flip_b:.1f}, "
          f"NLL above {a.ref}'s ({base:.4f}) <= {nll_b:.4f}")
    bad = 0
    for x in refs + cands:
        if x not in s:
            print(f"{x}: no data")
            bad = 1
            continue
        r = s[x]
        line = (f"{x:10s} KL mean {r['mean']:.6f}  p90 {r['p90']:.6f}  rows > {KL_HIGH:g}: {r['high']}  changed top-1 "
                f"{r['flips']}/{r['n']}  NLL {r['nll']:.4f} ({r['nll'] - base:+.4f})")
        if x in cands:
            fails = [w for w, b in (("mean", r["mean"] > mean_b), ("p90", r["p90"] > p90_b), ("KL>1 rows", r["high"] > high_b),
                                    ("top-1", r["flips"] > flip_b), ("NLL", r["nll"] - base > nll_b)) if b]
            line += f"  -> {'PASS' if not fails else 'FAIL (' + ', '.join(fails) + ')'}"
            bad |= bool(fails)
        print(line)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
