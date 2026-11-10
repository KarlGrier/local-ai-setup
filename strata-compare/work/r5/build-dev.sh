#!/bin/bash
# build-dev.sh <worktree> — build the strata engine in <worktree>/build exactly like work/r4/build-cstar4.sh
# (Release, sm_120, ggml + MMQ from the pinned llama.cpp 3cf03257 copied from strata-v0115). Caches in tmp/r5.
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/work/r5/env.sh
D=$(realpath "$1")
cd "$D"
[ -d third_party/llama.cpp ] || cp -a "$WS/strata-v0115/third_party/llama.cpp" third_party/
B=${BUILD_DIR:-build}
cmake -G Ninja -S . -B $B -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
  -DCMAKE_CUDA_ARCHITECTURES="${ARCHS:-120}" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
  -DSTRATA_GGML_DIR="$D/third_party/llama.cpp" > $B-configure.log
cmake --build $B --target strata -j 16 > $B.log 2>&1 || { tail -30 $B.log; exit 1; }
sha256sum $B/strata
$B/strata --help 2>&1 | head -2 || true
