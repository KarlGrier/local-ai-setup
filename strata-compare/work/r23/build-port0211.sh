#!/bin/bash
# build-port0211.sh [engine|tests|stock] - the v0.2.11 port (Karl 11-05, results/r23/port-0211/PORT.md): build-port0210.sh
# for branch r23-port0211 (worktree strata-r23p0211 = v0.2.11 c3b3f5035 + our 28) -> engine-r23p0211 (configs/P0211x.json).
# The served engine-r22p028x, its tree and every other worktree are not touched. The same flags as build-port0210.sh:
# Release, CUDA 13.3, "-DCMAKE_CUDA_ARCHITECTURES=89;120", the tree's pinned ggml (the shared llama.cpp checkout), the
# 8-row window build (CUDA auto), nice, <= BUILD_JOBS jobs. Run it ONLY under work/r23/nogap-run.sh (nice 19, frozen while
# a gap is open), i.e. beside a serving 8080: build_memguard.sh does not watch these trees and its resume point (32 GB) never
# comes while 8080 serves (~23-25 GB available), so an inline guard runs instead (guard() below; log
# logs/r23/build-port0211-memguard.log). BUILD_JOBS 2 there (11-05).
#   engine  strata only, tests OFF, into strata-r23p0211/build -> engine-r23p0211/{strata,SOURCE,SHA256}
#   tests   the unit tests gap 17 ran (ours, upstream's sampler tests, prefill_fused_iq_test) + v0.2.11's
#           native_expert_parity (the Q5_0 dot), tests ON, into strata-r23p0211/build-tests (no strata target)
#   stock   plain v0.2.11 (detached worktree strata-v0211stock, created here if missing) -> engine-v0211stock: the
#           gate's release reference ("patched, every switch off = the release")
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare
NVCC=/usr/local/cuda-13.3/bin/nvcc; LL=$(readlink -f $WS/strata/third_party/llama.cpp); NC=${PORT_COMMITS:-28}
MODE=${1:-engine}
case $MODE in
  engine|tests) W=$WS/strata-r23p0211; BR=r23-port0211;;
  stock) W=$WS/strata-v0211stock;;
  *) sed -n 2,13p "$0"; exit 2;;
esac
if [ $MODE = stock ]; then
  [ -d $W ] || git -C $WS/strata worktree add --detach $W v0.2.11
  [ "$(git -C $W rev-parse HEAD)" = "$(git -C $WS/strata rev-parse 'v0.2.11^{commit}')" ] || { echo "$W is not at v0.2.11"; exit 1; }
else
  [ "$(git -C $W rev-parse --abbrev-ref HEAD)" = $BR ] || { echo "$W is not on $BR"; exit 1; }
  [ "$(git -C $W rev-list --count v0.2.11..HEAD)" = "$NC" ] || { echo "not $NC commits on v0.2.11"; exit 1; }
