#!/usr/bin/env python3
"""desk_load.py T0 T1 — round 11: from logs/r13/gpu1-pmon.log (work/r13/gpu1mon.sh, nvidia-smi pmon every 2 s), the RTX
4060 Ti's mean SM % by graphics processes (your desktop: Xorg, gnome-shell, Chrome, ...) and by compute (the engine's
helper) between two times (epoch seconds or ISO).  Importable: load(t0, t1), label_load(runs.jsonl records)."""
import sys
from datetime import datetime
from pathlib import Path

LOG = Path("/home/USER/ai-speed-testing/strata-compare/logs/r13/gpu1-pmon.log")


def ts(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return datetime.fromisoformat(x).timestamp()


def load(t0, t1):
    """-> (desktop graphics SM %, engine compute SM %, samples) on the RTX 4060 Ti between two epoch times."""
    g, c, samples = 0.0, 0.0, set()
    for line in LOG.read_text().split("\n"):
        p = line.split()
        if len(p) < 6 or p[1].startswith("#"):
            continue
        t = float(p[0])
        if not t0 <= t <= t1:
            continue
        samples.add(round(t))
        sm = 0.0 if p[4] == "-" else float(p[4])
        if p[3] == "G":
            g += sm
        elif p[3] == "C":
            c += sm
    n = max(1, len(samples))
    return g / n, c / n, len(samples)


def label_load(runs):
    """the desktop's graphics SM % over the time span of a label's runs (results/runs.jsonl records), or None"""
    if not runs:
        return None
    t0 = min(ts(r["started"]) for r in runs)
    t1 = max(ts(r["started"]) + (r.get("t_total_s") or 0) for r in runs)
    g, _, n = load(t0, t1)
    return g if n else None


if __name__ == "__main__":
    a, b = ts(sys.argv[1]), ts(sys.argv[2])
    g, c, n = load(a, b)
    print(f"4060 Ti {datetime.fromtimestamp(a):%H:%M:%S}-{datetime.fromtimestamp(b):%H:%M:%S}: desktop (graphics) SM "
          f"{g:.1f} %, engine (compute) SM {c:.1f} %, {n} samples")
