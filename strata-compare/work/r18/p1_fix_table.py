#!/usr/bin/env python3
"""p1_fix_table.py - round 18 part 1: the r18 build's switches (off / side / quant / both) and C*14, CLI fixed computation:
per item each arm's ms per round, the GPU wait (wait for rings), the CPU pool, outputs; means and change vs off."""
import re
import sys
from pathlib import Path
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/bringup/lib")
from p0_table import parse as _parse
P = Path("/home/USER/ai-speed-testing/strata-compare/bringup/out/logs/prof")
def parse(l):
    d = _parse(l); t = (P / f"{l}.out").read_text(errors="replace")
    m = re.search(r"wait for rings ([\d.]+)\s+pool ([\d.]+)", t)
    d["rings"], d["poolw"] = (float(m[1]), float(m[2])) if m else (None, None)
    return d
pre = sys.argv[1] if len(sys.argv) > 1 else "r18-fix"
ST = [("off", "r18 build, switches off (= C*16)"), ("side", "STRATA_SIDE_IL=1"), ("quant", "STRATA_QUANT_IL=1"), ("sq", "SIDE_IL + SIDE_QKV_FIRST"),
      ("both", "both"), ("c14", "C*14 (reference)")]
print(f"# {pre}: CLI fixed computation, greedy 1,024 tokens, A B B A\n")
print("| arm | item | ms/round a / b | mean | vs off | GPU wait mean | vs off (ms) | CPU pool mean | outputs |")
print("|---|---|---|---|---|---|---|---|---|")
for it in ("math", "code"):
    base = None; bw = None
    for st, name in ST:
        try:
            r = [parse(f"{pre}-{st}-{s}-{it}") for s in "ab"]
        except FileNotFoundError:
            continue
        m = sum(d["ms_round"] for d in r) / 2; w = sum(d["rings"] for d in r) / 2; pw = sum(d["poolw"] for d in r) / 2
        if st == "off": base, bw = m, w
        print(f"| {name} | {it} | {r[0]['ms_round']:.2f} / {r[1]['ms_round']:.2f} | {m:.2f} | {100 * (m / base - 1):+.1f} % | "
              f"{w:.2f} | {w - bw:+.2f} | {pw:.2f} | {', '.join(sorted({d['out'] for d in r}))} |")
