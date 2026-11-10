#!/bin/bash
# build-afetch.sh - backlog I (Karl 11-09): r23-adaptfetch (worktree strata-r23afetch) = r22-port028x (P028x, v0.2.8 + 29)
# + upstream 24c6c2f68 (STRATA_ADAPT_FETCH) + our helper-cache patch = v0.2.8 + 31 -> engine-r23afetch. Flags as
# work/r22/build-port028x.sh (Release, CUDA 13.3, "89;120", the pinned llama.cpp ggml, its memory guard), but nice 19 and
# BUILD_JOBS 2 beside a serving 8080 (Karl 11-05). Run ONLY under work/r23/nogap-run.sh. Nothing served or installed.
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
NVCC=/usr/local/cuda-13.3/bin/nvcc; LL=$(readlink -f strata/third_party/llama.cpp); W=strata-r23afetch; BR=r23-adaptfetch; NC=${PORT_COMMITS:-31}
[ "$(git -C $W rev-parse --abbrev-ref HEAD)" = $BR ] || { echo "$W is not on $BR"; exit 1; }
[ -z "$(git -C $W status --porcelain --untracked-files=no)" ] || { echo "$W is dirty"; exit 1; }
[ "$(git -C $W rev-list --count v0.2.8..HEAD)" = "$NC" ] || { echo "not $NC commits on v0.2.8"; exit 1; }
PIN=$(cut -d' ' -f1 $W/third_party/ggml/VERSION.txt)
[ "$(git -C $LL rev-parse HEAD)" = "$PIN" ] || { echo "llama.cpp checkout is not the pinned ggml $PIN"; exit 1; }
J=${BUILD_JOBS:-2}
MODE=afetch; W=$WS/$W   # the inline memory guard of build-port0213.sh (it watches ninja under $W)
LG=$WS/logs/r23/build-afetch-memguard.log; mkdir -p $WS/logs/r23
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
W=strata-r23afetch
d=build
rm -rf $W/$d
(cd $W && nice -n 19 cmake -G Ninja -S . -B $d -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
   "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=$NVCC -DSTRATA_GGML_DIR="$LL" > $d-configure.log 2>&1 \
 && nice -n 19 cmake --build $d --target strata -j $J > $d.log 2>&1)
H=$(git -C $W rev-parse HEAD)
mkdir -p engine-r23afetch && cp $W/build/strata engine-r23afetch/strata
echo "v0.2.8 + $(git -C $W rev-list --count v0.2.8..HEAD) commits (branch $BR $H), tree $(git -C $W rev-parse HEAD^{tree})" > engine-r23afetch/SOURCE
sha256sum engine-r23afetch/strata > engine-r23afetch/SHA256; cat engine-r23afetch/SOURCE engine-r23afetch/SHA256
