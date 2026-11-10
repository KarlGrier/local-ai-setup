#!/bin/bash
# build-port0210.sh - gap 17 prep (11-03): build-port028x.sh for the v0.2.10 port - r22-port0210 (worktree strata-r22p0210,
# results/r22/port-0210.md) = v0.2.10 + 28 -> engine-r22p0210 (configs/P0210x.json). The served engine-r22p028x and its
# tree are not touched. Run only with no LDR run and no timed run live (it compiles: <= 16 jobs, nice, the memory guard).
# Kept at the 8-row window build (CUDA auto; port-0210.md risk 4: a 16-row build changes the fork's scratch offsets).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare
NVCC=/usr/local/cuda-13.3/bin/nvcc; LL=$(readlink -f $WS/strata/third_party/llama.cpp); W=$WS/strata-r22p0210; BR=r22-port0210; NC=${PORT_COMMITS:-28}
[ "$(git -C $W rev-parse --abbrev-ref HEAD)" = $BR ] || { echo "$W is not on $BR"; exit 1; }
[ -z "$(git -C $W status --porcelain --untracked-files=no)" ] || { echo "$W is dirty"; exit 1; }
[ "$(git -C $W rev-list --count v0.2.10..HEAD)" = "$NC" ] || { echo "not $NC commits on v0.2.10"; exit 1; }
PIN=$(cut -d' ' -f1 $W/third_party/ggml/VERSION.txt)
[ "$(git -C $LL rev-parse HEAD)" = "$PIN" ] || { echo "llama.cpp checkout is not v0.2.10's pinned ggml $PIN"; exit 1; }
J=${BUILD_JOBS:-16}
pgrep -f "work/r22/[b]uild_memguard.sh" > /dev/null || { setsid nohup $WS/work/r22/build_memguard.sh 14400 > /dev/null 2>&1 < /dev/null & }
rm -rf $W/build
nice -n 5 cmake -G Ninja -S $W -B $W/build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
  "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=$NVCC -DSTRATA_GGML_DIR="$LL" > $W/build-configure.log 2>&1
nice -n 5 cmake --build $W/build --target strata -j $J > $W/build.log 2>&1
mkdir -p $WS/engine-r22p0210 && cp $W/build/strata $WS/engine-r22p0210/strata
H=$(git -C $W rev-parse HEAD)
echo "v0.2.10 + $(git -C $W rev-list --count v0.2.10..HEAD) commits (branch $BR $H), tree $(git -C $W rev-parse HEAD^{tree})" > $WS/engine-r22p0210/SOURCE
sha256sum $WS/engine-r22p0210/strata > $WS/engine-r22p0210/SHA256; cat $WS/engine-r22p0210/SOURCE $WS/engine-r22p0210/SHA256
