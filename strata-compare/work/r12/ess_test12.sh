#!/bin/bash
# ess_test12.sh [N] — round 12 (Phase B, the cost-aware gate, class (c)): Round 9's exact-sampling chi-square test
# (work/r12/ess_test.cu: the real kernels of the gate build, tiny vocabularies, chi-square of the first emitted token and
# the first two, + the negative control) with two COST GATE cases (the draft length decided step by step by the round 12
# table on each step's raw top probability, before the draw). No model loaded; under the memory guard.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source work/r12/env.sh
S=$WS/strata-r12g; mkdir -p tmp/r12/ess12
/usr/local/cuda-13.3/bin/nvcc -O2 -std=c++17 -arch=sm_120 -I$S/include -o tmp/r12/ess12/ess_test work/r12/ess_test.cu \
  $S/build-mg/libstrata_kernels.a $S/build-mg/libstrata_core.a -lcuda 2>&1 | grep -v 'warning #' | head -20 || true
[ -x tmp/r12/ess12/ess_test ] || { echo "ess_test did not build"; exit 1; }
STRATA_COST_GATE=$WS/configs/r12-cost-gate.txt CUDA_VISIBLE_DEVICES=GPU-UUID-RTX5080 \
  .venv/bin/python work/r12/guard.py ess-test12 -- tmp/r12/ess12/ess_test ${1:-200000} 2>&1 | tee results/r12/ess-test12.txt
