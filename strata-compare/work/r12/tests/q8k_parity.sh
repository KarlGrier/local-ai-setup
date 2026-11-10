#!/bin/bash
# q8k_parity.sh BUILD_DIR [DEVICE] — build and run the A.2 parity test against a build's libstrata_kernels.a + libggml-base.a
set -e
WS=/home/USER/ai-speed-testing/strata-compare; B=$1; D=${2:-0}
source $WS/work/r12/env.sh
/usr/local/cuda-13.3/bin/nvcc -O2 -gencode arch=compute_120,code=sm_120 -gencode arch=compute_89,code=sm_89 \
  -o $WS/tmp/r12/q8k_parity $WS/work/r12/tests/q8k_parity.cu $B/libstrata_kernels.a $B/ggml/src/libggml-base.a -lcuda
CUDA_VISIBLE_DEVICES=$D $WS/tmp/r12/q8k_parity
