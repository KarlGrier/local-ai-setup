#!/bin/bash
# grbench.sh — round 9 Phase 0.3: the hyper-connection read microbenchmark (C*10's kernel library), modes alternated
# v5 v3 old old v3 v5 (one process each, under the memory guard), then the comparison. Run through the queue (GPU idle).
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source work/r9/env.sh
D=$WS/results/r9/grbench; mkdir -p $D; B=$WS/tmp/r9/grbench/gr_bench
i=0; for m in v5 v3 old old v3 v5; do
  n=$([ -f $D/$m-1.bin ] && echo 2 || echo 1)
  .venv/bin/python work/r9/guard.py grbench-$m-$n -- $B $m $D/$m-$n.bin > $D/$m-$n.out 2>&1; echo "$m run $n exit $?"
done
.venv/bin/python work/r9/gr_compare.py $D | tee $D/summary.md
