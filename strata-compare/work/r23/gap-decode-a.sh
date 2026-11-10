#!/bin/bash
# gap-decode-a.sh - round 23, the exact decode items, part a (Karl 11-04, queued second, one gap between two 7d
# questions; results/r23/decode-timing/GATE-PLAN.md sections 1-3.3 + ANALYSIS.md section 7). WRITTEN 11-04, NOT RUN.
# Measurements only: P028x stays served, nothing switches. Run: `bash work/r23/gap-decode-a.sh` (no arguments).
#   0 before the gap (no GPU, 8080 untouched): refuse if tmp/gpu-test.lock is held or a model server other than the 8080
#     queue's P028x runs; the worktree strata-r23decode = branch r23-decode-exact at c4c15d32c (fdd2fffa8 + 2, v0.2.10 +
#     30), clean; llama.cpp = its pinned ggml; configs, references (gap 17's g17-p210a exact7 + p210 yardstick), tools
#   1 port_gap4.sh begin (the running question finishes, test lock, 8080 down) - nothing else runs during the compile
#   2 BUILD in the gap (~15-20 min, CPU): cmake with tests ON into strata-r23decode/build, targets strata pool_tasks_test
#     pool_test pool_stress numa_pool_test patch_guard_test (nice 5, 16 jobs, a memory guard on ninja); installed as
#     engine-r23decode/strata + SOURCE + SHA256; source / 8-row / warning checks
#   3 TESTS (~10 min, CPU): pool_tasks_test (synthetic, then one real blob per type pair of the pack), pool_test
#     --selftest, numa_pool_test, pool_stress 20 (plain; STRATA_POOL_ONE_BATCH=1), patch_guard_test, the serve tests
#   4 exact7 x7 at pin 2500 (~25 min): r23-B vs g17-p210a, r23-B2 vs r23-B, r23-L / r23-O / r23-LO vs r23-B, r23-Bs (the
#     solo base), r23-Os vs r23-Bs; each engine's environment checked as it starts, each run's switch start lines
#   5 pf_yardstick long40 on r23-B and r23-LO (~18 min): 0 of 40 logit files may differ (B vs LO, B vs gap 17's p210)
#   6 the 4 timing arms (~18 min): one screen pass each on r23-Bt, r23-LOt (both cards), r23-Bst, r23-Ost (5080 alone),
#     read with t2_report.py; then the two-card timing pass on P028x: results/r23/decode-timing/t2pass.sh dv (~4 min)
#   7 decode_rules.py decide-a -> gap-a/decision.txt + decision.json (part b reads it); port_gap4.sh end + kernel check
# No new step after the deadline (R23A_MAX_MIN, default 125 min after the gap opens). A kernel check after every step; a
# failure stops new steps and leaves the gap OPEN (8080 down, exit 3: Karl decides). Exit 0 = done (outcome in
# decision.txt), 1 = refused / not opened (8080 untouched), 4 = port_gap4.sh end failed. Steps: work/r23/GAPS-README.md.
set -u -o pipefail
exec 8>&- 9>&-                     # no inherited lock descriptor (work/r22 lock-fd rule): this script holds none itself
WS=/home/USER/ai-speed-testing/strata-compare
export RB_CACHE=$WS/tmp/r23
source $WS/bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
for v in $(compgen -e | grep '^STRATA_'); do [ "$v" = STRATA_MON_GPU ] || unset "$v"; done   # no stray switch reaches an engine
export PROMPT_DIR=$WS/bringup/out/r20a/prompts EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
P=$WS/.venv/bin/python; KR=$WS/work/r22; RU=$WS/work/r23/decode_rules.py; R17=$KR/g17_rules.py
D=$WS/results/r23/decode-timing; GC=$D/gate-configs; PROF=$WS/bringup/out/logs/prof
O=$D/gap-a; G=$O/gates.txt; Y=$O/pfy; TM=$O/timing; TS=$O/tests
S=$D/gap-decode-starts.log         # until the pre-gap checks pass (then $O/summary.txt)
W=$WS/strata-r23decode; E=$WS/engine-r23decode; EXE=$E/strata
BR=r23-decode-exact; HEAD_WANT=c4c15d32c; BASE=fdd2fffa8; NCOMMITS=30
NVCC=/usr/local/cuda-13.3/bin/nvcc; LL=$(readlink -f $WS/strata/third_party/llama.cpp)
GGUF=$WS/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf; MTP=$WS/strata-v0115/mtp/rt
Y17=$WS/results/r22/gap17/pfy/p210; E7REF=g17-p210a
P028X_SHA=f4c4f654fb24             # engine-r22p028x/strata, served on 8080 since 10-30
MAXM=${R23A_MAX_MIN:-125}
ITEMS="x-math s-math x-code s-code x-p2000 x-32k x-112k"
declare -A E7L=([B]=r23-B [B2]=r23-B2 [L]=r23-L [O]=r23-O [LO]=r23-LO [Bs]=r23-Bs [Os]=r23-Os)
declare -A E7W=([B]=none [B2]=none [L]=late [O]=one [LO]=late,one [Bs]=none [Os]=one)
mkdir -p $D $WS/tmp/r23
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
gate() { echo "$1 $2 ${*:3} [23a $(date '+%m-%d %H:%M')]" >> $G; say "  gate $*"; }
gstat() { grep "^$1 " $G 2> /dev/null | tail -1 | cut -d' ' -f2; }
KFAIL=0; BUILT=0; T0=$(date +%s); DEADLINE=$T0
kc() { $WS/bringup/lib/kcheck.sh "r23a-$1" > /dev/null || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; return 1; }; }
left() { echo $(( DEADLINE - $(date +%s) )); }
ok_to_go() { [ $KFAIL = 0 ] && [ $(left) -gt 0 ]; }
sha12() { sha256sum "$1" | cut -c1-12; }
elog() { $P -c "import json; print(json.load(open('$1'))['log'])"; }
exe_of() { $P -c "import json; print(json.load(open('$1'))['exe'])"; }
slog() { ls -t $WS/bringup/out/logs/server_$1_*.log 2> /dev/null | head -1; }   # the newest server log of a with_server label
ppid_of() { local s; s=$(cat /proc/$1/stat 2> /dev/null) || return 0; s=${s##*) }; set -- $s; echo "${2:-}"; }

preflight() {   # refuse (exit 1, nothing touched) when a measurement holds the GPU lock or a model server other than the
  # 8080 queue's P028x runs: every engine process (exact names) and every NVIDIA compute process must belong to the server
  # listening on 8080, and that server's engine must be P028x (engine-r22p028x, sha $P028X_SHA; its vision helper allowed)
  local l p q apps bad=""
  if [ -s $WS/tmp/port-gap.lockpid ] && kill -0 "$(cat $WS/tmp/port-gap.lockpid)" 2> /dev/null; then
    say "another gap holds the test lock (tmp/port-gap.lockpid $(cat $WS/tmp/port-gap.lockpid)) - not started"; exit 1
  fi
  if ! flock -n -x $WS/tmp/gpu-test.lock true 2> /dev/null; then
    say "tmp/gpu-test.lock is held (a measurement or a test server) - not started"; exit 1
  fi
  l=$(ss -H -ltnp "( sport = :8080 )" 2> /dev/null | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2)
  apps=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2> /dev/null) || { say "nvidia-smi did not answer - not started"; exit 1; }
  for p in $( { for x in strata strata-host strata-vision strata-dsv41 llama-server ollama; do pgrep -x "$x"; done; echo "$apps"; } \
              | tr -d ' ' | grep -E '^[0-9]+$' | sort -un); do
    q=$p; while [ -n "$q" ] && [ "$q" -gt 1 ] && [ "$q" != "${l:-none}" ]; do q=$(ppid_of $q); done
    if [ -n "$l" ] && [ "$q" = "$l" ]; then
      case $(cat /proc/$p/comm 2> /dev/null) in
        strata|strata-host) [ "$(sha12 /proc/$p/exe 2> /dev/null)" = $P028X_SHA ] || bad="$bad 8080-engine:$p($(readlink /proc/$p/exe))";;
        strata-vision) ;;
        *) bad="$bad 8080:$p($(cat /proc/$p/comm 2> /dev/null))";;
      esac
    else bad="$bad $p($(cat /proc/$p/comm 2> /dev/null))"; fi
  done
  ss -H -ltn "( sport = :8081 )" 2> /dev/null | grep -q . && bad="$bad listener-on-8081(a-test-server)"
  [ -z "$bad" ] || { say "a model server other than the 8080 queue's P028x is running:$bad - not started"; exit 1; }
}
wait_mem() {   # after 8080 stops: its engines gone and their memory back, at most 120 s
  local i x left_p m
  for i in $(seq 60); do
    left_p=""; for x in strata strata-host strata-vision strata-dsv41; do pgrep -x $x > /dev/null && left_p="$left_p $x"; done
    m=$(awk '/^MemAvailable/ {printf "%d", $2 / 1048576}' /proc/meminfo)
    [ -z "$left_p" ] && [ "$m" -ge 40 ] && break
    sleep 2
  done
  say "8080 down: engines left:${left_p:- none}, MemAvailable ${m} GB"
}
fatalchk() {   # fatalchk NAME ENGINE_LOG OFFSET LABEL (gap 17): a fatal GPU error / stall / engine restart / non-finite
  local n=$1 L=$2 off=$3 sl hits
  sl=$(slog $4)
  hits=$( { tail -c +$((off + 1)) $L 2> /dev/null; [ -n "$sl" ] && cat $sl; } | grep -c -E "fatal GPU error|no progress for [0-9]+ s during a request|the engine had stopped \(exit code|became non-finite")
  [ "$hits" = 0 ] || gate fatal_$n FAIL "$hits line(s): fatal GPU error / stall / engine restart / non-finite (engine log $L from byte $off; $sl)"
}

