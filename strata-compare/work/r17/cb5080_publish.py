#!/usr/bin/env python3
"""cb5080_publish.py - r17b: put the RTX-5080-alone runs into the community report folder, in the same format as the
two-card files: results-5080-stock.json / results-5080-private.json (cb_bench records without drive_read_gb and
engine_rss_mib, as in results-stock.json), needles-5080-*.json (needle_bench's output as is), and two new keys in
summary.json (same layout as the existing ones; memory_guard from the guard's summary line of that server session).
Prints the README tables.

    python3 work/r17/cb5080_publish.py FOLDER [FOLDER ...]"""
import json
import re
import statistics as S
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
R = WS / "results/r17"
GUARD = WS / "bringup/out/logs/guard/summary.txt"
SETS = [("cb-stock-5080", "stock", "v0.1.41, RTX 5080 alone"),
        ("cb-c16-5080", "private", "private build (v0.1.41 + 27 local patches), RTX 5080 alone")]
NOTE = ("memory_after: MemAvailable, swap in use and each GPU's used VRAM right after the request (GPU 0 = RTX 5080, "
        "GPU 1 = RTX 4060 Ti, not used in these runs). timings: the server's own (llama.cpp names; cache_n = reused tokens, "
        "prompt_n = read tokens).")


def clean(rec):
    rec = {k: v for k, v in rec.items() if k != "drive_read_gb"}
    rec["memory_after"] = {k: v for k, v in rec["memory_after"].items() if k != "engine_rss_mib"}
    return rec


def stat(v):
    return {"runs": v, "median": S.median(v), "min": min(v), "max": max(v)}


def guard_line(label):
    lines = [l for l in GUARD.read_text().splitlines() if f" srv-r17-{label} " in l]
    assert lines, label
    m = dict(re.findall(r"(\w+)=([^ @]+)", lines[-1]))
    assert m["exit"] == "0" and lines[-1].rstrip().endswith(" ok"), lines[-1]
    return {"min_MemAvailable": m["min_MemAvailable"], "min_5080_free": m["min_5080_free"],
            "max_tree_RSS": m["max_tree_RSS"], "max_swap_used": m["max_swap_used"], "min_4060Ti_free": m["min_4060Ti_free"],
            "sampled": "every 0.2 s for the whole server session (load, warm-up, benchmark and needles); "
                       "RSS = the server's process tree"}


def mr(v, n=1):
    return f"{S.median(v):,.{n}f} ({min(v):,.{n}f}–{max(v):,.{n}f})"


out = {}
for label, short, key in SETS:
    d = json.loads((R / f"{label}.json").read_text())
    nd = json.loads((R / f"{label}-needles.json").read_text())
    pub = {"label": key, "warmup": clean(d["warmup"]), "runs": [clean(r) for r in d["runs"]], "note": NOTE}
    for r in pub["runs"] + [pub["warmup"]]:
        r["label"] = key
    sizes = {}
    print(f"\n### {key}\n")
    print("| Configuration | Actual prompt tokens | Reused tokens | Generated tokens | Runs | Prompt tok/s median (range) | Decode tok/s median (range) | TTFT seconds median (range) |")
    print("| --- | ---: | ---: | ---: | ---: | --- | --- | --- |")
    for size, name in (("4096", "4K"), ("32768", "32K"), ("128000", "128K")):
        rs = [r for r in d["runs"] if r["size"] == size]
        t = [r["timings"] for r in rs]
        pt = [x["prompt_per_second"] for x in t]; dt = [x["predicted_per_second"] for x in t]; tt = [r["ttft_s"] for r in rs]
        toks = [x["prompt_n"] + x["cache_n"] for x in t]
        sizes[size] = {"runs": len(rs), "prompt_tokens": toks, "reused_tokens": [x["cache_n"] for x in t],
                       "generated_tokens": [x["predicted_n"] for x in t], "finish": [r["finish"] for r in rs],
                       "prompt_tok_s": stat(pt), "decode_tok_s": stat(dt), "ttft_s": stat(tt),
                       "total_s": [r["total_s"] for r in rs],
                       "drafts_accepted_of_offered": [[x.get("draft_n_accepted"), x.get("draft_n")] for x in t]}
        tr = f"{min(toks):,}" if min(toks) == max(toks) else f"{min(toks):,}–{max(toks):,}"
        print(f"| {name} | {tr} | {', '.join(str(x['cache_n']) for x in t) if len({x['cache_n'] for x in t}) > 1 else t[0]['cache_n']} | "
              f"{', '.join(str(x['predicted_n']) for x in t)} | {len(rs)} | {mr(pt, 0)} | {mr(dt)} | {mr(tt, 2)} |")
        print(f"<!-- total s {min(r['total_s'] for r in rs)}–{max(r['total_s'] for r in rs)}, finish {[r['finish'] for r in rs]} -->")
    found = sum(1 for n in nd if n.get("found"))
    g = guard_line(label)
    out[key] = {"sizes": sizes, "memory_guard": g, "needles_found": f"{found} of {len(nd)}"}
    mem = [r["memory_after"] for r in d["runs"]]
    print(f"\nneedles {found} of {len(nd)}: " + "; ".join(f"{n['length']} d{n['depth']} {n['prompt_tokens']} tok {n['seconds']} s {'found' if n.get('found') else 'MISSED'}" for n in nd))
    print(f"guard: {g}")
    print(f"VRAM used after requests: GPU0 {min(m['gpu_used_mib']['0'] for m in mem):,}–{max(m['gpu_used_mib']['0'] for m in mem):,} MiB, "
          f"GPU1 {min(m['gpu_used_mib']['1'] for m in mem):,}–{max(m['gpu_used_mib']['1'] for m in mem):,} MiB; "
          f"MemAvailable after requests {min(m['mem_available_mib'] for m in mem):,}–{max(m['mem_available_mib'] for m in mem):,} MiB; "
          f"swap {min(m['swap_used_mib'] for m in mem)}–{max(m['swap_used_mib'] for m in mem)} MiB")
    for folder in sys.argv[1:]:
        F = Path(folder)
        (F / f"results-5080-{short}.json").write_text(json.dumps(pub, indent=1) + "\n")
        (F / f"needles-5080-{short}.json").write_bytes((R / f"{label}-needles.json").read_bytes())   # as is, like needles-stock.json

for folder in sys.argv[1:]:
    F = Path(folder)
    summ = json.loads((F / "summary.json").read_text())
    for k in out:
        summ[k] = out[k]
    (F / "summary.json").write_text(json.dumps(summ, indent=1) + "\n")
    print("updated", F.name)
