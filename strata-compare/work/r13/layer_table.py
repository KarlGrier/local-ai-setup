#!/usr/bin/env python3
"""layer_table.py ENGINE_LOG_PART [--groups ldr:0-11,math:12,code:13] [--out FILE.md] — round 11 Phase 0.2: reads the
profile build's per-request blocks (upstream's "strata decode timing" + "GPU stages" lines and the MEASUREMENT
"strata R11 L.." per-layer lines, then "strata serve: prompt N tokens") and prints, per group of requests (pooled over
their windows): the stage table, the per-window sums of the CPU path's parts, and the per-layer table."""
import argparse
import re
from collections import defaultdict
from pathlib import Path

TIM = re.compile(r"strata decode timing: (\d+) windows, avg T ([\d.]+), ([\d.]+) tokens/window, ([\d.]+) ms/window = verify ([\d.]+) "
                 r"\(GPU-reach wait ([\d.]+) \+ per-layer host ([\d.]+) \[plan ([\d.]+) actq ([\d.]+) jobs ([\d.]+) CPU ([\d.]+)\] \+ stage ([\d.]+)\) "
                 r"\+ commit/emit ([\d.]+) \+ draft ([\d.]+)")
STG = re.compile(r"strata decode GPU stages \(ms/window\): GDN layers:(.*?) \| QSA layers:(.*?) \| total ([\d.]+) ms/window")
LAY = re.compile(r"strata R11 L(\d+) (.*)")
PRM = re.compile(r"strata serve: prompt (\d+) tokens = (\d+) reused .*?, (\d+) generated in (\d+) ms")
HLP = re.compile(r"strata serve: CUDA1: .*?host (\d+) ms staging\+launching, (\d+) ms waiting")
NUM = re.compile(r"([a-zA-Z][\w-]*) (-?[\d.]+)")


def pairs(seg):
    return {m.group(1).strip(): float(m.group(2)) for m in re.finditer(r"([^\d][^|]*?) (\d+\.\d+)", " " + seg.strip())}


def parse(path):
    reqs, cur = [], None
    for line in Path(path).read_text(errors="replace").split("\n"):
        if (m := TIM.search(line)):
            cur = {"windows": int(m[1]), "T": float(m[2]), "tpw": float(m[3]), "ms_win": float(m[4]), "verify": float(m[5]),
                   "reach": float(m[6]), "host": float(m[7]), "plan": float(m[8]), "actq": float(m[9]), "jobs": float(m[10]),
                   "cpu": float(m[11]), "stage": float(m[12]), "commit": float(m[13]), "draft": float(m[14]), "layers": {}}
        elif cur is not None and (m := STG.search(line)):
            cur["gdn"], cur["qsa"], cur["gpu_total"] = pairs(m[1]), pairs(m[2]), float(m[3])
        elif cur is not None and (m := LAY.search(line)):
            cur["layers"][int(m[1])] = {k: float(v) for k, v in NUM.findall(m[2])}
        elif cur is not None and (m := PRM.search(line)):
            cur.update(prompt=int(m[1]), reused=int(m[2]), gen=int(m[3]), gen_ms=int(m[4]))
            reqs.append(cur)
            cur = None
        elif (m := HLP.search(line)) and reqs:
            reqs[-1]["helper_wait_ms"] = int(m[2])
            reqs[-1]["helper_host_ms"] = int(m[1])
    return reqs


def stages(r):
    g, q = r.get("gdn", {}), r.get("qsa", {})
    both = lambda k: g.get(k, 0) + q.get(k, 0)  # noqa: E731
    hc0 = both("hc0 norm") + both("hc0 down") + both("hc0 up")
    return {
        "hyper-connection reads (both; FFN read = the mixer read's time)": 2 * hc0,
        "router / ring / hits": both("hc-read1+router") - hc0,
        "plan wait (waitA)": both("waitA"),
        "shared expert + expert inputs": both("shared+quant"),
        "routed experts on the 5080 (VRAM hits)": both("VRAM hits"),
        "PCIe stage (empty)": both("PCIe grp") + both("waitB"),
        "**wait for the CPU (waitCPU)**": both("waitCPU"),
        "CPU rows + combine": both("copy+combine"),
        "GDN mixer (36 layers)": sum(g.get(k, 0) for k in ("q8+qkv/q-idx gemv", "conv", "ab", "z", "rec", "gate", "out-proj")),
        "QSA mixer (12 layers)": sum(q.get(k, 0) for k in ("q8+kv-idx", "k/v+norm-rope", "kv+idx append", "q+q-idx",
                                                           "scores+topk", "kv-resolve", "attention", "gate", "out-proj")),
        "head": both("head"),
        "gaps": both("(gap)"),
        "GPU stage total": r.get("gpu_total", 0),
    }


