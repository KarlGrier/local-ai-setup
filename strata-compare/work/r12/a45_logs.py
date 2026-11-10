#!/usr/bin/env python3
"""a45_logs.py — round 12 A4 / A5 from request TIMINGS already logged (the passive monitors' requests.csv: generation
start to the second, duration, prompt tokens, reused, prompt ms, decode ms; no content, no hashes). Your traffic only:
logs/r7/uptime (09-30 07:00-14:54, 529 requests, mostly Local Deep Research) and logs/r11/uptime-c121-r10end (10-04,
the 11 after Round 10's 3 rollback checks). The server stamps a request's start AFTER its queue wait, so arrival times
are not logged: a request that starts < GAP s after the previous one ended is counted as possibly queued (an upper
bound on queueing; a sequential client also lands there when it answers within the gap).
A4: share of decode time during which a second request may have been waiting (upper bound: the predecessor's decode).
A5: uncached prompt-reading time (prompt_ms covers only the tokens not reused) as a share of total request time."""
import csv
from datetime import datetime
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
SRC = [("r7 09-30", WS / "logs/r7/uptime/requests.csv", 0), ("r11 10-04", WS / "logs/r11/uptime-c121-r10end/requests.csv", 3)]
for GAP in (1.0, 2.0):
    tot = {"n": 0, "dec": 0.0, "pro": 0.0, "dur": 0.0, "q": 0, "qdec": 0.0, "bursts": 0}
    for name, f, skip in SRC:
        rows = list(csv.DictReader(open(f)))[skip:]
        prev_end = None
        for r in rows:
            t = datetime.fromisoformat(r["time"]).timestamp()
            dur = float(r["duration_s"] or 0); dec = float(r["decode_ms"] or 0) / 1000; pro = float(r["prompt_ms"] or 0) / 1000
            tot["n"] += 1; tot["dec"] += dec; tot["pro"] += pro; tot["dur"] += dur
            if prev_end is not None and t - prev_end[0] < GAP:
                tot["q"] += 1; tot["qdec"] += prev_end[1]
            prev_end = (t + dur, dec)
    print(f"GAP {GAP:.0f} s: {tot['n']} requests; time {tot['dur']/3600:.2f} h = prompt {tot['pro']/3600:.2f} h + decode {tot['dec']/3600:.2f} h "
          f"(+ server/other {(tot['dur']-tot['pro']-tot['dec'])/3600:.2f} h)")
    print(f"  A4: requests starting < {GAP:.0f} s after the previous ended: {tot['q']} ({100*tot['q']/tot['n']:.1f} %); "
          f"their predecessors' decode = {100*tot['qdec']/tot['dec']:.1f} % of all decode (upper bound on 'a second request waiting')")
    print(f"  A5: uncached prompt reading = {100*tot['pro']/tot['dur']:.1f} % of total request time (ceiling for shared prefixes)")
