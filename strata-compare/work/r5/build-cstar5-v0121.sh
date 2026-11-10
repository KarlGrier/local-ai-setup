#!/bin/bash
# build-cstar5.sh — clean-checkout build of C*5: clone Strata v0.1.21 (f1b1d96) from the local repository, apply
# patches/r5/*.patch in order (git am), build the engine exactly like setup.py (Release, sm_120, ggml + MMQ from the
# pinned llama.cpp 3cf03257), copy it to engine-cstar5/strata (+ SHA256, SOURCE) and keep the checkout as strata-cstar5/
# for the server (serve/ with the web app). Run it only when no benchmark is running (it uses all cores for ~20 s).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/work/r5/env.sh
DEST=$WS/strata-cstar5
rm -rf "$DEST"
git clone -q "$WS/strata" "$DEST"
cd "$DEST"
git checkout -q f1b1d961537fd66d37fee68a60015701375b7b5a        # v0.1.21
test "$(git rev-parse HEAD)" = "$(git rev-parse v0.1.21)"
git -c user.name=strata-compare -c user.email=339962272+KarlGrier@users.noreply.github.com am -q "$WS"/patches/r5/0*.patch
git log --oneline -12
cp -a "$WS/strata-v0115/third_party/llama.cpp" third_party/     # the pinned llama.cpp 3cf03257 (setup.py's zip, local copy)
cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
  -DCMAKE_CUDA_ARCHITECTURES=120 -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
  -DSTRATA_GGML_DIR="$DEST/third_party/llama.cpp" > build-configure.log
cmake --build build --target strata -j 16 > build.log 2>&1 || { tail -30 build.log; exit 1; }
mkdir -p $WS/engine-cstar5
cp build/strata $WS/engine-cstar5/strata
sha256sum $WS/engine-cstar5/strata | tee $WS/engine-cstar5/SHA256
echo "Strata v0.1.21 (f1b1d96) + patches/r5/*, clean clone $(date -Is); tree $(git rev-parse HEAD^{tree})" > $WS/engine-cstar5/SOURCE
