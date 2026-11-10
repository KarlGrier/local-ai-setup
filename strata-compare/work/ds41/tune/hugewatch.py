#!/usr/bin/env python3
"""hugewatch.py - 10-24 DeepSeek-V4.1 tuning round, the mmapoff screen (the user, 10-25: "a fixed copy of the hottest
experts on huge pages ... to see what huge pages are worth"): waits for that screen's server, then every 30 s records
the engine's AnonHugePages / RssAnon / RssFile (read-only from /proc) and MemAvailable to results/ds41/tuning/
mmapoff-hugepages.tsv; exits when the screen's server is gone, or after 14 h"""
import os
import time

OUT = "/home/USER/ai-speed-testing/strata-compare/results/ds41/tuning/mmapoff-hugepages.tsv"
TAG = b"DS41-tune-mmapoff.json"


def procs():
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                yield p, open(f"/proc/{p}/cmdline", "rb").read().split(b"\0")
            except OSError:
                pass


def kb(path, keys):
    d = {}
    try:
        for l in open(path):
            k = l.split(":")[0]
            if k in keys:
                d[k] = int(l.split()[1])
    except OSError:
        pass
    return d


t0, seen = time.time(), False
while time.time() - t0 < 14 * 3600:
    srv = any(any(TAG in a for a in argv) for _, argv in procs())
    if srv:
        seen = True
        for p, argv in procs():
            if argv and argv[0].endswith(b"/strata-dsv41"):
                sm = kb(f"/proc/{p}/smaps_rollup", ("AnonHugePages", "Anonymous"))
                st = kb(f"/proc/{p}/status", ("RssAnon", "RssFile"))
                mi = kb("/proc/meminfo", ("MemAvailable",))
                new = not os.path.exists(OUT)
                with open(OUT, "a") as f:
                    if new:
                        f.write("time\tanon_huge_gb\tanon_gb\trss_file_gb\tmemavail_gb\n")
                    f.write(f"{time.strftime('%H:%M:%S')}\t{sm.get('AnonHugePages', 0) / 1e6:.2f}\t{sm.get('Anonymous', 0) / 1e6:.2f}\t"
                            f"{st.get('RssFile', 0) / 1e6:.2f}\t{mi.get('MemAvailable', 0) / 1e6:.2f}\n")
    elif seen:
        break
    time.sleep(30)
