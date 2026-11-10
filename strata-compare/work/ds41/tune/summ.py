#!/usr/bin/env python3
"""summ.py RUNDIR - 10-24 DeepSeek-V4.1 tuning round: one arm's numbers from speed3.py's records -> RUNDIR/arm.json plus
summary lines. Decode: per pass the mean of W1-W3, the arm's mean, and the pass-to-pass spread (half the range of the pass
means, % of the mean). Prompt reading: P4K and P20K tok/s (mean, spread), SSD GB read per prompt. SSD GB read per
generated token (W1-W3). Thinking: per W prompt the reasoning / answer characters and whether the thinking ended before
the cap. Memory and VRAM from monitor.tsv; disk writes per request (the on-disk conversation state, when on).
"""
import json
import os
import re
import statistics as st
import sys


def spread(xs):
    return round(100 * (max(xs) - min(xs)) / 2 / st.mean(xs), 2) if len(xs) > 1 else None


def main():
    o = sys.argv[1]
    recs = [json.loads(l) for l in open(f"{o}/ds41.jsonl")]
    disk = {(d["id"], d["rep"]): d for d in map(json.loads, open(f"{o}/disk.jsonl"))}
    a = {"run": o}
    for key in ("P4K", "P20K"):
        rs = [r for r in recs if r["id"] == key and r.get("prompt_tps")]
        if rs:
            tps = [r["prompt_tps"] for r in rs]
            gb = [disk.get((r["id"], r["rep"]), {}).get("disk_read_gb") for r in rs]
            a[key] = {"tps": tps, "mean": round(st.mean(tps), 1), "spread_pct": spread(tps),
                      "tokens": [r["prompt_tokens"] for r in rs], "ttft_s": [r["ttft_s"] for r in rs], "disk_gb": gb,
                      "disk_gb_mean": round(st.mean([g for g in gb if g is not None]), 1) if any(g is not None for g in gb) else None}
    ws = [r for r in recs if r["id"][:2] in ("W1", "W2", "W3") and r.get("decode_tps")]
    passes = sorted({r["rep"] for r in ws})
    pm = [st.mean([r["decode_tps"] for r in ws if r["rep"] == p]) for p in passes]
    if ws:
        a["decode"] = {"mean": round(st.mean([r["decode_tps"] for r in ws]), 2), "pass_means": [round(x, 2) for x in pm],
                       "spread_pct": spread(pm), "n": len(ws)}
        per = {}
        for r in ws:
            d = disk.get((r["id"], r["rep"]), {})
            t = per.setdefault(r["id"], {"tps": [], "gb_per_token": [], "reasoning_chars": [], "content_chars": [],
                                         "tokens": [], "finish": [], "write_gb": []})
            t["tps"].append(r["decode_tps"]); t["gb_per_token"].append(d.get("disk_gb_per_token"))
            t["reasoning_chars"].append(r.get("reasoning_chars")); t["content_chars"].append(r.get("content_chars"))
            t["tokens"].append(r.get("completion_tokens")); t["finish"].append(r.get("finish")); t["write_gb"].append(d.get("disk_write_gb"))
        a["per_prompt"] = per
        g = [x for t in per.values() for x in t["gb_per_token"] if x is not None]
        a["disk_gb_per_token"] = round(st.mean(g), 4) if g else None
    mon = []
    for l in list(open(f"{o}/monitor.tsv"))[1:]:          # skip a line the 2-second monitor wrote half
        f = l.split()
        try:
            if len(f) >= 5: float(f[1]); int(f[2]); int(f[3].split(",")[0]); int(f[4].split(",")[0]); mon.append(f)
        except ValueError:
            pass
    if mon:
        a["lowest_memavail_gb"] = min(float(m[1]) for m in mon)
        a["peak_rss_mb"] = max(int(m[2]) for m in mon)
        a["peak_vram_mib"] = [max(int(m[3].split(",")[0]) for m in mon), max(int(m[4].split(",")[0]) for m in mon)]
    # placement per card (the engine's start lines), and the store / CPU lane
    log = ""
    for f in ("engine-run.log", "engine-start.log"):
        if os.path.exists(f"{o}/{f}"):
            log = open(f"{o}/{f}", errors="replace").read(); break
    cards = re.findall(r"CUDA(\d) layers \[([\d, ]+)\][^:]*: weights ([\d.]+) GB, experts ([\d.]+) GB \((\d+) of (\d+) in VRAM\)"
                       r"(?:, caches ([\d.]+) GB)?, (\d+) MiB free", log)
    a["cards"] = [{"dev": int(c[0]), "layers": c[1].replace(" ", ""), "weights_gb": float(c[2]), "experts_gb": float(c[3]),
                   "vram_experts": int(c[4]), "of": int(c[5]), "free_mib": int(c[7])} for c in cards]
    m = re.search(r"(\d+) routed experts on the CPU lane \(([\d.]+) GB", log)
    if m:
        a["cpu_lane_experts"], a["cpu_lane_gb"] = int(m.group(1)), float(m.group(2))
    # GPU clocks / utilisation while decoding (W requests after their first token) and while reading P20K (query only)
    try:
        recs_by = {(r["id"], r["rep"]): r for r in recs}
        win = {"decode": [], "prompt": []}
        for d in disk.values():
            r = recs_by.get((d["id"], d["rep"]))
            if not r or "t_start" not in d:
                continue
            ttft = r.get("ttft_s") or 0
            if d["id"][:2] in ("W1", "W2", "W3"):
                win["decode"].append((d["t_start"] + ttft, d["t_end"]))
            elif d["id"] == "P20K":
                win["prompt"].append((d["t_start"], d["t_start"] + ttft))
        rows = []
        for l in list(open(f"{o}/monitor.tsv"))[1:]:
            f = l.split()
            if len(f) >= 6 and f[3].count(",") >= 5:
                rows.append((float(f[5]), [list(map(float, f[3].split(","))), list(map(float, f[4].split(",")))]))
        clk = {}
        for k, ws in win.items():
            sel = [g for t, g in rows if any(t0 <= t <= t1 for t0, t1 in ws)]
            if sel:
                clk[k] = [{"sm_mhz": st.median(x[i][2] for x in sel), "util_pct": st.median(x[i][4] for x in sel),
                           "power_w": round(st.median(x[i][5] for x in sel), 1), "sm_mhz_p10": sorted(x[i][2] for x in sel)[len(sel) // 10]}
                          for i in (0, 1)]
        if clk:
            a["gpu_clocks"] = clk
    except (OSError, ValueError, KeyError, IndexError):
        pass
    for key in ("P4K", "P20K"):                        # the drive's own bytes vs the engine's (Engram readahead check)
        if key in a:
            dv = [disk.get((key, i), {}).get("device_read_gb") for i in range(len(a[key]["tps"]))]
            a[key]["device_gb"] = dv
    json.dump(a, open(f"{o}/arm.json", "w"), indent=1)
    for key in ("P4K", "P20K"):
        if key in a:
            p = a[key]
            print(f"{key}: {p['tps']} tok/s (mean {p['mean']}, spread {p['spread_pct']} %), tokens {p['tokens']}, SSD {p['disk_gb']} GB per prompt")
    if "decode" in a:
        d = a["decode"]
        for k, t in a["per_prompt"].items():
            print(f"{k}: decode {t['tps']} tok/s, {t['tokens']} tokens, finish {t['finish']}, SSD {t['gb_per_token']} GB/token, "
                  f"thinking chars {t['reasoning_chars']} / answer chars {t['content_chars']}")
        print(f"W1-W3 decode mean {d['mean']} tok/s over {d['n']} responses; pass means {d['pass_means']} (spread {d['spread_pct']} %); "
              f"SSD {a['disk_gb_per_token']} GB/token")
    for c in a.get("cards", []):
        print(f"CUDA{c['dev']} layers [{c['layers']}]: {c['vram_experts']} experts in VRAM ({c['experts_gb']} GB), weights {c['weights_gb']} GB, {c['free_mib']} MiB free")
    for k, v in a.get("gpu_clocks", {}).items():
        print(f"GPU clocks while {k}: " + "; ".join(f"GPU{i} SM {g['sm_mhz']:.0f} MHz (p10 {g['sm_mhz_p10']:.0f}), util {g['util_pct']:.0f} %, {g['power_w']} W" for i, g in enumerate(v)))
    if "lowest_memavail_gb" in a:
        print(f"lowest MemAvailable {a['lowest_memavail_gb']} GB, peak engine RSS {a['peak_rss_mb']} MB, peak VRAM {a['peak_vram_mib']} MiB")


if __name__ == "__main__":
    main()
