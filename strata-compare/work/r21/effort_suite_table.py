#!/usr/bin/env python3
"""effort_suite_table.py BASE LABEL... - per category: score, wall time and median reasoning tokens per answer for the
base run and each label, plus the paired verdict against the base (suite/results/compare-BASE-vs-LABEL.md, written by
`run.sh compare`). Markdown on stdout (2026-10-17, the effort suite runs)."""
import glob
import json
import os
import re
import statistics
import sys

R = "suite/results"
NAMES = {"coding": "Coding", "agentic": "Agentic", "math": "Math", "instruct": "Instruction following",
         "tools": "Tool calls", "longctx": "Long context", "honesty": "Honesty", "research": "Research",
         "freshness": "Freshness (not scored)", "visual": "Visual (not scored)"}


def load(label):
    p = f"{R}/{label}/scores.json"
    if not os.path.exists(p):
        return None
    s = json.load(open(p))
    med = {}
    for cat in NAMES:
        toks = [json.load(open(f))["tokens"]["reasoning"] for f in glob.glob(f"{R}/{label}/answers/{cat}/*.json")]
        med[cat] = statistics.median(toks) if toks else None
    return s, med


def verdicts(base, label):
    p = f"{R}/compare-{base}-vs-{label}.md"
    out = {}
    if os.path.exists(p):
        for line in open(p):
            m = re.match(r"\| ([^|]+?) \| \d+ \| [\d.]+ \| [\d.]+ \| (-?[\d.]+) \| ([^|]+) \| ([\d.]+) \| [^|]+ \| \*\*(.+?)\*\* \|", line)
            if m:
                out[m.group(1).split(" (")[0]] = (float(m.group(2)), m.group(3).strip(), m.group(5))
    return out


base, labels = sys.argv[1], [x for x in sys.argv[2:] if os.path.exists(f"{R}/{x}/scores.json")]
runs = {lb: load(lb) for lb in [base] + labels}
head = "| category | " + " | ".join(f"{lb}: score / wall min / median reasoning tok" for lb in runs) + " | " + \
       " | ".join(f"{lb} vs base: diff, 95 % interval, verdict" for lb in labels) + " |"
print(head)
print("|" + "---|" * (1 + len(runs) + len(labels)))
vs = {lb: verdicts(base, lb) for lb in labels}
for cat, name in NAMES.items():
    cells = []
    for lb, (s, med) in runs.items():
        c = s["categories"].get(cat)
        if not c:
            cells.append("-")
            continue
        sc = f"{100 * c['score']:.1f}" if c.get("score") is not None else "n/s"
        md = f"{med[cat]:,.0f}" if med[cat] is not None else "-"
        cells.append(f"{sc} / {c['wall_total_s'] / 60:.0f} / {md}")
    vcells = []
    for lb in labels:
        v = next((v for k, v in vs[lb].items() if k.lower().startswith(name.split(" (")[0].lower()[:6])), None)
        vcells.append(f"{v[0]:+.1f}, {v[1]}, {v[2]}" if v else "-")
    print(f"| {name} | " + " | ".join(cells) + " | " + " | ".join(vcells) + " |")
cells = []
for lb, (s, med) in runs.items():
    allr = [json.load(open(f))["tokens"]["reasoning"] for f in glob.glob(f"{R}/{lb}/answers/*/*.json")]
    o, t = s["overall"], s["totals"]
    cells.append(f"**{100 * o['score']:.1f}** [{100 * o['lo']:.1f}-{100 * o['hi']:.1f}] / {t['wall_s'] / 3600:.2f} h / "
                 f"{statistics.median(allr):,.0f}")
print("| **total** | " + " | ".join(cells) + " | " + " | ".join("" for _ in labels) + " |")
for lb, (s, med) in runs.items():
    t = s["totals"]
    print(f"\n{lb}: {t['answers']} answers, {t['cut_off']} cut off, {t['tokens']:,} output tokens; "
          f"cut: {json.dumps(s.get('cut_reasons'))[:300]}")
