#!/bin/bash
# p53mt.sh LABEL CONFIG.json [N] — round 13 Part 5.3 (report only): do the pinned long-prompt runs repeat with
# STRATA_IQ_MT_MIN=1 (the multi-token CPU expert kernels for every group size, #152)? Round 12 (A8 drift): 6 identical
# pinned runs (exact sampling off, seed 11 / T 1.0 / 0.95 / 20, the 16,110-token LDR prompt, 96 new tokens, exact7's pins,
# warm page cache) gave 3 different outputs. Here N runs per arm, alternating default / MT_MIN=1; count distinct outputs.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
L=$1 CFG=$2 N=${3:-6}
S='--seed 11 --temperature 1.0 --top-p 0.95 --top-k 20'
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 3500"
for i in $(seq 1 $N); do
  for arm in def mt1; do
    if [ $arm = mt1 ]; then E="STRATA_SPEC_EXACT=0 STRATA_IQ_MT_MIN=1"; else E="STRATA_SPEC_EXACT=0"; fi
    COLD=0 ENVX="$E" PROF_SAMPLING="$S" work/r13/run.sh $L-$arm-$i $CFG ldrsyn20k 96 $X > /dev/null
  done
done
.venv/bin/python - $L $N <<'PY'
import sys
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/r13")
from p0_table import parse
L, N = sys.argv[1], int(sys.argv[2])
for arm in ("def", "mt1"):
    h = [parse(f"{L}-{arm}-{i}").get("out") for i in range(1, N + 1)]
    t = [parse(f"{L}-{arm}-{i}").get("tps") for i in range(1, N + 1)]
    print(f"{arm}: {len(set(h))} distinct outputs in {N} runs: {' '.join(h)}; decode tok/s {' '.join(f'{x:.1f}' for x in t if x)}")
PY
