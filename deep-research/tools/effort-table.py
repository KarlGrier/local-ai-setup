#!/usr/bin/env python3
"""effort-table.py LABEL=RUN_DIR [LABEL=RUN_DIR ...] [--score LABEL=TEXT ...] - Karl 10-27: in the bundle's combined
rerun, research minutes and code-tool calls sit next to the answer-key score, so the effect of less research time can be
told apart from the fixes themselves. One Markdown row per run, from its summary.json (deep.elapsed_s,
deep.report_seconds) and deep/code-tool.jsonl (one line per code-tool operation: grep = code_search, read = code_read,
tree = code_tree, api / commits / history = the GitHub tools; clone / pin / pins / files are bookkeeping, not counted).
Only the research phase's calls count: 10-28, the version check (Fix 1) greps the same clone during the report stage and
its greps land in the same log (66 of the six-fix run's 327), so a call counts only up to the log's first line + elapsed
- report seconds; the checks' calls are shown apart.
The scores come from the blind grading (--score), never from this script."""
import collections
import json
import sys
from pathlib import Path

KINDS = {"grep": "search", "read": "read", "tree": "tree", "api": "github", "commits": "github", "history": "github"}


def row(label: str, run: Path, score: str) -> str:
    s = json.loads((run / "summary.json").read_text())
    d = s.get("deep") or {}
    elapsed = d.get("elapsed_s") or s.get("wall_s") or 0.0
    report = d.get("report_seconds") or 0.0
    c, late = collections.Counter(), 0
    f = run / "deep" / "code-tool.jsonl"
    if f.exists():
        t0 = None
        for line in f.open():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            t0 = r.get("t") if t0 is None else t0
            k = KINDS.get(r.get("tool"))
            if not k:
                continue
            if t0 is not None and r.get("t", 0) > t0 + elapsed - report:
                late += 1                                       # the report stage's checks
            else:
                c[k] += 1
    n = sum(c.values())
    rmin = (elapsed - report) / 60
    return (f"| {label} | {rmin:.0f} | {report / 60:.0f} | {n} ({c['search']} / {c['read']} / {c['tree']} / {c['github']}) | "
            f"{n / rmin if rmin > 0 else 0:.2f} | {late} | {score} |")


def main():
    runs, scores = [], {}
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--score":
            k, v = args[i + 1].split("=", 1)
            scores[k] = v
            i += 2
            continue
        k, v = args[i].split("=", 1)
        runs.append((k, Path(v)))
        i += 1
    print("| run | research min | report min | research code-tool calls (search / read / tree / GitHub) | calls per research "
          "min | checks' code-tool calls | answer key (blind) |")
    print("|---|---|---|---|---|---|---|")
    for k, p in runs:
        print(row(k, p, scores.get(k, "(not graded yet)")))


if __name__ == "__main__":
    main()
