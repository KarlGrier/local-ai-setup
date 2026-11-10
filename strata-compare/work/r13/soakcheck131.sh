#!/bin/bash
# soakcheck131.sh — round 13 Part 2.5: the C*13.1 soak's own summary (logs/r13/batch.log) and the soaked decode screen;
# all good -> tmp/r13/go-promote131 (the queue's hold before promote-c131.sh releases by itself).
# Good = 0 request errors, health loaded, MemAvailable min >= 20 GB, no RSS growth per 30-minute block beyond 1.5 GB,
# soaked decode within 2 % of the fresh screen (ab-soaked-vs-fresh.md).
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
.venv/bin/python - <<'PY'
import re
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
log = (WS / "logs/r13/batch.log").read_text(errors="replace")
i = log.rfind("RUN: STRATA_CONFIG=configs/Cstar131.json work/r13/soak13.sh 120")
blk = log[i:log.find("### ", log.find("\n", i) + 1)] if i >= 0 else ""
g = []
m = re.search(r"request errors (\d+), health (\{.*?\})", blk)
g.append(("0 request errors, health loaded", bool(m) and m.group(1) == "0" and '"loaded": true' in m.group(2)))
m = re.search(r"(\d+) requests, ", blk); n = int(m.group(1)) if m else 0
m2 = re.search(r"errors: (\d+) \| Stop pressed: (\d+)", blk)
g.append((f"{n} requests, errors {m2.group(1) if m2 else '?'}", n >= 200 and bool(m2) and m2.group(1) == "0"))
m = re.search(r"MemAvailable min ([\d.]+) GB", blk)
g.append((f"MemAvailable min {m.group(1) if m else '?'} GB >= 20", bool(m) and float(m.group(1)) >= 20.0))
rss = [float(x) for x in re.findall(r"min - *\d+ min: MemAvailable min [\d.]+ GB, RSS max ([\d.]+) GB", blk)] or \
      [float(x) for x in re.findall(r"RSS max ([\d.]+) GB", blk)]
g.append((f"RSS per block {rss}", len(rss) >= 3 and max(rss[1:]) - rss[1] <= 1.5))
ab = (WS / "results/r13/ab-soaked-vs-fresh.md")
d = None
if ab.exists():
    for l in ab.read_text().splitlines():
        if l.startswith("| decode (tok/s)"):
            mm = re.search(r"\| ([+-][\d.]+) % \|\s*$", l); d = float(mm.group(1)) if mm else None
g.append((f"soaked decode vs fresh {d} %", d is not None and d >= -2.0))
for name, ok in g:
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
if all(ok for _, ok in g):
    (WS / "tmp/r13/go-promote131").touch(); print("SOAK: ALL PASS -> releasing the promotion hold")
else:
    print("SOAK: NOT ALL PASS -> the promotion waits (hold promote131)")
PY
