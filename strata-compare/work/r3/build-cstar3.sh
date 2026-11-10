#!/bin/bash
# build-cstar3.sh — clean-checkout build of C*3: clone Strata v0.1.12 (481e0cd) from the local repository, apply
# patches/r3/*.patch in order (git am), build the engine exactly like setup.py (Release, sm_120, ggml from the pinned
# llama.cpp 3cf03257), copy it to engine-cstar3/strata (+ SHA256, SOURCE) and keep the checkout as strata-cstar3/ for the
# server (serve/ with the web app).  Run it only when no benchmark is running (it uses all cores).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare
DEST=$WS/strata-cstar3
rm -rf "$DEST"
git clone -q "$WS/strata" "$DEST"
cd "$DEST"
git checkout -q 481e0cd5088ba3518eb31dd5d5c0412820fa574c        # v0.1.12
git -c user.name=strata-compare -c user.email=339962272+KarlGrier@users.noreply.github.com am -q "$WS"/patches/r3/0*.patch
git log --oneline -9
cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
  -DCMAKE_CUDA_ARCHITECTURES=120 -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
  -DSTRATA_GGML_DIR="$WS/strata/third_party/llama.cpp" > build-configure.log
cmake --build build --target strata -j 16 > build.log 2>&1 || { tail -30 build.log; exit 1; }
mkdir -p $WS/engine-cstar3
cp build/strata $WS/engine-cstar3/strata
sha256sum $WS/engine-cstar3/strata | tee $WS/engine-cstar3/SHA256
echo "Strata v0.1.12 (481e0cd) + patches/r3/0001-0008, clean clone $(date -Is); tree $(git rev-parse HEAD^{tree})" > $WS/engine-cstar3/SOURCE
git -C "$WS/strata-r3" rev-parse r3-c3^{tree} | sed 's/^/tested r3-c3 tree /' >> $WS/engine-cstar3/SOURCE
