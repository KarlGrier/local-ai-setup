#!/bin/bash
# gap-basalt-a.sh - r23, the gate of the Basalt prompt-path port, PART A (correctness + the profile; GATE-PLAN.md
# sections 2-3, results/r23/basalt-prompt/). WRITTEN 11-04, NOT RUN. Started by work/r23/gap-series.sh (`bash <driver>`,
# no arguments) as the 6th gap of Karl's 11-04 series, between two item-7d questions. P028x stays served; NOTHING
# SWITCHES until item 7 is done - a part that passes is a candidate, Karl's call.
#   0 before the gap (no GPU, 8080 untouched): refuse (exit 1) if tmp/gpu-test.lock is held, another gap holds the test
#     lock, or a model server other than the 8080 queue's P028x runs; the worktree strata-r23basalt must be branch
#     r23-basalt-prompt, clean, head 3383d1f8d (31 commits on v0.2.10, the pinned ggml); the arm configs are written
#     (results/r23/basalt-prompt/gap-configs/, = configs/P0210x-h.json + each arm's switches) and checked; which KL form
#     decides is read from the NLL gap's decision (work/r23/basalt_rules.py nllmode)
#   1 port_gap4.sh begin (the running question finishes, the test lock, 8080 down)
#   2 BUILD (CPU only, nothing else runs: the queue is held, 8080 is down): engine-r23basalt/ from strata-r23basalt
#     (build-port0210.sh's cmake line, <= 16 jobs, nice 5, this script's own memory guard for that tree); gates: build,
#     no new prefill.cpp warning against the r22p0210 build log, the three switch names in the binary
#   3 A1 profile: B, T, G with STRATA_PREFILL_TIMING=1 + STRATA_TRACE=1 on Basalt's cold pp16k / pp64k (a fresh engine
#     each) -> profile.txt; G goes on only if its GDN phases are shorter than B's
#   4 A2 the base: exact7 at pin 2500 B vs gap 17's g17-p210a (7/7 MATCHED); pf_yardstick long40 B: 0 of 40 differ from
#     gap 17's p210. A miss -> nothing below is decided (the gap ends early)
#   5 A3 copy-ahead is exact: tail24 (24 cuts, a 256-1,000-token staged rest) at --prefill auto:16384 --kv int8: B16 vs
#     A16, then with the served CPU share B16s vs A16s, 24/24 byte-identical each; the "M read in place" lines; exact7 A
#   6 A4 exact7 U and K vs B; long40 U vs B (0 of 40)
#   7 A6 the tail split: unfused16 (+ PF_FUSED=0), T16 (its 24 plan lines), long40 T40; the KL rule on tail24 (ref16 =
#     B16, unfused16, cpushare16 = B16s) and long40 (gap 8's references)
#   8 optional G (only if A1 says go, and it fits with what C and the NLL arms still need): G16 + G40 + the KL rule
#   9 A7 the cap arm: one start of S (the parts passed so far) at --prefill auto:24576 + PF_FIRST_CHUNK=1 -> the lend's
#     chunk N; C = S + auto:N + FIRST_CHUNK on tail24 and long40 at auto:N; the KL rule; 5080 free >= 300 MiB throughout
#  10 the NEW NLL form only (the NLL gap validated + adopted): score.py run on ref / unfused / cpushare / T / C (+ G, and
#     A / U if they were not exact) at their chunks, --max-len 33536, validate each, then score.py compare (CPU, nice 19,
#     inside the gap) -> the many-positions NLL gates
#  11 optional A5: KP on the 16 cuts >= 33K with KV streaming kept (--keep-kv-resident 32768): 16/16 identical
#  12 basalt_rules.py decide-a -> results/r23/basalt-prompt/gap-a/decision-a.txt; port_gap4.sh end (P028x back, sha checked)
# Every engine's environment is checked as it starts (CLI jobs: envcli on the job's process tree by /proc/PID/exe; test
# servers: envcheck inside with_server.sh) - the config's env exactly, STRATA_ROUTE_TAIL_SKIP=0, no stray switch; a
# mismatching engine is stopped by its PID and the arm is void. Children run with 8>&- 9>&-. A kernel-check failure stops
# new steps and leaves the gap OPEN (8080 down, exit 3: Karl decides). No new step after GA_MAX_MIN (default 240) minutes
# with 8080 down; an optional step starts only if it fits. Exit 0 = done (outcome in decision-a.txt), 1 = refused / not
# opened (8080 untouched), 3 = kernel check failed (gap open), 4 = port_gap4.sh end failed. Steps and times:
# work/r23/GAPS-README.md (or GAPS-BASALT-README.md), section "Basalt prompt path".
set -u -o pipefail
exec 8>&- 9>&-     # no inherited lock fd reaches a child
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
for v in $(compgen -e | grep '^STRATA_'); do [ "$v" = STRATA_MON_GPU ] || unset "$v"; done   # no stray switch reaches an engine
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r22 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
P=$WS/.venv/bin/python; RU=$WS/work/r23/basalt_rules.py; KR=$WS/work/r22; B90=$KR/basalt-pr90
SCORE=$WS/work/r23/nll-many/score.py; LIB=$WS/bringup/lib
R=$WS/results/r23/basalt-prompt; O=$R/gap-a; CF=$R/gap-configs; S=$O/summary-a.txt; G=$O/gates.txt
Y=$O/pfy; Y40=$O/pfy40; NL=$O/nll; PF=$O/profile
W=$WS/strata-r23basalt; BR=r23-basalt-prompt; HEAD=3383d1f8d; NCOMMITS=31; E23=$WS/engine-r23basalt
NVCC=/usr/local/cuda-13.3/bin/nvcc; LL=$(readlink -f $WS/strata/third_party/llama.cpp)
Y8=$WS/results/r22/gap8/pfy; Y17=$WS/results/r22/gap17/pfy; PROF=$WS/bringup/out/logs/prof
P028X_SHA=f4c4f654fb24
MAXM=${GA_MAX_MIN:-240}
T24_MIN=14; T24H_MIN=10; T40_MIN=10; E7_MIN=4; TN_MIN=8; CMP_MIN=14   # a step's minutes with its kernel check (worst
# case until measured: tail24 = 916K prompt tokens, ~6 min at the plan's rate, ~14 at the yardstick's 1,120 tok/s);
# the tail24 / long40 / score.py times are replaced by the measured ones as the gap goes
mkdir -p $R $WS/logs $WS/tmp/r22
STARTS=$R/gap-a-starts.log      # until the pre-gap checks pass (then $S)
say() { echo "=== $(date '+%F %T') $*" | tee -a ${SAY_TO:-$STARTS}; }
gate() { echo "$1 $2 ${*:3} [23a $(date '+%m-%d %H:%M')]" >> $G; say "  gate $*"; }
gst() { grep "^$1 " $G 2> /dev/null | tail -1 | cut -d' ' -f2; }   # a gate's last status ("" = not written)
KFAIL=0; T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
kc() { $LIB/kcheck.sh "r23ba-$1" > /dev/null 8>&- 9>&- || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; return 1; }; }
left() { echo $(( DEADLINE - $(date +%s) )); }
ok_to_go() { [ $KFAIL = 0 ] && [ $(left) -gt 0 ]; }
fits() { [ $KFAIL = 0 ] && [ $(left) -ge $(( $1 * 60 )) ]; }
sha12() { sha256sum "$1" | cut -c1-12; }
elog() { $P -c "import json; print(json.load(open('$1'))['log'])"; }
slog() { ls -t $WS/bringup/out/logs/server_$1_*.log 2> /dev/null | head -1; }
ppid_of() { local s; s=$(cat /proc/$1/stat 2> /dev/null) || return 0; s=${s##*) }; set -- $s; echo "${2:-}"; }
mins() { echo $(( ($(date +%s) - $1 + 59) / 60 + 1 )); }

preflight() {   # refuse (exit 1, nothing touched): the GPU lock held, another gap open, or a model server other than the
  # 8080 queue's P028x: every engine process (exact names) and every NVIDIA compute process must belong to the server
  # listening on 8080, whose engine must be P028x (engine-r22p028x, sha $P028X_SHA; its vision helper allowed); nothing
  # may listen on the test port 8081
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
engines_left() { local x out=""; for x in strata strata-host strata-vision strata-dsv41 llama-server ollama; do pgrep -x $x > /dev/null && out="$out $x"; done; echo $out; }

fatalchk() {   # fatalchk GATE ENGINE_LOG OFFSET LABEL: a sticky CUDA error / stall / engine restart in the slice = void
  local L=$2 off=$3 sl hits
  sl=$(slog $4)
  hits=$( { tail -c +$((off + 1)) $L 2> /dev/null; [ -n "$sl" ] && cat $sl; } | grep -c -E "fatal GPU error|no progress for [0-9]+ s during a request|the engine had stopped \(exit code|became non-finite")
  [ "$hits" = 0 ] || gate $1 FAIL "$hits line(s): fatal GPU error / stall / engine restart / non-finite ($L from byte $off; $sl)"
}

e7() {   # e7 ARM LABEL CONFIG REF: exact7 at pin 2500 against REF's hashes and slots, every item's engine checked
  local arm=$1 L=$2 cfg=$3 ref=$4 jp
  ok_to_go || { say "skipped exact7 $L (deadline or kernel check)"; return 1; }
  say "exact7 $L ($(basename $cfg) against $ref)"
  ( PIN_CACHE=2500 REF=$ref $LIB/exact7.sh $L $cfg 2>&1 | tail -9 | tee -a $S ) 8>&- 9>&- &
  jp=$!
  $P -I -B $RU envcli $E23/strata $cfg --job $jp --mode e7 --kill --gate env_${arm}_e7 --gates $G 8>&- 9>&- 2>&1 | tee -a $S
  wait $jp
  $P -I -B $RU e7gate $S $L --gate e7_$arm --gates $G 8>&- 9>&- | tee -a $S
  kc e7-$L
}

pfy() {   # pfy ARM NAME CONFIG SET PREFILL KV [keep-share] [kvres:N] [env:K=V]...: the r23 yardstick (basalt_rules.py
  # pfy = pf_yardstick.py run + the plan's options) under guard.py, its engine checked as it starts; NAME's dir in $Y
  # (tail24 sets) or $Y40 (long40)
  local arm=$1 n=$2 cfg=$3 set=$4 pf=$5 kv=$6 x jp t0 dir opts="" eopts=""; shift 6
  for x in "$@"; do case $x in keep-share) opts="$opts --keep-share"; eopts="$eopts --keep-share";;
                               kvres:*) opts="$opts --keep-kv-resident ${x#kvres:}"; eopts="$eopts --kv-resident ${x#kvres:}";;
                               env:*) opts="$opts --env ${x#env:}"; eopts="$eopts --set ${x#env:}";; esac; done
  ok_to_go || { say "skipped pf_yardstick $n (deadline or kernel check)"; return 1; }
  dir=$Y/$n; [ $set = long40 ] && dir=$Y40/$n
  say "pf_yardstick r23 $n ($(basename $cfg), $set, --prefill $pf, --kv $kv${opts:+;$opts})"
  t0=$(date +%s)
  ( $P $LIB/guard.py pfy23-$n -- $P -I -B $RU pfy $cfg $dir --set $set --prefill $pf --kv $kv $opts 2>&1 | grep -v "^engine:" | tail -2 | sed "s/^/pfy $n: /" | tee -a $S ) 8>&- 9>&- &
  jp=$!
  $P -I -B $RU envcli $E23/strata $cfg --job $jp --mode pfy --prefill $pf --kv $kv $eopts --kill --gate env_${arm}_pfy-$n --gates $G 8>&- 9>&- 2>&1 | tee -a $S
  wait $jp
  case $set in tail24) T24_MIN=$(mins $t0);; tail24hi) T24H_MIN=$(mins $t0);; long40) T40_MIN=$(mins $t0);; esac
  kc pfy-$n
}

