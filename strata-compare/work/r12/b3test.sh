#!/bin/bash
# b3test.sh — round 11 B.3: the interleaved-activation matvec (r11-b3) through its own parity test (every format x shape
# x 1..8 columns x rows a warp, bitwise against native_mmvq) and the rows-a-warp sweep on the RTX 5080 (--bench), linked
# against the branch's kernel library; under the memory guard, no model server beside it.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source work/r12/env.sh
# round 11 (v0.1.39): b3test.sh [WORKTREE] [TAG] — default strata-r11b3, outputs results/r12/b3-*TAG.txt
WT=${1:-strata-r11b3}; TAG=${2:-}
S=$WS/$WT; mkdir -p tmp/r12/b3$TAG results/r12
/usr/local/cuda-13.3/bin/nvcc -O2 -std=c++17 -arch=sm_120 -I$S/include -o tmp/r12/b3$TAG/mmvq_il_parity $S/src/kernels/mmvq_il_parity.cu \
  $S/build/libstrata_kernels.a $S/build/libstrata_core.a -lcuda 2>&1 | grep -v 'warning #' | head -5
G5080=GPU-UUID-RTX5080
CUDA_VISIBLE_DEVICES=$G5080 .venv/bin/python work/r12/guard.py b3parity -- tmp/r12/b3$TAG/mmvq_il_parity 2>&1 | tail -3 | tee results/r12/b3-parity$TAG.txt
CUDA_VISIBLE_DEVICES=$G5080 .venv/bin/python work/r12/guard.py b3bench -- tmp/r12/b3$TAG/mmvq_il_parity --bench 2>&1 | grep BENCH | tee results/r12/b3-bench$TAG.txt
