#!/usr/bin/env python3
"""merge_windows.py A.route A.rec B.route B.rec [W ...] — round 7 item 4c: distinct CPU-side experts per layer in a
window whose tokens come from TWO unrelated conversations, against a window of the same size from ONE conversation.

* X.route = the fixed --dump-routing trace (patch 0010: only kept verify rows; per record int32 layer, int32 k, k int32
  ids, k float weights; within a window the records are layer-major, n_keep per layer).
* X.rec = the round-7 oracle recording of the same run (per verify-window layer: the experts the CPU pool computed and
  every routed expert) -> which experts are CPU-side: static placement (--adapt-swaps 0), so an expert that was routed
  but never computed by the CPU is in the 5080's VRAM tier or on the helper GPU.  Both conversations ran on the same
  engine and config, so their placements are the same; the union of both recordings classifies the experts.
* Same-conversation window of W tokens = W consecutive accepted tokens of A (or of B); merged window = W/2 consecutive
  tokens of A + W/2 of B.  Windows are taken at every position (stride W/2) over the common length.
Prints per W: mean distinct routed experts per layer, mean distinct CPU-side experts per layer, and the CPU-side blob
bytes per window (the pool's DRAM traffic), same-conversation vs merged."""
import json
import struct
import sys
from pathlib import Path

import numpy as np

WS = Path("/home/USER/ai-speed-testing/strata-compare")
BLOB = np.array(json.load(open(WS / "results/r6/blob-bytes.json")), dtype=np.float64)
L = 48


def load_route(p):
    """-> array (n_tokens, 48, k) of expert ids, accepted tokens in order"""
    b = Path(p).read_bytes()
    at, recs = 0, []
    while at + 8 <= len(b):
        layer, k = struct.unpack_from("<ii", b, at)
        at += 8
        ids = struct.unpack_from(f"<{k}i", b, at)
        at += 4 * k + 4 * k
        recs.append((layer, ids))
    toks, win = [], []
    prev = -1
    for layer, ids in recs:
        if layer < prev:                 # a new window
            toks += flush(win)
            win = []
        win.append((layer, ids))
        prev = layer
    toks += flush(win)
    return np.array(toks, dtype=np.int32)


def flush(win):
    if not win:
        return []
    by = {}
    for layer, ids in win:
        by.setdefault(layer, []).append(ids)
    n = len(by[0])
    if any(len(by.get(l, [])) != n for l in range(L)):
        raise SystemExit("a window without n_keep rows in every layer")
    return [[by[l][j] for l in range(L)] for j in range(n)]


def load_rec(p):
    """-> (cpu[layer] set, routed[layer] set) over the whole recording"""
    b = Path(p).read_bytes()
    at = 0
    cpu = [set() for _ in range(L)]
    routed = [set() for _ in range(L)]
    while at + 28 <= len(b):
        w, l, T, nc, nr = struct.unpack_from("<5i", b, at)
        at += 20 + 8
        c = struct.unpack_from(f"<{nc}i", b, at); at += 4 * nc
        r = struct.unpack_from(f"<{nr}i", b, at); at += 4 * nr
        cpu[l].update(c)
        routed[l].update(r)
    return cpu, routed


def stats(windows, cpu_side):
    d_all, d_cpu, byt = [], [], []
    for win in windows:                 # win: (W, 48, k)
        tot_b = 0.0
        for l in range(L):
            u = set(win[:, l, :].ravel().tolist())
            c = u & cpu_side[l]
            d_all.append(len(u))
            d_cpu.append(len(c))
            tot_b += len(c) * BLOB[l]
        byt.append(tot_b)
    return np.mean(d_all), np.mean(d_cpu), np.mean(byt) / 1e6


def main():
    a_route, a_rec, b_route, b_rec = sys.argv[1:5]
    Ws = [int(x) for x in sys.argv[5:]] or [2, 4, 6, 8]
    A, B = load_route(a_route), load_route(b_route)
    ca, ra = load_rec(a_rec)
    cb, rb = load_rec(b_rec)
    cpu_side = [ca[l] | cb[l] for l in range(L)]
    resident = [(ra[l] | rb[l]) - cpu_side[l] for l in range(L)]
    n = min(len(A), len(B))
    print(f"tokens: A {len(A)}, B {len(B)} (common {n}); CPU-side experts seen per layer: "
          f"{np.mean([len(c) for c in cpu_side]):.1f}, resident (VRAM or helper) seen: {np.mean([len(r) for r in resident]):.1f}")
    print(f"{'W':>3} {'window':<22} {'distinct routed/layer':>22} {'distinct CPU/layer':>19} {'CPU blob MB/window':>19}")
    for W in Ws:
        h = W // 2
        same_a = [A[i:i + W] for i in range(0, n - W + 1, h)]
        same_b = [B[i:i + W] for i in range(0, n - W + 1, h)]
        merged = [np.concatenate([A[i:i + h], B[i:i + h]]) for i in range(0, n - h + 1, h)]
        for name, ws in (("same conversation (A)", same_a), ("same conversation (B)", same_b),
                         ("merged A+B", merged)):
            da, dc, mb = stats(ws, cpu_side)
            print(f"{W:>3} {name:<22} {da:>22.2f} {dc:>19.2f} {mb:>19.1f}")


if __name__ == "__main__":
    main()
