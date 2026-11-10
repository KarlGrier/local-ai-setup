#!/usr/bin/env python3
"""relief_counts.py - 8080 memory-relief restarts during each bench question (Karl 11-01: record each question's count
beside its grade; flag a pair where one side had many more).

  relief_counts.py LABEL [LABEL ...]        e.g.  relief_counts.py p4s9 pc3c   or   p5 p5final
      -> one row per question of results/bench2/runs/<set>-deep-<LABEL>/ and <set>-baseline-<LABEL>/<qid>/bench.json
      (11-05 staging/post7d copy: every set, so Phase 5's holdout folders too; the item7d copy reads three sets)

A question's window is bench.json's "ended" minus "wall_s". A restart is a research-runner.log line "restart_strata
(freeing memory ..." (the runner's relief restart while a run holds the GPU). The runner log is in naive local time, so
the hour repeated at a clock change is resolved by the log's own order (each line is taken at the earliest reading not
before the line above it); "ended" is read with its UTC offset when it has one (bench2.py since 10-31), else as local
time (older runs ended before 11-01's change).
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import importlib.util

WS = Path("/home/USER/ai/deep-research")
RUNS = WS / "results" / "bench2" / "runs"
TZ = ZoneInfo("America/Chicago")
# 11-07 (Karl): context-overflow flags beside search trips (staging/phase5/overflow.py, results/bench2/p5-run-flags.json)
_spec = importlib.util.spec_from_file_location("overflow_rc", WS / "staging" / "phase5" / "overflow.py")
OV = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(OV)
LINE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d) restart_strata \(freeing memory")


def restarts() -> list[float]:
    out, last = [], 0.0
    for line in (WS / "logs" / "research-runner.log").read_text(errors="replace").splitlines():
        m = LINE.match(line)
        if not m:
            continue
        naive = datetime.fromisoformat(m.group(1))
        cands = sorted({naive.replace(tzinfo=TZ, fold=f).timestamp() for f in (0, 1)})
        t = next((c for c in cands if c >= last - 1), cands[-1])
        out.append(t)
        last = t
    return out


def ended(s: str) -> float:
    d = datetime.fromisoformat(s)
    return (d if d.tzinfo else d.replace(tzinfo=TZ)).timestamp()


def main() -> None:
    rs = restarts()
    print(f"{'label':6} {'question':9} {'start':16} {'wall min':>8} {'held min':>8} {'restarts':>8}  flag")
    for label in sys.argv[1:]:
        # 11-05 (staging/post7d): every set's deep and baseline folders of the label - Phase 5's holdout, hard-holdout,
        # p5-harder, p5-o01 (<set>-baseline-p5, <set>-deep-p5final) besides screen / hard-screen / shop-7e
        folders = sorted(p.name for p in RUNS.iterdir() if p.is_dir()
                         and (p.name.endswith(f"-deep-{label}") or p.name.endswith(f"-baseline-{label}")))
        for folder in folders:
            for b in sorted((RUNS / folder).glob("*/bench.json")):
                d = json.loads(b.read_text())
                end = ended(d["ended"])
                start = end - float(d["wall_s"])
                n = sum(start <= t <= end for t in rs)
                st = datetime.fromtimestamp(start, TZ).strftime("%m-%d %H:%M %Z")
                fl = OV.flags(b.parent, d)[0]    # 11-06 search trip, 11-07 context overflow (Karl)
                flag = ("flagged: " + "; ".join(fl)) if fl else ""
                print(f"{label:6} {d['id']:9} {st:16} {d['wall_s'] / 60:8.0f} {d.get('held_s', 0) / 60:8.1f} {n:8}  {flag}")


if __name__ == "__main__":
    main()
