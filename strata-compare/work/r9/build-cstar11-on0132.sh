#!/bin/bash
# build-cstar11.sh — round 9 Phase C: clean-checkout build of the C*11 candidate: clone Strata v0.1.32 (c499bd1) from the local
# repository, apply patches/r9c/0*.patch (= C*10's 13 patches ported to v0.1.32 + 0014 exact speculative sampling + 0015
# deterministic swap landing), check the tree equals branch r10-c11's, build like setup.py (Release, ggml + MMQ from the
# pinned llama.cpp 3cf03257) for sm_89 + sm_120, copy to engine-cstar11/strata (+ SHA256, SOURCE) and keep the checkout
# as strata-cstar11/ for the server. Run it through the queue (no benchmark beside it).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/work/r9/env.sh
DEST=$WS/strata-cstar11
rm -rf "$DEST"
git clone -q "$WS/strata" "$DEST"
cd "$DEST"
git checkout -q c499bd102e7a4135c0de389dcfe38c399759ccc8        # v0.1.32
test "$(git rev-parse HEAD)" = "$(git -C $WS/strata rev-parse v0.1.32)"
(cd $WS/patches/r9c && sha256sum -c --quiet SHA256SUMS)
git -c user.name=strata-compare -c user.email=339962272+KarlGrier@users.noreply.github.com am -q "$WS"/patches/r9c/0*.patch
git log --oneline -15
test "$(git rev-parse HEAD^{tree})" = "23d7d1b150bce8e0b65a0b47ef17a8dce34ae5f4" || { echo "tree differs from r10-c11"; exit 1; }
cp -a "$WS/strata-v0115/third_party/llama.cpp" third_party/
cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
  "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
  -DSTRATA_GGML_DIR="$DEST/third_party/llama.cpp" > build-configure.log
cmake --build build --target strata -j 16 > build.log 2>&1 || { tail -30 build.log; exit 1; }
mkdir -p $WS/engine-cstar11
cp build/strata $WS/engine-cstar11/strata
sha256sum $WS/engine-cstar11/strata | tee $WS/engine-cstar11/SHA256
echo "Strata v0.1.32 (c499bd1) + patches/r9c/0001-0015 (sm_89+sm_120), clean clone $(date -Is); tree $(git rev-parse HEAD^{tree})" > $WS/engine-cstar11/SOURCE
cat $WS/engine-cstar11/SOURCE
