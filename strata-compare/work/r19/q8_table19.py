#!/usr/bin/env python3
"""q8_table19.py - round 19 #1682: Q8_0 stand-in, the 5080 + --resident-budget-gib 64, stock v0.1.42 with
STRATA_ROUTE_TAIL_SKIP=0, A B B A per thread setting: the read rule vs STRATA_UNBUFFERED_LOAD=1 (greedy math, 1,024 tokens,
cold page cache, STRATA_IO_STATS=1), with STRATA_IO_THREADS unset (the default), 16 and 64."""
import os, re, sys
from pathlib import Path
sys.argv = [sys.argv[0], "x"]
src = Path("/home/USER/ai-speed-testing/strata-compare/work/r15/s4_table.py").read_text().split("\ndef fmt")[0]
ns = {}; exec(src, ns); parse = ns["parse"]
P = Path("/home/USER/ai-speed-testing/strata-compare/bringup/out/logs/prof")
print("# r19 — #1682 on stock v0.1.42 (STRATA_ROUTE_TAIL_SKIP=0): Q8_0, the 5080 + 64 GiB budget, read rule vs forced unbuffered (A B B A per thread setting)\n")
print("| STRATA_IO_THREADS | arm | file tier (engine line) | decode tok/s | ms / round | file MB / round | file ms / round | not in the page cache | min MemAvailable GiB | max swap GiB | tail-skip ON line |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
summ = []
PFX = os.environ.get("PFX", "r19")   # label prefix (r19b = the clean re-run after the RAM fix)
for T in os.environ.get("TS", "def 16 64 def2").split():
    res = {}
    for o, s in (("rule", "a"), ("ub1", "a"), ("ub1", "b"), ("rule", "b")):
        L = f"{PFX}-q8B-t{T}-{o}-{s}"; d = parse(L) or {}
        err = (P / f"{L}.err").read_text(errors="replace") if (P / f"{L}.err").exists() else ""
        m = re.findall(r"the file tier reads ([^\n]*)", err)
        ts = "yes" if re.search(r"TAIL_SKIP=\d+ is ON", err) else "no"
        f = lambda k, n=1: "–" if d.get(k) is None else f"{d[k]:.{n}f}"
        line = (m[-1][:90] + ("…" if len(m[-1]) > 90 else "")) if m else "–"
        print(f"| { {"def": "unset (default)", "def2": "unset (default), repeated"}.get(T, T) } | {o}-{s} | {line} | {f('tps', 2)} | {f('ms_round')} | {f('file_mb_round')} | {f('file_ms_round')} | {f('miss_share', 2)} | {f('minavail')} | {f('maxswap', 2)} | {ts} |" + (f" {d['guard']}" if d.get("guard") else ""))
        if d.get("tps"): res.setdefault(o, []).append(d["tps"])
    if res.get("rule") and res.get("ub1"):
        r, u = sum(res["rule"]) / len(res["rule"]), sum(res["ub1"]) / len(res["ub1"])
        summ.append(f"- STRATA_IO_THREADS { {"def": "unset", "def2": "unset, repeated"}.get(T, T) }: rule {r:.2f} tok/s (arms {', '.join(f'{x:.2f}' for x in res['rule'])}), "
                    f"forced unbuffered {u:.2f} (arms {', '.join(f'{x:.2f}' for x in res['ub1'])}): **{100 * (u / r - 1):+.1f} %**")
print("\n" + "\n".join(summ))
