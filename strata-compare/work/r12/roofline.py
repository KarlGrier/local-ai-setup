#!/usr/bin/env python3
"""roofline.py LABEL [--bw GBPS] [--hit H] [--helper F] — round 9 A.1: per-kernel GPU time of the served decode trace
(logs/r12/prof/LABEL.sqlite, the trace engine under nsys; NVTX "window" ranges carry T) with a roofline column.

No hardware counters here (RmProfilingAdminOnly=1), so bytes and FLOPs are MODELLED from the model file:
  * dense GEMVs (native_*mmvq*, bf16 mmvf): every non-expert weight matrix is read once per window
    (GGUF tensor sizes: Q6_K / Q4_K / Q5_K / IQ4_XS / Q8_0 via mmvq, BF16 router / indexer / ssm alpha,beta via mmvf,
    the output head 521 MB via the Q6_K kernel); FLOPs = 2 x params x T;
  * hyper-connection kernels (gr_*): the BF16 hc down/up matrices, 26.2 MB per layer + the output HC;
  * the GPU's own expert kernels (native_gu / native_down): distinct VRAM-hit experts per window x their gate+up /
    down bytes; distinct = entries x a dedup factor (a routed expert shared by several tokens of the window is read
    once) - an ESTIMATE with its range stated;
  * everything else: time only (attention, GDN, norms, copies, flag waits).
Achieved GB/s = modelled bytes / kernel time; % of the measured copy bandwidth (--bw, default 870 GB/s = what a
device-to-device copy reaches on this card; measure with --measure-bw when no server runs)."""
import argparse
import collections
import sqlite3
import statistics as st
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")


def gguf_sizes():
    sys.path.insert(0, str(WS / "strata-v0115/third_party/llama.cpp/gguf-py"))
    from gguf import GGUFReader
    r = GGUFReader(str(WS / "models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf"))
    out = {}
    for t in r.tensors:
        out[t.name] = (t.tensor_type.name, int(t.n_bytes), int(t.n_elements))
    return out


