#!/usr/bin/env python3
"""q4_table19.py - round 19 #1683: UD-Q4_K_XL, stock v0.1.42 (K-quant build, STRATA_ROUTE_TAIL_SKIP=0), the 5080 +
--resident-budget-gib 72 / --resident-experts / --resident-budget-gib 66, each a fresh server, two 32K prompts: read time,
drive reads, decode, the engine's RAM-copy and lend lines, the run's lowest MemAvailable (memory guard)."""
import json, os, re
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); R = WS / "results/r19"
G = (WS / "bringup/out/logs/guard/summary.txt").read_text().splitlines()
A3 = os.environ.get("A3", "a3"); PFX = os.environ.get("PFX", "r19")   # r19b / a3b: the clean re-run
print("# r19 — #1683 on stock v0.1.42 (STRATA_ROUTE_TAIL_SKIP=0): UD-Q4_K_XL, RAM budget 72 / --resident-experts / budget 66\n")
print("| arm | RAM copy (engine) | lent slots' experts in RAM | prompt | read tokens | prompt ms | prompt tok/s | TTFT s | drive GB during the request | decode tok/s | MemAvailable after (MiB) |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
low = {}
for o in ("b72", "res", "b66"):
    st = (R / f"{A3}-q4-{o}-start.txt").read_text(errors="replace") if (R / f"{A3}-q4-{o}-start.txt").exists() else ""
    m = re.search(r"resident RAM mode: ([\d.]+ GiB) of experts in RAM", st); ram = m.group(1) if m else "–"
    m = re.search(r"(\d+) of the prompt path's (\d+) lendable slots keep their experts in RAM", st)
    m2 = re.search(r"lends (\d+) cache slots to the prompt path, but only (\d+) of their experts fit in RAM", st)
    lend = f"{m.group(1)} of {m.group(2)}" if m else (f"{m2.group(2)} of {m2.group(1)}" if m2 else "–")
    for line in G:
        if f" srv-{PFX}-q4-{o} " in line:
            mm = re.search(r"min_MemAvailable=([\d.]+)GiB", line); low[o] = mm.group(1) if mm else "–"
    f = R / f"{A3}-q4-{o}.json"
    if not f.exists():
        print(f"| {o} | {ram} | {lend} | did not run | | | | | | | |"); continue
    for r in json.loads(f.read_text())["runs"]:
        t = r["timings"] or {}
        print(f"| {o} | {ram} | {lend} | 32K r{r['rep']} | {t.get('prompt_n')} | {t.get('prompt_ms')} | {t.get('prompt_per_second')} | {r['ttft_s']} | {r['drive_read_gb']} | {t.get('predicted_per_second')} | {r['memory_after']['mem_available_mib']} |")
print("\nLowest MemAvailable over each server's whole run (memory guard, GiB): " + ", ".join(f"{o} {v}" for o, v in low.items()))
for o in ("b72", "res", "b66"):
    f = R / f"{A3}-q4-{o}-start.txt"
    if f.exists():
        print(f"\n{o} start lines:\n```\n" + f.read_text()[:3500] + "```")