pfy40() {   # pfy40 ARM NAME CONFIG: work/r22/pf_yardstick.py run --set long40 itself (gap 17's form, bare auto, fp16)
  local arm=$1 n=$2 cfg=$3 jp t0
  ok_to_go || { say "skipped pf_yardstick long40 $n (deadline or kernel check)"; return 1; }
  say "pf_yardstick long40 $n ($(basename $cfg))"
  t0=$(date +%s)
  ( $P $LIB/guard.py pfy23-$n -- $P -I $KR/pf_yardstick.py run $cfg $Y40/$n --set long40 2>&1 | grep -v "^engine:" | tail -3 | sed "s/^/pfy $n: /" | tee -a $S ) 8>&- 9>&- &
  jp=$!
  $P -I -B $RU envcli $E23/strata $cfg --job $jp --mode pfy --kill --gate env_${arm}_pfy-$n --gates $G 8>&- 9>&- 2>&1 | tee -a $S
  wait $jp
  T40_MIN=$(mins $t0)
  kc pfy-$n
}

nllarm() {   # nllarm ARM NAME CONFIG PREFILL [K=V]: score.py run (long11, every 8th row, --max-len 33536) at PREFILL, its
  # engine checked as it starts; then score.py validate (CPU, ~20 s) -> nllval_NAME
  local arm=$1 n=$2 cfg=$3 pf=$4 ev=${5:-} jp t0
  ok_to_go || { say "skipped score.py run $n (deadline or kernel check)"; return 1; }
  say "score.py run $n ($(basename $cfg), --prefill $pf${ev:+, $ev}; every 8th row, --max-len 33536)"
  t0=$(date +%s)
  ( $P $LIB/guard.py nll23-$n -- $P -I -B $RU nllrun $cfg $NL/$n --prefill $pf ${ev:+--env $ev} 2>&1 | grep -vE "^engine" | tail -2 | sed "s/^/nll $n: /" | tee -a $S ) 8>&- 9>&- &
  jp=$!
  $P -I -B $RU envcli $E23/strata $cfg --job $jp --mode nll --prefill $pf ${ev:+--set $ev} --kill --gate env_${arm}_nll-$n --gates $G 8>&- 9>&- 2>&1 | tee -a $S
  wait $jp
  TN_MIN=$(mins $t0)
  kc nll-$n || return 1
  if nice -n 19 $P -I $SCORE validate $NL/$n > $NL/validate-$n.txt 2>&1 8>&- 9>&-; then gate nllval_$n PASS "$(tail -1 $NL/validate-$n.txt | cut -c1-140)"
  else gate nllval_$n FAIL "$(tail -1 $NL/validate-$n.txt | cut -c1-140)"; fi
}

