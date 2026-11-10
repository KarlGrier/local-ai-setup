#!/usr/bin/env python3
"""cb_table.py RESULT.json [NEEDLES.json] [--summary OUT.json] - the community report's table: per size the actual prompt
tokens, reused tokens, generated tokens, runs, prompt tok/s / decode tok/s / TTFT (median and range), plus memory."""
import json, statistics as S, sys
from pathlib import Path
args = [a for a in sys.argv[1:] if not a.startswith("--")]
out = sys.argv[sys.argv.index("--summary") + 1] if "--summary" in sys.argv else None
if out: args = [a for a in args if a != out]
d = json.loads(Path(args[0]).read_text())
summ = {}
def mr(v, n=1):
    return f"{S.median(v):,.{n}f} ({min(v):,.{n}f}–{max(v):,.{n}f})"
print("| Prompt size | Actual prompt tokens | Reused tokens | Generated tokens | Runs | Prompt tok/s median (range) | Decode tok/s median (range) | TTFT s median (range) |")
print("| --- | ---: | ---: | ---: | ---: | --- | --- | --- |")
for size in ("4096", "32768", "128000"):
    rs = [r for r in d["runs"] if r["size"] == size]
    t = [r["timings"] for r in rs]
    pt = [x["prompt_per_second"] for x in t]; dt = [x["predicted_per_second"] for x in t]; tt = [r["ttft_s"] for r in rs]
    toks = sorted({x["prompt_n"] + x["cache_n"] for x in t}); reused = sorted({x["cache_n"] for x in t}); gen = [x["predicted_n"] for x in t]
    fin = [r["finish"] for r in rs]
    print(f"| {int(size):,} | {', '.join(f'{x:,}' for x in toks)} | {', '.join(str(x) for x in reused)} | {', '.join(str(x) for x in gen)} | {len(rs)} | {mr(pt)} | {mr(dt)} | {mr(tt, 2)} |")
    summ[size] = {"prompt_tokens": [x["prompt_n"] + x["cache_n"] for x in t], "reused": [x["cache_n"] for x in t], "generated": gen,
                  "finish": fin, "prompt_tok_s": pt, "decode_tok_s": dt, "ttft_s": tt,
                  "prompt_tok_s_median": S.median(pt), "decode_tok_s_median": S.median(dt), "ttft_s_median": S.median(tt),
                  "drafts_accepted_of_offered": [[x.get("draft_n_accepted"), x.get("draft_n")] for x in t]}
mem = [r["memory_after"] for r in d["runs"]]
print(f"\nMemory after each request: MemAvailable {min(m['mem_available_mib'] for m in mem):,}–{max(m['mem_available_mib'] for m in mem):,} MiB, "
      f"engine RSS {min(m['engine_rss_mib'] for m in mem):,}–{max(m['engine_rss_mib'] for m in mem):,} MiB, "
      + ", ".join(f"GPU {g} {min(m['gpu_used_mib'][g] for m in mem):,}–{max(m['gpu_used_mib'][g] for m in mem):,} MiB used" for g in mem[0]["gpu_used_mib"]))
print("finish reasons:", {s: summ[s]["finish"] for s in summ})
if len(args) > 1:
    n = json.loads(Path(args[1]).read_text())
    print("needles:", json.dumps(n)[:1500])
if out:
    Path(out).write_text(json.dumps({"label": d["label"], "warmup": {k: d["warmup"][k] for k in ("ttft_s", "timings", "finish")}, "sizes": summ,
                                     "memory_after_requests": {"mem_available_mib_min": min(m['mem_available_mib'] for m in mem),
                                                               "engine_rss_mib_max": max(m['engine_rss_mib'] for m in mem),
                                                               "gpu_used_mib_max": {g: max(m['gpu_used_mib'][g] for m in mem) for g in mem[0]["gpu_used_mib"]}}}, indent=1))
