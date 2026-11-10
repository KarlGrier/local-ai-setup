"""hold_table.py LABEL,... — round 9 Phase C holdout (work/r12/holdout.py): per run, engine decode over the holdout's
long answers (accepted output tokens / decode time, requests > 100 tokens), TTFT of the ~28K-token document and of
the three short questions (median), and the full request time of all eight requests (sum)."""
import json, os, statistics, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
runs = [json.loads(l) for l in open(WS / "results/runs.jsonl", encoding="utf-8")]
print("| run | decode tok/s (engine, 4 long answers + doc) | tokens | TTFT document (s) | TTFT short, median (s) | all 8 requests, total (s) |")
print("|---|---|---|---|---|---|")
for L in sys.argv[1].split(","):
    # round 9: SINCE (env, ISO time) keeps only this round's runs - round 8's holdout used the labels H10-a / H10-b too
    since = os.environ.get("SINCE", "2026-10-04T02:53")
    rs = [r for r in runs if r["config"] == L and r["scenario"] in ("holdout", "holdout10") and not r.get("error")
          and r.get("started", "") >= since]
    e = [r["engine"] for r in rs if r.get("engine") and r.get("completion_tokens", 0) > 100]
    g = sum(x["generated"] for x in e); ms = sum(x["decode_ms"] for x in e)
    doc = [r["ttft_s"] for r in rs if r["item"] in ("doc28k", "devdoc") and r.get("ttft_s")]
    sh = [r["ttft_s"] for r in rs if r["item"].startswith("short") and r.get("ttft_s")]
    tot = sum(r["t_total_s"] for r in rs)
    print(f"| {L} | {(g / (ms / 1000)) if ms else float('nan'):.1f} | {g} | {doc[0] if doc else float('nan'):.2f} | "
          f"{statistics.median(sh) if sh else float('nan'):.2f} | {tot:.1f} ({len(rs)} requests) |")
