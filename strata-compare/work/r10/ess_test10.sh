#!/bin/bash
# ess_test.sh [N] — round 9 Phase A.1: build work/r10/ess_test.cu against strata-ess10 (v0.1.32 base)'s kernel library (sm_120) and run
# it under the memory guard (no model loaded). Output: results/r10/ess-test10.txt
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source work/r10/env.sh
S=$WS/strata-ess10; mkdir -p tmp/r10/ess10
/usr/local/cuda-13.3/bin/nvcc -O2 -std=c++17 -arch=sm_120 -I$S/include -o tmp/r10/ess10/ess_test work/r10/ess_test.cu \
  $S/build/libstrata_kernels.a $S/build/libstrata_core.a -lcuda 2>&1 | grep -v 'warning #' | head -20 || true
[ -x tmp/r10/ess10/ess_test ] || { echo "ess_test did not build"; exit 1; }
.venv/bin/python work/r10/guard.py ess-test -- tmp/r10/ess10/ess_test ${1:-200000} 2>&1 | tee results/r10/ess-test10.txt
