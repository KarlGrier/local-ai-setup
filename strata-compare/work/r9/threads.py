#!/usr/bin/env python3
"""threads.py PID LABEL [--interval S] [--duration S] — round 9 A.3: every thread of the engine process, sampled from
/proc/PID/task/*: name (comm), allowed CPUs (Cpus_allowed_list), and CPU time used between samples (utime + stime).
Writes logs/r9/threads-LABEL.csv (one row per thread per sample) and prints a summary per thread-name group:
threads, allowed-CPU sets, CPU seconds used in the window, and which ones are pinned to ONE core.
Read-only: nothing is sent to the process."""
import argparse
import collections
import csv
import os
import time
from pathlib import Path

TICK = os.sysconf("SC_CLK_TCK")
WS = Path("/home/USER/ai-speed-testing/strata-compare")


def snap(pid):
    out = {}
    for tid in os.listdir(f"/proc/{pid}/task"):
        try:
            comm = open(f"/proc/{pid}/task/{tid}/comm").read().strip()
            st = open(f"/proc/{pid}/task/{tid}/stat").read().rsplit(")", 1)[1].split()
            cpus = next(l.split(":", 1)[1].strip() for l in open(f"/proc/{pid}/task/{tid}/status")
                        if l.startswith("Cpus_allowed_list"))
            out[int(tid)] = (comm, cpus, (int(st[11]) + int(st[12])) / TICK, int(st[36]))   # last CPU it ran on
        except (OSError, StopIteration, IndexError):
            pass
    return out


def ncpus(lst):
    n = 0
    for part in lst.split(","):
        a, _, b = part.partition("-")
        n += (int(b) - int(a) + 1) if b else 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pid", type=int)
    ap.add_argument("label")
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--duration", type=float, default=30.0)
    a = ap.parse_args()
    f = open(WS / f"logs/r9/threads-{a.label}.csv", "w", newline="")
    w = csv.writer(f)
    w.writerow(["t", "tid", "comm", "cpus_allowed", "cpu_s_total", "last_cpu"])
    first = snap(a.pid)
    t0 = time.time()
    last = first
    while time.time() - t0 < a.duration:
        time.sleep(a.interval)
        try:
            last = snap(a.pid)
        except FileNotFoundError:
            break
        for tid, (comm, cpus, cs, lc) in last.items():
            w.writerow([round(time.time() - t0, 2), tid, comm, cpus, cs, lc])
    f.close()
    groups = collections.defaultdict(lambda: {"n": 0, "cpus": collections.Counter(), "used": 0.0, "single": 0})
    for tid, (comm, cpus, cs, lc) in last.items():
        key = comm.rstrip("0123456789-_ ") or comm
        g = groups[key]
        g["n"] += 1
        g["cpus"][cpus] += 1
        g["used"] += cs - first.get(tid, (comm, cpus, cs, lc))[2]
        g["single"] += ncpus(cpus) == 1
    print(f"threads of pid {a.pid} ({a.label}), {len(last)} threads, CPU seconds used over {a.duration:.0f} s:")
    for k, g in sorted(groups.items(), key=lambda kv: -kv[1]["used"]):
        print(f"  {k:24s} x{g['n']:3d}  cpu {g['used']:7.2f} s  single-core {g['single']:3d}  allowed: "
              + "; ".join(f"{c} (x{n})" for c, n in g["cpus"].most_common(6)))


if __name__ == "__main__":
    main()
