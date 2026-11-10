#!/bin/bash
# build-cstar7.sh — round 7: clean-checkout build of the C*7 candidate: clone Strata v0.1.27 (a790805) from the local
# repository, apply patches/r7/0*.patch (= C*6's 12 patches ported; 0009 merged with upstream's Turing chunking), build like
# setup.py (Release, ggml + MMQ from the pinned llama.cpp 3cf03257) for sm_89 + sm_120, copy to engine-cstar7/strata (+ SHA256,
# SOURCE) and keep the checkout as strata-cstar7/ for the server. Run it through the queue (no benchmark beside it).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/work/r7/env.sh
DEST=$WS/strata-cstar7
rm -rf "$DEST"
git clone -q "$WS/strata" "$DEST"
cd "$DEST"
git checkout -q a79080535d1b2a71a3419a0d97d8e7dca194b0f1        # v0.1.27
test "$(git rev-parse HEAD)" = "$(git -C $WS/strata rev-parse v0.1.27)"
git -c user.name=strata-compare -c user.email=339962272+KarlGrier@users.noreply.github.com am -q "$WS"/patches/r7/0*.patch
git log --oneline -13
test "$(git rev-parse HEAD^{tree})" = "$(git -C $WS/strata rev-parse r7-port^{tree})" || { echo "tree differs from r7-port"; exit 1; }
cp -a "$WS/strata-v0115/third_party/llama.cpp" third_party/
cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
  "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
  -DSTRATA_GGML_DIR="$DEST/third_party/llama.cpp" > build-configure.log
cmake --build build --target strata -j 16 > build.log 2>&1 || { tail -30 build.log; exit 1; }
mkdir -p $WS/engine-cstar7
cp build/strata $WS/engine-cstar7/strata
sha256sum $WS/engine-cstar7/strata | tee $WS/engine-cstar7/SHA256
echo "Strata v0.1.27 (a790805) + patches/r7/* (sm_89+sm_120), clean clone $(date -Is); tree $(git rev-parse HEAD^{tree})" > $WS/engine-cstar7/SOURCE
