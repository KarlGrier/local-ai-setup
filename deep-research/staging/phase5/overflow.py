#!/usr/bin/env python3
"""overflow.py - context-overflow flags for bench runs (Karl 11-07; a dated results note, not a rule change).

Karl 11-07, on Phase 5's o04 / o06: "count them as they are, flagged beside the grades like search trips: 'context
overflow: cut-off answer' (o04) and 'context overflow: snippet fallback' (o06). Write it into the Phase 5 results as a
dated note, not a rule change. Count overflows per arm in the Phase 5 summary."

How a run is detected, from its research-logs.json (LDR's own log; WARNING / ERROR entries only):
  refused       requests the server refused ("request exceeds the context window: prompt (N tokens) ..."), counted
                once per request: LDR logs one refusal as a WARNING and, from the agent, again as an ERROR
  raw_fallback  "Citation handler failed, using raw agent answer" (the synthesis was refused; LDR kept the agent's text)
  near_window   INFO only: LDR's "Context overflow detected" warnings, which it logs for any prompt above ~80 % of the
                window (o04: 105K-125K tokens), whether or not anything was cut
A run with a refusal or a raw fallback has a context overflow. Its flag text comes from results/bench2/p5-run-flags.json, the dated
note where each overflow's kind is written after it is checked by hand. A run that is not in that note yet is flagged
"context overflow (kind not yet checked)". The proxy's calls.jsonl status-400 count is kept beside it as a cross-check.

Used by staging/phase5/p5.py (REPORT.md "## Runs", p5-results.json) and staging/post7d/tools/relief_counts.py (its flag
column). Reads only; writes nothing.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")
RUNS = WS / "results" / "bench2" / "runs"
FLAGS = WS / "results" / "bench2" / "p5-run-flags.json"
REFUSED = "exceeds the context window"
WINDOW = "Context overflow detected"
RAW = "Citation handler failed, using raw agent answer"
PROMPT_N = re.compile(r"prompt \((\d+) tokens\)")


def run_key(run: Path) -> str:
    return f"{run.parent.name}/{run.name}"


def noted() -> dict:
    try:
        return json.loads(FLAGS.read_text()).get("flags", {})
    except (OSError, ValueError):
        return {}


def overflow(run: Path) -> dict | None:
    """the run's overflow counts, or None when it had none (or has no LDR log)"""
    try:
        logs = json.loads((run / "research-logs.json").read_text(errors="replace"))
    except (OSError, ValueError):
        return None
    items = logs if isinstance(logs, list) else (logs.get("logs") or logs.get("items") or [])
    c = {"refused": 0, "raw_fallback": False, "near_window": 0}
    seen = set()
    for x in items:
        if not isinstance(x, dict) or x.get("log_type") not in ("WARNING", "ERROR"):
            continue
        m = str(x.get("message") or "")
        if REFUSED in m:
            n = PROMPT_N.search(m)
            seen.add(n.group(1) if n else m[:200])
        if WINDOW in m:
            c["near_window"] += 1
        if RAW in m:
            c["raw_fallback"] = True
    c["refused"] = len(seen)
    if not (c["refused"] or c["raw_fallback"]):
        return None
    try:
        c["http_400"] = sum(1 for line in (run / "calls.jsonl").read_text().splitlines()
                            if line.strip() and json.loads(line).get("status") == 400)
    except (OSError, ValueError):
        c["http_400"] = None
    return c


def flags(run: Path, bench: dict | None = None) -> tuple[list[str], dict | None]:
    """(flag texts beside the grade, overflow counts or None): the 11-06 search-trip flag, then the 11-07 overflow flag"""
    if bench is None:
        try:
            bench = json.loads((run / "bench.json").read_text())
        except (OSError, ValueError):
            bench = {}
    out = []
    if bench.get("search_trip"):
        out.append("search trip, end check passed")
    ov = overflow(run)
    note = noted().get(run_key(run))
    if note:
        out.append(note["flag"])
    elif ov:
        out.append("context overflow (kind not yet checked)")
    return out, ov


if __name__ == "__main__":
    import sys
    for a in sys.argv[1:]:
        r = Path(a) if "/" in a and Path(a).is_dir() else RUNS / a
        print(run_key(r), flags(r))
