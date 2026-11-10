#!/bin/bash
# build-cstar4.sh — clean-checkout build of C*4: clone Strata v0.1.15 (d551edf) from the local repository, apply
# patches/r4/*.patch in order (git am), build the engine exactly like setup.py (Release, sm_120, ggml + MMQ from the
# pinned llama.cpp 3cf03257), copy it to engine-cstar4/strata (+ SHA256, SOURCE) and keep the checkout as strata-cstar4/
# for the server (serve/ with the web app). Run it only when no benchmark is running (it uses all cores for ~20 s).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/work/r4/env.sh
DEST=$WS/strata-cstar4
rm -rf "$DEST"
git clone -q "$WS/strata" "$DEST"
cd "$DEST"
git checkout -q d551edf42c157f1c8c20f07f68c5dfe506b1edda        # v0.1.15
git -c user.name=strata-compare -c user.email=339962272+KarlGrier@users.noreply.github.com am -q "$WS"/patches/r4/0*.patch
git log --oneline -12
cp -a "$WS/strata-v0115/third_party/llama.cpp" third_party/     # the pinned llama.cpp 3cf03257 (setup.py's zip, local copy)
cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
  -DCMAKE_CUDA_ARCHITECTURES=120 -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
  -DSTRATA_GGML_DIR="$DEST/third_party/llama.cpp" > build-configure.log
cmake --build build --target strata -j 16 > build.log 2>&1 || { tail -30 build.log; exit 1; }
mkdir -p $WS/engine-cstar4
cp build/strata $WS/engine-cstar4/strata
sha256sum $WS/engine-cstar4/strata | tee $WS/engine-cstar4/SHA256
echo "Strata v0.1.15 (d551edf) + patches/r4/*, clean clone $(date -Is); tree $(git rev-parse HEAD^{tree})" > $WS/engine-cstar4/SOURCE
