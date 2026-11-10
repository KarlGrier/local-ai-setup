"""Round-2 screen table (sampled runs: no token-identity column). Per config: 1K decode median [min-max] of the 3
prompts, 32K decode, 32K TTFT (prompt tok/s), correctness-set decode median (sampled), draft acceptance and tokens per
verify round over speed+correctness, 8K long-reasoning decode, 120K TTFT, peak GPU used / min MemAvailable (monitor).
    r2_table.py LABEL[,LABEL...]"""
import csv, json, statistics, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
runs = [json.loads(l) for l in open(WS / "results/runs.jsonl", encoding="utf-8")]
def med(v): return f"{statistics.median(v):.1f} [{min(v):.1f}–{max(v):.1f}]" if v else "–"
def peaks(L):
    try:
        rows = [r for r in csv.DictReader(open(WS / f"logs/r3/monitor-{L}.sys.csv")) if r["pid"]]
        g = [l.strip().split(", ") for l in open(WS / f"logs/r3/monitor-{L}.gpu.csv") if l.count(",") >= 5]
        gpu = [int(x[1]) for x in g if x[1].isdigit()]
        return f"{max(gpu)} / {min(int(r['memavail_mib']) for r in rows) / 1024:.1f} GB / {max(int(r['rss_mib']) for r in rows) / 1024:.1f} GB"
    except Exception:
        return "–"
print("| config | 1K decode tok/s (3 prompts) | agg decode 1K+32K (engine) | 32K decode | 32K TTFT s (PP tok/s) | correctness decode (5, sampled) | acceptance | tok/round | 8K reasoning tok/s (acc) | 120K TTFT s (PP) | peak GPU MiB / min MemAvail / peak RSS |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for L in sys.argv[1].split(","):
    rs = [r for r in runs if r["config"] == L and not r.get("error")]
    s1 = [r["decode_tps"] for r in rs if r["scenario"] == "speed" and r["item"] == "1k"]
    s32 = [r for r in rs if r["scenario"] == "speed" and r["item"] == "32k"]
    s120 = [r for r in rs if r["scenario"] == "speed" and r["item"] == "120k"]
    cr = [r["decode_tps"] for r in rs if r["scenario"] == "correctness" and r.get("decode_tps")]
    eng = [r["engine"] for r in rs if r.get("engine") and r["scenario"] in ("speed", "correctness")]
    acc = sum(e["drafts_accepted"] for e in eng) / max(1, sum(e["drafts_offered"] for e in eng))
    rounds = sum(e["generated"] - e["drafts_accepted"] for e in eng)
    tpr = sum(e["generated"] for e in eng) / max(1, rounds)
    sp = [r["engine"] for r in rs if r.get("engine") and r["scenario"] == "speed" and r["item"] in ("1k", "32k")]
    agg = sum(e["generated"] for e in sp) / max(1e-9, sum(e["decode_ms"] for e in sp) / 1000) if sp else 0
    lr = [r for r in rs if r["scenario"] == "longreason"]
    lrs = "–"
    if lr:
        e = lr[-1].get("engine") or {}
        lrs = f"{lr[-1]['decode_tps']:.1f} ({e.get('drafts_accepted', 0) / max(1, e.get('drafts_offered', 1)):.3f})"
    t32 = f"{s32[-1]['decode_tps']:.1f} | {s32[-1]['ttft_s']:.2f} ({s32[-1]['prompt_tps_client']:.0f})" if s32 else "– | –"
    t120 = f"{s120[-1]['ttft_s']:.1f} ({s120[-1]['prompt_tps_client']:.0f})" if s120 else "–"
    print(f"| {L} | {med(s1)} | {agg:.1f} | {t32} | {med(cr)} | {acc:.3f} | {tpr:.2f} | {lrs} | {t120} | {peaks(L)} |")
