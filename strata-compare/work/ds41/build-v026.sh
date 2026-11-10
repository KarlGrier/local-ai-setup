#!/bin/bash
# build-v026.sh - 10-25 (the user: "get the v0.2.6 DeepSeek engine the same way as 0.2.4.2"; copy of build-v024.sh): Strata v0.2.6's DeepSeek-V4.1 engine (strata-dsv41), built STOCK in its own folder -
# no port of our series. Worktree strata-v026 (detached at the tag), binary + SOURCE + SHA256 in engine-v026-ds41/.
# Same toolchain as our builds (CUDA 13.3, sm_89 + sm_120, our llama.cpp checkout = v0.2.6's pinned ggml, the same 3cf03257 as v0.2.4),
# at most 16 jobs, work/r22/build_memguard.sh (pauses the build below 24 GB free, stops it below 18 GB).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
NVCC=/usr/local/cuda-13.3/bin/nvcc; LL=$(readlink -f strata/third_party/llama.cpp); W=strata-v026; T=v0.2.6
[ -d $W ] || git -C strata worktree add --detach $WS/$W $T > /dev/null
[ "$(git -C $W rev-parse HEAD)" = "$(git -C strata rev-parse $T^{commit})" ] || { echo "$W is not at $T"; exit 1; }
[ -z "$(git -C $W status --porcelain --untracked-files=no)" ] || { echo "$W is dirty"; exit 1; }
PIN=$(cut -d' ' -f1 $W/third_party/ggml/VERSION.txt)
[ "$(git -C $LL rev-parse HEAD)" = "$PIN" ] || { echo "llama.cpp checkout is not $T's pinned ggml $PIN"; exit 1; }
pgrep -f "work/r22/[b]uild_memguard.sh" > /dev/null || { setsid nohup work/r22/build_memguard.sh 14400 > /dev/null 2>&1 < /dev/null & }
rm -rf $W/build
(cd $W && nice -n 5 cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
   -DSTRATA_BUILD_DSV41=ON "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=$NVCC -DSTRATA_GGML_DIR="$LL" > build-configure.log 2>&1 \
 && nice -n 5 cmake --build build --target strata-dsv41 -j ${BUILD_JOBS:-16} > build.log 2>&1)
mkdir -p engine-v026-ds41 && cp $W/build/strata-dsv41 engine-v026-ds41/strata-dsv41
echo "stock $T ($(git -C $W rev-parse HEAD)), target strata-dsv41, no local commits" > engine-v026-ds41/SOURCE
sha256sum engine-v026-ds41/strata-dsv41 > engine-v026-ds41/SHA256; cat engine-v026-ds41/SOURCE engine-v026-ds41/SHA256
