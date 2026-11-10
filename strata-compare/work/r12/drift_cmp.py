#!/usr/bin/env python3
"""drift_cmp.py LABEL N — round 12 A8: the oracle files of N identical runs (drift.sh): per run the first line that differs
from run 1 (V12 = a target row, D12 = a draft step), the decode window it belongs to, and for the first D12 that differs
the largest raw-logit difference among the shared top-64 ids."""
import sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
L, N = sys.argv[1], int(sys.argv[2])
runs = [[l.rstrip("\n") for l in open(WS / f"tmp/r12/drift-{L}-{i}.txt") if l.startswith(("V12", "D12"))] for i in range(1, N + 1)]
ref = runs[0]
for i, r in enumerate(runs[1:], 2):
    first = next((k for k in range(min(len(ref), len(r))) if ref[k] != r[k]), None)
    if first is None:
        print(f"run {i}: identical to run 1 ({len(r)} lines)" + ("" if len(r) == len(ref) else f" but length {len(r)} vs {len(ref)}"))
        continue
    nv = sum(1 for l in ref[:first] if l.startswith("V12"))
    a, b = ref[first], r[first]
    msg = f"run {i}: first difference at line {first} ({a.split()[0]}, after {nv} identical verify windows)"
    if a.startswith("D12") and b.startswith("D12"):
        la = dict(kv.split(":") for kv in a.split(" | L ")[1].split(","))
        lb = dict(kv.split(":") for kv in b.split(" | L ")[1].split(","))
        common = set(la) & set(lb)
        d = max((abs(float(la[k]) - float(lb[k])) for k in common), default=float("nan"))
        msg += f"; same draft token: {a.split()[3] == b.split()[3]}; max |raw logit diff| over {len(common)} shared ids {d:.3g}; gate {a.split()[4]} vs {b.split()[4]}"
    else:
        msg += f"; {a[:90]} | vs | {b[:90]}"
    print(msg)
