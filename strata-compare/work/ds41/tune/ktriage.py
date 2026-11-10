#!/usr/bin/env python3
"""ktriage.py SINCE [RUNDIR] - 10-25 (the user's rule change after the mmapoff screen): sort the kernel log since SINCE
("YYYY-mm-dd HH:MM:SS") into clean / alloc / stop. Prints one JSON line; exit 0 clean, 10 alloc, 20 stop.
  alloc  every error line (kwatch.sh's patterns, plus panic) is a "page allocation failure" warning - no machine check,
         GPU Xid, oops / panic or hardware error - no oops / machine-check / bad-page / lockup / warning taint bit, and
         memory was under pressure: the warning's own dump shows the Normal zone at or below its low watermark, or the
         run's monitor (RUNDIR) shows MemAvailable under 20 GB or swap growth. The driver then drops the run and goes on.
  stop   anything else: stop everything and wait for the user.
"""
import json
import re
import subprocess
import sys

PAT = re.compile(r"Oops|BUG:|kernel BUG|Machine check|mce: |\[Hardware Error\]|EDAC .*(error|CE|UE)|Bad page|Bad rss|"
                 r"general protection|soft lockup|hung_task|blocked for more than|Out of memory|oom-kill|oom_reaper|"
                 r"NVRM: Xid|segfault|WARNING: CPU|watchdog: |page allocation failure|I/O error|nvme.*(timeout|reset)|"
                 r"Kernel panic", re.I)   # kwatch.sh's PAT + panic
ZONE = re.compile(r"Node \d+ Normal free:(\d+)kB boost:\d+kB min:(\d+)kB low:(\d+)kB")
TAINT_BAD = 128 | 16 | 32 | 16384 | 512   # kcheck.sh's bits: oops, machine check, bad page, soft lockup, warning


def run_pressure(d):
    """the run's own monitor: lowest MemAvailable and swap growth (tunearm.sh's monitor.tsv / swap.tsv)"""
    out = {}
    try:
        xs = [float(l.split()[1]) for l in open(f"{d}/monitor.tsv").read().splitlines()[1:] if len(l.split()) > 1]
        out["lowest_memavail_gb"] = min(xs) if xs else None
    except (OSError, ValueError):
        pass
    try:
        s0 = int(open(f"{d}/swap-start-mb").read())
        sw = [int(l.split()[1]) for l in open(f"{d}/swap.tsv").read().splitlines() if len(l.split()) > 1]
        out["swap_growth_mb"] = max(sw) - s0 if sw else 0
    except (OSError, ValueError):
        pass
    return out


def main():
    since, d = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "")
    log = subprocess.run(["journalctl", "-k", "--since", since, "--no-pager", "-o", "short-iso"],
                         capture_output=True, text=True).stdout.splitlines()
    hits = [l for l in log if PAT.search(l)]
    taint = int(open("/proc/sys/kernel/tainted").read()) & TAINT_BAD
    res = {"since": since, "lines": [l[:300] for l in hits[:20]], "n": len(hits), "taint_bad_bits": taint}
    if not hits and not taint:
        res["verdict"] = "clean"
    else:
        other = [l for l in hits if "page allocation failure" not in l]
        zones = [tuple(map(int, m.groups())) for m in map(ZONE.search, log) if m]
        rp = run_pressure(d) if d else {}
        pressure = (any(f <= low for f, _, low in zones)
                    or (rp.get("lowest_memavail_gb") is not None and rp["lowest_memavail_gb"] < 20)
                    or (rp.get("swap_growth_mb") or 0) > 0)
        res.update({"zones_free_min_low_kb": zones[:4], "run": rp, "pressure": pressure, "other": [l[:300] for l in other[:10]]})
        if hits and not other and not taint and pressure:
            res["verdict"] = "alloc"
            res["why"] = (f"{len(hits)} page allocation failure warning(s) under memory pressure, nothing else "
                          "(no machine check, GPU Xid, oops / panic or hardware error)")
        else:
            res["verdict"] = "stop"
            res["why"] = ("other kernel errors" if other else "taint bits set" if taint else
                          "page allocation failure without memory pressure" if hits else "?")
    print(json.dumps(res))
    return {"clean": 0, "alloc": 10}.get(res["verdict"], 20)


if __name__ == "__main__":
    sys.exit(main())
