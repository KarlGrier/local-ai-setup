#!/usr/bin/env python3
"""b3_table.py BENCH.txt native_mmvq.cu — B.3's rows-a-warp table re-derived from `mmvq_il_parity --bench` on this
machine (Round 11's rule): per format, columns (1-4) and row class (out < 2048 / 4096 / 8192 / 12288 / more), sum each
kernel's time over the bench's shapes of that class; take the fastest of native_mmvq (0) / 1 / 2 / 4 rows a warp, but
only when it is at least 3 % faster than native_mmvq - otherwise 0. Prints the derived table, the compiled one (kIlRows
in native_mmvq.cu) and the cells that differ. Every choice computes the same bits (mmvq_il_parity), so a different
table changes speed only. NOTE: the bench's shapes are mmvq_il_parity.cu's list (this model's projections); on a new
model, set that list to its projection sizes first (bringup/RUNBOOK.md, stage b3table)."""
import re
import sys
from collections import defaultdict

bench, src = sys.argv[1], sys.argv[2]
TYPES = {"IQ4_XS": 23, "Q4_K": 12, "Q5_K": 13, "Q6_K": 14, "Q8_0": 8, "IQ3_S": 21}
cls_of = lambda n: 0 if n < 2048 else 1 if n < 4096 else 2 if n < 8192 else 3 if n < 12288 else 4  # noqa: E731
tot = defaultdict(lambda: defaultdict(float))
pat = re.compile(r"BENCH (\S+)\s+(\d+) ->\s+(\d+) .*?cols (\d): mmvq\s+([\d.]+)\s+r1\s+([\d.]+)\s+r2\s+([\d.]+)\s+r4\s+([\d.]+)")
for line in open(bench, errors="replace"):
    m = pat.search(line)
    if not m:
        continue
    t, n_in, n_out, c = m[1], int(m[2]), int(m[3]), int(m[4])
    key = (t, c, cls_of(n_out))
    for name, v in zip(("0", "1", "2", "4"), m.groups()[4:8]):
        tot[key][name] += float(v)
derived = {}
for (t, c, k), d in tot.items():
    best = min(d, key=d.get)
    derived[(t, c, k)] = int(best) if best != "0" and d[best] <= 0.97 * d["0"] else 0
s = open(src, errors="replace").read()
compiled = {}
for t, rows in re.findall(r"\{(\d+), \{(\{[^}]*\}, \{[^}]*\}, \{[^}]*\}, \{[^}]*\})\}\}", s):
    name = {v: k for k, v in TYPES.items()}.get(int(t), t)
    for c, row in enumerate(re.findall(r"\{([^}]*)\}", rows), 1):
        for k, v in enumerate(int(x) for x in row.split(",")):
            compiled[(name, c, k)] = v
diff = [(key, compiled.get(key), v) for key, v in sorted(derived.items()) if compiled.get(key) != v]
print("| format | cols | class (rows out) | derived | compiled |\n|---|---|---|---|---|")
for key, v in sorted(derived.items()):
    print(f"| {key[0]} | {key[1]} | {['<2048', '<4096', '<8192', '<12288', '>=12288'][key[2]]} | {v} | {compiled.get(key)} |")
print(f"b3 table: {len(derived)} cells measured, {len(diff)} differ from the compiled table"
      + (": " + ", ".join(f"{k[0]} c{k[1]} class{k[2]} {a}->{b}" for k, a, b in diff[:12]) if diff else " (keep it)"))
