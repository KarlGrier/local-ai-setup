#!/bin/bash
# grbench10.sh — round 9, v0.1.32: the hyper-connection read micro-benchmark against the PORT's kernel library (strata-r10):
# v5 (ours) / v3 / old (= #315's staged, upstream's default) / plain, alternated v5 v3 old plain plain old v3 v5.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source work/r10/env.sh
S=$WS/strata-r10; D=$WS/results/r10/grbench10; mkdir -p $D tmp/r10/grbench10
/usr/local/cuda-13.3/bin/nvcc -O2 -std=c++17 -arch=sm_120 -I$S/include -o tmp/r10/grbench10/gr_bench10 work/r10/gr_bench10.cu \
  $S/build/libstrata_kernels.a $S/build/libstrata_core.a -lcuda 2>&1 | grep -v 'warning #' | head -5
for m in v5 v3 old plain plain old v3 v5; do
  n=$([ -f $D/$m-1.bin ] && echo 2 || echo 1)
  .venv/bin/python work/r10/guard.py grbench10-$m-$n -- tmp/r10/grbench10/gr_bench10 $m $D/$m-$n.bin > $D/$m-$n.out 2>&1; echo "$m run $n exit $?"
done
.venv/bin/python work/r10/gr_compare.py $D | tee $D/summary.md
