#!/usr/bin/env python3
"""neartie_compare.py DIR REF CAND... - round 22 (10-27, Karl: upstream's sampling path must be distribution-preserving, by the
token-distribution test our exact sampling passed): the round-19 near-tie count (work/r19/d6_sampler43.sh, the test behind
#2028). Case arith-j3 at T 0.6: among the samples whose first j tokens are the case's path, how often the tie token ('=')
comes next, in each arm's sp-strata-LABEL.jsonl, against the reference arm (speculation off on the same build): a
two-proportion z-test. p >= 0.05: no difference shown (the verdict line says PASS); p < 0.05: not shown to be
distribution-preserving - 4,000 more samples on each side before a verdict (round 19's sp_more.sh did that once).
Power: round 19's bias was +4.1 points; at 4,000 per arm that is z ~ 3.6."""
import json
import math
import sys
from pathlib import Path

CASE, TEMP = "arith-j3", 0.6


def tally(f: Path, c: dict):
    on = eq = 0
    for line in open(f):
        r = json.loads(line)
        if r["case"] != CASE or abs(r["temp"] - TEMP) > 1e-6 or not r["ids"] or r["ids"][:c["j"]] != c["path"]:
            continue
        on += 1
        eq += r["ids"][c["j"]] == c["b_token"]
    return eq, on


def main():
    d, ref, cands = Path(sys.argv[1]), sys.argv[2], sys.argv[3:]
    c = [x for x in json.loads((d / "sp-cases.json").read_text()) if x["case"] == CASE][0]
    t = {}
    for lab in [ref] + cands:
        f = d / f"sp-strata-{lab}.jsonl"
        t[lab] = tally(f, c) if f.exists() else (0, 0)
        e, n = t[lab]
        print(f"{lab}: {c['b_text']!r} {e} of {n}" + (f" = {100 * e / n:.1f} %" if n else " (no samples on the path)"))
    b, m = t[ref]
    for lab in cands:
        a, n = t[lab]
        if not n or not m:
            print(f"{lab} vs {ref}: NO VERDICT (an arm has no samples on the path)")
            continue
        p = (a + b) / (n + m)
        z = (a / n - b / m) / math.sqrt(p * (1 - p) * (1 / n + 1 / m))
        pv = math.erfc(abs(z) / math.sqrt(2))
        verdict = "PASS (no difference shown)" if pv >= 0.05 else "NOT SHOWN distribution-preserving (4,000 more each before a verdict)"
        print(f"{lab} vs {ref}: {100 * (a / n - b / m):+.1f} points, z {z:.2f}, two-sided p {pv:.3g} - {verdict}")


if __name__ == "__main__":
    main()
