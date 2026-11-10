#!/usr/bin/env python3
"""q8_table.py - r17: Q8_0 stand-in, placement B (5080 + 64 GiB budget), stock v0.1.41, A B B A: v0.1.41's read rule vs
STRATA_UNBUFFERED_LOAD=1 (greedy math, 1,024 tokens, cold page cache, STRATA_IO_STATS=1 on both)."""
import re, sys
from pathlib import Path
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/r15")
sys.argv = [sys.argv[0], "x"]
src = Path("/home/USER/ai-speed-testing/strata-compare/work/r15/s4_table.py").read_text().split("\ndef fmt")[0]
ns = {}; exec(src, ns); parse = ns["parse"]
P = Path("/home/USER/ai-speed-testing/strata-compare/bringup/out/logs/prof")
print("# r17 — Q8_0 stand-in, placement B, stock v0.1.41: read rule vs forced unbuffered (A B B A)\n")
print("| arm | file tier (engine line) | decode tok/s | ms / round | file MB / round | file ms / round | not in the page cache | min MemAvailable GiB | max swap GiB |")
print("|---|---|---|---|---|---|---|---|---|")
res = {}
for o, s in (("rule", "a"), ("ub1", "a"), ("ub1", "b"), ("rule", "b")):
    L = f"r17-q8B-{o}-{s}"; d = parse(L) or {}
    err = (P / f"{L}.err").read_text(errors="replace") if (P / f"{L}.err").exists() else ""
    m = re.findall(r"the file tier reads ([^\n]*)", err)
    f = lambda k, n=1: "–" if d.get(k) is None else f"{d[k]:.{n}f}"
    print(f"| {o}-{s} | {m[-1][:200] if m else '–'} | {f('tps')} | {f('ms_round')} | {f('file_mb_round')} | {f('file_ms_round')} | {f('miss_share', 2)} | {f('minavail')} | {f('maxswap', 2)} |" + (f" {d['guard']}" if d.get("guard") else ""))
    if d.get("tps"): res.setdefault(o, []).append(d["tps"])
if res.get("rule") and res.get("ub1"):
    r, u = sum(res["rule"]) / len(res["rule"]), sum(res["ub1"]) / len(res["ub1"])
    print(f"\nrule {r:.2f} tok/s (arms {', '.join(f'{x:.2f}' for x in res['rule'])}), forced unbuffered {u:.2f} (arms {', '.join(f'{x:.2f}' for x in res['ub1'])}): **{100 * (u / r - 1):+.1f} %**")
