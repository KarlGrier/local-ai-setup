#!/usr/bin/env python3
"""rerun_pick.py LABEL_A LABEL_B - the scored categories where the two runs differ by more than one item: the sums of
the item scores (partial credit counts) on the items both answered differ by more than 1.0. Prints the categories
comma-separated (empty line if none) and the per-category sums on stderr (2026-10-17, your rerun rule)."""
import collections
import json
import sys

SCORED = ["coding", "agentic", "math", "instruct", "tools", "longctx", "honesty", "research"]


def sums(label):
    g = json.load(open(f"suite/results/{label}/grades.json"))
    out = collections.defaultdict(dict)
    for k, v in g.items():
        if isinstance(v, dict) and v.get("score") is not None:
            out[v["category"]][k] = float(v["score"])
    return out


a, b = sums(sys.argv[1]), sums(sys.argv[2])
pick = []
for cat in SCORED:
    keys = set(a.get(cat, {})) & set(b.get(cat, {}))
    sa = sum(a[cat][k] for k in keys) if keys else 0.0
    sb = sum(b[cat][k] for k in keys) if keys else 0.0
    flag = abs(sa - sb) > 1.0
    print(f"{cat:9s} items {len(keys):3d}  {sys.argv[1]} {sa:6.2f}  {sys.argv[2]} {sb:6.2f}  diff {sb - sa:+6.2f}"
          f"{'  -> rerun' if flag else ''}", file=sys.stderr)
    if flag:
        pick.append(cat)
print(",".join(pick))
