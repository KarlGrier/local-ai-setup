#!/usr/bin/env python3
"""s3_table.py LABEL... — round 15 step 3's numbers per placement session (work/r15/s3session.sh), from results/runs.jsonl
(the engine's per-request lines, scripts/bench.py), the memory guard's samples, logs/r15/ssd.csv, the needle results and
the CLI split (--stats). Prints one markdown block per label and a JSON line per label to results/r15/s3-rows.jsonl."""
import csv
import json
import re
import statistics
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
runs = [json.loads(l) for l in open(WS / "results/runs.jsonl", encoding="utf-8")]


def agg(rows):
    e = [r["engine"] for r in rows if r.get("engine") and (r.get("completion_tokens") or 0) > 100]
    g = sum(x["generated"] for x in e)
    ms = sum(x["decode_ms"] for x in e)
    if not ms:
        return {}
    rounds = sum(x["generated"] - x["drafts_accepted"] for x in e)
    off = sum(x["drafts_offered"] for x in e)
    look = sum(x.get("lookups", 0) for x in e)
    hits = sum(x.get("hits", 0) for x in e)
    offl = sum(x.get("offload", 0) for x in e)
    osmb = sum(x.get("os_read_mb", 0) or 0 for x in e)
    exmb = sum(x.get("expert_read_mb", 0) or 0 for x in e)
    tot = look + offl
    return {"tps": g / (ms / 1000), "ms_round": ms / max(1, rounds), "tpr": g / max(1, rounds),
            "acc": sum(x["drafts_accepted"] for x in e) / off if off else None,
            "share_5080": hits / tot if tot else None, "share_card2": offl / tot if tot else None,
            "share_cpu": (look - hits) / tot if tot else None,
            "drive_gib_round": osmb / 1024 / max(1, rounds), "file_gib_round": exmb / 1024 / max(1, rounds),
            "rounds": rounds, "generated": g}


def split(label, kind):
    f = WS / f"bringup/out/logs/prof/{label}-split-{kind}.out"
    if not f.exists():
        return {}
    t = f.read_text(errors="replace")
    d = {}
    m = re.search(r"^decode\s+\d+ tokens in [\d.]+ ms\s+->\s+([\d.]+) tok/s", t, re.M)
    if m: d["tps"] = float(m.group(1))
    m = re.search(r"^speculation\s+(\d+) rounds of \d+, drafts accepted \d+ of \d+ \(([\d.]+)\), ([\d.]+) tokens per round", t, re.M)
    if m and "tps" in d: d["ms_round"] = 1000 / d["tps"] * float(m.group(3))
    m = re.search(r"verify window\s+wait for rings ([\d.]+)\s+pool ([\d.]+)", t)
    if m: d["wait_rings"] = float(m.group(1)); d["pool"] = float(m.group(2))
    m = re.search(r"expert tiers\s+decode: RAM (\d+) blobs, files (\d+) blobs, ([\d.]+) MB read from the files \(([\d.]+) MB/round, ([\d.]+) ms/round of reading", t)
    if m: d["file_mb_round"] = float(m.group(4)); d["file_ms_round"] = float(m.group(5)); d["ram_blobs"] = int(m.group(1)); d["file_blobs"] = int(m.group(2))
    m = re.search(r"page cache held ([\d.]+) MB, not ([\d.]+) MB", t)
    if m: d["pc_held_mb"] = float(m.group(1)); d["pc_miss_mb"] = float(m.group(2))
    m = re.search(r"decode waited ([\d.]+) ms/round in the fetches", t)
    if m: d["fetch_wait"] = float(m.group(1))
    m = re.search(r"R4 expert-cache hits\s+(\d+) of (\d+)", t)
    if m: d["gpu_hit"] = int(m.group(1)) / max(1, int(m.group(2)))
    m = re.search(r"CUDA1 experts\s+(\d+) routed", t)
    if m: d["cuda1"] = int(m.group(1))
    m = re.search(r"min_MemAvailable=([\d.]+)GiB", t)
    if m: d["minavail"] = float(m.group(1))
    m = re.search(r"max_swap_used=([\d.]+)GiB", t)
    if m: d["maxswap"] = float(m.group(1))
    return d


