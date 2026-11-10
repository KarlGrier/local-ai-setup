#!/usr/bin/env python3
"""bl_verdict.py ARM_DIR - 11-04: a long-prompt memory arm's verdict (report.py's BL rule, for gate.sh's store ladder):
PASS = L64 and L97 both answered (tokens generated, no error), no GUARD / SOFTSTOP file (tunearm.sh: 12 GB hard, 14 GB
soft, the swap rule), and the arm's lowest MemAvailable (monitor.tsv's 2 s samples and the client's 0.5 s per-request
lows) >= 14 GB with the daily services up. Prints one JSON line; exit 0 PASS, 1 FAIL, 2 no results."""
import json
import os
import sys


def main():
    d = os.path.realpath(sys.argv[1])
    try:
        lj = json.load(open(f"{d}/long.json"))
    except (OSError, ValueError):
        print(json.dumps({"dir": d, "pass": False, "why": "no long.json"})); return 2
    lows = [p["memavail_low_gb"] for p in lj if p.get("memavail_low_gb") is not None]
    try:
        a = json.load(open(f"{d}/arm.json"))
        if a.get("lowest_memavail_gb") is not None:
            lows.append(a["lowest_memavail_gb"])
    except (OSError, ValueError):
        pass
    done = {p["id"] for p in lj if not p.get("error") and p.get("completion_tokens")}
    stops = [k for k in ("GUARD", "SOFTSTOP") if os.path.exists(f"{d}/{k}")]
    low = min(lows) if lows else None
    ok = done >= {"L64", "L97"} and not stops and low is not None and low >= 14.0
    print(json.dumps({"dir": d, "pass": ok, "lowest_gb": low, "answered": sorted(done), "stops": stops,
                      "lines": {str(t): low is not None and low >= t for t in (14, 13, 12)},
                      "per_prompt": {p["id"]: [p.get("memavail_before_gb"), p.get("memavail_low_gb")] for p in lj}}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