srvrun() {   # srvrun ARM LABEL CONFIG GATE_STEP SLICE CMD: one fresh test server (with_server.sh: cold page cache, the
  # memory guard, the shared test lock), its engine's env checked, then CMD; the engine log slice -> SLICE
  local arm=$1 lab=$2 cfg=$3 st=$4 sl=$5 cmd=$6 L off
  ok_to_go || { say "skipped $lab (deadline or kernel check)"; return 1; }
  L=$(elog $cfg); touch $L; off=$(stat -c %s $L)
  say "server $lab ($(basename $cfg))"
  $LIB/with_server.sh $lab $cfg -- "$P -I -B $RU envcheck $E23/strata $cfg --gate env_${arm}_$st --gates $G && $cmd" 8>&- 9>&- 2>&1 \
    | grep -E "engine pid [0-9]+:|ENV CHECK| pass |ready|exited|refus|Error|GUARD|Traceback" | tee -a $S
  tail -c +$((off + 1)) $L > $sl
  fatalchk fatal_${arm}_$st $L $off $lab
  kc $lab
}

memguard23() {   # build_memguard.sh's rule for THIS tree (that script watches other trees and is not edited): ninja
  # in strata-r23basalt paused below 24 GB MemAvailable, resumed above 32, the build stopped below 14 (the floor is 12)
  local p n a paused="" low=999999 lg=$O/build-memguard.log
  trap 'for p in $paused; do kill -CONT $p 2> /dev/null; done; echo "$(date "+%F %T") end: lowest MemAvailable $low MB" >> $lg; exit 0' TERM
  echo "$(date '+%F %T') start (pause < 24 GB, resume > 32 GB, stop < 14 GB)" >> $lg
  while :; do
    n=""; for p in $(pgrep -x ninja); do case $(readlink /proc/$p/cwd 2> /dev/null) in $W|$W/*) n="$n $p";; esac; done
    a=$(awk '/MemAvailable/ {print int($2 / 1024)}' /proc/meminfo)
    if [ -n "$n" ]; then
      [ $a -lt $low ] && low=$a
      if [ $a -lt 14336 ]; then
        for p in $n; do kill -CONT $p 2> /dev/null; kill -TERM $p 2> /dev/null; done; paused=""; echo "$(date '+%F %T') MemAvailable $a MB: build STOPPED" >> $lg
      elif [ $a -lt 24576 ] && [ -z "$paused" ]; then
        for p in $n; do kill -STOP $p; done; paused=$n; echo "$(date '+%F %T') MemAvailable $a MB: ninja$n paused" >> $lg
      elif [ -n "$paused" ] && [ $a -gt 32768 ]; then
        for p in $paused; do kill -CONT $p 2> /dev/null; done; echo "$(date '+%F %T') MemAvailable $a MB: resumed" >> $lg; paused=""
      fi
    fi
    sleep 0.5
  done
}

build23() {   # build-port0210.sh's build for strata-r23basalt -> engine-r23basalt (SHA256 + SOURCE)
  local mg rc t0=$(date +%s)
  say "BUILD strata-r23basalt ($BR @ $HEAD) -> engine-r23basalt (CPU only; the queue is held and 8080 is down, nothing else runs)"
  rm -rf $W/build
  memguard23 8>&- 9>&- &
  mg=$!
  nice -n 5 cmake -G Ninja -S $W -B $W/build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
      "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=$NVCC -DSTRATA_GGML_DIR="$LL" > $O/build-configure.log 2>&1 8>&- 9>&- \
    && nice -n 5 cmake --build $W/build --target strata -j ${BUILD_JOBS:-16} > $O/build.log 2>&1 8>&- 9>&-
  rc=$?
  kill $mg 2> /dev/null; wait $mg 2> /dev/null
  if [ $rc = 0 ] && [ -x $W/build/strata ]; then
    mkdir -p $E23 && cp $W/build/strata $E23/strata
    echo "v0.2.10 + $(git -C $W rev-list --count v0.2.10..HEAD) commits (branch $BR $(git -C $W rev-parse HEAD)), tree $(git -C $W rev-parse 'HEAD^{tree}')" > $E23/SOURCE
    sha256sum $E23/strata > $E23/SHA256
    gate build_r23 PASS "engine-r23basalt $(sha12 $E23/strata) = $(cut -c1-110 $E23/SOURCE) ($(( ($(date +%s) - t0) / 60 )) min)"
  else
    gate build_r23 FAIL "rc $rc: $(tail -3 $O/build.log 2> /dev/null | tr '\n' ' ' | cut -c1-200) (results/r23/basalt-prompt/gap-a/build.log)"
    return 1
  fi
  wk() { grep -E "prefill\.cpp:[0-9]+:[0-9]+: warning:" "$1" 2> /dev/null | sed -E 's/^.*warning: //' | sort | uniq -c | sed 's/^ *//' | sort; }
  local new; new=$(comm -13 <(wk $WS/strata-r22p0210/build.log) <(wk $O/build.log) | tr '\n' ';')
  if [ -z "$new" ]; then gate warnings PASS "no prefill.cpp warning beyond the r22p0210 build's ($(wk $O/build.log | wc -l) kinds, as before)"
  else gate warnings FAIL "new prefill.cpp warning(s): ${new:0:240}"; fi
  strings $E23/strata > $O/strings.txt
  local miss=""; for x in STRATA_PF_AHEAD STRATA_PF_TAIL_SPLIT STRATA_PF_FIRST_CHUNK; do grep -qx "$x" $O/strings.txt || miss="$miss $x"; done
  rm -f $O/strings.txt
  [ -z "$miss" ] && gate strings PASS "STRATA_PF_AHEAD, STRATA_PF_TAIL_SPLIT, STRATA_PF_FIRST_CHUNK in the binary" || gate strings FAIL "missing:$miss"
  kc build
}

