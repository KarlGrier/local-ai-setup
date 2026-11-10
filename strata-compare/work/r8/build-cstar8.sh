#!/bin/bash
# build-cstar8.sh — round 8: clean-checkout build of the C*8 candidate: clone Strata v0.1.30 (30ec18e) from the local
# repository, apply patches/r8/0*.patch (= C*7's patches 0001-0012 ported; 0013 dropped for upstream's #205 fix; the chat
# cache's store renamed for #189), build like setup.py (Release, ggml + MMQ from the pinned llama.cpp 3cf03257) for
# sm_89 + sm_120, copy to engine-cstar8/strata (+ SHA256, SOURCE) and keep the checkout as strata-cstar8/ for the server.
# Run it through the queue (no benchmark beside it).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/work/r8/env.sh
DEST=$WS/strata-cstar8
rm -rf "$DEST"
git clone -q "$WS/strata" "$DEST"
cd "$DEST"
git checkout -q 30ec18ec7094550fcc594fd948220d511d80464e        # v0.1.30
test "$(git rev-parse HEAD)" = "$(git -C $WS/strata rev-parse v0.1.30)"
git -c user.name=strata-compare -c user.email=339962272+KarlGrier@users.noreply.github.com am -q "$WS"/patches/r8/0*.patch
git log --oneline -12
test "$(git rev-parse HEAD^{tree})" = "$(git -C $WS/strata rev-parse r8-port^{tree})" || { echo "tree differs from r8-port"; exit 1; }
cp -a "$WS/strata-v0115/third_party/llama.cpp" third_party/
cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
  "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
  -DSTRATA_GGML_DIR="$DEST/third_party/llama.cpp" > build-configure.log
cmake --build build --target strata -j 16 > build.log 2>&1 || { tail -30 build.log; exit 1; }
mkdir -p $WS/engine-cstar8
cp build/strata $WS/engine-cstar8/strata
sha256sum $WS/engine-cstar8/strata | tee $WS/engine-cstar8/SHA256
echo "Strata v0.1.30 (30ec18e) + patches/r8/* (sm_89+sm_120), clean clone $(date -Is); tree $(git rev-parse HEAD^{tree})" > $WS/engine-cstar8/SOURCE
cat $WS/engine-cstar8/SOURCE
