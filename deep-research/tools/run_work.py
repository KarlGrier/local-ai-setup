#!/usr/bin/env python3
"""run_work.py - the work a bench2 run did, in build-independent units (2026-10-19, the user's rule for phase 4).

Phase 4 runs on a new Strata build (the 0.2.0 port + the chat-cache change), so its minutes are not compared with
phase 3's. Across the switch, runs are compared by calls and tokens; minutes only between runs on the same build.

Per run (results/bench2/runs/<set>-<profile>-<level>/<id>/bench.json): the proxy's calls (logs/llm-calls.jsonl) inside
the run's window [ended - wall_s, ended] - calls per class, prompt tokens, of them read fresh (not reused from a cached
prefix), generated tokens, Strata busy time - and the agent's searches and page fetches (the run's capture).

  run_work.py [RUN_DIR ...]      (default: every run with a bench.json)   -> a table; --json for one JSON line per run
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")
RUNS = WS / "results" / "bench2" / "runs"
CALLS = WS / "logs" / "llm-calls.jsonl"


def load_calls() -> list[dict]:
    out = []
    with open(CALLS, encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def work(run: Path, calls: list[dict]) -> dict:
    b = json.loads((run / "bench.json").read_text())
    end = datetime.fromisoformat(b["ended"]).timestamp()
    start = end - float(b["wall_s"])
    mine = [c for c in calls if start <= float(c.get("t0") or 0) <= end and c.get("path") == "/v1/chat/completions"]
    u = [c.get("usage") or {} for c in mine]
    prompt = sum(x.get("prompt_tokens") or 0 for x in u)
    cached = sum((x.get("prompt_tokens_details") or {}).get("cached_tokens") or 0 for x in u)
    tools = Counter()
    cap = run / "capture" / "calls.jsonl"
    if cap.exists():
        for line in open(cap, encoding="utf-8"):
            try:
                c = json.loads(line)
            except ValueError:
                continue
            for t in c.get("tool_calls") or []:
                tools[((t.get("function") or {}).get("name")) or t.get("name") or "?"] += 1
    return {"run": f"{run.parent.name}/{run.name}", "wall_min": round(float(b["wall_s"]) / 60, 1),
            "calls": len(mine), "by_class": dict(Counter(c.get("cls") for c in mine)),
            "prompt_tok": prompt, "fresh_tok": prompt - cached,
            "gen_tok": sum(x.get("completion_tokens") or 0 for x in u),
            "strata_busy_min": round(sum(float(c.get("duration_s") or 0) for c in mine) / 60, 1),
            "searches": tools.get("web_search", 0), "fetches": tools.get("fetch_content", 0)}


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--json"]
    runs = [Path(a) for a in args] or sorted(p.parent for p in RUNS.glob("*/*/bench.json"))
    calls = load_calls()
    rows = [work(r, calls) for r in runs if (r / "bench.json").exists()]
    if "--json" in sys.argv:
        for r in rows:
            print(json.dumps(r))
        return
    print(f"{'run':38s} {'wall':>6s} {'calls':>5s} {'prompt':>10s} {'fresh':>10s} {'gen':>8s} {'busy':>6s} {'srch':>5s} {'fetch':>5s}")
    for r in rows:
        print(f"{r['run']:38s} {r['wall_min']:6.1f} {r['calls']:5d} {r['prompt_tok']:10,d} {r['fresh_tok']:10,d} "
              f"{r['gen_tok']:8,d} {r['strata_busy_min']:6.1f} {r['searches']:5d} {r['fetches']:5d}")


if __name__ == "__main__":
    main()