def guard(label):
    f = WS / f"bringup/out/logs/guard/srv-{label}.csv"
    if not f.exists():
        return {}
    rows = list(csv.DictReader(open(f)))
    if not rows:
        return {}
    ma = [float(r["memavail_gib"]) for r in rows]
    sw = [float(r["swap_used_gib"]) for r in rows]
    vf = [float(r["vram_free_mib"]) for r in rows]
    return {"min_memavail": min(ma), "swap0": sw[0], "swap_max": max(sw), "min_5080_free": min(vf)}


def ssd(t0, t1):
    rows = [r for r in csv.DictReader(open(WS / "logs/r15/ssd.csv")) if t0 <= r["time"][:19] <= t1]
    if not rows:
        return {}
    return {"ssd_max_c": max(max(int(r["composite_c"]), int(r["sensor1_c"]), int(r["sensor2_c"])) for r in rows),
            "ssd_comp_max": max(int(r["composite_c"]) for r in rows),
            "ssd_read_gb": float(rows[-1]["read_gb_cum"]) - float(rows[0]["read_gb_cum"])}


def needle(label):
    f = WS / "bringup/out/results/needle2.jsonl"
    if not f.exists():
        return None
    r = [json.loads(l) for l in open(f) if f'"{label}"' in l]
    r = [x for x in r if x.get("label") == label]
    if not r:
        return None
    return sum(x.get("score", 0) for x in r), 6 * len(r)


DT_RE = re.compile(r"strata decode timing: (\d+) windows, avg T ([\d.]+), ([\d.]+) tokens/window, ([\d.]+) ms/window = "
                   r"verify ([\d.]+) \(GPU-reach wait ([\d.]+) \+ per-layer host ([\d.]+) \[plan ([\d.]+) actq ([\d.]+) jobs ([\d.]+) "
                   r"CPU ([\d.]+)\] \+ stage ([\d.]+)\) \+ commit/emit ([\d.]+) \+ draft ([\d.]+); per layer-window: CPU experts "
                   r"([\d.]+) \(([\d.]+) entries\), VRAM hits ([\d.]+), PCIe ([\d.]+)")
DT_KEYS = ["windows", "T", "tok_w", "ms_w", "verify", "gpu_wait", "host", "plan", "actq", "jobs", "cpu", "stage", "commit",
           "draft", "cpu_exp", "entries", "vram_hits", "pcie"]


def dtiming(label):
    """The serve path's STRATA_DECODE_TIMING lines of the session, averaged per window (weighted by windows)."""
    f = WS / f"results/r15/s3/{label}-engine.log"
    if not f.exists():
        return {}
    rows = [dict(zip(DT_KEYS, map(float, m.groups()))) for m in DT_RE.finditer(f.read_text(errors="replace"))]
    w = sum(r["windows"] for r in rows)
    if not w:
        return {}
    return {k: sum(r[k] * r["windows"] for r in rows) / w for k in DT_KEYS if k != "windows"} | {"windows": w}


def f(v, n=1):
    return "–" if v is None else (f"{v:.{n}f}" if isinstance(v, float) else str(v))


