#!/usr/bin/env python3
"""a2_table.py LABEL... — round 8 A.2: the prompt path's shares from STRATA_PREFILL_TIMING (logs/r8/prof/LABEL.err),
grouped the way the Phase A question asks: GDN mixer (projections in, conv + gates, recurrence, out projection), expert
GEMMs (gate/up, down), expert group copies (the per-expert gather 'dequant' + 'gather' + waiting for the stream copies),
QSA (projections, indexer, selection, attention), the draft-layer pass (host, after each chunk), n-gram work (PLE GPU +
host), hyper-connection reads, the rest."""
import re
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
GROUPS = {
    "GDN mixer (proj in + conv/gates + recurrence + out proj)": ["gdn", "gdn conv+gates", "gdn recurrence", "gdn out proj"],
    "  of which the recurrence": ["gdn recurrence"],
    "expert GEMMs (MMQ gate/up + down)": ["gemm gate/up", "gemm down"],
    "expert group copies (gather + 'dequant' + wait for stream copies)": ["dequant", "gather", "wait copy"],
    "QSA (proj + indexer + select + attn)": ["qsa proj", "qsa indexer", "qsa select", "qsa attn"],
    "hyper-connection reads": ["hc read"],
    "router + shared expert + combine": ["router+shared", "combine", "host grouping"],
    "embed + steps (per-chunk setup, first-use loading)": ["embed+steps"],
    "n-gram (PLE) on the GPU": ["ple"],
    "KV stage": ["kv stage"],
}


def parse(label):
    t = (WS / f"logs/r8/prof/{label}.err").read_text(errors="replace")
    m = re.search(r"prefill timing: (\d+) tokens, GPU timeline (\d+) ms, wall (\d+) ms, host staging (\d+) ms: (.*)", t)
    if not m:
        return None
    d = {"tokens": int(m[1]), "gpu": float(m[2]), "wall": float(m[3]), "staging": float(m[4])}
    for name, ms in re.findall(r"([a-z+/ ]+?) (\d+) \([\d.]+%\)", m[5]):
        d[name.strip()] = float(ms)
    h = re.search(r"after each chunk \(the draft layer, progress\) (\d+) ms, PLE (\d+) ms", t)
    if h:
        d["draft layer (host, after each chunk)"] = float(h[1])
        d["PLE (host)"] = float(h[2])
    return d


def main():
    runs = {L: parse(L) for L in sys.argv[1:]}
    runs = {k: v for k, v in runs.items() if v}
    print("| share of the prompt | " + " | ".join(f"{L} ({v['tokens']} tok, wall {v['wall'] / 1000:.2f} s)" for L, v in runs.items()) + " |")
    print("|---|" + "---|" * len(runs))
    for g, keys in GROUPS.items():
        cells = []
        for L, v in runs.items():
            ms = sum(v.get(k, 0.0) for k in keys)
            cells.append(f"{ms:.0f} ms ({ms / v['gpu'] * 100:.1f} % of GPU)")
        print(f"| {g} | " + " | ".join(cells) + " |")
    for k in ("draft layer (host, after each chunk)", "PLE (host)"):
        print(f"| {k} | " + " | ".join(f"{v.get(k, 0):.0f} ms ({v.get(k, 0) / v['wall'] * 100:.1f} % of wall)" for v in runs.values()) + " |")


if __name__ == "__main__":
    main()
