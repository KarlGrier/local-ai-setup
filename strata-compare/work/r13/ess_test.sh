#!/bin/bash
# ess_test.sh [N] — round 9 Phase A.1: build work/r13/ess_test.cu against strata-r9e's kernel library (sm_120) and run
# it under the memory guard (no model loaded). Output: results/r13/ess-test.txt
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source work/r13/env.sh
S=$WS/strata-r9e; mkdir -p tmp/r13/ess
/usr/local/cuda-13.3/bin/nvcc -O2 -std=c++17 -arch=sm_120 -I$S/include -o tmp/r13/ess/ess_test work/r13/ess_test.cu \
  $S/build/libstrata_kernels.a $S/build/libstrata_core.a -lcuda 2>&1 | grep -v 'warning #' | head -20 || true
[ -x tmp/r13/ess/ess_test ] || { echo "ess_test did not build"; exit 1; }
.venv/bin/python work/r13/guard.py ess-test -- tmp/r13/ess/ess_test ${1:-200000} 2>&1 | tee results/r13/ess-test.txt
