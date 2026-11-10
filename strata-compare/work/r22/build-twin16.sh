#!/bin/bash
# build-twin16.sh m21t|s28t - round 22 gap 16 (Karl 10-30, condition 1: "the same scoring for every build ... P021m, stock
# v0.2.8, and the port with the fork on and off"): the check-(2) MEASUREMENT twins of the two builds that had none, each =
# the build + the 4 MEASUREMENT commits (force=N scoring, server hooks) + the STRATA_FORCE_T1 switch, exactly as the port's
# twin r22-port028x-meas (their changed lines are the port twin's, line for line; one loop condition resolved by hand:
# P021m's `lim`, stock's `max_new`):
#   m21t  r22-port021m-meas (worktree strata-r22p021mt) = P021m's branch r22-port021-cont2 (a653ae6c) + 5 = v0.2.1 + 35
#         -> engine-r22p021mt
#   s28t  r22-stock028-meas (worktree strata-r22s028t) = upstream v0.2.8 + 5 -> engine-r22s028t
# The strata binary only (tests off); built as build-port028x.sh builds (pinned ggml, nvcc 13.3, arch 89;120, the memory
# guard, nice). Only inside a gap. The served engine-r22p021m and its worktree are not touched.
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
NVCC=/usr/local/cuda-13.3/bin/nvcc; LL=$(readlink -f strata/third_party/llama.cpp)
case "${1:-}" in
  m21t) W=strata-r22p021mt; BR=r22-port021m-meas; BASE=v0.2.1; NC=35; E=engine-r22p021mt;;
  s28t) W=strata-r22s028t; BR=r22-stock028-meas; BASE=v0.2.8; NC=5; E=engine-r22s028t;;
  *) echo "usage: build-twin16.sh m21t|s28t"; exit 2;;
esac
[ "$(git -C $W rev-parse --abbrev-ref HEAD)" = $BR ] || { echo "$W is not on $BR"; exit 1; }
[ -z "$(git -C $W status --porcelain --untracked-files=no)" ] || { echo "$W is dirty"; exit 1; }
[ "$(git -C $W rev-list --count $BASE..HEAD)" = "$NC" ] || { echo "not $NC commits on $BASE"; exit 1; }
git -C $W log -1 --format=%s | grep -q 'STRATA_FORCE_T1' || { echo "$W's last commit is not the FORCE_T1 switch"; exit 1; }
PIN=$(cut -d' ' -f1 $W/third_party/ggml/VERSION.txt)
[ "$(git -C $LL rev-parse HEAD)" = "$PIN" ] || { echo "llama.cpp checkout is not $W's pinned ggml $PIN"; exit 1; }
J=${BUILD_JOBS:-16}
pgrep -f "work/r22/[b]uild_memguard.sh" > /dev/null || { setsid nohup work/r22/build_memguard.sh 14400 > /dev/null 2>&1 < /dev/null & }
rm -rf $W/build-twin
(cd $W && nice -n 5 cmake -G Ninja -S . -B build-twin -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
   "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=$NVCC -DSTRATA_GGML_DIR="$LL" > build-twin-configure.log 2>&1 \
 && nice -n 5 cmake --build build-twin --target strata -j $J > build-twin.log 2>&1)
mkdir -p $E && cp $W/build-twin/strata $E/strata
echo "twin: $BASE + $(git -C $W rev-list --count $BASE..HEAD) commits (branch $BR $(git -C $W rev-parse HEAD)), tree $(git -C $W rev-parse HEAD^{tree})" > $E/SOURCE
sha256sum $E/strata > $E/SHA256; cat $E/SOURCE $E/SHA256
