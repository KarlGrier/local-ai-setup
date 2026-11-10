#!/bin/bash
# Clean-checkout verification: clone Strata at v0.1.11 into a fresh directory, apply patches/*.patch in order
# (git am), build the engine exactly like setup.py (Release, sm_120, ggml from the pinned llama.cpp 3cf03257),
# and report the binary's sha256.   build-patched.sh [DEST]   (default: work/clean-build)
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare
DEST=${1:-$WS/work/clean-build}
rm -rf "$DEST"; mkdir -p "$(dirname "$DEST")"
git clone -q "$WS/strata" "$DEST"                 # local clone of the reviewed repository (same objects)
cd "$DEST"
git checkout -q 8117643ccc68e3d08f80d38e064333742d4474bb   # v0.1.11
git -c user.name=strata-compare -c user.email=339962272+KarlGrier@users.noreply.github.com am -q "$WS"/patches/0*.patch
git log --oneline -3
cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
  -DCMAKE_CUDA_ARCHITECTURES=120 -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
  -DSTRATA_GGML_DIR="$WS/strata/third_party/llama.cpp" ${EXTRA_CMAKE:-} > build-configure.log
cmake --build build --target strata -j 16 > build.log 2>&1 || { tail -30 build.log; exit 1; }
sha256sum build/strata
