#!/usr/bin/env python3
"""p1_pre_table.py - round 18 part 1 pre-screen table: per state and item, C*14 vs C*16 ms per verify round (two arms each),
outputs, and the gap; then each switch's own effect per build (state vs on)."""
import sys
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/bringup/lib")
from p0_table import parse as _parse
import re
from pathlib import Path


def parse(label):
    d = _parse(label)
    t = (Path("/home/USER/ai-speed-testing/strata-compare/bringup/out/logs/prof") / f"{label}.out").read_text(errors="replace")
    m = re.search(r"wait for rings ([\d.]+)\s+pool ([\d.]+)", t)
    d["rings"], d["poolw"] = (float(m[1]), float(m[2])) if m else (None, None)
    return d
P = sys.argv[1] if len(sys.argv) > 1 else "r18-pre"
ST = [("on", "as served"), ("il0", "STRATA_MMVQ_IL=0 (B.3 / F4 off)"), ("sm0", "STRATA_SIDE_MIXER=0")]
m = {}
print(f"# {P}: C*14 vs C*16, CLI fixed computation, greedy 1,024 tokens, A B B A per state\n")
print("| state | item | C*14 arms ms/round | C*16 arms ms/round | C*14 mean | C*16 mean | C*16 vs C*14 | outputs |")
print("|---|---|---|---|---|---|---|---|")
for st, name in ST:
    for it in ("math", "code"):
        r = {b: [parse(f"{P}-{st}-{b}-{s}-{it}") for s in "ab"] for b in ("c14", "c16")}
        mm = {b: sum(d["ms_round"] for d in r[b]) / 2 for b in r}
        m[(st, it)] = mm
        outs = {d["out"] for b in r for d in r[b]}
        print(f"| {name} | {it} | {' / '.join(f'{d['ms_round']:.2f}' for d in r['c14'])} | "
              f"{' / '.join(f'{d['ms_round']:.2f}' for d in r['c16'])} | {mm['c14']:.2f} | {mm['c16']:.2f} | "
              f"{100 * (mm['c16'] / mm['c14'] - 1):+.1f} % | {'identical' if len(outs) == 1 else ', '.join(sorted(outs))} |")
print("\n| state | item | GPU wait (wait for rings) C*14 mean | C*16 mean | difference | CPU pool C*14 / C*16 |\n|---|---|---|---|---|---|")
for st, name in ST:
    for it in ("math", "code"):
        r = {b: [parse(f"{P}-{st}-{b}-{s}-{it}") for s in "ab"] for b in ("c14", "c16")}
        w = {b: sum(d["rings"] for d in r[b]) / 2 for b in r}; pw = {b: sum(d["poolw"] for d in r[b]) / 2 for b in r}
        print(f"| {name} | {it} | {w['c14']:.2f} | {w['c16']:.2f} | {w['c16'] - w['c14']:+.2f} ms | {pw['c14']:.2f} / {pw['c16']:.2f} |")
print("\n| switch | item | effect on C*14 (ms/round, % vs on) | effect on C*16 |\n|---|---|---|---|")
for st, name in ST[1:]:
    for it in ("math", "code"):
        a, o = m[(st, it)], m[("on", it)]
        print(f"| {name} | {it} | {a['c14'] - o['c14']:+.2f} ({100 * (a['c14'] / o['c14'] - 1):+.1f} %) | "
              f"{a['c16'] - o['c16']:+.2f} ({100 * (a['c16'] / o['c16'] - 1):+.1f} %) |")
