#!/usr/bin/env python3
"""sp43_table.py - round 19 Part D 6: the near-tie counts on v0.1.43 (results/r19/sp-v43/) as the issue's table rows."""
import json, math
from pathlib import Path
O = Path("/home/USER/ai-speed-testing/strata-compare/results/r19/sp-v43")
c = [x for x in json.loads((O / "sp-cases.json").read_text()) if x["case"] == "arith-j3"][0]
def tally(a):
    f = O / f"sp-strata-v43-{a}.jsonl"
    if not f.exists(): return None
    on = eq = 0
    for line in open(f):
        r = json.loads(line)
        if r["ids"] and r["ids"][:c["j"]] == c["path"]: on += 1; eq += r["ids"][c["j"]] == 28
    return eq, on
rows = [("nospec", "speculation off (`--spec-min-p 2`: no draft passes)"), ("sp", "`STRATA_SPEC_PROB=1`, `--spec-min-p 0.5`"),
        ("spmp0", "`STRATA_SPEC_PROB=1`, `--spec-min-p 0`"), ("sptop", "`STRATA_SPEC_PROB=1`, `--spec-min-p 0.5`, `STRATA_SPEC_PROB_GATE=top`"),
        ("em", "default exact-match drafting, `--spec-min-p 0.5`"), ("exact", "our local exact-sampling patch, `--spec-min-p 0.5` (not in Strata)")]
t = {a: tally(a) for a, _ in rows}
ref = t["nospec"]
for a, name in rows:
    if t[a] is None or t[a][1] == 0: print(f"| {name} | (pending) | | |"); continue
    e, n = t[a]
    if a == "nospec": print(f"| {name} | {e:,} of {n:,} | {100 * e / n:.1f} % | - |"); continue
    b, m = ref; p = (e + b) / (n + m); z = (e / n - b / m) / math.sqrt(p * (1 - p) * (1 / n + 1 / m))
    print(f"| {name} | {e:,} of {n:,} | {100 * e / n:.1f} % | {100 * (e / n - b / m):+.1f} points, z {z:.1f}, p {math.erfc(abs(z) / math.sqrt(2)):.2g} |")
