#!/usr/bin/env python3
"""stage_table.py ELOG [LABEL...] — round 10 Phase 0.2 / C.3: upstream's per-request decode timing and GPU stage stamps
(STRATA_DECODE_TIMING=1 + STRATA_VERIFY_PROFILE=1) from an engine log, per request, and grouped into the stages of your
list (router / ring / hits, expert inputs, routed experts, shared expert, GDN mixer, QSA mixer, hyper-connection reads,
head, n-gram block, draft round, commit, wait for the CPU), ms per window.  LABELs name the requests in log order
(e.g. math code ldr math code ldr).  The stamps cost ~2 us each (each stage includes one), so the GPU stage total runs
a little over an untraced window."""
import re
import sys
from collections import defaultdict
from pathlib import Path

log = Path(sys.argv[1]).read_text(errors="replace")
labels = sys.argv[2:]
TIM = re.compile(r"strata decode timing: (\d+) windows, avg T ([\d.]+), ([\d.]+) tokens/window, ([\d.]+) ms/window = verify ([\d.]+) "
                 r"\(GPU-reach wait ([\d.]+) \+ per-layer host ([\d.]+) \[plan ([\d.]+) actq ([\d.]+) jobs ([\d.]+) CPU ([\d.]+)\] \+ stage ([\d.]+)\) "
                 r"\+ commit/emit ([\d.]+) \+ draft ([\d.]+)")
STG = re.compile(r"strata decode GPU stages \(ms/window\): GDN layers:(.*?) \| QSA layers:(.*?) \| total ([\d.]+) ms/window")
HLP = re.compile(r"strata serve: CUDA1: .*?host (\d+) ms staging\+launching, (\d+) ms waiting")
PAIR = re.compile(r"\s*(.+?) (\d+\.\d+)(?=\s{1,3}\S|\s*$)")


def pairs(seg):
    out, rest = {}, seg.strip()
    for m in re.finditer(r"([^\d][^|]*?) (\d+\.\d+)", " " + rest):
        out[m.group(1).strip()] = float(m.group(2))
    return out


reqs, cur = [], {}
for line in log.split("\n"):
    if (m := TIM.search(line)):
        cur = {"windows": int(m[1]), "T": float(m[2]), "tpw": float(m[3]), "ms_win": float(m[4]), "verify": float(m[5]),
               "gpu_reach_wait": float(m[6]), "layer_host": float(m[7]), "cpu": float(m[11]), "commit": float(m[13]),
               "draft": float(m[14])}
    elif (m := STG.search(line)) and cur:
        cur["gdn"], cur["qsa"], cur["gpu_total"] = pairs(m[1]), pairs(m[2]), float(m[3])
    elif (m := HLP.search(line)) and cur:
        cur["helper_wait_ms"] = int(m[2])
        reqs.append(cur)
        cur = {}
if labels:
    for r, lab in zip(reqs, labels):
        r["label"] = lab


def stages(r):
    g, q = r["gdn"], r["qsa"]
    both = lambda k: g.get(k, 0) + q.get(k, 0)  # noqa: E731
    hc0 = both("hc0 norm") + both("hc0 down") + both("hc0 up")
    hc0_per_layer = hc0  # the FFN read (hc-read1) runs the same kernels: estimated as hc-read0's time
    out = {
        "hyper-connection reads (mixer read measured, FFN read = same estimate)": 2 * hc0_per_layer,
        "router / ring / hits (hc-read1+router minus the FFN read; waitA = the pool's plan)": both("hc-read1+router") - hc0_per_layer + both("waitA"),
        "shared expert + expert inputs (shared+quant)": both("shared+quant"),
        "routed experts on the 5080 (VRAM hits)": both("VRAM hits"),
        "PCIe call + its flag wait (empty at --pcie-frac 0)": both("PCIe grp") + both("waitB"),
        "wait for the CPU (waitCPU)": both("waitCPU"),
        "CPU rows + combine": both("copy+combine"),
        "GDN mixer (36 layers)": sum(g.get(k, 0) for k in ("q8+qkv/q-idx gemv", "conv", "ab", "z", "rec", "gate", "out-proj")),
        "QSA mixer (12 layers)": sum(q.get(k, 0) for k in ("q8+kv-idx", "k/v+norm-rope", "kv+idx append", "q+q-idx", "scores+topk",
                                                           "kv-resolve", "attention", "gate", "out-proj")),
        "head": both("head"),
        "gaps between layers": both("(gap)"),
    }
    return out


print("| request | windows | avg T | tok/window | ms/window (host) | GPU stage total | draft round (host) | commit (host) | host waits for helper |")
print("|---|---|---|---|---|---|---|---|---|")
for r in reqs:
    print(f"| {r.get('label', '?')} | {r['windows']} | {r['T']:.2f} | {r['tpw']:.2f} | {r['ms_win']:.2f} | {r['gpu_total']:.2f} | "
          f"{r['draft']:.2f} | {r['commit']:.2f} | {r.get('helper_wait_ms', 0)} ms |")
groups = defaultdict(list)
for r in reqs:
    groups[r.get("label", "?")].append(r)
names = list(stages(reqs[0]).keys()) if reqs else []
print("\n| stage (ms per window) | " + " | ".join(groups) + " |")
print("|---|" + "---|" * len(groups))
for n in names:
    print(f"| {n} | " + " | ".join(f"{sum(stages(r)[n] for r in rs) / len(rs):.2f}" for rs in groups.values()) + " |")
print("| draft round (the MTP layer after the window, host clock) | " + " | ".join(f"{sum(r['draft'] for r in rs) / len(rs):.2f}" for rs in groups.values()) + " |")
print("| commit + emit (host; the commit graph runs beside the draft) | " + " | ".join(f"{sum(r['commit'] for r in rs) / len(rs):.2f}" for rs in groups.values()) + " |")
print("| **window, host clock** | " + " | ".join(f"**{sum(r['ms_win'] for r in rs) / len(rs):.2f}**" for rs in groups.values()) + " |")
