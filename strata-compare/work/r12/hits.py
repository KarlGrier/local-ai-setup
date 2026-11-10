#!/usr/bin/env python3
"""hits.py CONFIG_NAME... — round 9 Phase B: the engine's own decode expert-cache hit rate per server process (the
last cumulative "decode expert cache hit rate" line of each process in logs/engine-NAME.log)."""
import re, sys
for n in sys.argv[1:]:
    runs, cur = [], None
    for line in open(f"/home/USER/ai-speed-testing/strata-compare/logs/engine-{n}.log", errors="replace"):
        if line.startswith("strata generate: native pack:"):
            if cur: runs.append(cur)
            cur = None
        m = re.search(r"decode expert cache hit rate: ([\d.]+)% \((\d+) hits / (\d+) lookups\)", line)
        if m: cur = (float(m.group(1)), int(m.group(3)))
    if cur: runs.append(cur)
    print(f"{n}: " + ", ".join(f"{h:.1f} % of {k} lookups" for h, k in runs))