fi
[ -z "$(git -C $W status --porcelain --untracked-files=no)" ] || { echo "$W is dirty"; exit 1; }
PIN=$(cut -d' ' -f1 $W/third_party/ggml/VERSION.txt)
[ "$(git -C $LL rev-parse HEAD)" = "$PIN" ] || { echo "llama.cpp checkout is not v0.2.11's pinned ggml $PIN"; exit 1; }
J=${BUILD_JOBS:-16}
LG=$WS/logs/r23/build-port0211-memguard.log; mkdir -p $WS/logs/r23
desc() { local c; for c in $(pgrep -P $1); do echo $c; desc $c; done; }
guard() {   # the memory guard beside a serving 8080 (MB): < 23 GB pauses ninja (no new jobs; its compilers finish), > 23.5 GB
  # resumes it; < 22 GB also freezes the running compilers (no more growth), thawed > 22.75 GB; < 21 GB stops the build (one
  # GB above the research queue's 20 GB relief restart of 8080). Re-applied every second, so nogap-run.sh's SIGCONT after
  # a gap cannot undo a pause or a freeze.
  set +e; local low=999999 st=run n a p k
  trap 'for p in $(pgrep -x ninja); do case $(readlink /proc/$p/cwd 2> /dev/null) in $W|$W/*) kill -CONT $p $(desc $p) 2> /dev/null;; esac; done; echo "$(date "+%F %T") $MODE end: lowest MemAvailable $low MB" >> $LG; exit 0' TERM
  echo "$(date '+%F %T') $MODE start, $J jobs (pause < 23 GB / resume > 23.5 GB, freeze < 22 GB / thaw > 22.75 GB, stop the build < 21 GB)" >> $LG
  while :; do
    n=""; for p in $(pgrep -x ninja); do case $(readlink /proc/$p/cwd 2> /dev/null) in $W|$W/*) n="$n $p";; esac; done
    a=$(awk '/^MemAvailable/ {print int($2 / 1024)}' /proc/meminfo)
    if [ -n "$n" ]; then
      [ $a -lt $low ] && low=$a
      k=""; for p in $n; do k="$k $(desc $p | tr '\n' ' ')"; done
      if [ $a -lt 21504 ]; then
        for p in $n $k; do kill -CONT $p 2> /dev/null; kill -TERM $p 2> /dev/null; done
        echo "$(date '+%F %T') MemAvailable $a MB < 21 GB: build STOPPED (ninja$n)" >> $LG; st=run
      elif [ $a -lt 22528 ] || { [ $st = frozen ] && [ $a -le 23296 ]; }; then
        for p in $n $k; do kill -STOP $p 2> /dev/null; done
        [ $st = frozen ] || echo "$(date '+%F %T') MemAvailable $a MB: ninja$n and its compilers frozen" >> $LG; st=frozen
      elif [ $a -lt 23552 ] || { [ $st != run ] && [ $a -le 24064 ]; }; then
        for p in $n; do kill -STOP $p 2> /dev/null; done; for p in $k; do kill -CONT $p 2> /dev/null; done
        [ $st = paused ] || echo "$(date '+%F %T') MemAvailable $a MB: ninja$n paused (its compilers run)" >> $LG; st=paused
      elif [ $st != run ]; then
        for p in $n $k; do kill -CONT $p 2> /dev/null; done; echo "$(date '+%F %T') MemAvailable $a MB: resumed" >> $LG; st=run
      fi
    fi
    sleep 1
  done
}
guard 8>&- 9>&- & GP=$!
trap 'kill -TERM $GP 2> /dev/null' EXIT
build() {   # build DIR TESTS(ON|OFF) TARGET...   (RESUME=1: an existing, configured DIR is continued - after a guard stop -
  # instead of wiped; ninja redoes every step without a build-log entry, so an interrupted compile is redone)
  local d=$1 t=$2; shift 2
  if [ "${RESUME:-0}" = 1 ] && [ -f $W/$d/build.ninja ] && grep -q "STRATA_BUILD_TESTS:BOOL=$t" $W/$d/CMakeCache.txt 2> /dev/null; then
    echo "$(date '+%F %T') resume $W/$d" >> $W/$d.log
  else
    rm -rf $W/$d
    nice -n 5 cmake -G Ninja -S $W -B $W/$d -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=$t \
      "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=$NVCC -DSTRATA_GGML_DIR="$LL" > $W/$d-configure.log 2>&1
    : > $W/$d.log
  fi
  nice -n 5 cmake --build $W/$d --target "$@" -j $J >> $W/$d.log 2>&1
  grep -q 'windows hold up to 8 rows' $W/$d-configure.log || { echo "$W/$d-configure.log does not say 8-row windows"; exit 1; }
}
NV=$($NVCC --version | tail -1)
case $MODE in
  engine)
    build build OFF strata
    E=$WS/engine-r23p0211; mkdir -p $E && cp $W/build/strata $E/strata
    echo "v0.2.11 + $(git -C $W rev-list --count v0.2.11..HEAD) commits (branch $BR $(git -C $W rev-parse HEAD)), tree $(git -C $W rev-parse 'HEAD^{tree}'); nvcc: $NV; jobs $J" > $E/SOURCE
    sha256sum $E/strata > $E/SHA256; cat $E/SOURCE $E/SHA256;;
  tests)
    build build-tests ON patch_guard_test cost_gate_test draft_cum_test spec_prob_test gated_proposal_test \
      spec_verify_parity spec_proposal_parity prefill_fused_iq_test native_expert_parity
    echo "tests built in $W/build-tests at $(git -C $W rev-parse HEAD); nvcc: $NV";;
  stock)
    build build OFF strata
    E=$WS/engine-v0211stock; mkdir -p $E && cp $W/build/strata $E/strata
    echo "stock v0.2.11 ($(git -C $W rev-parse HEAD), detached worktree strata-v0211stock), none of our commits, tree $(git -C $W rev-parse 'HEAD^{tree}'); nvcc: $NV; jobs $J" > $E/SOURCE
    sha256sum $E/strata > $E/SHA256; cat $E/SOURCE $E/SHA256;;
esac