LCOLS = ["cpu-entries", "cpu-experts", "reach", "host", "plan", "helper-begin", "actq", "jobs", "pool", "gu", "midq", "down",
         "park", "wake-us", "helper-finish", "waitA", "waitCPU", "vram", "shared"]


def pooled(rs, f):
    w = sum(r["windows"] for r in rs)
    return sum(f(r) * r["windows"] for r in rs) / w if w else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--groups", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    reqs = parse(a.log)
    groups = {}
    if a.groups:
        for spec in a.groups.split(","):
            name, rng = spec.split(":")
            lo, _, hi = rng.partition("-")
            groups[name] = reqs[int(lo):int(hi or lo) + 1]
    else:
        groups["all"] = reqs
    out = []
    p = out.append
    p(f"requests parsed: {len(reqs)}")
    p("\n| # | prompt | reused | generated | windows | avg T | tok/window | ms/window | GPU stage total | draft | helper wait ms |")
    p("|---|---|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(reqs):
        p(f"| {i} | {r.get('prompt')} | {r.get('reused')} | {r.get('gen')} | {r['windows']} | {r['T']:.2f} | {r['tpw']:.2f} | "
          f"{r['ms_win']:.2f} | {r.get('gpu_total', 0):.2f} | {r['draft']:.2f} | {r.get('helper_wait_ms', '')} |")
    names = list(stages(reqs[0]).keys()) if reqs else []
    p("\n### Stage table (GPU stamps, ms per window; pooled over each group's windows)\n")
    p("| stage | " + " | ".join(groups) + " |")
    p("|---|" + "---|" * len(groups))
    for n in names:
        p(f"| {n} | " + " | ".join(f"{pooled(rs, lambda r: stages(r)[n]):.2f}" for rs in groups.values()) + " |")
    for k, lab in (("draft", "draft round (host)"), ("commit", "commit + emit (host)"), ("ms_win", "**window, host clock**"),
                   ("tpw", "tokens per window")):
        p(f"| {lab} | " + " | ".join(f"{pooled(rs, lambda r: r[k]):.2f}" for rs in groups.values()) + " |")
    # CPU path per window: sums over layers
    p("\n### The CPU path, ms per window (summed over the 48 layers; pooled)\n")
    p("| part | " + " | ".join(groups) + " |")
    p("|---|" + "---|" * len(groups))
    for c in ("reach", "host", "plan", "helper-begin", "actq", "jobs", "pool", "gu", "midq", "down", "park", "helper-finish",
              "waitA", "waitCPU", "cpu-entries", "cpu-experts"):
        p(f"| {c} | " + " | ".join(f"{pooled(rs, lambda r: sum(L.get(c, 0) for L in r['layers'].values())):.3f}"
                                    for rs in groups.values()) + " |")
    p("| pool overhead = pool − gu − midq − down | " + " | ".join(
        f"{pooled(rs, lambda r: sum(L.get('pool', 0) - L.get('gu', 0) - L.get('midq', 0) - L.get('down', 0) for L in r['layers'].values())):.3f}"
        for rs in groups.values()) + " |")
    p("| mean worker wake-up (µs, per phase) | " + " | ".join(
        f"{pooled(rs, lambda r: sum(L.get('wake-us', 0) for L in r['layers'].values()) / max(1, len(r['layers']))):.1f}"
        for rs in groups.values()) + " |")
    for gname, rs in groups.items():
        if not rs or not rs[0]["layers"]:
            continue
        p(f"\n### Per layer — {gname} (ms per window; entries per window)\n")
        p("| layer | " + " | ".join(LCOLS) + " |")
        p("|---|" + "---|" * len(LCOLS))
        nl = max(max(r["layers"]) for r in rs if r["layers"]) + 1
        for l in range(nl):
            vals = []
            for c in LCOLS:
                v = pooled(rs, lambda r: r["layers"].get(l, {}).get(c, 0))
                vals.append(f"{v:.1f}" if c == "wake-us" else f"{v:.3f}")
            p(f"| {l} | " + " | ".join(vals) + " |")
    text = "\n".join(out)
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n")


if __name__ == "__main__":
    main()
