#!/bin/bash
# build-port.sh [tests] - round 22 gap 1: the 0.2.0 port's engine (from work/r20/build-cstar18.sh). Only inside a port
# gap (work/r22/port_gap.sh begin ... end), with Strata stopped.
#   strata-r22port   worktree of branch r22-port020 = v0.2.0-beta (3d1fb480) + 26 commits (25 carried + 64ce1d05)
#   engine-r22port   the served binary (build/, tests off) + SOURCE + SHA256
#   tests            a second tree build-tests/ with STRATA_BUILD_TESTS=ON (the C++ unit / parity tests, run by gap1.sh)
# ggml: our llama.cpp checkout (strata/third_party/llama.cpp) is at 3cf03257, the commit 0.2.0 pins
# (third_party/ggml/VERSION.txt) - checked below, so nothing is downloaded.
# Memory (the user, 10-19 evening: the build must not push free memory under the 16 GB floor): it runs inside a gap, so
# Strata is stopped (port_gap.sh begin); at most BUILD_JOBS (16) compile jobs; work/r22/build_memguard.sh pauses the
# build below 24 GB free and stops it below 18 GB (log logs/r22/build-memguard.log).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
NVCC=/usr/local/cuda-13.3/bin/nvcc; LL=$(readlink -f strata/third_party/llama.cpp); W=strata-r22port
[ "$(git -C $W rev-parse --abbrev-ref HEAD)" = r22-port020 ] || { echo "$W is not on r22-port020"; exit 1; }
[ -z "$(git -C $W status --porcelain --untracked-files=no)" ] || { echo "$W is dirty"; exit 1; }
[ "$(git -C $W rev-list --count v0.2.0-beta..HEAD)" = 26 ] || { echo "not 26 commits on v0.2.0-beta"; exit 1; }
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
mkdir -p engine-r22port && cp $W/build/strata engine-r22port/strata
H=$(git -C $W rev-parse HEAD)
echo "v0.2.0-beta + $(git -C $W rev-list --count v0.2.0-beta..HEAD) commits (branch r22-port020 $H), tree $(git -C $W rev-parse HEAD^{tree})" > engine-r22port/SOURCE
sha256sum engine-r22port/strata > engine-r22port/SHA256; cat engine-r22port/SOURCE engine-r22port/SHA256
