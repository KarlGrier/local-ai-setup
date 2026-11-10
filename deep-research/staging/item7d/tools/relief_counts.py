#!/usr/bin/env python3
"""relief_counts.py - 8080 memory-relief restarts during each bench question (Karl 11-01: record each question's count
beside its grade; flag a pair where one side had many more).

  relief_counts.py LABEL [LABEL ...]        e.g.  relief_counts.py p4s8 p7b
      -> one row per question of results/bench2/runs/{screen,hard-screen,shop-7e}-deep-<LABEL>/<qid>/bench.json

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

WS = Path("/home/USER/ai/deep-research")
RUNS = WS / "results" / "bench2" / "runs"
TZ = ZoneInfo("America/Chicago")
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
    print(f"{'label':6} {'question':9} {'start':16} {'wall min':>8} {'held min':>8} {'restarts':>8}")
    for label in sys.argv[1:]:
        for folder in (f"screen-deep-{label}", f"hard-screen-deep-{label}", f"shop-7e-deep-{label}"):   # 11-03: + 7e/7d s1-s4
            for b in sorted((RUNS / folder).glob("*/bench.json")):
                d = json.loads(b.read_text())
                end = ended(d["ended"])
                start = end - float(d["wall_s"])
                n = sum(start <= t <= end for t in rs)
                st = datetime.fromtimestamp(start, TZ).strftime("%m-%d %H:%M %Z")
                print(f"{label:6} {d['id']:9} {st:16} {d['wall_s'] / 60:8.0f} {d.get('held_s', 0) / 60:8.1f} {n:8}")


if __name__ == "__main__":
    main()
