#!/usr/bin/env python3
"""gr_compare.py DIR — round 9 Phase 0.3: outputs of gr_bench (v5 / v3 / old) compared per T and apply; timing table
from the .out files (medians over the runs of each mode)."""
import re, sys, statistics
from pathlib import Path
import numpy as np
D = Path(sys.argv[1]); N, HC, LR = 2560, 4, 320
def parts(path):
    a = np.fromfile(path, dtype=np.float32); o = 0; res = {}
    for apply in (0, 1):
        for T in range(1, 9):
            for name, n in (("lo", T * LR), ("rs", T * HC), ("inject", T * HC), ("mixed", T * N), ("R", T * N * HC)):
                res[(apply, T, name)] = a[o:o + n]; o += n
    assert o == a.size, (o, a.size)
    return res
MODES = [m for m in ("v5", "v3", "old", "plain") if (D / f"{m}-1.bin").exists()]
P = {m: parts(D / f"{m}-1.bin") for m in MODES}
for m in MODES:           # determinism: run 2 = run 1 bitwise
    q = parts(D / f"{m}-2.bin"); same = all(np.array_equal(P[m][k].view(np.uint32), q[k].view(np.uint32)) for k in q)
    print(f"{m}: run 1 vs run 2 bit-identical: {same}")
for x, y in [p for p in (("v3", "v5"), ("old", "v5"), ("v3", "old"), ("plain", "old"), ("plain", "v5")) if p[0] in P and p[1] in P]:
    worst = {}
    for k in P[x]:
        a, b = P[x][k].astype(np.float64), P[y][k].astype(np.float64)
        same = int(np.sum(P[x][k].view(np.uint32) == P[y][k].view(np.uint32)))
        rel = np.max(np.abs(a - b) / np.maximum(np.abs(a), 1e-6)) if a.size else 0.0
        w = worst.setdefault(k[2], [0, 0, 0.0]); w[0] += same; w[1] += a.size; w[2] = max(w[2], float(rel))
    print(f"{x} vs {y}: " + "; ".join(f"{n} {s}/{t} identical, max rel {r:.2e}" for n, (s, t, r) in worst.items()))
tim = {}
for f in sorted(D.glob("*.out")):
    m = f.stem.split("-")[0]
    for l in f.read_text().splitlines():
        r = re.match(r"apply=(\d) T=(\d) cold_us ([\d.]+) warm_us ([\d.]+)", l)
        if r: tim.setdefault((m, int(r[1]), int(r[2])), []).append((float(r[3]), float(r[4])))
print("\n| T | apply | " + " | ".join(f"{m} cold / warm µs" for m in MODES) + " | v3 vs v5 (cold) |")
print("|---|---|" + "---|" * len(MODES) + "---|")
for apply in (1, 0):
    for T in range(1, 9):
        c = {m: (statistics.median(x[0] for x in tim[(m, apply, T)]), statistics.median(x[1] for x in tim[(m, apply, T)])) for m in MODES}
        print(f"| {T} | {apply} | " + " | ".join(f"{c[m][0]:.1f} / {c[m][1]:.1f}" for m in MODES) + f" | {100*(c['v3'][0]/c['v5'][0]-1):+.1f} % |")
