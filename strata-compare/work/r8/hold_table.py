"""hold_table.py LABEL,... — round 8 Phase C holdout (work/r8/holdout.py): per run, engine decode over the holdout's
long answers (accepted output tokens / decode time, requests > 100 tokens), TTFT of the ~28K-token document and of
the three short questions (median), and the full request time of all eight requests (sum)."""
import json, statistics, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
runs = [json.loads(l) for l in open(WS / "results/runs.jsonl", encoding="utf-8")]
print("| run | decode tok/s (engine, 4 long answers + doc) | tokens | TTFT doc 28K (s) | TTFT short, median (s) | all 8 requests, total (s) |")
print("|---|---|---|---|---|---|")
for L in sys.argv[1].split(","):
    rs = [r for r in runs if r["config"] == L and r["scenario"] == "holdout" and not r.get("error")]
    e = [r["engine"] for r in rs if r.get("engine") and r.get("completion_tokens", 0) > 100]
    g = sum(x["generated"] for x in e); ms = sum(x["decode_ms"] for x in e)
    doc = [r["ttft_s"] for r in rs if r["item"] == "doc28k" and r.get("ttft_s")]
    sh = [r["ttft_s"] for r in rs if r["item"].startswith("short") and r.get("ttft_s")]
    tot = sum(r["t_total_s"] for r in rs)
    print(f"| {L} | {(g / (ms / 1000)) if ms else float('nan'):.1f} | {g} | {doc[0] if doc else float('nan'):.2f} | "
          f"{statistics.median(sh) if sh else float('nan'):.2f} | {tot:.1f} ({len(rs)} requests) |")
