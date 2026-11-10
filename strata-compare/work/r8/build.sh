#!/bin/bash
# build.sh [WORKTREE] [ENGINE_DIR] — round 8: build a worktree (default strata-r8 = branch r8-port: v0.1.30 + the
# C*7 patches minus 0013) for sm_89 + sm_120 into ENGINE_DIR/strata (+ SHA256, SOURCE). Run through the queue (no benchmark beside it).
# Env: BDIR (build dir, default build-mg), CMAKE_EXTRA (e.g. -DCMAKE_CXX_FLAGS=-DSTRATA_NVTX for the nsys trace build).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/work/r8/env.sh
WT=${1:-strata-r8} OUT=${2:-engine-r8c}
cd $WS/$WT
[ -d third_party/llama.cpp ] || cp -a $WS/strata-v0115/third_party/llama.cpp third_party/
cmake -G Ninja -S . -B ${BDIR:-build-mg} -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
  "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
  -DSTRATA_GGML_DIR="$PWD/third_party/llama.cpp" ${CMAKE_EXTRA:-} > ${BDIR:-build-mg}-configure.log
t0=$(date +%s)
cmake --build ${BDIR:-build-mg} --target strata -j 16 > ${BDIR:-build-mg}.log 2>&1 || { tail -30 ${BDIR:-build-mg}.log; exit 1; }
mkdir -p $WS/$OUT
cp ${BDIR:-build-mg}/strata $WS/$OUT/strata
sha256sum $WS/$OUT/strata | tee $WS/$OUT/SHA256
echo "$WT $(git rev-parse --abbrev-ref HEAD) $(git rev-parse --short HEAD) on $(git describe --tags --abbrev=0) + $(git log --oneline $(git describe --tags --abbrev=0)..HEAD | wc -l) commits; tree $(git rev-parse HEAD^{tree}); dirty=$(git status --porcelain -uno | wc -l); sm_89+sm_120; built in $(( $(date +%s) - t0 )) s; $(date -Is)" > $WS/$OUT/SOURCE
cat $WS/$OUT/SOURCE
