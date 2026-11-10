#!/usr/bin/env python3
"""sweep_report.py OUTDIR - Karl's upgrade-pricing sweep (11-03): one table per model, an arm per row, from
work/sweep/sweep-gap.sh's output (OUTDIR/ds-ARM -> results/ds41/tuning/..., OUTDIR/splice-ARM).

Per arm: experts in VRAM (the engine's start lines), decode = the mean of W1-W3's decode_tps (client clock, 1 pass),
prompt = P4K / P20K prompt_tps, and the decode requests' (W1-W3) tier split of the routed experts:
  DeepSeek: GPU = 100 - the engine's "CPU lane N%" (routed experts run on the GPUs: from VRAM or read from the RAM store over PCIe - not split by the engine); SSD = the engine's disk bytes read per token / the expert size
            (132 GB / 15,360 = 8.59 MB) / 240 routed experts per token (6 x 40 layers) - this counts every disk read of
            the engine (the Engram's too), so it is an upper bound; CPU lane from RAM (store + page cache) = the CPU lane - SSD.
  The splice: 5080 cache = hits / routed, PCIe or the 4060 Ti = "more read" / routed (the engine does not separate the
            two), CPU = (lookups - hits) / routed; SSD = disk bytes / the Q5 expert size (91.6 GiB / 24,576 = 4.00 MB) /
            routed; RAM = CPU - SSD. SSD GB per token = disk bytes / completion tokens (both models).
"""
import json
import os
import re
import statistics as st
import sys

O = sys.argv[1]
DS_EXP_B, DS_PER_TOK = 132e9 / 15360, 240
SP_EXP_B = 91.6 * 2**30 / 24576


def jl(p):
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def common(d):
    recs = {(r["id"], r.get("rep")): r for r in jl(f"{d}/ds41.jsonl")}
    disk = jl(f"{d}/disk.jsonl")
    dec = [r for k, r in recs.items() if k[0].startswith(("W1", "W2", "W3")) and r.get("decode_tps")]   # failed requests: no rate
    out = {"decode": st.mean(r["decode_tps"] for r in dec) if dec else None, "n_decode": len(dec)}
    for pid in ("P4K", "P20K"):
        v = [r["prompt_tps"] for k, r in recs.items() if k[0] == pid and r.get("prompt_tps")]
        out[pid] = st.mean(v) if v else None
    ddec = [x for x in disk if x["id"].startswith(("W1", "W2", "W3"))]
    rb = sum(x["disk_read_gb"] or 0 for x in ddec) * 1e9; tok = sum(x["completion_tokens"] or 0 for x in ddec)
    out["ssd_gb_tok"] = rb / 1e9 / tok if tok else None
    for pid in ("P4K", "P20K"):
        v = [x["disk_read_gb"] for x in disk if x["id"] == pid and x.get("disk_read_gb") is not None]
        out[pid + "_ssd_gb"] = st.mean(v) if v else None
    return out, ddec, rb, tok


def ds_arm(d):
    out, ddec, rb, tok = common(d)
    log = open(f"{d}/engine-run.log", errors="replace").read() if os.path.exists(f"{d}/engine-run.log") else ""
    cards = re.findall(r"CUDA(\d) layers \[[\d, ]+\][^:]*: weights [\d.]+ GB, experts ([\d.]+) GB \((\d+) of (\d+) in VRAM\)", log)
    st_ = re.findall(r"RAM store: (\d+) of the profile's hottest experts read in \(([\d.]+) GB\)", log)
    out["vram_experts"] = sum(int(c[2]) for c in cards[-2:]) if cards else None
    out["store_experts"] = int(st_[-1][0]) if st_ else None
    lanes = [v for x in ddec for v in ((x.get("tier_lines") or {}).get("cpu_lane_pct") or [])]
    if lanes and tok:
        lane = st.mean(lanes) / 100
        ssd = min(rb / DS_EXP_B / tok / DS_PER_TOK, lane)
        out.update(vram=1 - lane, ssd=ssd, ram=lane - ssd)
    return out


