#!/bin/bash
# ess_test.sh [N] — bring-up: build bringup/lib/ess_test.cu against $TREE's kernel library (build-mg, sm_120) and run
# it under the memory guard (no model loaded): exact speculative sampling's chi-square cases + the negative control.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
S=$WS/${TREE:-strata-r13}; mkdir -p bringup/out/tmp/ess
B=$S/build-mg; [ -f $B/libstrata_kernels.a ] || B=$S/build
/usr/local/cuda-13.3/bin/nvcc -O2 -std=c++17 -arch=sm_120 -I$S/include -o bringup/out/tmp/ess/ess_test ${ESS_SRC:-bringup/lib/ess_test.cu} \
  $B/libstrata_kernels.a $B/libstrata_core.a -lcuda 2>&1 | grep -v 'warning #' | head -20 || true
[ -x bringup/out/tmp/ess/ess_test ] || { echo "ess_test did not build"; exit 1; }
.venv/bin/python bringup/lib/guard.py ess-test -- bringup/out/tmp/ess/ess_test ${1:-200000} 2>&1 | tee bringup/out/results/ess-test.txt
