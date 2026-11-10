#!/bin/bash
# grbench35.sh — round 10 B.3: #443's STRATA_GR_DOWN_MAX4 against our v5 and upstream's v3 (C*11's read) at 1-4 tokens (and
# 5-8 for the record): work/r10/gr_bench35.cu linked against the #443 transplant's kernel library (strata-v36b443/build,
# = the base's kernels + #443's), one mode per process, alternated, under the memory guard; outputs compared bitwise.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source work/r10/env.sh
S=$WS/strata-v36b443; D=$WS/results/r10/grbench35; mkdir -p $D tmp/r10/grbench35
/usr/local/cuda-13.3/bin/nvcc -O2 -std=c++17 -arch=sm_120 -I$S/include -o tmp/r10/grbench35/gr_bench35 work/r10/gr_bench35.cu \
  $S/build/libstrata_kernels.a $S/build/libstrata_core.a -lcuda 2>&1 | grep -v 'warning #' | head -5
for m in v5 v3 old max4 plain max4plain max4plain plain max4 old v3 v5; do
  n=$([ -f $D/$m-1.bin ] && echo 2 || echo 1)
  .venv/bin/python work/r10/guard.py grbench35-$m-$n -- tmp/r10/grbench35/gr_bench35 $m $D/$m-$n.bin > $D/$m-$n.out 2>&1; echo "$m run $n exit $?"
done
for p in "old max4" "plain max4plain"; do set -- $p; for n in 1 2; do cmp -s $D/$1-$n.bin $D/$2-$n.bin && echo "$1 = $2 bit for bit (run $n)" || echo "$1 != $2 (run $n)"; done; done
.venv/bin/python work/r10/gr_compare.py $D | tee $D/summary.md
