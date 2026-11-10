#!/bin/bash
# build-port021n.sh [tests] - round 22 (10-21 evening): the P021 backport (copy of build-port021.sh). Only inside a phase 4 gap
# (work/r22/port_gap4.sh begin ... end), with Strata stopped. The user, 10-21 evening: if the next gap's two checks pass
# (40-prompt kernel check, C vs A with the rebuilt tool-call turns), 8080 switches to THIS build, not to 0.2.2.
#   strata-r22p021n  worktree of branch r22-port021-next = r22-port021 (P021: v0.2.1 + our 26 commits) + 4518c9b3 (the
#                    cost gate past its table), 632ae8b7 (STRATA_DRAFT_CUM) and 785e45df (STRATA_PREFILL_V2): 29 commits,
#                    cherry-picked from r22-port022-next (one conflict: 0.2.2's spec_start_test line in CMakeLists.txt)
#   engine-r22p021n  the binary (build/, tests off) + SOURCE + SHA256; the picture reader stays engine-r22p021/strata-vision
#   tests            a second tree build-tests/ with STRATA_BUILD_TESTS=ON (the C++ unit / parity tests, run by gap1.sh)
# ggml: our llama.cpp checkout (strata/third_party/llama.cpp) is at 3cf03257, the commit 0.2.0 pins
# (third_party/ggml/VERSION.txt) - checked below, so nothing is downloaded.
# Memory (the user, 10-19 evening: the build must not push free memory under the 16 GB floor): it runs inside a gap, so
# Strata is stopped (port_gap.sh begin); at most BUILD_JOBS (16) compile jobs; work/r22/build_memguard.sh pauses the
# build below 24 GB free and stops it below 18 GB (log logs/r22/build-memguard.log).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
NVCC=/usr/local/cuda-13.3/bin/nvcc; LL=$(readlink -f strata/third_party/llama.cpp); W=strata-r22p021n
[ "$(git -C $W rev-parse --abbrev-ref HEAD)" = r22-port021-next ] || { echo "$W is not on r22-port021-next"; exit 1; }
[ -z "$(git -C $W status --porcelain --untracked-files=no)" ] || { echo "$W is dirty"; exit 1; }
[ "$(git -C $W rev-list --count v0.2.1..HEAD)" = 29 ] || { echo "not 29 commits on v0.2.1"; exit 1; }
PIN=$(cut -d' ' -f1 $W/third_party/ggml/VERSION.txt)
[ "$(git -C $LL rev-parse HEAD)" = "$PIN" ] || { echo "llama.cpp checkout is not 0.2.0's pinned ggml $PIN"; exit 1; }
J=${BUILD_JOBS:-16}
pgrep -f "work/r22/[b]uild_memguard.sh" > /dev/null || { setsid nohup work/r22/build_memguard.sh 14400 > /dev/null 2>&1 < /dev/null & }
build() {   # build DIR TESTS(ON|OFF) TARGET...
  local d=$1 t=$2; shift 2
  rm -rf $W/$d
  (cd $W && nice -n 5 cmake -G Ninja -S . -B $d -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=$t \
     "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=$NVCC -DSTRATA_GGML_DIR="$LL" > $d-configure.log 2>&1 \
   && nice -n 5 cmake --build $d ${1:+--target "$@"} -j $J > $d.log 2>&1)
}
if [ "${1:-}" = tests ]; then
  build build-tests ON
  echo "tests built: $(cd $W/build-tests && ctest -N | tail -1)"
  exit 0
fi
build build OFF strata
mkdir -p engine-r22p021n && cp $W/build/strata engine-r22p021n/strata
H=$(git -C $W rev-parse HEAD)
echo "v0.2.1 + $(git -C $W rev-list --count v0.2.1..HEAD) commits (branch r22-port021-next $H), tree $(git -C $W rev-parse HEAD^{tree})" > engine-r22p021n/SOURCE
sha256sum engine-r22p021n/strata > engine-r22p021n/SHA256; cat engine-r22p021n/SOURCE engine-r22p021n/SHA256
