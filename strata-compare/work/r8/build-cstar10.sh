#!/bin/bash
# build-cstar10.sh — round 8 Phase D: clean-checkout build of the C*10 candidate: clone Strata v0.1.31 (9259cad) from the local
# repository, apply patches/r9/0*.patch (= C*9 minus 0011 (upstream #253) on v0.1.31; PR245 transplanted onto 0.1.31; MMQ expert
# offsets), build like setup.py (Release, ggml + MMQ from the pinned llama.cpp 3cf03257) for
# sm_89 + sm_120, copy to engine-cstar10/strata (+ SHA256, SOURCE) and keep the checkout as strata-cstar10/ for the server.
# Run it through the queue (no benchmark beside it).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/work/r8/env.sh
DEST=$WS/strata-cstar10
rm -rf "$DEST"
git clone -q "$WS/strata" "$DEST"
cd "$DEST"
git checkout -q 9259cad4cfa3543cd3b8decab5962672b968c649        # v0.1.31
test "$(git rev-parse HEAD)" = "$(git -C $WS/strata rev-parse v0.1.31)"
git -c user.name=strata-compare -c user.email=339962272+KarlGrier@users.noreply.github.com am -q "$WS"/patches/r9/0*.patch
git log --oneline -13
test "$(git rev-parse HEAD^{tree})" = "$(git -C $WS/strata rev-parse r9-pr245^{tree})" || { echo "tree differs from r9-pr245"; exit 1; }
cp -a "$WS/strata-v0115/third_party/llama.cpp" third_party/
cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
  "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
  -DSTRATA_GGML_DIR="$DEST/third_party/llama.cpp" > build-configure.log
cmake --build build --target strata -j 16 > build.log 2>&1 || { tail -30 build.log; exit 1; }
mkdir -p $WS/engine-cstar10
cp build/strata $WS/engine-cstar10/strata
sha256sum $WS/engine-cstar10/strata | tee $WS/engine-cstar10/SHA256
echo "Strata v0.1.31 (9259cad) + patches/r9/* (sm_89+sm_120), clean clone $(date -Is); tree $(git rev-parse HEAD^{tree})" > $WS/engine-cstar10/SOURCE
cat $WS/engine-cstar10/SOURCE
