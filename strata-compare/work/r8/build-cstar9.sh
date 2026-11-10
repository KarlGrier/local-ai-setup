#!/bin/bash
# build-cstar9.sh — round 8 Phase C: clean-checkout build of the C*9 candidate: clone Strata v0.1.30 (30ec18e) from the local
# repository, apply patches/r8c/0*.patch (= C*8 0001-0012 + Phase B: 0013 PR245 grouped experts, 0014 MMQ expert
# offsets), build like setup.py (Release, ggml + MMQ from the pinned llama.cpp 3cf03257) for
# sm_89 + sm_120, copy to engine-cstar9/strata (+ SHA256, SOURCE) and keep the checkout as strata-cstar9/ for the server.
# Run it through the queue (no benchmark beside it).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/work/r8/env.sh
DEST=$WS/strata-cstar9
rm -rf "$DEST"
git clone -q "$WS/strata" "$DEST"
cd "$DEST"
git checkout -q 30ec18ec7094550fcc594fd948220d511d80464e        # v0.1.30
test "$(git rev-parse HEAD)" = "$(git -C $WS/strata rev-parse v0.1.30)"
git -c user.name=strata-compare -c user.email=339962272+KarlGrier@users.noreply.github.com am -q "$WS"/patches/r8c/0*.patch
git log --oneline -14
test "$(git rev-parse HEAD^{tree})" = "$(git -C $WS/strata rev-parse r8-c9^{tree})" || { echo "tree differs from r8-c9"; exit 1; }
cp -a "$WS/strata-v0115/third_party/llama.cpp" third_party/
cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
  "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
  -DSTRATA_GGML_DIR="$DEST/third_party/llama.cpp" > build-configure.log
cmake --build build --target strata -j 16 > build.log 2>&1 || { tail -30 build.log; exit 1; }
mkdir -p $WS/engine-cstar9
cp build/strata $WS/engine-cstar9/strata
sha256sum $WS/engine-cstar9/strata | tee $WS/engine-cstar9/SHA256
echo "Strata v0.1.30 (30ec18e) + patches/r8c/* (sm_89+sm_120), clean clone $(date -Is); tree $(git rev-parse HEAD^{tree})" > $WS/engine-cstar9/SOURCE
cat $WS/engine-cstar9/SOURCE
