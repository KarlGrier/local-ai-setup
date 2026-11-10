#!/bin/bash
# clusterfix.sh — round 10 (v0.1.36 cluster kernels): fixed-computation decode timing, STRATA_QSA_CLUSTER on vs off, on
# the served flags (configs/V36.json: adaptive tier + deterministic landing), sampled at T 1.0 / 0.95 / 20 with a fixed
# seed so both arms produce the same tokens (checked by hash). Contexts: short (math prompt, 1,024 new), 32K (512 new),
# 112K (512 new). Order per context: on off off on on off. Through the queue.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
S='--seed 11 --temperature 1.0 --top-p 0.95 --top-k 20'
for spec in "short math 1024" "32k 32k 512" "112k tf-long112k.prompt 512"; do
  set -- $spec; C=$1 T=$2 N=$3; i=0
  for arm in 1 0 0 1 1 0; do
    i=$((i + 1))
    COLD=0 ENVX="STRATA_QSA_CLUSTER=$arm" PROF_SAMPLING="$S" work/r11/run.sh cfx-$C-$arm-$i configs/V36.json $T $N > /dev/null
  done
done
.venv/bin/python - <<'PY' | tee results/r11/ab-v36-cluster-fixed.md
import sys, statistics as st
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/r11")
from p0_table import parse
print("| context | arm | output hash per run | ms per verify round per run | mean | decode tok/s mean |\n|---|---|---|---|---|---|")
res = {}
for C in ("short", "32k", "112k"):
    for arm, name in (("0", "cluster off"), ("1", "cluster on")):
        ds = [parse(f"cfx-{C}-{arm}-{i}") for i in range(1, 7) if (arm == "1") == (i in (1, 4, 5))]
        ms = [d.get("ms_round", 0) for d in ds]; tps = [d.get("tps", 0) for d in ds]
        res[(C, arm)] = st.mean(ms)
        print(f"| {C} | {name} | {' '.join(d['out'] for d in ds)} | {' / '.join(f'{m:.2f}' for m in ms)} | **{st.mean(ms):.2f}** | {st.mean(tps):.1f} |")
print()
for C in ("short", "32k", "112k"):
    print(f"- {C}: ms per verify round, cluster on vs off: {100 * (res[(C, '1')] / res[(C, '0')] - 1):+.2f} %")
PY