out = open(WS / "results/r15/s3-rows.jsonl", "a")
for L in sys.argv[1:]:
    rs = [r for r in runs if r.get("config") == L and not r.get("error")]
    if not rs:
        print(f"## {L}: no requests recorded\n")
        continue
    dec = agg([r for r in rs if r["scenario"] in ("longreason", "correctness")])
    ldr = agg([r for r in rs if str(r["scenario"]).startswith("ldr-")])
    allr = agg(rs)
    pr = {}
    for sz in ("8k", "32k", "64k", "120k"):
        x = [r for r in rs if r["scenario"] == "speed" and r["item"] == sz]
        if x:
            r = x[-1]
            pr[sz] = (r.get("ttft_s"), (r.get("engine") or {}).get("decode_tps"))
    t0 = min(r["started"] for r in rs)[:19]
    t1 = max(r["started"] for r in rs)[:19]
    g = guard(L)
    s = ssd(t0, t1)
    nd = needle(L)
    sc, sw = split(L, "cold"), split(L, "warm")
    dt = dtiming(L)
    row = dict(label=L, dec=dec, ldr=ldr, all=allr, prompts=pr, guard=g, ssd=s, needle=nd, split_cold=sc, split_warm=sw, dtiming=dt)
    out.write(json.dumps(row) + "\n")
    print(f"## {L}  ({t0} → {t1})\n")
    print("| metric | decode screen items | LDR screen | all requests |\n|---|---|---|---|")
    for k, name, n in (("tps", "decode tok/s", 1), ("ms_round", "ms per round", 1), ("tpr", "tokens per round", 2),
                       ("acc", "acceptance", 3), ("share_5080", "5080 share of expert lookups", 3),
                       ("share_card2", "4060 Ti share", 3), ("share_cpu", "CPU share (RAM + files)", 3),
                       ("drive_gib_round", "GiB read from the drive per round (OS)", 4),
                       ("file_gib_round", "GiB of expert reads per round (file tier)", 4)):
        print(f"| {name} | {f(dec.get(k), n)} | {f(ldr.get(k), n)} | {f(allr.get(k), n)} |")
    print("\n| prompt | time to first token s | decode after it tok/s |\n|---|---|---|")
    for sz, (tt, dd) in pr.items():
        print(f"| {sz} | {f(tt, 2)} | {f(dd, 1)} |")
    print(f"\nmemory: min MemAvailable {f(g.get('min_memavail'), 1)} GiB, swap {f(g.get('swap0'), 2)} → max {f(g.get('swap_max'), 2)} GiB, "
          f"5080 min free {f(g.get('min_5080_free'), 0)} MiB; SSD max {s.get('ssd_max_c', '–')} °C (composite {s.get('ssd_comp_max', '–')}), "
          f"{f(s.get('ssd_read_gb'), 1)} GB read from it during the session; needle 120K: {nd[0] if nd else '–'}/{nd[1] if nd else '–'}")
    if dt:
        print(f"\nwindow split (served, STRATA_DECODE_TIMING, {dt['windows']:.0f} windows, avg T {dt['T']:.2f}): {dt['ms_w']:.1f} ms/window = "
              f"verify {dt['verify']:.1f} (the GPU's reach wait {dt['gpu_wait']:.1f} + the per-layer host {dt['host']:.1f} [CPU experts "
              f"{dt['cpu']:.1f}, plan {dt['plan']:.2f}, quantize {dt['actq']:.2f}, jobs {dt['jobs']:.2f}] + stage {dt['stage']:.1f}) + "
              f"commit/emit {dt['commit']:.2f} + draft {dt['draft']:.2f}; per layer-window: CPU experts {dt['cpu_exp']:.2f}, "
              f"VRAM hits {dt['vram_hits']:.2f}, PCIe {dt['pcie']:.2f}")
    for k, d in (("cold", sc), ("warm", sw)):
        if d:
            gpu = (d["ms_round"] - d.get("pool", 0)) if d.get("ms_round") else None
            print(f"\nsplit ({k}, CLI greedy 1,024 tokens): {f(d.get('tps'))} tok/s, {f(d.get('ms_round'), 1)} ms/round = GPU ~{f(gpu, 1)} "
                  f"+ the CPU pool {f(d.get('pool'), 1)} (of which file-tier reading {f(d.get('file_ms_round'), 1)} ms over "
                  f"{f(d.get('file_mb_round'), 1)} MB/round; the decode waited {f(d.get('fetch_wait'), 1)} ms/round in fetches); page cache "
                  f"held {f(d.get('pc_held_mb'), 0)} MB, not {f(d.get('pc_miss_mb'), 0)} MB; GPU cache hit {f(d.get('gpu_hit'), 3)}; "
                  f"min MemAvailable {f(d.get('minavail'), 1)} GiB, swap {f(d.get('maxswap'), 2)} GiB")
    print()
