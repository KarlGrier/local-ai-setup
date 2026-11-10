#!/usr/bin/env python3
"""stock_table.py — round 9 Phase 0.1: the full-screen table (work/r11/r8_table.py's rows) for S0 / S1 / C*10, two rounds each,
plus the decode screens (label with 'd': S0-a -> S0d-a), the chat-switch test (L-switch: back to the 40K chat A after
another chat), and the mean of each arm's two rounds."""
import csv, json, statistics, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
runs = [json.loads(l) for l in open(WS / "results/runs.jsonl", encoding="utf-8")]
ARMS = [("S0 (stock, setup defaults)", "S0"), ("S1 (stock binary, C*10's config)", "S1"), ("C*10", "C10")]
def rs(L): return [r for r in runs if r["config"] == L and not r.get("error")]
def one(L, sc, it, key):
    v = [r[key] for r in rs(L) if r["scenario"] == sc and r["item"] == it and r.get(key) is not None]
    return v[-1] if v else None
def med(L, sc, it, key):
    v = [r[key] for r in rs(L) if r["scenario"] == sc and r["item"] == it and r.get(key) is not None]
    return statistics.median(v) if v else None
def agg(L, scen):
    e = [r["engine"] for r in rs(L) if r.get("engine") and r["scenario"] in scen and r.get("completion_tokens", 0) > 100]
    g = sum(x["generated"] for x in e); ms = sum(x["decode_ms"] for x in e)
    rounds = sum(x["generated"] - x["drafts_accepted"] for x in e)
    acc = sum(x["drafts_accepted"] for x in e) / sum(x["drafts_offered"] for x in e) if e and sum(x["drafts_offered"] for x in e) else None
    return (g / (ms / 1000) if ms else None, ms / max(1, rounds) if ms else None, g / max(1, rounds) if ms else None, acc)
def back(L):
    v = [r["ttft_s"] for r in rs(L + "-switch") if r["scenario"] == "chat_back" and r["item"].startswith("A") and r.get("ttft_s")]
    return statistics.median(v) if v else None
def mon(L):
    try:
        rows = [r for r in csv.DictReader(open(WS / f"logs/r11/monitor-{L}.sys.csv")) if r["pid"]]
        g = [l.strip().split(", ") for l in open(WS / f"logs/r11/monitor-{L}.gpu.csv") if l.count(",") >= 5]
        gpu = [int(x[1]) for x in g if x[1].isdigit()]
        return max(gpu), min(int(r["memavail_mib"]) for r in rows) / 1024, max(int(r["rss_mib"]) for r in rows) / 1024
    except Exception:
        return None, None, None
dl = lambda L: L.replace("-", "d-", 1)
R = [("decode, all 768+-token answers, full screen (tok/s)", lambda L: agg(L, ("speed", "longreason"))[0], 1),
     ("decode, decode screen (long reasoning 4K + correctness + 32K) (tok/s)", lambda L: agg(dl(L), ("speed", "longreason", "correctness"))[0], 1),
     ("long reasoning math, 8K cap (tok/s)", lambda L: one(L, "longreason", "math", "decode_tps"), 1),
     ("long reasoning code, 8K cap (tok/s)", lambda L: one(L, "longreason", "code", "decode_tps"), 1),
     ("ms per verify round", lambda L: agg(L, ("speed", "longreason"))[1], 2),
     ("tokens per round", lambda L: agg(L, ("speed", "longreason"))[2], 2),
     ("draft acceptance", lambda L: agg(L, ("speed", "longreason"))[3], 3),
     ("decode after 120K (tok/s)", lambda L: one(L, "speed", "120k", "decode_tps"), 1),
     ("TTFT 1K, median of 3 (s)", lambda L: med(L, "speed", "1k", "ttft_s"), 2),
     ("TTFT 32K (s)", lambda L: one(L, "speed", "32k", "ttft_s"), 2),
     ("TTFT 64K (s)", lambda L: one(L, "speed", "64k", "ttft_s"), 2),
     ("TTFT 120K (s)", lambda L: one(L, "speed", "120k", "ttft_s"), 2),
     ("back to a 40K chat after another chat, median of 4 (s)", back, 2),
     ("peak VRAM used on the RTX 5080 (MiB)", lambda L: mon(L)[0], 0),
     ("lowest MemAvailable (GB)", lambda L: mon(L)[1], 1),
     ("peak engine RSS (GB)", lambda L: mon(L)[2], 1)]
fmt = lambda v, d: "–" if v is None else f"{v:.{d}f}"
cols = [(n, a) for n, a in ARMS]
print("| metric | " + " | ".join(f"{n}: round a / b → mean" for n, _ in cols) + " |")
print("|---|" + "---|" * len(cols))
for name, fn, d in R:
    cells = []
    for _, a in cols:
        va, vb = fn(f"{a}-a"), fn(f"{a}-b")
        m = statistics.mean([v for v in (va, vb) if v is not None]) if (va is not None or vb is not None) else None
        cells.append(f"{fmt(va, d)} / {fmt(vb, d)} → **{fmt(m, d)}**")
    print(f"| {name} | " + " | ".join(cells) + " |")
