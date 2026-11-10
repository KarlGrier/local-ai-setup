#!/usr/bin/env python3
"""cc_table.py LABEL... — round 9 B4: chatsoak "many" back-to-a-chat times per run (r1 = oldest first, r2 = shuffled):
median / mean / max TTFT and how many of the 16 came back from the chat cache; the guard's min MemAvailable and peak RSS."""
import re, statistics as st, sys
L = open("/home/USER/ai-speed-testing/strata-compare/logs/r11/batch.log").read()
print("| run | back r1: median / mean / max TTFT (s), from cache | back r2 | min MemAvailable / peak RSS |")
print("|---|---|---|---|")
for lab in sys.argv[1:]:
    blk = re.search(rf"RUN: work/r11/with_server.sh {re.escape(lab)} .*?END \(\d+\): work/r11/with_server.sh {re.escape(lab)} ", L, re.S)
    if not blk: print(f"| {lab} | missing | | |"); continue
    b = blk.group(0); cells = []
    for r in ("r1", "r2"):
        rows = re.findall(rf"many_back\s+M\d+\s+\d+K {r}\s+prompt\s+(\d+) reused\s+(\d+) ttft\s+([\d.]+)s", b)
        t = [float(x[2]) for x in rows]; hit = sum(1 for x in rows if int(x[1]) > 0)
        cells.append(f"{st.median(t):.2f} / {st.mean(t):.2f} / {max(t):.2f}, {hit}/{len(rows)}" if t else "–")
    g = re.search(r"min_MemAvailable=([\d.]+)GiB.*?max_tree_RSS=([\d.]+)GiB", b)
    print(f"| {lab} | {cells[0]} | {cells[1]} | {g.group(1) if g else '?'} GiB / {g.group(2) if g else '?'} GB |")
