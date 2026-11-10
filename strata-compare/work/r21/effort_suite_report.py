#!/usr/bin/env python3
"""effort_suite_report.py - 2026-10-17, your effort runs against Friday's xhigh runs, per category: score, wall time,
median reasoning tokens per answer, answers cut off (token limit / loop stop), the paired difference against the same
model's xhigh run, and the category reruns (two runs pooled) where IQ3_S and NVFP4 at medium differed by more than one
item. Markdown on stdout; runs that do not exist yet are left out."""
import glob
import json
import os
import re
import statistics

R = "suite/results"
RUNS = [  # label, name, Friday's xhigh run of the same model (None for the bases themselves)
    ("c18-iq3s-quick", "IQ3_S xhigh (10-15)", None),
    ("c18t-quick-medium", "IQ3_S medium", "c18-iq3s-quick"),
    ("c18t-quick-low", "IQ3_S low", "c18-iq3s-quick"),
    ("c18-nvfp4-quick", "NVFP4 xhigh (10-16)", None),
    ("c18-nvfp4-quick-medium", "NVFP4 medium", "c18-nvfp4-quick"),
]
RERUNS = {"c18t-quick-medium": "c18t-quick-medium-rr", "c18-nvfp4-quick-medium": "c18-nvfp4-quick-medium-rr"}
CATS = [("coding", "Coding"), ("agentic", "Agentic"), ("math", "Math"), ("instruct", "Instruction following"),
        ("tools", "Tool calls"), ("longctx", "Long context"), ("honesty", "Honesty"), ("research", "Research"),
        ("freshness", "Freshness (not scored)"), ("visual", "Visual (not scored)")]


def have(lb):
    return os.path.exists(f"{R}/{lb}/scores.json")


def answers(lb, cat="*"):
    return [json.load(open(f)) for f in glob.glob(f"{R}/{lb}/answers/{cat}/*.json")]


def cut_kind(reason):
    r = (reason or "").lower()
    if "max_tokens" in r:
        return "T"
    if "stopped it early" in r:
        return "L"
    return "?"


runs = [(lb, name, base) for lb, name, base in RUNS if have(lb)]
S = {lb: json.load(open(f"{R}/{lb}/scores.json")) for lb, _, _ in runs}
cuts = {}
for lb, _, _ in runs:
    c = {}
    for item, run, reason in S[lb].get("cut_reasons") or []:
        cat = item.split("/")[0]
        c.setdefault(cat, []).append(cut_kind(reason))
    cuts[lb] = c


def verdict(base, lb):
    p = f"{R}/compare-{base}-vs-{lb}.md"
    out = {}
    if os.path.exists(p):
        for line in open(p):
            m = re.match(r"\| ([^|]+?) \| \d+ \| [\d.]+ \| [\d.]+ \| (-?[\d.]+) \| ([^|]+) \| ([\d.]+) \| ([^|]+) \| \*\*(.+?)\*\* \|", line)
            if m:
                out[m.group(1).split(" (")[0].lower()[:6]] = f"{float(m.group(2)):+.1f} ({m.group(3).strip()}; {m.group(6)})"
    return out


def table(title, cell):
    print(f"\n**{title}**\n")
    print("| category | " + " | ".join(n for _, n, _ in runs) + " |")
    print("|---|" + "---|" * len(runs))
    for cat, name in CATS:
        print(f"| {name} | " + " | ".join(cell(lb, cat) for lb, _, _ in runs) + " |")
    print("| **all** | " + " | ".join(cell(lb, None) for lb, _, _ in runs) + " |")


def score(lb, cat):
    if cat is None:
        o = S[lb]["overall"]
        return f"**{100 * o['score']:.1f}** [{100 * o['lo']:.1f}-{100 * o['hi']:.1f}]"
    c = S[lb]["categories"].get(cat)
    return "-" if not c else ("not scored" if c.get("score") is None else f"{100 * c['score']:.1f}")


def wall(lb, cat):
    if cat is None:
        return f"{S[lb]['totals']['wall_s'] / 3600:.2f} h"
    c = S[lb]["categories"].get(cat)
    return "-" if not c else f"{c['wall_total_s'] / 60:.0f} min"


def medreason(lb, cat):
    t = [a["tokens"]["reasoning"] for a in answers(lb, cat or "*")]
    return f"{statistics.median(t):,.0f}" if t else "-"


def cutcell(lb, cat):
    ks = sum(cuts[lb].values(), []) if cat is None else cuts[lb].get(cat, [])
    if not ks:
        return "0"
    return " / ".join(f"{ks.count(k)} {dict(T='token limit', L='loop stop').get(k, 'other')}" for k in "TL?" if ks.count(k))


print("Suite quick, your sampling (T 1.0 / 0.95 / 20 / min-p 0.05, sent by the suite); effort through --extra-body.")
print("IQ3_S = C*18t (10-17) / C*18 (10-15 xhigh); NVFP4 = the GPTQ pack, configs/r20-nv18.json (10-16 xhigh, 10-17 medium).")
table("Score % (8 scored categories; total = their mean, 95 % interval)", score)
table("Wall time", wall)
table("Median reasoning tokens per answer", medreason)
table("Answers cut off (token limit = max_tokens 81,920; loop stop = one token repeated 256 times)", cutcell)

print("\n**Against the same model's xhigh run** (paired by item: difference in points, 95 % interval; verdict)\n")
pairs = [(lb, name, base) for lb, name, base in runs if base and have(base)]
if have("c18t-quick-medium") and have("c18-nvfp4-quick-medium"):
    pairs.append(("c18-nvfp4-quick-medium", "NVFP4 medium vs IQ3_S medium", "c18t-quick-medium"))
print("| category | " + " | ".join(n if "vs" in n else f"{n} vs xhigh" for _, n, _ in pairs) + " |")
print("|---|" + "---|" * len(pairs))
V = {(base, lb): verdict(base, lb) for lb, _, base in pairs}
for cat, name in CATS[:8]:
    print(f"| {name} | " + " | ".join(V[(base, lb)].get(name.lower()[:6], "-") for lb, _, base in pairs) + " |")

rr = [(a, b) for a, b in RERUNS.items() if have(b)]
if rr:
    print("\n**Category reruns (IQ3_S and NVFP4 at medium differed by more than one item): run 1 + rerun, solved items**\n")
    print("| category | IQ3_S medium run 1 | rerun | NVFP4 medium run 1 | rerun |")
    print("|---|---|---|---|---|")
    cats = sorted({c for _, b in rr for c, v in json.load(open(f"{R}/{b}/scores.json"))["categories"].items()
                   if v.get("score") is not None})
    for cat in cats:
        row = []
        for a, b in RERUNS.items():
            for lb in (a, b):
                c = S.get(lb, json.load(open(f"{R}/{lb}/scores.json")) if have(lb) else {}).get("categories", {}).get(cat)
                row.append(f"{c['solved_sum']:.1f} / {c['answers']} ({100 * c['score']:.1f} %)" if c else "-")
        print(f"| {cat} | " + " | ".join(row) + " |")
