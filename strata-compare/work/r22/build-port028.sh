#!/bin/bash
# build-port028.sh - round 22 (10-29, Karl: v0.2.8 is the port target): the hand-ported series rebased onto v0.2.8, branch r22-port028 (worktree strata-r22p028) = v0.2.7 + 17 of P021m's commits (results/r22/port-027.md) -> engine-r22p028. Copy of build-port021m.sh. Only inside a phase 4 gap
# (work/r22/port_gap4.sh begin ... end), with Strata stopped. The user, 10-21 evening: if the next gap's two checks pass
# (40-prompt kernel check, C vs A with the rebuilt tool-call turns), 8080 switches to THIS build, not to 0.2.2.
#   strata-r22p021n  worktree of branch r22-port021-next = r22-port021 (P021: v0.2.1 + our 26 commits) + 4518c9b3 (the
#                    cost gate past its table), 632ae8b7 (STRATA_DRAFT_CUM) and 785e45df (STRATA_PREFILL_V2): 29 commits,
#                    cherry-picked from r22-port022-next (one conflict: 0.2.2's spec_start_test line in CMakeLists.txt)
#   engine-r22p028  the binary (build/, tests off) + SOURCE + SHA256; the picture reader stays engine-r22p021/strata-vision
#   tests            a second tree build-tests/ with STRATA_BUILD_TESTS=ON (the C++ unit / parity tests, run by gap1.sh)
#   twin             (10-27, Karl: upstream's sampling path must pass the near-tie distribution test our exact sampling
#                    passed) the MEASUREMENT twin: branch r22-port027-meas (worktree strata-r22p027m) = r22-port027 + the
#                    4 MEASUREMENT commits (patches/r20-meas-v04441, 6 conflicts resolved by hand: both sides kept) ->
#                    engine-r22p028m, built with tests ON in build-twin/ together with upstream's sampler tests
#                    (spec_prob_test, gated_proposal_test, spec_verify_parity, spec_proposal_parity)
# ggml: our llama.cpp checkout (strata/third_party/llama.cpp) is at 3cf03257, the commit 0.2.0 pins
# (third_party/ggml/VERSION.txt) - checked below, so nothing is downloaded.
# Memory (the user, 10-19 evening: the build must not push free memory under the 16 GB floor): it runs inside a gap, so
# Strata is stopped (port_gap.sh begin); at most BUILD_JOBS (16) compile jobs; work/r22/build_memguard.sh pauses the
# build below 24 GB free and stops it below 18 GB (log logs/r22/build-memguard.log).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
NVCC=/usr/local/cuda-13.3/bin/nvcc; LL=$(readlink -f strata/third_party/llama.cpp); W=strata-r22p028; BR=r22-port028; NC=${PORT_COMMITS:-27}   # 10-29: 27 rebased onto v0.2.8 (PORT_COMMITS after a culprit drop)
[ "${1:-}" = twin ] && { W=strata-r22p028m; BR=r22-port028-meas; NC=$((NC + 4)); }
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
  mkdir -p engine-r22p028m && cp $W/build-twin/strata engine-r22p028m/strata
  echo "twin: v0.2.8 + $(git -C $W rev-list --count v0.2.8..HEAD) commits (branch $BR $(git -C $W rev-parse HEAD)), tree $(git -C $W rev-parse HEAD^{tree})" > engine-r22p028m/SOURCE
  sha256sum engine-r22p028m/strata > engine-r22p028m/SHA256; cat engine-r22p028m/SOURCE engine-r22p028m/SHA256
  exit 0
fi
if [ "${1:-}" = tests ]; then
  build build-tests ON
  echo "tests built: $(cd $W/build-tests && ctest -N | tail -1)"
  exit 0
fi
build build OFF strata
mkdir -p engine-r22p028 && cp $W/build/strata engine-r22p028/strata
H=$(git -C $W rev-parse HEAD)
echo "v0.2.8 + $(git -C $W rev-list --count v0.2.8..HEAD) commits (branch r22-port028 $H), tree $(git -C $W rev-parse HEAD^{tree})" > engine-r22p028/SOURCE
sha256sum engine-r22p028/strata > engine-r22p028/SHA256; cat engine-r22p028/SOURCE engine-r22p028/SHA256
