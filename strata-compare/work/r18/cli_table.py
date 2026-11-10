#!/usr/bin/env python3
"""cli_table.py PREFIX arm=name ... - round 18: CLI A/B (labels PREFIX-arm-{a,b}-{math,code}): per item each arm's ms per
round (a / b), the GPU wait (wait for rings) and the CPU pool per round, outputs; vs the first arm."""
import re, sys
from pathlib import Path
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/bringup/lib")
from p0_table import parse as _parse
P = Path("/home/USER/ai-speed-testing/strata-compare/bringup/out/logs/prof")
def parse(l):
    d = _parse(l); t = (P / f"{l}.out").read_text(errors="replace")
    m = re.search(r"wait for rings ([\d.]+)\s+pool ([\d.]+)", t)
    d["rings"], d["poolw"] = (float(m[1]), float(m[2])) if m else (None, None)
    return d
pre = sys.argv[1]; arms = [a.split("=", 1) for a in sys.argv[2:]]
print(f"# {pre}: CLI fixed computation, greedy 1,024 tokens\n")
print("| arm | item | ms/round a / b | GPU wait a / b | GPU wait mean | vs first (ms) | CPU pool a / b | outputs |")
print("|---|---|---|---|---|---|---|---|")
for it in ("math", "code"):
    w0 = None
    for k, name in arms:
        r = [parse(f"{pre}-{k}-{s}-{it}") for s in "ab"]
        w = sum(d["rings"] for d in r) / 2
        if w0 is None: w0 = w
        print(f"| {name} | {it} | {r[0]['ms_round']:.2f} / {r[1]['ms_round']:.2f} | {r[0]['rings']:.3f} / {r[1]['rings']:.3f} | {w:.3f} | "
              f"{w - w0:+.3f} | {r[0]['poolw']:.1f} / {r[1]['poolw']:.1f} | {', '.join(sorted({d['out'] for d in r}))} |")
