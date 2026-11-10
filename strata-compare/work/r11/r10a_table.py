#!/usr/bin/env python3
"""r10a_table.py NAME=ENGINE_LOG ... - round 11 C.1: the counting build's per-request "R10A" lines pooled per config:
routed entries and distinct experts by who computed them (the 5080's cache, PCIe, the helper GPU, the CPU pool), as
shares, plus the adaptive tier's swaps."""
import re
import sys

R = re.compile(r"R10A entries gpu0 (\d+) pcie (\d+) helper (\d+) cpu (\d+); distinct gpu0 (\d+) pcie (\d+) helper (\d+) cpu (\d+); "
               r"adapt calls (\d+) swaps (\d+)")
print("| config | requests | entries: 5080 / helper / CPU | distinct experts: 5080 / helper / CPU | swaps |")
print("|---|---|---|---|---|")
for arg in sys.argv[1:]:
    name, path = arg.split("=", 1)
    tot = [0] * 10
    n = 0
    for line in open(path, errors="replace"):
        m = R.search(line)
        if m:
            n += 1
            tot = [a + int(b) for a, b in zip(tot, m.groups())]
    e = sum(tot[0:4]) or 1
    d = sum(tot[4:8]) or 1
    print(f"| {name} | {n} | {100*tot[0]/e:.1f} / {100*tot[2]/e:.1f} / {100*tot[3]/e:.1f} % | "
          f"{100*tot[4]/d:.1f} / {100*tot[6]/d:.1f} / {100*tot[7]/d:.1f} % | {tot[9]} |")
