#!/usr/bin/env python3
"""fork_align.py OURS.out FORK.out [OURS2.out FORK2.out ...] — round 10 C.3: our GPU stage stamps (upstream's
STRATA_VERIFY_PROFILE=1, printed by the trace build's CLI stats) next to Eddoursul's fork's --window-profile, both from
CLI runs on the same prompt, aligned to your stage list, ms per verify window.  Also the host-side lines both print
(verify window, mtp) for the draft round and the commit.  Each stamped stage includes one ~2 us stamp in both."""
import re
import sys
from pathlib import Path


def ours(path):
    t = Path(path).read_text(errors="replace")
    m = re.search(r"GPU stages \(ms/window\):\s*GDN layers:(.*?) \| QSA layers:(.*?) \| total ([\d.]+) ms/window over (\d+)", t)
    if not m:
        return None

    def pairs(seg):
        return {k.strip(): float(v) for k, v in re.findall(r"([^\d][^|]*?) (\d+\.\d+)", " " + seg.strip())}
    g, q = pairs(m[1]), pairs(m[2])
    both = lambda k: g.get(k, 0) + q.get(k, 0)  # noqa: E731
    hc0 = both("hc0 norm") + both("hc0 down") + both("hc0 up")
    d = {"total": float(m[3]), "windows": int(m[4])}
    d["hyper-connection reads"] = 2 * hc0                                  # the FFN read estimated as the mixer read
    d["router / ring / hits"] = both("hc-read1+router") - hc0
    d["wait for the pool's plan"] = both("waitA")
    d["shared expert + expert inputs"] = both("shared+quant")
    d["routed experts (VRAM)"] = both("VRAM hits")
    d["routed experts (PCIe stage)"] = both("waitB") + both("PCIe grp")
    d["wait for the CPU"] = both("waitCPU")
    d["CPU rows + combine"] = both("copy+combine")
    d["GDN mixer"] = sum(g.get(k, 0) for k in ("q8+qkv/q-idx gemv", "conv", "ab", "z", "rec", "gate", "out-proj"))
    d["QSA mixer"] = sum(q.get(k, 0) for k in ("q8+kv-idx", "k/v+norm-rope", "kv+idx append", "q+q-idx", "scores+topk",
                                               "kv-resolve", "attention", "gate", "out-proj"))
    d["head"] = both("head")
    d["gaps"] = both("(gap)")
    host(t, d)
    return d


def host(t, d):
    m = re.search(r"verify window\s+wait for rings ([\d.]+)\s+pool ([\d.]+)\s+host ([\d.]+)\s+commit ([\d.]+) ms/round", t)
    if m:
        d["host: commit"] = float(m[4])
    m = re.search(r"\nmtp\s+([\d.]+) ms/round drafting", t)
    if m:
        d["host: draft round"] = float(m[1])
    m = re.search(r"speculation\s+(\d+) rounds.*?([\d.]+) tokens per round", t)
    if m:
        d["tokens per round"] = float(m[2])
    m = re.search(r"\ndecode\s+(\d+) tokens in ([\d.]+) ms\s+->\s+([\d.]+) tok/s", t)
    if m:
        d["decode tok/s"] = float(m[3])


def fork(path):
    t = Path(path).read_text(errors="replace")
    m = re.search(r"window profile\s+GPU time over (\d+) windows, ms per window: inputs ([\d.]+), head ([\d.]+), whole window "
                  r"([\d.]+); one stamp ([\d.]+) us", t)
    if not m:
        return None
    st = {k.strip(): (float(a), float(b), float(c)) for k, a, b, c in
          re.findall(r"\n  ([A-Za-z0-9 ,+]+?)\s{2,}(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)", t)}
    ms = lambda k: st.get(k, (0, 0, 0))[2]  # noqa: E731
    d = {"total": float(m[4]), "windows": int(m[1]), "window inputs": float(m[2])}
    d["hyper-connection reads"] = ms("HC read, mixer") + ms("HC read, FFN") + ms("last HC write")
    d["router / ring / hits"] = ms("router, ring, hits")
    d["wait for the pool's plan"] = ms("wait for PCIe plan")
    d["shared expert + expert inputs"] = ms("expert inputs")              # the shared expert runs beside (below)
    d["shared expert (on its own branch, beside)"] = ms("shared expert, beside")
    d["routed experts (VRAM)"] = ms("VRAM experts")
    d["routed experts (PCIe stage)"] = ms("PCIe experts")
    d["wait for the CPU"] = ms("wait for CPU")
    d["wait for the second GPU"] = ms("wait for 2nd GPU")
    d["CPU rows + combine"] = ms("rows + combine")
    gdn_us, qsa_us = st.get("mixer", (0, 0, 0))[:2]
    d["GDN mixer"] = gdn_us * 36 / 1000
    d["QSA mixer"] = qsa_us * 12 / 1000
    d["head"] = float(m[3])
    d["gaps"] = ms("stamp gap")
    host(t, d)
    return d


ROWS = ["router / ring / hits", "wait for the pool's plan", "shared expert + expert inputs",
        "shared expert (on its own branch, beside)", "routed experts (VRAM)", "routed experts (PCIe stage)",
        "wait for the CPU", "wait for the second GPU", "CPU rows + combine", "GDN mixer", "QSA mixer",
        "hyper-connection reads", "window inputs", "head", "gaps", "total", "host: draft round", "host: commit",
        "tokens per round", "decode tok/s"]
args = sys.argv[1:]
for i in range(0, len(args), 2):
    o, f = ours(args[i]), fork(args[i + 1])
    print(f"\n### {Path(args[i]).stem} vs {Path(args[i + 1]).stem} (ms per verify window)\n")
    print("| stage | ours (base) | fork | fork − ours |")
    print("|---|---|---|---|")
    for r in ROWS:
        a = None if o is None else o.get(r)
        b = None if f is None else f.get(r)
        fa = "–" if a is None else f"{a:.2f}"
        fb = "–" if b is None else f"{b:.2f}"
        dd = "" if a is None or b is None else f"{b - a:+.2f}"
        print(f"| {r} | {fa} | {fb} | {dd} |")