end_gap() {
  if [ $KFAIL = 1 ]; then say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"; exit 3; fi
  $P -I -B $RU decide-a $O > /dev/null 2>&1 8>&- 9>&-
  [ -f $O/decision-a.txt ] && tee -a $S < $O/decision-a.txt || say "basalt_rules.py decide-a failed - rerun it by hand ($RU decide-a $O)"
  say "P028x back on 8080 (port_gap4.sh end) - nothing switched"
  if ! $KR/port_gap4.sh end 8>&- 9>&- 2>&1 | tee -a $S; then
    say "port_gap4.sh end FAILED: 8080 and the research queue need a look"; exit 4
  fi
  kc end || { say "the kernel check failed after P028x came back: Karl decides"; exit 3; }
  say "Basalt gap part a done ($(( ($(date +%s) - T0) / 60 )) min with 8080 down)"
  exit 0
}

# ================================================================ before the gap (no GPU; 8080 untouched)
say "BASALT PROMPT-PATH GATE part a (work/r23/gap-basalt-a.sh): build + correctness + the profile (a test; P028x stays served, nothing switches)"
preflight
for f in $WS/configs/P0210x-h.json $RU $KR/pf_yardstick.py $SCORE $LIB/exact7.sh $LIB/with_server.sh $LIB/guard.py $LIB/kcheck.sh \
         $KR/port_gap4.sh $B90/bp90_client.py /home/USER/ai-speed-testing/basalt-pr90-data/prefill.ids $WS/strata-r22p0210/build.log \
         $Y8/ref/index.json $Y8/unfused/index.json $Y8/cpushare/index.json $Y17/p210/index.json $W/serve/server.py; do
  [ -f $f ] || { say "missing $f - not started"; exit 1; }
