#!/bin/bash
# build-port028x.sh - round 22 gap 16 (10-30): build-port028.sh for the exact-v2 branch. r22-port028x (worktree
# strata-r22p028x) = r22-port028 + 8f7a48aa (STRATA_PREFILL_V2 takes the current kernels' term: v2 on = v2 off bit for
# bit; prefill_fused_iq_test part 3 requires it) = v0.2.8 + 28 -> engine-r22p028x. Twin: r22-port028x-meas (worktree
# strata-r22p028xm) = r22-port028-meas + the same commit + the MEASUREMENT STRATA_FORCE_T1 switch (check (2)'s reference
# in 1-token windows; results/r22/switch-diag/gr-fork.md) = v0.2.8 + 33 -> engine-r22p028xm. The ready branch r22-port028
# and its engines are not touched. Everything else as build-port028.sh (memory guard, pinned ggml, nice).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
NVCC=/usr/local/cuda-13.3/bin/nvcc; LL=$(readlink -f strata/third_party/llama.cpp); W=strata-r22p028x; BR=r22-port028x; NC=${PORT_COMMITS:-28}
[ "${1:-}" = twin ] && { W=strata-r22p028xm; BR=r22-port028x-meas; NC=$((NC + 5)); }
[ "$(git -C $W rev-parse --abbrev-ref HEAD)" = $BR ] || { echo "$W is not on $BR"; exit 1; }
[ -z "$(git -C $W status --porcelain --untracked-files=no)" ] || { echo "$W is dirty"; exit 1; }
[ "$(git -C $W rev-list --count v0.2.8..HEAD)" = "$NC" ] || { echo "not $NC commits on v0.2.8"; exit 1; }
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
if [ "${1:-}" = twin ]; then
  build build-twin ON strata spec_prob_test gated_proposal_test spec_verify_parity spec_proposal_parity \
    patch_guard_test cost_gate_test draft_cum_test prefill_fused_iq_test   # 10-29: our hand-ported switches' own tests
  mkdir -p engine-r22p028xm && cp $W/build-twin/strata engine-r22p028xm/strata
  echo "twin: v0.2.8 + $(git -C $W rev-list --count v0.2.8..HEAD) commits (branch $BR $(git -C $W rev-parse HEAD)), tree $(git -C $W rev-parse HEAD^{tree})" > engine-r22p028xm/SOURCE
  sha256sum engine-r22p028xm/strata > engine-r22p028xm/SHA256; cat engine-r22p028xm/SOURCE engine-r22p028xm/SHA256
  exit 0
fi
if [ "${1:-}" = tests ]; then
  build build-tests ON
  echo "tests built: $(cd $W/build-tests && ctest -N | tail -1)"
  exit 0
fi
build build OFF strata
mkdir -p engine-r22p028x && cp $W/build/strata engine-r22p028x/strata
H=$(git -C $W rev-parse HEAD)
echo "v0.2.8 + $(git -C $W rev-list --count v0.2.8..HEAD) commits (branch r22-port028x $H), tree $(git -C $W rev-parse HEAD^{tree})" > engine-r22p028x/SOURCE
sha256sum engine-r22p028x/strata > engine-r22p028x/SHA256; cat engine-r22p028x/SOURCE engine-r22p028x/SHA256