def sp_arm(d):
    out, ddec, rb, tok = common(d)
    log = open(f"{d}/engine.log", errors="replace").read() if os.path.exists(f"{d}/engine.log") else ""
    m0 = re.findall(r"expert cache (\d+) slots", log); m1 = re.findall(r"CUDA1: (\d+) additional experts", log)
    out["vram_experts"] = (int(m0[-1]) if m0 else 0) + (int(m1[-1]) if m1 else 0)
    out["slots"] = f"{m0[-1] if m0 else '?'} + {m1[-1] if m1 else 0}"
    H = L = Pp = 0
    for x in ddec:
        for h, l, p in ((x.get("tier_lines") or {}).get("hits") or []):
            H += h; L += l; Pp += p
    R = L + Pp
    if R:
        ssd = min(rb / SP_EXP_B / R, (L - H) / R)
        out.update(vram=H / R, peer=Pp / R, ssd=ssd, ram=(L - H) / R - ssd)
    return out


def f(x, pct=False, nd=1):
    return "-" if x is None else (f"{100 * x:.1f} %" if pct else f"{x:,.{nd}f}")


def main():
    lines = ["# Upgrade-pricing sweep (11-03): speed against the experts held in VRAM, 1 pass each", ""]
    lines += ["## DeepSeek V4.1 Flash, the daily config (15,360 experts)", "",
              "| arm | experts in VRAM | RAM store | on the GPU (VRAM or RAM over PCIe) | CPU lane from RAM | SSD (upper bound) | SSD GB / token | decode | P4K | P20K | P20K SSD GB |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for arm in ("on-v10", "on-v075", "on-v05", "off-v10", "off-v075", "off-v05"):
        d = f"{O}/ds-{arm}"
        if not os.path.isdir(d):
            lines.append(f"| {arm} | (not run) |||||||||| "); continue
        a = ds_arm(d)
        lines.append(f"| {arm} | {f(a.get('vram_experts'), nd=0)} | {f(a.get('store_experts'), nd=0)} | {f(a.get('vram'), True)} | "
                     f"{f(a.get('ram'), True)} | {f(a.get('ssd'), True)} | {f(a.get('ssd_gb_tok'), nd=3)} | {f(a['decode'])} | "
                     f"{f(a['P4K'], nd=0)} | {f(a['P20K'], nd=0)} | {f(a.get('P20K_ssd_gb'), nd=2)} |")
    lines += ["", "## Round 15's splice on the P028x engine (24,576 experts, Q5 ~4.0 MB each)", "",
              "| arm | slots 5080 + 4060 Ti | 5080 cache | PCIe / 4060 Ti | RAM | SSD | SSD GB / token | decode | P4K | P20K | P20K SSD GB |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    # 11-03: SPLICE_PREFIX picks the splice run (splice = the first gap at 64 GiB RAM, guard-stopped; splice58 = the rerun)
    pre = os.environ.get("SPLICE_PREFIX", "splice")
    lines[-3] = lines[-3].replace("each)", f"each) - {pre}")
    for arm in ("on-100", "on-75", "on-50", "off-100", "off-75", "off-50"):
        d = f"{O}/{pre}-{arm}"
        if not os.path.isdir(d):
            lines.append(f"| {arm} | (not run) |||||||||| "); continue
        a = sp_arm(d)
        lines.append(f"| {arm} | {a.get('slots')} | {f(a.get('vram'), True)} | {f(a.get('peer'), True)} | {f(a.get('ram'), True)} | "
                     f"{f(a.get('ssd'), True)} | {f(a.get('ssd_gb_tok'), nd=3)} | {f(a['decode'])} ({a.get('n_decode', 0)} of 3) | "
                     f"{f(a['P4K'], nd=0)} | {f(a['P20K'], nd=0)} | {f(a.get('P20K_ssd_gb'), nd=2)} |")
    open(f"{O}/sweep{'' if pre == 'splice' else '-' + pre}.md", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
