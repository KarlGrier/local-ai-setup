#!/usr/bin/env python3
"""summarize.py [TAG...] - the harness comparison table from results/usability-runs/*/result.json (markdown)."""
import json
import sys
from pathlib import Path

RUNS = Path("/home/USER/ai-speed-testing/strata-compare/results/usability-runs")  # copied from tmp/usability/runs (deleted 10-16)
ARMS = ["opencode", "codex", "dsh-minimal", "dsh-standard", "dsh-ptc"]
TASKS = ["a1_inventory", "a2_textstats", "a3_cronlite", "rt_effort"]
tags = sys.argv[1:] or ["r1"]

rows = []
for f in sorted(RUNS.glob("*/result.json")):
    r = json.loads(f.read_text())
    tag = r["label"].rsplit("-", 1)[1]
    if tag not in tags:
        continue
    rows.append(r)
rows.sort(key=lambda r: (TASKS.index(r["task"]), ARMS.index(r["arm"]), r["label"]))

print("| task | harness | run | green | steps | output tok | wall s | prompt tok re-read (total / median per turn / max) |"
      " model s | largest prompt | tool calls | unparsed calls | bad args | early ends | side requests |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for r in rows:
    m, g = r["metrics"], r["grade"]
    green = "yes" if g["green"] else ("visible only" if g.get("visible_green") else "no")
    if r["task"] == "rt_effort" and not g["green"]:
        green = f"no (hidden {'ok' if g.get('hidden_green') else 'fail'}, suite {'ok' if g.get('suite_green') else 'fail'})"
    print(f"| {r['task']} | {r['arm']} | {r['label'].rsplit('-', 1)[1]} | {green} | {m['steps']} | {m['output_tokens']:,} |"
          f" {r['wall_s']:.0f} | {m['reread_tokens']:,} / {m['reread_per_turn_median']:,} / {m['reread_per_turn_max']:,} |"
          f" {m['model_wall_s']:.0f} | {m['max_prompt']:,} | {m['tool_calls']} | {m['unparsed_calls']} | {m['bad_tool_args']} | {m['early_ends']} |"
          f" {m['title_requests']} |")

print()
print("Totals per harness (all tasks in these tags):")
for arm in ARMS:
    rs = [r for r in rows if r["arm"] == arm]
    if not rs:
        continue
    s = lambda k: sum(r["metrics"][k] for r in rs)
    print(f"- {arm}: green {sum(r['grade']['green'] for r in rs)}/{len(rs)}, steps {s('steps')}, output tokens "
          f"{s('output_tokens'):,}, wall {sum(r['wall_s'] for r in rs):.0f} s (model {s('model_wall_s'):.0f} s), re-read {s('reread_tokens'):,}, unparsed "
          f"{s('unparsed_calls')}, bad args {s('bad_tool_args')}, early ends {s('early_ends')}")
