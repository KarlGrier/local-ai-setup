#!/bin/bash
# build-basalt-fix.sh [engine|tests] - r23 (11-05): the Basalt prompt-path fix commits (results/r23/basalt-prompt/FIX-1105.md)
# on branch r23-basalt-prompt (worktree strata-r23basalt, head = the three "r23 fix:" commits on 3383d1f8d) -> a NEW
# engine folder engine-r23basalt-fix/. engine-r23basalt/ (gap a's build, which gap b uses) and the worktree's build/
# dir are NOT touched: this builds in build-fix/ and build-fix-tests/. The same flags as gap-basalt-a.sh's build23:
# Release, CUDA 13.3, "-DCMAKE_CUDA_ARCHITECTURES=89;120", the tree's pinned ggml (the shared llama.cpp checkout).
# Run it ONLY under work/r23/nogap-run.sh (nice 19, frozen while a gap is open), beside a serving 8080: the inline memory
# guard of build-port0211.sh (pause < 23 GB, freeze < 22 GB, stop < 21 GB; log logs/r23/build-basalt-fix-memguard.log),
# BUILD_JOBS 2 by default.
#   engine  strata only, tests OFF -> engine-r23basalt-fix/{strata,SOURCE,SHA256} + the gap-a build gates (warnings: no
#           prefill.cpp warning beyond the r22p0210 build's; strings: the three switch names) -> engine-r23basalt-fix/GATES
#   tests   the CPU tests (r23_plan_test - the new one -, share_rules_test, prefill_plan_test, routed_stream_test,
#           kva_test, batch_read_test; all header-only, no GPU) built AND run -> engine-r23basalt-fix/TESTS
#   gputest prefill_fused_iq_test built only (a GPU test: for a gap) -> engine-r23basalt-fix/TESTS-GPU
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare
W=$WS/strata-r23basalt; BR=r23-basalt-prompt; BASE=3383d1f8d; E=$WS/engine-r23basalt-fix
NVCC=/usr/local/cuda-13.3/bin/nvcc; LL=$(readlink -f $WS/strata/third_party/llama.cpp)
MODE=${1:-engine}
case $MODE in engine|tests|gputest) ;; *) sed -n 2,16p "$0"; exit 2;; esac
[ "$(git -C $W rev-parse --abbrev-ref HEAD)" = $BR ] || { echo "$W is not on $BR"; exit 1; }
[ -z "$(git -C $W status --porcelain --untracked-files=no)" ] || { echo "$W is dirty"; exit 1; }
git -C $W merge-base --is-ancestor $BASE HEAD || { echo "HEAD does not contain $BASE"; exit 1; }
[ "$(git -C $W rev-list --count $BASE..HEAD)" -ge 3 ] || { echo "fewer than 3 commits on $BASE"; exit 1; }
PIN=$(cut -d' ' -f1 $W/third_party/ggml/VERSION.txt)
[ "$(git -C $LL rev-parse HEAD)" = "$PIN" ] || { echo "llama.cpp checkout is not the pinned ggml $PIN"; exit 1; }
J=${BUILD_JOBS:-2}
LG=$WS/logs/r23/build-basalt-fix-memguard.log; mkdir -p $WS/logs/r23
desc() { local c; for c in $(pgrep -P $1); do echo $c; desc $c; done; }
guard() {   # build-port0211.sh's guard (MB): < 23 GB pauses ninja, > 23.5 GB resumes; < 22 GB freezes the compilers too,
  # thawed > 22.75 GB; < 21 GB stops the build. Re-applied every second (nogap-run.sh's SIGCONT cannot undo it).
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
build() {   # build DIR TESTS(ON|OFF) TARGET...   (RESUME=1: an existing, configured DIR is continued after a guard stop)
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
}
NV=$($NVCC --version | tail -1)
case $MODE in
  engine)
    build build-fix OFF strata
    mkdir -p $E && cp $W/build-fix/strata $E/strata
    echo "v0.2.10 + $(git -C $W rev-list --count v0.2.10..HEAD) commits (branch $BR $(git -C $W rev-parse HEAD)), tree $(git -C $W rev-parse 'HEAD^{tree}'); nvcc: $NV; jobs $J; build dir strata-r23basalt/build-fix" > $E/SOURCE
    sha256sum $E/strata > $E/SHA256
    # gap a's build gates (gap-basalt-a.sh build23): no new prefill.cpp warning against the r22p0210 build log; the names
    wk() { grep -E "prefill\.cpp:[0-9]+:[0-9]+: warning:" "$1" 2> /dev/null | sed -E 's/^.*warning: //' | sort | uniq -c | sed 's/^ *//' | sort; }
    new=$(comm -13 <(wk $WS/strata-r22p0210/build.log) <(wk $W/build-fix.log) | tr '\n' ';')
    st=$(mktemp -p $WS/work/r23/scratch-basalt-fix strings.XXXXXX); strings $E/strata > $st
    miss=""; for x in STRATA_PF_AHEAD STRATA_PF_TAIL_SPLIT STRATA_PF_FIRST_CHUNK; do grep -qx "$x" $st || miss="$miss $x"; done
    rm -f $st
    { [ -z "$new" ] && echo "warnings PASS no prefill.cpp warning beyond the r22p0210 build's ($(wk $W/build-fix.log | wc -l) kinds)" \
        || echo "warnings FAIL new prefill.cpp warning(s): ${new:0:240}"
      [ -z "$miss" ] && echo "strings PASS STRATA_PF_AHEAD, STRATA_PF_TAIL_SPLIT, STRATA_PF_FIRST_CHUNK in the binary" || echo "strings FAIL missing:$miss"
    } > $E/GATES
    cat $E/SOURCE $E/SHA256 $E/GATES;;
  tests)
    T="r23_plan_test share_rules_test prefill_plan_test routed_stream_test kva_test batch_read_test"
    build build-fix-tests ON $T
    out=$E/TESTS; mkdir -p $E
    echo "CPU tests at $(git -C $W rev-parse HEAD) (strata-r23basalt/build-fix-tests; nvcc: $NV)" > $out
    rc=0
    for t in $T; do
      f=$(find $W/build-fix-tests -maxdepth 3 -type f -name $t -perm -u+x | head -1)
      if [ -z "$f" ]; then echo "$t MISSING (not built)" >> $out; rc=1; continue; fi
      if timeout 300 nice -n 19 $f > $W/build-fix-tests/$t.out 2>&1; then echo "$t PASS ($(tail -1 $W/build-fix-tests/$t.out | cut -c1-120))" >> $out
      else echo "$t FAIL rc $? ($(tail -1 $W/build-fix-tests/$t.out | cut -c1-160))" >> $out; rc=1; fi
    done
    cat $out; exit $rc;;
  gputest)
    RESUME=1 build build-fix-tests ON prefill_fused_iq_test
    f=$(find $W/build-fix-tests -maxdepth 3 -type f -name prefill_fused_iq_test -perm -u+x | head -1)
    echo "prefill_fused_iq_test at $(git -C $W rev-parse HEAD): ${f:+BUILT ($f; a GPU test: run it only in a gap)}${f:-MISSING}" | tee $E/TESTS-GPU;;
esac