done
[ "$(ls $PROF/g17-p210a-*.out 2> /dev/null | wc -l)" = 7 ] || { say "gap 17's exact7 g17-p210a (the base's reference) is incomplete - not started"; exit 1; }
if [ "$(git -C $W rev-parse --abbrev-ref HEAD 2> /dev/null)" != $BR ] || [ -n "$(git -C $W status --porcelain --untracked-files=no)" ] \
   || [ "$(git -C $W rev-parse HEAD | cut -c1-9)" != $HEAD ] || [ "$(git -C $W rev-list --count v0.2.10..HEAD)" != $NCOMMITS ]; then
  say "strata-r23basalt is not $BR @ $HEAD clean with $NCOMMITS commits on v0.2.10 - not started"; exit 1
fi
[ "$(git -C $LL rev-parse HEAD)" = "$(cut -d' ' -f1 $W/third_party/ggml/VERSION.txt)" ] || { say "the llama.cpp checkout is not strata-r23basalt's pinned ggml - not started"; exit 1; }
[ -f $WS/tmp/r19/kwatch.pid ] && kill -0 "$(cat $WS/tmp/r19/kwatch.pid)" 2> /dev/null || { say "the kernel-log watcher is not running - not started"; exit 1; }
if [ -e $O ]; then PREV=$R/gap-a-prev-$(date +%m%d-%H%M%S); mv $O $PREV; say "an earlier attempt's outputs moved to $PREV"; fi
mkdir -p $O $Y $Y40 $NL $PF $CF
SAY_TO=$S; cat $STARTS >> $S 2> /dev/null
$P -I -B $RU arms $CF --gate cfg --gates $G 8>&- 9>&- 2>&1 | tee -a $S
[ "$(gst cfg)" = PASS ] || { say "the arm configs are not P0210x-h + their switches - not started"; exit 1; }
$P -I -B $RU nllmode --gate nll_mode --gates $G 8>&- 9>&- | tee -a $S
NLLM=$(gst nll_mode | tr 'A-Z' 'a-z'); [ "$NLLM" = new ] || NLLM=old
say "the KL rule's NLL check for the rounding-level parts: the $NLLM form ($(grep '^nll_mode ' $G | tail -1 | cut -d' ' -f3- | cut -c1-160))"
for x in ref unfused cpushare; do ln -sfn $Y8/$x $Y40/$x; done      # gap 8's long40 references

