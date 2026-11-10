#!/bin/bash
# ess_test12.sh [N] — round 13 (Phase B, the cost-aware gate, class (c)): Round 9's exact-sampling chi-square test
# (work/r13/ess_test.cu: the real kernels of the gate build, tiny vocabularies, chi-square of the first emitted token and
# the first two, + the negative control) with two COST GATE cases (the draft length decided step by step by the round 13
# table on each step's raw top probability, before the draw). No model loaded; under the memory guard.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source work/r13/env.sh
S=$WS/strata-r12g; mkdir -p tmp/r13/ess12
/usr/local/cuda-13.3/bin/nvcc -O2 -std=c++17 -arch=sm_120 -I$S/include -o tmp/r13/ess12/ess_test work/r13/ess_test.cu \
  $S/build-mg/libstrata_kernels.a $S/build-mg/libstrata_core.a -lcuda 2>&1 | grep -v 'warning #' | head -20 || true
[ -x tmp/r13/ess12/ess_test ] || { echo "ess_test did not build"; exit 1; }
STRATA_COST_GATE=$WS/configs/r12-cost-gate.txt CUDA_VISIBLE_DEVICES=GPU-UUID-RTX5080 \
  .venv/bin/python work/r13/guard.py ess-test12 -- tmp/r13/ess12/ess_test ${1:-200000} 2>&1 | tee results/r13/ess-test12.txt
