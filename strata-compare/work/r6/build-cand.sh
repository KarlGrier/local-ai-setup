#!/bin/bash
# build-cand.sh — round 6: build the candidate branch r6-cand (worktree strata-r6c) for sm_89 + sm_120 (the RTX 4060 Ti
# helper needs sm_89), copy it to engine-r6c/strata (+ SHA256, SOURCE).  Run through the queue (no benchmark beside it).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/work/r6/env.sh
cd $WS/strata-r6c
[ -d third_party/llama.cpp ] || cp -a $WS/strata-v0115/third_party/llama.cpp third_party/
cmake -G Ninja -S . -B build-mg -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
  "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
  -DSTRATA_GGML_DIR="$PWD/third_party/llama.cpp" > build-mg-configure.log
cmake --build build-mg --target strata -j 16 > build-mg.log 2>&1 || { tail -30 build-mg.log; exit 1; }
mkdir -p $WS/engine-r6c
cp build-mg/strata $WS/engine-r6c/strata
sha256sum $WS/engine-r6c/strata | tee $WS/engine-r6c/SHA256
echo "r6-cand $(git rev-parse --short HEAD) on v0.1.24 (3ce2523) + patches/r5 0001-0009 + $(git log --oneline r5e-v5..HEAD | wc -l) round-6 patches; tree $(git rev-parse HEAD^{tree}); sm_89+sm_120; $(date -Is)" > $WS/engine-r6c/SOURCE
cat $WS/engine-r6c/SOURCE
