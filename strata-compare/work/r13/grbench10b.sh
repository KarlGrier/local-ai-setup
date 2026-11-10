#!/bin/bash
# grbench10b.sh — round 9: re-run of grbench10.sh's "old" (= #315's checked variant) and "plain" modes WITH fused_gr_check()
# (the first run skipped the check, so "old" ran the plain read); v5 / v3 results copied from grbench10.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source work/r13/env.sh
S=$WS/strata-r10; D=$WS/results/r13/grbench10b; mkdir -p $D
for m in v5 v3; do cp results/r13/grbench10/$m-1.bin results/r13/grbench10/$m-2.bin results/r13/grbench10/$m-1.out results/r13/grbench10/$m-2.out $D/; done
/usr/local/cuda-13.3/bin/nvcc -O2 -std=c++17 -arch=sm_120 -I$S/include -o tmp/r13/grbench10/gr_bench10b work/r13/gr_bench10.cu \
  $S/build/libstrata_kernels.a $S/build/libstrata_core.a -lcuda 2>&1 | grep -v 'warning #' | head -5
for m in old plain plain old; do
  n=$([ -f $D/$m-1.bin ] && echo 2 || echo 1)
  .venv/bin/python work/r13/guard.py grbench10b-$m-$n -- tmp/r13/grbench10/gr_bench10b $m $D/$m-$n.bin > $D/$m-$n.out 2>&1; echo "$m run $n exit $?"; grep -m1 'strata hc' $D/$m-$n.out
done
.venv/bin/python work/r13/gr_compare.py $D | tee $D/summary.md