# ================================================================ the gap
$KR/port_gap4.sh begin "Basalt prompt-path gate part a: build + correctness (a test; P028x stays served, nothing switches)" 8>&- 9>&- 2>&1 | tee -a $S
[ -s $WS/tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
echo "$T0 $(date -Is)" > $O/t0.txt
kc open || end_gap
for i in $(seq 60); do [ -z "$(engines_left)" ] && break; sleep 2; done
if [ -n "$(engines_left)" ]; then say "engine processes still running 120 s after 8080 stopped: $(engines_left) - ending the gap"; end_gap; fi
for i in $(seq 24); do [ "$(awk '/^MemAvailable/ {print int($2 / 1048576)}' /proc/meminfo)" -ge 40 ] && break; sleep 5; done
say "8080 down: no engine left, MemAvailable $(awk '/^MemAvailable/ {print int($2 / 1048576)}' /proc/meminfo) GB"

# ---- 2 the build
build23 || { say "the build failed: nothing to test"; end_gap; }
[ "$(gst warnings)" = PASS ] && [ "$(gst strings)" = PASS ] || say "note: a build gate failed (warnings / strings) - BUILD fails in the decision; the steps still run for the record"

# ---- 3 A1 the profile (B, T, G; a fresh engine per fixture)
say "A1 profile: B, T, G with STRATA_PREFILL_TIMING=1 + STRATA_TRACE=1 on Basalt's cold pp16k and pp64k"
for a in Bp Tp Gp; do
  for set in pp16k pp64k; do
    srvrun ${a%p} r23a-$a-$set $CF/r23-$a.json prof-$set $PF/$a-$set.englog \
      "$P -I -B $B90/bp90_client.py http://127.0.0.1:8081 --label r23a-$a-$set --sets $set --passes 1 --tree $W --out $PF/cold-$a.jsonl"
  done
done
$P -I -B $RU profile $PF $O/profile.txt --gate g_go --gates $G 8>&- 9>&- 2>&1 | tail -12 | tee -a $S

# ---- 4 A2 the base is today's build
say "A2 the base: exact7 B vs gap 17's g17-p210a; long40 B vs gap 17's p210"
e7 B r23b-B $CF/r23-B.json g17-p210a
pfy40 B B40 $CF/r23-B.json
$P -I -B $RU same $Y40/B40 $Y17/p210 --gate logits_B40 --gates $G 8>&- 9>&- | tee -a $S
if [ "$(gst e7_B)" != PASS ] || [ "$(gst logits_B40)" != PASS ]; then
  say "the base is not P0210x-h bit for bit (e7_B $(gst e7_B), logits_B40 $(gst logits_B40)): nothing below is decided - ending the gap"
  end_gap
fi

# ---- 5 A3 copy-ahead is exact
say "A3 tail24 at --prefill auto:16384 --kv int8: B16 / A16, then with the served CPU share B16s / A16s; exact7 A"
pfy B B16 $CF/r23-B.json tail24 auto:16384 int8
pfy A A16 $CF/r23-A.json tail24 auto:16384 int8
$P -I -B $RU same $Y/B16 $Y/A16 --gate same_A16 --gates $G 8>&- 9>&- | tee -a $S
$P -I -B $RU ahead $Y/A16 --gate ahead_A16 --gates $G 8>&- 9>&- | tee -a $S
pfy B B16s $CF/r23-B.json tail24 auto:16384 int8 keep-share
pfy A A16s $CF/r23-A.json tail24 auto:16384 int8 keep-share
$P -I -B $RU same $Y/B16s $Y/A16s --gate same_A16s --gates $G 8>&- 9>&- | tee -a $S
$P -I -B $RU ahead $Y/A16s --gate ahead_A16s --gates $G 8>&- 9>&- | tee -a $S
ln -sfn B16s $Y/cpushare16    # cpushare16 = B + STRATA_PREFILL_CPU_SHARE=0.4 (_MAX 1792 from the config) = B16s exactly
e7 A r23b-A $CF/r23-A.json r23b-B

# ---- 6 A4 the two existing exact switches
say "A4 exact7 U and K vs B; long40 U vs B"
e7 U r23b-U $CF/r23-U.json r23b-B
e7 K r23b-K $CF/r23-K.json r23b-B
pfy40 U U40 $CF/r23-U.json
$P -I -B $RU same $Y40/U40 $Y40/B40 --gate logits_U40 --gates $G 8>&- 9>&- | tee -a $S

# ---- 7 A6 the tail split (rounding-level) + the KL rule (and A / U if they are not exact)
say "A6 tail24: unfused16 (B + STRATA_PF_FUSED=0), T16; long40 T40; the KL rule ($NLLM form)"
pfy ref unfused16 $CF/r23-B.json tail24 auto:16384 int8 env:STRATA_PF_FUSED=0
pfy T T16 $CF/r23-T.json tail24 auto:16384 int8
$P -I -B $RU planlines $Y/T16 --kind tail --chunk 16384 --smin 1024 --gate plan_T16 --gates $G 8>&- 9>&- | tee -a $S
pfy40 T T40 $CF/r23-T.json
CT="T16:T"; C40="T40:T"
if [ "$(gst same_A16)" = FAIL ] || [ "$(gst same_A16s)" = FAIL ] || [ "$(gst e7_A)" = FAIL ]; then
  say "A is not exact: it may go on as rounding-level only by the KL rule (tail24 A16 + long40 A40)"
  CT="$CT,A16:A"; fits $T40_MIN && { pfy40 A A40 $CF/r23-A.json; C40="$C40,A40:A"; }
fi
[ "$(gst logits_U40)" = FAIL ] || [ "$(gst e7_U)" = FAIL ] && { say "U is not exact: the KL rule on long40 decides"; C40="$C40,U40:U"; }
$P -I -B $RU kl $Y --set tail24 --ref B16 --refs unfused16,cpushare16 --cands $CT --mode $NLLM --gates $G 8>&- 9>&- 2>&1 | tee $O/kl-tail24.txt | tee -a $S
$P -I -B $RU kl $Y40 --set long40 --ref ref --refs unfused,cpushare --cands $C40 --mode $NLLM --gates $G 8>&- 9>&- 2>&1 | tee $O/kl-long40.txt | tee -a $S

# ---- 8 (before C, so S is complete) optional G: only if A1 says go and it fits
GRUN=0
REQ=$(( 2 + T24_MIN + T40_MIN )); [ $NLLM = new ] && REQ=$(( REQ + 5 * TN_MIN + CMP_MIN ))   # what C (+ the NLL arms) still need
if [ "$(gst g_go)" = PASS ] && fits $(( T24_MIN + T40_MIN + REQ )); then
  say "G (STRATA_GDN_CHUNKED=2): its GDN phases were shorter than B's - tail24 G16, long40 G40, the KL rule"
  pfy G G16 $CF/r23-G.json tail24 auto:16384 int8
  pfy40 G G40 $CF/r23-G.json
  $P -I -B $RU kl $Y --set tail24 --ref B16 --refs unfused16,cpushare16 --cands G16:G --mode $NLLM --gates $G 8>&- 9>&- 2>&1 | tee $O/kl-tail24-G.txt | tee -a $S
  $P -I -B $RU kl $Y40 --set long40 --ref ref --refs unfused,cpushare --cands G40:G --mode $NLLM --gates $G 8>&- 9>&- 2>&1 | tee $O/kl-long40-G.txt | tee -a $S
  GRUN=1
else
  say "G not run (g_go $(gst g_go), or $(( T24_MIN + T40_MIN )) min + the $REQ min C and the NLL arms need do not fit)"
fi

# ---- 9 A7 the cap arm: the lend's chunk, then C on tail24 + long40 at it
$P -I -B $RU decide-a $O --provisional > /dev/null 2>&1 8>&- 9>&-
SP=$(grep '^S_PARTS ' $O/decision-a-provisional.txt 2> /dev/null | cut -d' ' -f2)
say "A7 the cap arm on the parts passed so far (${SP:-none}): one start at --prefill auto:24576 + STRATA_PF_FIRST_CHUNK=1"
$P -I -B $RU arms $CF --stack "$SP" --scan --gate cfg_s --gates $G 8>&- 9>&- 2>&1 | tail -1 | tee -a $S
NC=0
if [ "$(gst cfg_s)" = PASS ]; then
  srvrun C r23a-Cscan $CF/r23-Cscan.json scan $O/cscan.englog "sleep 2"
  NC=$($P -I -B $RU lend $O/cscan.englog --gate c_lend --gates $G 8>&- 9>&- | tail -1)
fi
if [ "${NC:-0}" -gt 16384 ] 2> /dev/null; then
  gate c_parts INFO "${SP:-none} (C = these + --prefill auto:$NC + STRATA_PF_FIRST_CHUNK=1)"
  $P -I -B $RU arms $CF --stack "$SP" --cap $NC --gate cfg_c --gates $G 8>&- 9>&- 2>&1 | tail -1 | tee -a $S
  pfy C C16 $CF/r23-C.json tail24 auto:$NC int8
  $P -I -B $RU planlines $Y/C16 --kind first --chunk $NC --smin 1024 --gate plan_C16 --gates $G 8>&- 9>&- | tee -a $S
  pfy C C40 $CF/r23-C.json long40 auto:$NC fp16
  $P -I -B $RU vram srv-r23a-Cscan pfy23-C16 pfy23-C40 --gate vram_C --gates $G 8>&- 9>&- | tee -a $S
  $P -I -B $RU kl $Y --set tail24 --ref B16 --refs unfused16,cpushare16 --cands C16:C --mode $NLLM --gates $G 8>&- 9>&- 2>&1 | tee $O/kl-tail24-C.txt | tee -a $S
  $P -I -B $RU kl $Y40 --set long40 --ref ref --refs unfused,cpushare --cands C40:C --mode $NLLM --gates $G 8>&- 9>&- 2>&1 | tee $O/kl-long40-C.txt | tee -a $S
else
  say "C: no chunk above 16384 from the lend (c_lend $(gst c_lend), cfg_s $(gst cfg_s)) - C is not run"
  [ "$(gst cfg_s)" = PASS ] && $P -I -B $RU vram srv-r23a-Cscan --gate vram_C --gates $G 8>&- 9>&- | tee -a $S
fi

# ---- 10 the NEW NLL form: the many-positions check (score.py) for the rounding-level candidates
if [ $NLLM = new ]; then
  say "the many-positions NLL check (the NLL gap validated the offline head and adopted the bound): score.py arms on engine-r23basalt"
  nllarm ref ref $CF/r23-B.json auto:16384
  nllarm ref unfused $CF/r23-B.json auto:16384 STRATA_PF_FUSED=0
  nllarm ref cpushare $CF/r23-B.json auto:16384 STRATA_PREFILL_CPU_SHARE=0.4
  NC_="T"; nllarm T T $CF/r23-T.json auto:16384
  if [ -f $CF/r23-C.json ] && [ "${NC:-0}" -gt 16384 ] 2> /dev/null; then nllarm C C $CF/r23-C.json auto:$NC && NC_="$NC_,C"; fi
  [ $GRUN = 1 ] && fits $(( TN_MIN + CMP_MIN )) && nllarm G G $CF/r23-G.json auto:16384 && NC_="$NC_,G"
  case $CT in *A16:A*) fits $(( TN_MIN + CMP_MIN )) && nllarm A A $CF/r23-A.json auto:16384 && NC_="$NC_,A";; esac
  case $C40 in *U40:U*) fits $(( TN_MIN + CMP_MIN )) && nllarm U U $CF/r23-U.json auto:16384 && NC_="$NC_,U";; esac
  have=""; for x in ${NC_//,/ }; do [ -f $NL/$x/index.json ] && have="$have,$x"; done
  if [ $KFAIL = 0 ] && [ -n "$have" ] && [ -f $NL/ref/index.json ] && [ -f $NL/unfused/index.json ] && [ -f $NL/cpushare/index.json ]; then
    say "score.py compare (CPU, nice 19, 4 BLAS threads, inside the gap - nothing else runs): ${have#,} against ref / unfused / cpushare"
    nice -n 19 $P -I $SCORE --threads 4 compare $NL --ref ref --refs unfused,cpushare --cands ${have#,} $($P -I -B $RU nllargs) \
      --json $NL/result.json --rows-out $NL/rows.tsv > $NL/compare.txt 2>&1 8>&- 9>&-
    tail -12 $NL/compare.txt | tee -a $S
  fi
  $P -I -B $RU nllgate $NL/result.json --cands ${NC_} --gates $G 8>&- 9>&- | tee -a $S
fi

# ---- 11 optional A5: KV prefix prefetch (the 16 cuts >= 33K with KV streaming kept)
if fits $(( 2 * T24H_MIN )); then
  say "A5 KP (STRATA_KV_PREFETCH=1): the 16 cuts >= 33K with --keep-kv-resident 32768 --kv int8, B vs KP"
  pfy B B16k $CF/r23-B.json tail24hi auto:16384 int8 kvres:32768
  pfy KP KP16k $CF/r23-KP.json tail24hi auto:16384 int8 kvres:32768
  $P -I -B $RU same $Y/B16k $Y/KP16k --gate same_KP --gates $G 8>&- 9>&- | tee -a $S
else
  say "A5 (optional) not run: $(( 2 * T24H_MIN )) min do not fit before the deadline (or a kernel check failed)"
fi

# ---- 12 the rules, P028x back
end_gap