buildguard() {   # build_memguard.sh's thresholds for ninja in strata-r23decode (build_memguard.sh does not watch this tree):
  # MemAvailable < 24 GB pauses ninja (its running compilers finish), > 32 GB resumes it, < 14 GB stops the build
  local p n a paused="" idle=0 low=999999 LG=$O/build-memguard.log
  trap 'for p in $paused; do kill -CONT $p 2> /dev/null; done; echo "$(date "+%F %T") end: lowest MemAvailable $low MB" >> $LG; exit 0' TERM
  echo "$(date '+%F %T') start (pause < 24 GB, resume > 32 GB, stop the build < 14 GB)" >> $LG
  while [ $idle -lt 1800 ]; do
    n=""; for p in $(pgrep -x ninja); do case $(readlink /proc/$p/cwd 2> /dev/null) in $W|$W/*) n="$n $p";; esac; done
    a=$(awk '/^MemAvailable/ {print int($2 / 1024)}' /proc/meminfo)
    if [ -z "$n" ]; then idle=$((idle + 1)); paused=""; sleep 1; continue; fi
    idle=0; [ $a -lt $low ] && low=$a
    if [ $a -lt 14336 ]; then
      for p in $n; do kill -CONT $p 2> /dev/null; kill -TERM $p 2> /dev/null; done; paused=""
      echo "$(date '+%F %T') MemAvailable $a MB < 14 GB: build STOPPED (ninja$n)" >> $LG
    elif [ $a -lt 24576 ] && [ -z "$paused" ]; then
      for p in $n; do kill -STOP $p 2> /dev/null; done; paused=$n; echo "$(date '+%F %T') MemAvailable $a MB: ninja$n paused" >> $LG
    elif [ -n "$paused" ] && [ $a -gt 32768 ]; then
      for p in $paused; do kill -CONT $p 2> /dev/null; done; echo "$(date '+%F %T') MemAvailable $a MB: resumed" >> $LG; paused=""
    fi
    sleep 1
  done
  echo "$(date '+%F %T') end (idle): lowest MemAvailable $low MB" >> $LG
}
build() {   # GATE-PLAN section 1: Release, CUDA 13.3, arch 89;120, the tree's pinned ggml, tests ON, nice 5, <= 16 jobs
  [ "$(git -C $LL rev-parse HEAD)" = "$(cut -d' ' -f1 $W/third_party/ggml/VERSION.txt)" ] || { echo "llama.cpp is not $W's pinned ggml" > $O/build.log; return 1; }
  rm -rf $W/build
  nice -n 5 cmake -G Ninja -S $W -B $W/build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=ON \
      "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=$NVCC -DSTRATA_GGML_DIR="$LL" > $O/build-configure.log 2>&1 8>&- 9>&- \
    && nice -n 5 cmake --build $W/build --target strata pool_tasks_test pool_test pool_stress numa_pool_test patch_guard_test \
      -j ${BUILD_JOBS:-16} > $O/build.log 2>&1 8>&- 9>&-
}
tst() {   # tst GATE TIMEOUT CMD...: one test under the memory guard -> gate (PASS = rc 0)
  local g=$1 to=$2 rc; shift 2
  timeout $to $P $WS/bringup/lib/guard.py r23a-$g -- "$@" > $TS/$g.txt 2>&1 < /dev/null 8>&- 9>&-
  rc=$?
  say "  $g rc $rc: $(grep -v '^\s*$' $TS/$g.txt | tail -1 | cut -c1-160)"
  if [ $rc = 0 ]; then gate $g PASS "rc 0: $(grep -v '^\s*$' $TS/$g.txt | tail -1 | cut -c1-120)"
  else gate $g FAIL "rc $rc: $(grep -v '^\s*$' $TS/$g.txt | tail -2 | tr '\n' ' ' | cut -c1-200)"; fi
}
e7() {   # e7 KEY CONFIG NGPU REF [ENVX]: exact7 at pin 2500 (bringup/lib/exact7.sh: 7 items, --adapt-swaps 0
  # --suffix-draft 0), every item's engine environment checked as it starts (ENVX: K=V over the config's), its gate, the
  # switches' start lines in its 7 logs
  local k=$1 cfg=$2 ng=$3 ref=$4 ex=${5:-} L=${E7L[$1]} jp sets="" kv info="" i errs=""
  ok_to_go || { say "skipped exact7 $L (deadline or kernel check)"; return 1; }
  for kv in $ex; do sets="$sets --set $kv"; done
  say "exact7 $L ($(basename $cfg), $ng GPU(s), against $ref${ex:+; $ex})"
  ( PIN_CACHE=2500 REF=$ref ENVX="$ex" $WS/bringup/lib/exact7.sh $L $cfg 2>&1 | tail -9 | tee -a $S ) 8>&- 9>&- &
  jp=$!
  $P -I -B $RU envcli $EXE $cfg --job $jp --mode e7 --ngpu $ng --kill $sets --gate env_e7-$L --gates $G 8>&- 9>&- 2>&1 \
    | tee $O/env-e7-$L.txt | tail -1 | tee -a $S
  wait $jp
  [ $k = Bs ] && info=--info
  $P -I -B $RU e7gate $S $L $info --gate e7_$k --gates $G | tee -a $S
  for i in $ITEMS; do errs="$errs $PROF/$L-$i.err"; done
  $P -I -B $RU lines --want ${E7W[$k]} $errs --gate e7lines_$k --gates $G | tee -a $S
  kc e7-$L
}
pfy() {   # pfy NAME CONFIG: pf_yardstick long40 (gap 17's form), its engine's environment checked as it starts
  local n=$1 cfg=$2 jp
  ok_to_go || { say "skipped pf_yardstick $n (deadline or kernel check)"; return 1; }
  say "pf_yardstick long40 $n ($(basename $cfg))"
  ( $P $WS/bringup/lib/guard.py pfy23-$n -- $P -I $KR/pf_yardstick.py run $cfg $Y/$n --set long40 2>&1 | grep -v "^engine:" | tail -3 | sed "s/^/pfy $n: /" | tee -a $S ) 8>&- 9>&- &
  jp=$!
  $P -I -B $RU envcli $EXE $cfg --job $jp --mode pfy --ngpu 2 --kill --gate env_pfy-$n --gates $G 8>&- 9>&- 2>&1 | tail -1 | tee -a $S
  wait $jp
  kc pfy-$n
}
ndiff() {   # ndiff DIR_A DIR_B: "differing files of all" over A's first.* logit files
  local nd=0 nf=0 f
  for f in $1/first.*; do [ -e "$f" ] || continue; nf=$((nf + 1)); cmp -s $f $2/$(basename $f) || nd=$((nd + 1)); done
  echo "$nd $nf"
}
tarm() {   # tarm NAME CONFIG NGPU WANT: one 9-workload screen pass with the timing logs on (GATE-PLAN 3.3; gap 18's harness)
  local n=$1 cfg=$2 ng=$3 want=$4 L off
  ok_to_go || { say "skipped timing arm $n (deadline or kernel check)"; return 1; }
  L=$(elog $cfg); touch $L; off=$(stat -c %s $L)
  say "timing arm $n ($(basename $cfg), $ng GPU(s))"
  $WS/bringup/lib/with_server.sh r23a-$n $cfg -- "$P -I -B $R17 envcheck $EXE $cfg --ngpu $ng --pins --gate env_t-$n --gates $G && bash $KR/abarm.sh http://127.0.0.1:8081 $off $TM $n ${n}n=normal:1:W1,W2,W3 ${n}a=agent:1 ${n}r=research4:1" 8>&- 9>&- 2>&1 \
    | grep -E "engine pid [0-9]+:|ENV CHECK|tok/s|ready|exited|refus|Error|GUARD|vram" | tee -a $S
  tail -c +$((off + 1)) $L > $TM/engine-$n.log
  fatalchk t-$n $L $off r23a-$n
  $P -I -B $RU lines --want $want $TM/engine-$n.log $(slog r23a-$n) --gate lines_t-$n --gates $G | tee -a $S
  python3 -I $D/t2_report.py $TM/engine-$n.log > $TM/report-$n.txt 2>&1
  say "  timing $n: $(grep -v '^\s*$' $TM/report-$n.txt | head -1 | cut -c1-200)"
  kc t-$n
}
end_gap() {
  if [ $KFAIL = 1 ]; then say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides (no decision file: part b will refuse)"; exit 3; fi
  $P -I -B $RU decide-a $O > /dev/null 2>&1 || say "decode_rules.py decide-a failed - rerun it by hand ($RU decide-a $O)"
  [ -f $O/decision.txt ] && tee -a $S < $O/decision.txt
  say "P028x back on 8080 (port_gap4.sh end) - nothing switched"
  if ! $KR/port_gap4.sh end 8>&- 9>&- 2>&1 | tee -a $S; then
    say "port_gap4.sh end FAILED: 8080 and the research queue need a look"; exit 4
  fi
  kc end || { say "the kernel check failed after P028x came back: Karl decides"; exit 3; }
  say "decode gap a done ($(( ($(date +%s) - T0) / 60 )) min with 8080 down)"
  exit 0
}

# ================================================================ before the gap (no GPU; 8080 untouched)
say "start attempt: work/r23/gap-decode-a.sh (pre-gap checks)"
preflight
[ -f $WS/tmp/r19/kwatch.pid ] && kill -0 "$(cat $WS/tmp/r19/kwatch.pid)" 2> /dev/null || { say "the kernel-log watcher is not running - not started"; exit 1; }
why=""
[ "$(git -C $W rev-parse --abbrev-ref HEAD 2> /dev/null)" = $BR ] || why="$why not-on-$BR"
[ "$(git -C $W rev-parse HEAD 2> /dev/null | cut -c1-9)" = $HEAD_WANT ] || why="$why HEAD-not-$HEAD_WANT"
[ "$(git -C $W rev-parse HEAD~2 2> /dev/null | cut -c1-9)" = $BASE ] || why="$why HEAD~2-not-the-port-$BASE"
[ "$(git -C $W rev-list --count v0.2.10..HEAD 2> /dev/null)" = $NCOMMITS ] || why="$why not-v0.2.10+$NCOMMITS"
[ -z "$(git -C $W status --porcelain --untracked-files=no 2> /dev/null)" ] || why="$why dirty"
[ "$(git -C $LL rev-parse HEAD)" = "$(cut -d' ' -f1 $W/third_party/ggml/VERSION.txt 2> /dev/null)" ] || why="$why llama.cpp-not-the-pinned-ggml"
[ -x $NVCC ] || why="$why no-nvcc"
[ -z "$why" ] || { say "the worktree strata-r23decode is not the tree GATE-PLAN.md was written for:$why - not started"; exit 1; }
for f in r23-B r23-Bs r23-L r23-O r23-LO r23-Os r23-Bt r23-LOt r23-Bst r23-Ost; do
  [ -f $GC/$f.json ] || { say "missing $GC/$f.json - not started"; exit 1; }
  [ "$(exe_of $GC/$f.json)" = $EXE ] || { say "$f.json's exe is not $EXE - not started"; exit 1; }
done
for f in $RU $R17 $KR/pf_yardstick.py $KR/port_gap4.sh $KR/abarm.sh $WS/bringup/lib/exact7.sh $WS/bringup/lib/with_server.sh \
         $WS/bringup/lib/guard.py $D/t2pass.sh $D/t2_report.py $D/x28h-t2dv.json $GGUF $MTP/experts.bin $Y17/index.json; do
  [ -f $f ] || { say "missing $f - not started"; exit 1; }
done
[ "$(ls $Y17/first.* 2> /dev/null | wc -l)" = 40 ] || { say "gap 17's p210 yardstick dir does not hold 40 logit files - not started"; exit 1; }
[ "$(ls $PROF/$E7REF-*.out 2> /dev/null | wc -l)" = 7 ] || { say "gap 17's exact7 $E7REF is not complete (7 .out files) - not started"; exit 1; }
[ "$(stat -c %s $MTP/experts.bin)" = $(( 512 * 1382400 )) ] || { say "$MTP/experts.bin is not 512 Strata-form blobs (pool_test's input) - not started"; exit 1; }
PREV=""
if [ -e $O ]; then PREV=$D/gap-a-prev-$(date +%m%d-%H%M%S); mv $O $PREV; fi   # the rules judge only this attempt's files
mkdir -p $O $Y $TM $TS
S=$O/summary.txt
say "DECODE ITEMS GAP A (work/r23/gap-decode-a.sh): build + tests + exact7 + pf_yardstick + timing (GATE-PLAN.md) - measurements only, P028x stays served, nothing switches (Karl 11-04)"
[ -n "$PREV" ] && say "an earlier attempt's outputs moved to $PREV"
say "the tree: $BR $(git -C $W rev-parse HEAD) (v0.2.10 + $NCOMMITS); engine-r23decode before the build: $( [ -x $EXE ] && sha12 $EXE || echo none)"

# ================================================================ the gap
$KR/port_gap4.sh begin "r23 decode items gap a: build + tests + exact7 + pf_yardstick + timing (measurements only; P028x stays served, nothing switches - Karl 11-04)" 8>&- 9>&- 2>&1 | tee -a $S
[ -s $WS/tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
echo "$T0 $(date -Is)" > $O/t0.txt
wait_mem
kc open || end_gap

# ---- 2 build (nothing else runs: the queue is held, 8080 is down, the test lock is ours)
say "2 build strata-r23decode (tests ON) -> engine-r23decode"
buildguard 8>&- 9>&- &
BG=$!
if build; then
  mkdir -p $E && cp $W/build/strata $EXE
  echo "v0.2.10 + $(git -C $W rev-list --count v0.2.10..HEAD) commits (branch $BR $(git -C $W rev-parse HEAD)), tree $(git -C $W rev-parse 'HEAD^{tree}'); the r23 decode items L (STRATA_REMOTE_LATE_LAUNCH) + O (STRATA_POOL_ONE_BATCH), both off by default; built in gap decode-a $(date '+%F %H:%M'), tests ON" > $E/SOURCE
  sha256sum $EXE > $E/SHA256
  BUILT=1
  gate build_x PASS "engine-r23decode $(sha12 $EXE) = $(cut -c1-110 $E/SOURCE)"
else
  gate build_x FAIL "$O/build.log: $(tail -3 $O/build.log 2> /dev/null | tr '\n' ' ' | cut -c1-200)"
fi
kill $BG 2> /dev/null; wait $BG 2> /dev/null
say "  build memory guard: $(tail -1 $O/build-memguard.log 2> /dev/null)"
if grep -q 'windows hold up to 8 rows' $O/build-configure.log 2> /dev/null; then gate build8 PASS "configure: verify / batch windows hold up to 8 rows (the port's 8-row build)"
else gate build8 FAIL "configure log: $(grep -o 'windows hold up to [0-9]* rows' $O/build-configure.log 2> /dev/null || echo 'no window line')"; fi
$P -I -B $RU srccheck $W --gate build_src --gates $G | tee -a $S
[ $BUILT = 1 ] && $P -I -B $RU warncheck $O/build.log --tree $W --base $BASE --port $WS/strata-r22p0210/build.log $WS/strata-r22p0210/build-tests.log --gate build_warn --gates $G | tee -a $S
kc build

# ---- 3 tests (CPU)
if [ $BUILT = 1 ] && ok_to_go; then
  say "3 tests: pool_tasks_test (synthetic + one real blob per type pair), pool_test, numa_pool_test, pool_stress x2, patch_guard_test, serve tests"
  tst t_pooltasks 900 $W/build/pool_tasks_test
  $P -I -B $RU blobs $WS/bringup/out/r20a/pack $GGUF $TS/blobs > $TS/blobs.txt 2> $TS/blobs.err
  [ -s $TS/blobs.err ] && say "  blobs: $(cat $TS/blobs.err | tr '\n' ' ' | cut -c1-200)"
  while read -r gu dt f pair rest; do tst t_pooltasks_$pair 900 $W/build/pool_tasks_test $gu $dt $f; done < $TS/blobs.txt
  tst t_pool 900 $W/build/pool_test --selftest --file $MTP/experts.bin --layer 0
  tst t_numa 600 $W/build/numa_pool_test
  tst t_stress 600 $W/build/pool_stress 20
  tst t_stress_ob 600 env STRATA_POOL_ONE_BATCH=1 $W/build/pool_stress 20
  tst t_guard 900 $W/build/patch_guard_test $GGUF $MTP
  timeout 1800 env -C $WS $P -B -m unittest discover -s $W/serve -t $W -p 'test_*.py' > $TS/servetests.txt 2>&1 8>&- 9>&-
  tail -3 $TS/servetests.txt | tee -a $S
  $P -I -B $R17 servetests $TS/servetests.txt --gate servetests --gates $G | tee -a $S
  kc tests
fi

# ---- 4 exact7 at pin 2500, slots MATCHED (GATE-PLAN 3.1)
if [ $BUILT = 1 ]; then
  say "4 exact7 at pin 2500: the base against the port, its repeat, each item against the base; the solo pair"
  e7 B  $GC/r23-B.json 2 $E7REF
  e7 B2 $GC/r23-B.json 2 r23-B
  e7 L  $GC/r23-B.json 2 r23-B STRATA_REMOTE_LATE_LAUNCH=1
  e7 O  $GC/r23-B.json 2 r23-B STRATA_POOL_ONE_BATCH=1
  e7 LO $GC/r23-B.json 2 r23-B "STRATA_REMOTE_LATE_LAUNCH=1 STRATA_POOL_ONE_BATCH=1"
  e7 Bs $GC/r23-Bs.json 1 c13
  e7 Os $GC/r23-Bs.json 1 r23-Bs STRATA_POOL_ONE_BATCH=1

  # ---- 5 bit-identical first-token logits (GATE-PLAN 3.2)
  say "5 pf_yardstick long40 on r23-B and r23-LO"
  pfy B $GC/r23-B.json
  pfy LO $GC/r23-LO.json
  if [ -f $Y/B/index.json ] && [ -f $Y/LO/index.json ]; then
    read nd nf <<< "$(ndiff $Y/B $Y/LO)"
    [ "$nf" = 40 ] && [ "$nd" = 0 ] && gate pfy_B_LO PASS "0 of 40 first-token logit files differ (B vs LO)" || gate pfy_B_LO FAIL "$nd of $nf differ (B vs LO)"
  fi
  if [ -f $Y/B/index.json ]; then
    read nd nf <<< "$(ndiff $Y/B $Y17)"
    [ "$nf" = 40 ] && [ "$nd" = 0 ] && gate pfy_B_p210 PASS "0 of 40 differ (B vs gap 17's P0210x-h)" || gate pfy_B_p210 FAIL "$nd of $nf differ (B vs gap 17's P0210x-h)"
  fi

  # ---- 6 the timing arms (GATE-PLAN 3.3; INFO: the mechanism, not the gate)
  say "6 timing arms: r23-Bt, r23-LOt (both cards), r23-Bst, r23-Ost (the 5080 alone)"
  tarm Bt  $GC/r23-Bt.json  2 none
  tarm LOt $GC/r23-LOt.json 2 late,one
  tarm Bst $GC/r23-Bst.json 1 none
  tarm Ost $GC/r23-Ost.json 1 one
else
  say "no r23 engine (the build failed): exact7, pf_yardstick and the timing arms are not run"
fi

# ---- 6b the two-card timing pass on P028x (ANALYSIS.md section 7; P028x's served engine, no build)
if ok_to_go; then
  say "6b the two-card timing pass: results/r23/decode-timing/t2pass.sh dv"
  bash $D/t2pass.sh dv 8>&- 9>&- 2>&1 | tail -12 | tee -a $S
  rc=${PIPESTATUS[0]}
  case $rc in
    0) gate t2pass INFO "t2/report-T2dv.txt: $(grep -v '^\s*$' $D/t2/report-T2dv.txt 2> /dev/null | head -1 | cut -c1-160)";;
    3) say "KERNEL CHECK FAILED inside t2pass.sh"; KFAIL=1;;
    *) gate t2pass INFO "t2pass.sh rc $rc";;
  esac
  [ $KFAIL = 0 ] && kc t2pass
else
  say "skipped the two-card timing pass (deadline or kernel check)"
fi
end_gap
