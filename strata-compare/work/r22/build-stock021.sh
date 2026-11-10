#!/bin/bash
# build-stock021.sh - Basalt round 2 (the user, 10-21: "Make the stock arm required ... Build stock v0.2.1 after the
# Basalt timing runs if needed (same rules as before)"): upstream Strata v0.2.1 with NONE of our commits, built exactly
# like build-port021.sh (Release, CUDA arch 89;120, tests off, nvcc 13.3, the same ggml pin, the memory guard). Only
# inside a gap (work/r22/gap6.sh, after the Basalt runs), with Strata stopped.
#   strata-v021stock   detached worktree of the strata repo at tag v0.2.1 (90767252), created here if missing
#   engine-v021stock   the binary (build/, tests off) + SOURCE + SHA256
# The stock server (strata-v021stock/serve/server.py) runs from the worktree: configs/basalt-ab/s0.json, s1.json, s1s7.json.
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
NVCC=/usr/local/cuda-13.3/bin/nvcc; LL=$(readlink -f strata/third_party/llama.cpp); W=strata-v021stock; TAG=v0.2.1
TAGC=90767252f420e25223c739d604145ad15911d48b
[ -d $W ] || git -C strata worktree add --detach $WS/$W $TAG
[ "$(git -C $W rev-parse HEAD)" = $TAGC ] || { echo "$W is not at $TAG ($TAGC)"; exit 1; }
[ -z "$(git -C $W status --porcelain --untracked-files=no)" ] || { echo "$W is dirty"; exit 1; }
PIN=$(cut -d' ' -f1 $W/third_party/ggml/VERSION.txt)
[ "$(git -C $LL rev-parse HEAD)" = "$PIN" ] || { echo "llama.cpp checkout is not v0.2.1's pinned ggml $PIN"; exit 1; }
J=${BUILD_JOBS:-16}
pgrep -f "work/r22/[b]uild_memguard.sh" > /dev/null || { setsid nohup work/r22/build_memguard.sh 14400 > /dev/null 2>&1 < /dev/null & }
rm -rf $W/build
(cd $W && nice -n 5 cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
   "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=$NVCC -DSTRATA_GGML_DIR="$LL" > build-configure.log 2>&1 \
 && nice -n 5 cmake --build build --target strata -j $J > build.log 2>&1)
mkdir -p engine-v021stock && cp $W/build/strata engine-v021stock/strata
echo "stock $TAG ($TAGC, detached worktree $W), none of our commits, tree $(git -C $W rev-parse HEAD^{tree})" > engine-v021stock/SOURCE
sha256sum engine-v021stock/strata > engine-v021stock/SHA256; cat engine-v021stock/SOURCE engine-v021stock/SHA256
