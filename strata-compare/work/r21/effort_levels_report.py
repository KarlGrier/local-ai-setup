#!/usr/bin/env python3
"""effort_levels_report.py - 2026-10-17, your item 1: C*18t (IQ3_S) at low vs medium vs xhigh per category, the
long-context rerun pooled into medium (run 1 + rerun), and your rule for the default: low if it scores at least as
well as medium in every scored category, else medium.  Markdown on stdout; the chosen level on the last line
("DEFAULT: low|medium")."""
import glob
import json
import os
import re
import statistics
import sys

sys.path.insert(0, "suite")
from msuite.report import _by_cat  # noqa: E402
from msuite.stats import category_score  # noqa: E402

R = "suite/results"
XH, MED, MED_RR, LOW = "c18-iq3s-quick", "c18t-quick-medium", "c18t-quick-medium-rr", "c18t-quick-low"
CATS = [("coding", "Coding"), ("agentic", "Agentic"), ("math", "Math"), ("instruct", "Instruction following"),
        ("tools", "Tool calls"), ("longctx", "Long context"), ("honesty", "Honesty"), ("research", "Research")]
UNSCORED = [("freshness", "Freshness (not scored)"), ("visual", "Visual (not scored)")]


def load(lb):
    p = f"{R}/{lb}/scores.json"
    return json.load(open(p)) if os.path.exists(p) else None


S = {lb: load(lb) for lb in (XH, MED, MED_RR, LOW)}
RR = S[MED_RR]["categories"] if S[MED_RR] else {}


def labels(lb, cat):
    """The runs that make one column's cell: medium takes its rerun too where there is one."""
    return [lb, MED_RR] if lb == MED and cat in RR else [lb]


def cat_score(lb, cat):
    """(solved, answers, score) over the column's runs, scored as the suite does (msuite.stats.category_score: weighted
    mean over items of each item's mean over its runs; a rerun counts as one more run of its items); None if not
    scored."""
    items, solved, answers = {}, 0.0, 0
    for x in labels(lb, cat):
        g = json.load(open(f"{R}/{x}/grades.json"))
        part = {k: v for k, v in g.items() if isinstance(v, dict) and v.get("category") == cat}
        for it, e in _by_cat(part).get(cat, {}).items():
            items.setdefault(it, {"runs": [], "weight": e["weight"], "stratum": e["stratum"]})["runs"] += e["runs"]
            solved += sum(e["runs"])
            answers += len(e["runs"])
    if not items:
        return None
    return solved, answers, category_score(items)[0]


def reasoning(lb, cat):
    return [json.load(open(f))["tokens"]["reasoning"] for x in labels(lb, cat)
            for f in glob.glob(f"{R}/{x}/answers/{cat}/*.json")]


def cut(lb, cat):
    out = []
    for x in labels(lb, cat):
        for item, run, reason in S[x].get("cut_reasons") or []:
            if item.split("/")[0] == cat:
                r = (reason or "").lower()
                out.append("T" if "max_tokens" in r else "L" if "stopped it early" in r else "?")
    return out


def cutcell(ks):
    if not ks:
        return "0"
    return " / ".join(f"{ks.count(k)} {dict(T='token limit', L='loop stop').get(k, 'other')}" for k in "TL?"
                      if ks.count(k))


def verdicts(a, b):
    p = f"{R}/compare-{a}-vs-{b}.md"
    out = {}
    if os.path.exists(p):
        for line in open(p):
            m = re.match(r"\| ([^|]+?) \| \d+ \| [\d.]+ \| [\d.]+ \| (-?[\d.]+) \| ([^|]+) \| ([\d.]+) \| ([^|]+) \| "
                         r"\*\*(.+?)\*\*", line)
            if m:
                out[m.group(1).split(" (")[0].lower()[:6]] = f"{float(m.group(2)):+.1f} ({m.group(3).strip()}; {m.group(6)})"
    return out


cols = [(XH, "xhigh (10-15)"), (MED, "medium"), (LOW, "low")]
cols = [(lb, n) for lb, n in cols if S[lb]]
print("C\\*18t (IQ3_S), suite quick, your sampling; effort through --extra-body. xhigh = Friday's c18-iq3s-quick "
      "(C\\*18, same engine and weights).")
print(f"Medium's long context = run 1 + the rerun ({MED_RR}), pooled: 12 answers." if RR else "")

print("\n**Score %** (scored as the suite does: honesty items weighted; solved / answers in brackets)\n")
print("| category | " + " | ".join(n for _, n in cols) + " |")
print("|---|" + "---|" * len(cols))
tot = {lb: [] for lb, _ in cols}
for cat, name in CATS:
    cells = []
    for lb, _ in cols:
        v = cat_score(lb, cat)
        if v is None:
            cells.append("-")
            continue
        tot[lb].append(v[2])
        cells.append(f"{100 * v[2]:.1f} ({v[0]:.1f} / {v[1]:.0f})")
    print(f"| {name} | " + " | ".join(cells) + " |")
print("| **total** (mean of the 8) | " + " | ".join(f"**{100 * statistics.mean(tot[lb]):.1f}**" for lb, _ in cols) + " |")

print("\n**Wall time (run 1 only), median reasoning tokens per answer, answers cut off**\n")
print("| category | " + " | ".join(f"{n} wall | {n} reasoning | {n} cut" for _, n in cols) + " |")
print("|---|" + "---|---|---|" * len(cols))
for cat, name in CATS + UNSCORED:
    cells = []
    for lb, _ in cols:
        c = S[lb]["categories"].get(cat)
        t = reasoning(lb, cat)
        cells += [f"{c['wall_total_s'] / 60:.0f} min" if c else "-", f"{statistics.median(t):,.0f}" if t else "-",
                  cutcell(cut(lb, cat))]
    print(f"| {name} | " + " | ".join(cells) + " |")
cells = []
for lb, _ in cols:
    t = [json.load(open(f))["tokens"]["reasoning"] for f in glob.glob(f"{R}/{lb}/answers/*/*.json")]
    allcut = sum((cut(lb, c) for c, _ in CATS + UNSCORED), [])
    cells += [f"{S[lb]['totals']['wall_s'] / 3600:.2f} h", f"{statistics.median(t):,.0f}", cutcell(allcut)]
print("| **all** | " + " | ".join(cells) + " |")

pairs = [(XH, LOW, "low vs xhigh"), (MED, LOW, "low vs medium (run 1)"), (XH, MED, "medium vs xhigh")]
pairs = [p for p in pairs if S[p[0]] and S[p[1]]]
if pairs:
    print("\n**Paired by item** (difference in points, 95 % interval; verdict from `run.sh compare`)\n")
    print("| category | " + " | ".join(n for _, _, n in pairs) + " |")
    print("|---|" + "---|" * len(pairs))
    V = {(a, b): verdicts(a, b) for a, b, _ in pairs}
    for cat, name in CATS:
        print(f"| {name} | " + " | ".join(V[(a, b)].get(name.lower()[:6], "-") for a, b, _ in pairs) + " |")

if S[LOW] and S[MED]:
    worse = []
    for cat, name in CATS:
        lo, me = cat_score(LOW, cat), cat_score(MED, cat)
        if lo and me and lo[2] < me[2] - 1e-9:
            worse.append(f"{name} {100 * lo[2]:.1f} < {100 * me[2]:.1f}")
    print("\n**Your rule** (low if it scores at least as well as medium in every category): " +
          ("low is at least as good everywhere -> **low**" if not worse else
           "low is below medium in " + "; ".join(worse) + " -> **medium**"))
    print(f"\nDEFAULT: {'low' if not worse else 'medium'}")
