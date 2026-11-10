#!/usr/bin/env python3
"""s4_table.py NAME OPTION... — round 15 step 4's table from the --stats outputs (bringup/out/logs/prof/s4-NAME-*):
per option, base A / opt A / opt B / base B: decode tok/s, ms per round, the file tier's reads (MB / round, ms / round of
reading), the drive's share (page cache held vs not), min MemAvailable, swap growth; the option's change vs the base
(mean of its two arms vs the base's two). Keep at >= +3 %."""
import re
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
P = WS / "bringup/out/logs/prof"


def parse(label):
    f = P / f"{label}.out"
    if not f.exists():
        return None
    t = f.read_text(errors="replace")
    d = {}
    m = re.search(r"^decode\s+(\d+) tokens in ([\d.]+) ms\s+->\s+([\d.]+) tok/s", t, re.M)
    if m:
        d["tps"] = float(m.group(3))
    m = re.search(r"^speculation\s+(\d+) rounds of \d+, drafts accepted (\d+) of (\d+) \(([\d.]+)\), ([\d.]+) tokens per round", t, re.M)
    if m:
        d["rounds"] = int(m.group(1)); d["tpr"] = float(m.group(5))
        if "tps" in d:
            d["ms_round"] = 1000.0 / d["tps"] * d["tpr"]
    m = re.search(r"expert tiers\s+decode: RAM (\d+) blobs, files (\d+) blobs, ([\d.]+) MB read from the files \(([\d.]+) MB/round, ([\d.]+) ms/round of reading", t)
    if m:
        d["file_mb_round"] = float(m.group(4)); d["file_ms_round"] = float(m.group(5))
    m = re.search(r"page cache held ([\d.]+) MB, not ([\d.]+) MB", t)
    if m:
        held, miss = float(m.group(1)), float(m.group(2))
        d["miss_share"] = miss / (held + miss) if held + miss else 0.0
    m = re.search(r"decode waited ([\d.]+) ms/round in the fetches", t)
    if m:
        d["wait_ms_round"] = float(m.group(1))
    m = re.search(r"verify window\s+wait for rings ([\d.]+)\s+pool ([\d.]+)", t)
    if m:
        d["pool_ms_round"] = float(m.group(2))
    m = re.search(r"min_MemAvailable=([\d.]+)GiB", t)
    if m:
        d["minavail"] = float(m.group(1))
    m = re.search(r"max_swap_used=([\d.]+)GiB", t)
    if m:
        d["maxswap"] = float(m.group(1))
    m = re.search(r"exit=(\S+)", t)
    d["exit"] = m.group(1) if m else "?"
    err = (P / f"{label}.err").read_text(errors="replace") if (P / f"{label}.err").exists() else ""
    if "GUARD-STOP" in t or "GUARD-STOP" in err:
        d["guard"] = "GUARD-STOP"
    return d


def fmt(v, k, n=1):
    return "–" if v is None or v.get(k) is None else f"{v[k]:.{n}f}"


name = sys.argv[1]
print(f"# Round 15 step 4 — file-tier options, {name} (each alone, A B B A, greedy math 1,024 tokens, cold page cache)\n")
print("| option | arm | decode tok/s | ms / round | file MB / round | file ms / round | fetch wait ms / round | pool ms / round | not in the page cache | min MemAvailable GiB | swap GiB |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
summary = []
for opt in sys.argv[2:]:
    on = opt.split(":")[0]
    arms = {k: parse(f"s4-{name}-{on}-{k}") for k in ("base-a", "opt-a", "opt-b", "base-b")}
    for k, v in arms.items():
        print(f"| {opt} | {k} | {fmt(v, 'tps')} | {fmt(v, 'ms_round')} | {fmt(v, 'file_mb_round')} | {fmt(v, 'file_ms_round')} | "
              f"{fmt(v, 'wait_ms_round')} | {fmt(v, 'pool_ms_round')} | {fmt(v, 'miss_share', 2)} | {fmt(v, 'minavail')} | {fmt(v, 'maxswap', 2)} |"
              + (f" {v.get('guard')}" if v and v.get('guard') else ""))
    b = [v["tps"] for k, v in arms.items() if k.startswith("base") and v and v.get("tps")]
    o = [v["tps"] for k, v in arms.items() if k.startswith("opt") and v and v.get("tps")]
    if b and o:
        ch = 100 * (sum(o) / len(o) / (sum(b) / len(b)) - 1)
        spread = 100 * (max(b) / min(b) - 1)
        summary.append(f"| {opt} | {sum(b)/len(b):.2f} | {sum(o)/len(o):.2f} | **{ch:+.1f} %** | {spread:.1f} % | {'KEEP' if ch >= 3 else 'no'} |")
    else:
        summary.append(f"| {opt} | – | – | – | – | did not run (see the .err) |")
print("\n| option | base tok/s | option tok/s | change | base arms' spread | >= +3 % |\n|---|---|---|---|---|---|")
print("\n".join(summary))
