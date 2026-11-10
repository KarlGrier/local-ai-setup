"""r4_table.py LABEL,LABEL,... — round-8 A/B table (copy of r7_table.py) (copy of r6_table.py) (copy of work/r5/r5_table.py, monitors in logs/r6) (rows = metrics, columns = screens) from results/runs.jsonl and
logs/r11/monitor-<L>.*: prompt reading (TTFT) 1K/32K/64K/120K, decode at depth (768 tokens after each prompt),
long reasoning (8K cap), aggregate decode, ms per verify round at equal tokens/round, acceptance, VRAM/RAM."""
import csv, json, statistics, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
runs = [json.loads(l) for l in open(WS / "results/runs.jsonl", encoding="utf-8")]
labels = sys.argv[1].split(",")
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
    acc = sum(x["drafts_accepted"] for x in e) / max(1, sum(x["drafts_offered"] for x in e))
    return (g / (ms / 1000) if ms else None, ms / max(1, rounds), g / max(1, rounds), acc)
def mon(L):
    try:
        rows = [r for r in csv.DictReader(open(WS / f"logs/r11/monitor-{L}.sys.csv")) if r["pid"]]
        g = [l.strip().split(", ") for l in open(WS / f"logs/r11/monitor-{L}.gpu.csv") if l.count(",") >= 5]
        gpu = [int(x[1]) for x in g if x[1].isdigit()]
        return max(gpu), min(int(r["memavail_mib"]) for r in rows) / 1024, max(int(r["rss_mib"]) for r in rows) / 1024
    except Exception:
        return None, None, None
f = lambda v, d=2: "–" if v is None else f"{v:.{d}f}"
rows = [("TTFT 1K prompt, median of 3 (s)", lambda L: f(med(L, "speed", "1k", "ttft_s"))),
        ("TTFT short prompts 68-87 tokens, median of 5 (s)", lambda L: f(statistics.median([r["ttft_s"] for r in rs(L) if r["scenario"] == "correctness" and r.get("ttft_s")] or [0]))),
        ("TTFT 32K prompt (s)", lambda L: f(one(L, "speed", "32k", "ttft_s"))),
        ("TTFT 64K prompt (s)", lambda L: f(one(L, "speed", "64k", "ttft_s"))),
        ("TTFT 120K prompt (s)", lambda L: f(one(L, "speed", "120k", "ttft_s"))),
        ("decode after 1K, median of 3 (tok/s)", lambda L: f(med(L, "speed", "1k", "decode_tps"), 1)),
        ("decode after 32K (tok/s)", lambda L: f(one(L, "speed", "32k", "decode_tps"), 1)),
        ("decode after 64K (tok/s)", lambda L: f(one(L, "speed", "64k", "decode_tps"), 1)),
        ("decode after 120K (tok/s)", lambda L: f(one(L, "speed", "120k", "decode_tps"), 1)),
        ("long reasoning math, 8,192 tokens (tok/s)", lambda L: f(one(L, "longreason", "math", "decode_tps"), 1)),
        ("long reasoning code, 8,192 tokens (tok/s)", lambda L: f(one(L, "longreason", "code", "decode_tps"), 1)),
        ("decode, all 768+ token requests (engine tok/s)", lambda L: f(agg(L, ("speed", "longreason"))[0], 1)),
        ("ms per verify round / tokens per round", lambda L: f"{f(agg(L, ('speed', 'longreason'))[1])} / {f(agg(L, ('speed', 'longreason'))[2])}"),
        ("draft acceptance", lambda L: f(agg(L, ("speed", "longreason"))[3], 3)),
        ("correctness decode, median of 5 (tok/s)", lambda L: f(statistics.median([r["decode_tps"] for r in rs(L) if r["scenario"] == "correctness" and r.get("decode_tps")] or [0]), 1)),
        ("peak GPU used (MiB) / min MemAvailable (GB) / peak RSS (GB)", lambda L: " / ".join(f(x, 1) if isinstance(x, float) else str(x) for x in mon(L)))]
print("| metric | " + " | ".join(labels) + " |")
print("|---|" + "---|" * len(labels))
for name, fn in rows:
    print(f"| {name} | " + " | ".join(fn(L) for L in labels) + " |")
