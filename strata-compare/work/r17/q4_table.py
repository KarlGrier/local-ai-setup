#!/usr/bin/env python3
"""q4_table.py - r17: UD-Q4_K_XL, stock v0.1.41 (K-quant build), the 5080 + --resident-budget-gib 66 vs --resident-experts,
A B B A, each a fresh server: the 32K prompts' read time, drive reads, decode; the engine's lend / RAM-copy lines."""
import json
from pathlib import Path
R = Path("/home/USER/ai-speed-testing/strata-compare/results/r17")
print("# r17 — UD-Q4_K_XL on stock v0.1.41: RAM budget vs --resident-experts (A B B A, fresh server each)\n")
print("| arm | prompt | read tokens | prompt ms | prompt tok/s | TTFT s | drive GB during the request | decode tok/s | MemAvailable after (MiB) |")
print("|---|---|---|---|---|---|---|---|---|")
for o, s in (("budget", "a"), ("resident", "a"), ("resident", "b"), ("budget", "b")):
    f = R / f"q4-{o}-{s}.json"
    if not f.exists():
        print(f"| {o}-{s} | did not run | | | | | | | |"); continue
    d = json.loads(f.read_text())
    for r in d["runs"]:
        t = r["timings"] or {}
        print(f"| {o}-{s} | 32K r{r['rep']} | {t.get('prompt_n')} | {t.get('prompt_ms')} | {t.get('prompt_per_second')} | {r['ttft_s']} | {r['drive_read_gb']} | {t.get('predicted_per_second')} | {r['memory_after']['mem_available_mib']} |")
for o, s in (("budget", "a"), ("resident", "a")):
    f = R / f"q4-{o}-{s}-start.txt"
    if f.exists():
        print(f"\n{o}-{s} start lines:\n```\n" + f.read_text()[:3000] + "```")
