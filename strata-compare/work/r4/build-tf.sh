#!/bin/bash
# build-tf.sh — the R4 teacher-force engine (r4-port + patches/measurement/0001) → engine-r4up/strata-tf (measurement only)
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; source $WS/work/r4/env.sh
cd $WS/strata-r4-tf
cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
  -DCMAKE_CUDA_ARCHITECTURES=120 -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
  -DSTRATA_GGML_DIR=$PWD/third_party/llama.cpp > build-configure.log 2>&1
t=$(date +%s); cmake --build build --target strata -j 16 > build.log 2>&1 || { tail -20 build.log; exit 1; }
mkdir -p $WS/engine-r4up; cp build/strata $WS/engine-r4up/strata-tf
echo "built engine-r4up/strata-tf in $(( $(date +%s) - t )) s from $(git rev-parse --short HEAD)"
