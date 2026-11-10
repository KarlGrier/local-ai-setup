#!/usr/bin/env python3
"""research_wo_r04.py - 2026-10-13: each label's research score and total with and without r04_strata_release
(local v0.1.43-era servers score 0 there: the quoted </tool_call> server bug, fixed upstream in 0.1.43.1; the scored
labels stay as they are, this is the side-by-side view). Research = mean over items of the mean over scored runs
(UNCHECKED runs are not scored), as report.py does; total = mean of the 8 category scores."""
import json
import statistics
import sys
from pathlib import Path

R = Path("/home/USER/ai-speed-testing/strata-compare/suite/results")
print("| label | research | research w/o r04 | r04 | total | total w/o r04 |")
print("|---|---|---|---|---|---|")
for lb in sys.argv[1:]:
    g = json.loads((R / lb / "grades.json").read_text())
    s = json.loads((R / lb / "scores.json").read_text())
    per = {}
    for x in g.values():
        if x["category"] == "research" and x["score"] is not None:
            per.setdefault(x["item"], []).append(x["score"])
    items = {k: statistics.mean(v) for k, v in per.items()}
    r_all = statistics.mean(items.values())
    r_wo = statistics.mean(v for k, v in items.items() if not k.endswith("r04_strata_release"))
    cats = s["categories"]
    sc = {c: (cats[c]["score"] if isinstance(cats[c], dict) else cats[c]) for c in s["overall"]["categories"]}
    assert abs(sc["research"] - r_all) < 1e-9, (lb, sc["research"], r_all)
    tot = statistics.mean(sc.values())
    tot_wo = statistics.mean([v for c, v in sc.items() if c != "research"] + [r_wo])
    r04 = items.get("research/r04_strata_release")
    print(f"| {lb} | {100*r_all:.1f} | {100*r_wo:.1f} | {'-' if r04 is None else f'{100*r04:.0f}'} | {100*tot:.1f} | {100*tot_wo:.1f} |")