def model_bytes(sz):
    """per-window bytes and params by family"""
    fam = collections.defaultdict(lambda: [0, 0])   # bytes, params
    for n, (ty, b, ne) in sz.items():
        if "exps" in n or n == "token_embd.weight" or ty == "F32":
            continue
        if n.startswith("output.weight"):
            f = "head (Q6_K mmvq)"
        elif "hc_" in n and ty == "BF16" and ("_down" in n or "_up" in n):
            f = "hyper-connection (gr_*)"
        elif ty == "BF16":
            f = "bf16 mmvf (router, indexer, ssm a/b, inject)"
        else:
            f = "quantized dense mmvq"
        fam[f][0] += b
        fam[f][1] += ne
    return fam


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("--bw", type=float, default=870.0)
    ap.add_argument("--hit", type=float, default=0.72, help="5080 VRAM hit fraction of routed entries")
    ap.add_argument("--dedup", type=float, default=0.85, help="distinct experts / hit entries in a window (T>1)")
    a = ap.parse_args()
    db = sqlite3.connect(WS / f"logs/r12/prof/{a.label}.sqlite")
    cur = db.cursor()
    strings = dict(cur.execute("SELECT id, value FROM StringIds"))
    cols = [r[1] for r in cur.execute("PRAGMA table_info(CUPTI_ACTIVITY_KIND_KERNEL)")]
    nc = "shortName" if "shortName" in cols else "demangledName"
    K = [(s, e, strings.get(n, str(n))) for s, e, n in cur.execute(f"SELECT start, end, {nc} FROM CUPTI_ACTIVITY_KIND_KERNEL ORDER BY start")]
    ncols = [r[1] for r in cur.execute("PRAGMA table_info(NVTX_EVENTS)")]
    txt = "COALESCE(text, (SELECT value FROM StringIds WHERE id = textId))" if "textId" in ncols else "text"
    pay = "int64Value" if "int64Value" in ncols else "NULL"
    W = [(s, e, p) for s, e, t, p in cur.execute(f"SELECT start, end, {txt}, {pay} FROM NVTX_EVENTS WHERE end IS NOT NULL") if t == "window"]
    W.sort()
    if not W:
        sys.exit("no window ranges")
    Ts = [p or 0 for _, _, p in W]
    nwin = len(W)
    # kernels inside windows (host NVTX ranges bound the GPU work launched in them; the GPU runs slightly later, so a
    # kernel is attributed to the window whose [start, next start) contains its start)
    starts = [s for s, _, _ in W] + [W[-1][1] + 10**9]
    per = collections.defaultdict(float)
    cnt = collections.Counter()
    j = 0
    for s, e, n in K:
        while j + 1 < len(starts) and s >= starts[j + 1]:
            j += 1
        if s < starts[0] or j >= nwin:
            continue
        per[n] += (e - s) / 1e6
        cnt[n] += 1
    wall = sum(e - s for s, e, _ in W) / 1e6 / nwin
    Tm = st.mean(Ts)
    sz = gguf_sizes()
    fam = model_bytes(sz)
    # experts: per layer and window, hit entries = T x 10 x hit; distinct = hit entries (T=1) or x dedup
    gu_b = st.mean([sz[f"blk.{l}.ffn_gate_exps.weight"][1] + sz[f"blk.{l}.ffn_up_exps.weight"][1] for l in range(48)]) / 512
    dn_b = st.mean([sz[f"blk.{l}.ffn_down_exps.weight"][1] for l in range(48)]) / 512
    ent = collections.Counter(Ts)
    distinct = sum(c * (t * 10 * a.hit * (1.0 if t <= 1 else a.dedup)) for t, c in ent.items()) / nwin * 48
    model = {
        "native_gu_kernel": (distinct * gu_b, 0),
        "native_down_kernel": (distinct * dn_b, 0),
    }
    fam_time = collections.defaultdict(float)
    for n, t in per.items():
        if "mmvq" in n and "q6_k" in n:
            fam_time["head (Q6_K mmvq)"] += t        # the head and the MTP head's subset (both Q6_K)
        elif "mmvq" in n:
            fam_time["quantized dense mmvq"] += t
        elif "mmvf" in n:
            fam_time["bf16 mmvf (router, indexer, ssm a/b, inject)"] += t
        elif n.startswith("gr_"):
            fam_time["hyper-connection (gr_*)"] += t
    print(f"trace {a.label}: {nwin} windows, mean T {Tm:.2f}, window wall {wall:.2f} ms; peak copy bandwidth {a.bw:.0f} GB/s\n")
    print("| kernel | launches/window | ms/window | share of window | µs each |")
    print("|---|---|---|---|---|")
    for n, t in sorted(per.items(), key=lambda kv: -kv[1])[:30]:
        print(f"| {n} | {cnt[n] / nwin:.1f} | {t / nwin:.3f} | {t / nwin / wall * 100:.1f} % | {t / cnt[n] * 1000:.2f} |")
    print("\n| family (modelled bytes per window) | GB/window | GFLOP/window | ms/window | achieved GB/s | % of peak |")
    print("|---|---|---|---|---|---|")
    for f, (b, ne) in sorted(fam.items(), key=lambda kv: -kv[1][0]):
        t = fam_time.get(f, 0) / nwin
        print(f"| {f} | {b / 1e9:.3f} | {2 * ne * Tm / 1e9:.2f} | {t:.3f} | {b / 1e6 / t if t else 0:.0f} | {b / 1e6 / t / a.bw * 100 if t else 0:.0f} % |")
    for n, (b, _) in model.items():
        t = per.get(n, 0) / nwin
        lo, hi = b * 0.8, b * 1.15
        print(f"| {n} (estimate: hit {a.hit:.2f}, dedup {a.dedup:.2f}) | {b / 1e9:.3f} ({lo / 1e9:.2f}–{hi / 1e9:.2f}) | – | {t:.3f} | "
              f"{b / 1e6 / t if t else 0:.0f} | {b / 1e6 / t / a.bw * 100 if t else 0:.0f} % |")


if __name__ == "__main__":
    main()
