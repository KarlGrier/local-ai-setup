#!/bin/bash
# build-cstar6.sh — round 6: clean-checkout build of C*6: clone Strata v0.1.24 (3ce2523) from the local repository, apply
# patches/r6/0*.patch in order (git am; = C*5's 9 patches + 3 round-6 patches), build like setup.py (Release, ggml + MMQ from
# the pinned llama.cpp 3cf03257) for sm_89 + sm_120 (the RTX 4060 Ti helper needs sm_89), copy it to engine-cstar6/strata
# (+ SHA256, SOURCE) and keep the checkout as strata-cstar6/ for the server. Run it through the queue (no benchmark beside it).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/work/r6/env.sh
DEST=$WS/strata-cstar6
rm -rf "$DEST"
git clone -q "$WS/strata" "$DEST"
cd "$DEST"
git checkout -q 3ce2523c2823687de5372be3af58534f56cbf286        # v0.1.24
test "$(git rev-parse HEAD)" = "$(git rev-parse v0.1.24)"
git -c user.name=strata-compare -c user.email=339962272+KarlGrier@users.noreply.github.com am -q "$WS"/patches/r6/0*.patch
git log --oneline -13
test "$(git rev-parse HEAD^{tree})" = "$(git -C $WS/strata rev-parse r6-cand^{tree})" || { echo "tree differs from r6-cand"; exit 1; }
cp -a "$WS/strata-v0115/third_party/llama.cpp" third_party/     # the pinned llama.cpp 3cf03257 (setup.py's zip, local copy)
cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
  "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
  -DSTRATA_GGML_DIR="$DEST/third_party/llama.cpp" > build-configure.log
cmake --build build --target strata -j 16 > build.log 2>&1 || { tail -30 build.log; exit 1; }
mkdir -p $WS/engine-cstar6
cp build/strata $WS/engine-cstar6/strata
sha256sum $WS/engine-cstar6/strata | tee $WS/engine-cstar6/SHA256
echo "Strata v0.1.24 (3ce2523) + patches/r6/* (sm_89+sm_120), clean clone $(date -Is); tree $(git rev-parse HEAD^{tree})" > $WS/engine-cstar6/SOURCE
