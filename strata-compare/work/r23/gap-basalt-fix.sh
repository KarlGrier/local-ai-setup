#!/bin/bash
# gap-basalt-fix.sh - r23 (11-05): the RERUN of the three Basalt prompt-path switches that never engaged in gap a
# (STRATA_PF_AHEAD = A, STRATA_PF_TAIL_SPLIT = T, STRATA_PF_FIRST_CHUNK = C; results/r23/basalt-prompt/FIX-1105.md), on
# engine-r23basalt-fix (branch r23-basalt-prompt + the three "r23 fix:" commits, built BEFORE the gap by
# work/r23/build-basalt-fix.sh under nogap-run.sh). WRITTEN 11-05, NOT RUN, no .ready file: Karl schedules it. P028x stays
# served; NOTHING SWITCHES - a part that passes is a candidate, Karl's call. Rules: work/r23/basalt_fix_rules.py (its
# docstring), the same as gap a's for these parts (exact7 / logits identity for the exact claim, kernel_rule2 + 3 for the
# rounding-level ones, NLL information only, each switch's "exercised" lines required), with the three test fixes:
#   - the yardstick's tail24 arms read at an EXPLICIT --prefill 16384 (gap a's auto:16384 was 1024 on the one-slot
#     yardstick engine: nothing lendable), C's at an explicit --prefill N; every switch arm's r23 layout line must say so
#   - the plan-line formula takes the engine's n = tokens - 1 (T16: 22 of 24 at 16384)
#   - the cap arm's scan starts at --prefill auto:32768 (auto:24576 was auto:16384)
#   0 before the gap (no GPU, 8080 untouched): refuse (exit 1) if tmp/gpu-test.lock is held, another gap holds the test
#     lock, a model server other than the 8080 queue's P028x runs, the fix engine does not check out (buildcheck: SHA256,
#     SOURCE at the fix head, its build gates and CPU tests), or a file is missing; the arm configs
#     (results/r23/basalt-prompt/gap-fix/configs/ = configs/P0210x-h.json + each arm's switches, exe engine-r23basalt-fix)
#     written and checked
#   1 port_gap4.sh begin (the running question finishes, the test lock, 8080 down)
#   2 BASELINE: exact7 B (pin 2500) vs gap 17's g17-p210a 7/7 MATCHED; long40 B40 vs gap 17's p210 0 of 40 differ. A miss
#     -> nothing is decided (the gap ends)
#   3 A: tail24 at --prefill 16384 --kv int8: B16 / A16, then with the served CPU share B16s / A16s, 24/24 byte-identical
#     each; "M read in place" with M > 0 in both; the layout lines say 16384; exact7 A vs this gap's B
#   4 T: unfused16 (B + PF_FUSED=0), T16 (its plan lines = the formula's: 22); long40 at an explicit --prefill 16384, fp16
#     (Karl 11-05; gap a's bare-auto T40 read at 1024, where T cannot fire): B40_16, unfused40_16, cpushare40_16 (B + the
#     served share), T40_16 (its plan line: 1, tf-long64k-17408); the KL rule on tail24 (ref16 = B16, unfused16,
#     cpushare16 = B16s) and long40 (B40_16, unfused40_16, cpushare40_16)
#   5 C: the stack S = gap a's S_PARTS + A / T where they passed (provisional decision); one start of S + FIRST_CHUNK at
#     --prefill auto:32768 -> the scan's chunk N (> 16384 or C is not run); C16 (tail24, int8) and C40 (long40, fp16) at
#     an explicit --prefill N: the FIRST_CHUNK plan lines, the layout lines, the KL rule (C40 against step T's 16384 long40
#     references; gap 8's 1024-chunk ones beside it as INFO only); 5080 free >= 300 MiB throughout
#   6 basalt_fix_rules.py decide -> results/r23/basalt-prompt/gap-fix/decision-fix.txt; port_gap4.sh end (P028x back)
# Every engine's environment is checked as it starts (CLI jobs: envcli on the job's process tree by /proc/PID/exe; the
# scan's test server: envcheck inside with_server.sh) - the config's env exactly, STRATA_ROUTE_TAIL_SKIP=0, no stray
# switch; a mismatching engine is stopped by its PID and the arm is void. Children run with 8>&- 9>&-. A kernel-check
# failure stops new steps and leaves the gap OPEN (8080 down, exit 3: Karl decides). No new step after GF_MAX_MIN (default
# 190, Karl 11-05) minutes with 8080 down; C starts only if the scan, C16, C40 and the close fit. Exit 0 = done (outcome in decision-fix.txt), 1 = refused / not
# opened (8080 untouched), 3 = kernel check failed (gap open), 4 = port_gap4.sh end failed.
# Time with 8080 down (estimates; tail24 at 16384 ~6-8 min instead of gap a's 14 at 1024, long40 at 16384 ~5-8): open ~3,
# baseline ~14, A 28-36, T 32-48 (2 tail24 + 4 long40 runs), C 14-16 (scan + C16 + C40 at ~21K), close ~3 -> ~1.6-2.0 h
# (deadline 190 min).
set -u -o pipefail
exec 8>&- 9>&-     # no inherited lock fd reaches a child
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
for v in $(compgen -e | grep '^STRATA_'); do [ "$v" = STRATA_MON_GPU ] || unset "$v"; done   # no stray switch reaches an engine
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r22 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
P=$WS/.venv/bin/python; RU=$WS/work/r23/basalt_rules.py; FR=$WS/work/r23/basalt_fix_rules.py; KR=$WS/work/r22
LIB=$WS/bringup/lib
R=$WS/results/r23/basalt-prompt; O=$R/gap-fix; CF=$O/configs; S=$O/summary-fix.txt; G=$O/gates.txt
Y=$O/pfy; Y40=$O/pfy40
W=$WS/strata-r23basalt; E23=$WS/engine-r23basalt-fix
Y8=$WS/results/r22/gap8/pfy; Y17=$WS/results/r22/gap17/pfy; PROF=$WS/bringup/out/logs/prof
P028X_SHA=f4c4f654fb24
MAXM=${GF_MAX_MIN:-190}
CH=16384                                  # the served chunk, explicit (the yardstick's auto is 1024)
T24_MIN=8; T40_MIN=8; E7_MIN=4; SCAN_MIN=3; END_MIN=4   # a step's minutes with its kernel check (T24 / T40 replaced by the
# measured tail24 / long40 runs; END_MIN = the decision + port_gap4.sh end)
mkdir -p $R $WS/logs $WS/tmp/r22
STARTS=$R/gap-fix-starts.log    # until the pre-gap checks pass (then $S)
say() { echo "=== $(date '+%F %T') $*" | tee -a ${SAY_TO:-$STARTS}; }
gate() { echo "$1 $2 ${*:3} [23fx $(date '+%m-%d %H:%M')]" >> $G; say "  gate $*"; }
gst() { grep "^$1 " $G 2> /dev/null | tail -1 | cut -d' ' -f2; }   # a gate's last status ("" = not written)
br() { $P -I -B $FR br "$@" 8>&- 9>&-; }     # basalt_rules.py's subcommands (its exe default: the fix engine)
fr() { $P -I -B $FR "$@" 8>&- 9>&-; }        # basalt_fix_rules.py's own
KFAIL=0; T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
kc() { $LIB/kcheck.sh "r23fx-$1" > /dev/null 8>&- 9>&- || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; return 1; }; }
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
  # may listen on the test port 8081 (gap-basalt-a.sh's)
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
  br envcli $E23/strata $cfg --job $jp --mode e7 --kill --gate env_${arm}_e7 --gates $G 2>&1 | tee -a $S
  wait $jp
  br e7gate $S $L --gate e7_$arm --gates $G | tee -a $S
  kc e7-$L
}

pfy() {   # pfy ARM NAME CONFIG SET PREFILL KV [keep-share] [env:K=V]...: the r23 yardstick (basalt_rules.py pfy) under
  # guard.py, its engine checked as it starts; NAME's dir in $Y (tail24) or $Y40 (long40)
  local arm=$1 n=$2 cfg=$3 set=$4 pf=$5 kv=$6 x jp t0 dir opts="" eopts=""; shift 6
  for x in "$@"; do case $x in keep-share) opts="$opts --keep-share"; eopts="$eopts --keep-share";;
                               env:*) opts="$opts --env ${x#env:}"; eopts="$eopts --set ${x#env:}";; esac; done
  ok_to_go || { say "skipped pf_yardstick $n (deadline or kernel check)"; return 1; }
  dir=$Y/$n; [ $set = long40 ] && dir=$Y40/$n
  say "pf_yardstick r23fx $n ($(basename $cfg), $set, --prefill $pf, --kv $kv${opts:+;$opts})"
  t0=$(date +%s)
  ( $P $LIB/guard.py pfyfx-$n -- $P -I -B $FR br pfy $cfg $dir --set $set --prefill $pf --kv $kv $opts 2>&1 | grep -v "^engine:" | tail -2 | sed "s/^/pfy $n: /" | tee -a $S ) 8>&- 9>&- &
  jp=$!
  br envcli $E23/strata $cfg --job $jp --mode pfy --prefill $pf --kv $kv $eopts --kill --gate env_${arm}_pfy-$n --gates $G 2>&1 | tee -a $S
  wait $jp
  case $set in tail24) T24_MIN=$(mins $t0);; long40) T40_MIN=$(mins $t0);; esac
  kc pfy-$n
}

pfy40() {   # pfy40 ARM NAME CONFIG: work/r22/pf_yardstick.py run --set long40 itself (gap 17's / gap a's form, bare auto, fp16)
  local arm=$1 n=$2 cfg=$3 jp t0
  ok_to_go || { say "skipped pf_yardstick long40 $n (deadline or kernel check)"; return 1; }
  say "pf_yardstick long40 $n ($(basename $cfg))"
  t0=$(date +%s)
  ( $P $LIB/guard.py pfyfx-$n -- $P -I $KR/pf_yardstick.py run $cfg $Y40/$n --set long40 2>&1 | grep -v "^engine:" | tail -3 | sed "s/^/pfy $n: /" | tee -a $S ) 8>&- 9>&- &
  jp=$!
  br envcli $E23/strata $cfg --job $jp --mode pfy --kill --gate env_${arm}_pfy-$n --gates $G 2>&1 | tee -a $S
  wait $jp
  T40_MIN=$(mins $t0)
  kc pfy-$n
}

srvrun() {   # srvrun ARM LABEL CONFIG GATE_STEP SLICE CMD: one fresh test server (with_server.sh: cold page cache, the
  # memory guard, the shared test lock), its engine's env checked, then CMD; the engine log slice -> SLICE
  local arm=$1 lab=$2 cfg=$3 st=$4 sl=$5 cmd=$6 L off
  ok_to_go || { say "skipped $lab (deadline or kernel check)"; return 1; }
  L=$(elog $cfg); touch $L; off=$(stat -c %s $L)
  say "server $lab ($(basename $cfg))"
  $LIB/with_server.sh $lab $cfg -- "$P -I -B $FR br envcheck $E23/strata $cfg --gate env_${arm}_$st --gates $G && $cmd" 8>&- 9>&- 2>&1 \
    | grep -E "engine pid [0-9]+:|ENV CHECK| pass |ready|exited|refus|Error|GUARD|Traceback" | tee -a $S
  tail -c +$((off + 1)) $L > $sl
  fatalchk fatal_${arm}_$st $L $off $lab
  kc $lab
}

end_gap() {
  if [ $KFAIL = 1 ]; then say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"; exit 3; fi
  fr decide $O > /dev/null 2>&1
  [ -f $O/decision-fix.txt ] && tee -a $S < $O/decision-fix.txt || say "basalt_fix_rules.py decide failed - rerun it by hand ($FR decide $O)"
  say "P028x back on 8080 (port_gap4.sh end) - nothing switched"
  if ! $KR/port_gap4.sh end 8>&- 9>&- 2>&1 | tee -a $S; then
    say "port_gap4.sh end FAILED: 8080 and the research queue need a look"; exit 4
  fi
  kc end || { say "the kernel check failed after P028x came back: Karl decides"; exit 3; }
  say "Basalt fix rerun done ($(( ($(date +%s) - T0) / 60 )) min with 8080 down)"
  exit 0
}

# ================================================================ before the gap (no GPU; 8080 untouched)
say "BASALT PROMPT-PATH FIX RERUN (work/r23/gap-basalt-fix.sh): A, T, C on engine-r23basalt-fix (a test; P028x stays served, nothing switches)"
preflight
for f in $WS/configs/P0210x-h.json $RU $FR $KR/pf_yardstick.py $LIB/exact7.sh $LIB/with_server.sh $LIB/guard.py $LIB/kcheck.sh \
         $KR/port_gap4.sh $Y8/ref/index.json $Y8/unfused/index.json $Y8/cpushare/index.json $Y17/p210/index.json \
         $W/serve/server.py $R/gap-a/decision-a.txt $E23/strata; do
  [ -f $f ] || { say "missing $f - not started"; exit 1; }
done
[ "$(ls $PROF/g17-p210a-*.out 2> /dev/null | wc -l)" = 7 ] || { say "gap 17's exact7 g17-p210a (the base's reference) is incomplete - not started"; exit 1; }
[ -f $WS/tmp/r19/kwatch.pid ] && kill -0 "$(cat $WS/tmp/r19/kwatch.pid)" 2> /dev/null || { say "the kernel-log watcher is not running - not started"; exit 1; }
$P -I -B $FR selftest > /dev/null 2>&1 || { say "basalt_fix_rules.py selftest failed (its formulas are not r23_plan.hpp's) - not started"; exit 1; }
BC=$(fr buildcheck 2>&1 | tail -1)
case $BC in "BUILD CHECK OK:"*) ;; *) say "the fix engine does not check out: $BC - not started (build it: work/r23/build-basalt-fix.sh engine + tests under nogap-run.sh)"; exit 1;; esac
if [ -e $O ]; then PREV=$R/gap-fix-prev-$(date +%m%d-%H%M%S); mv $O $PREV; say "an earlier attempt's outputs moved to $PREV"; fi
mkdir -p $O $Y $Y40 $CF
SAY_TO=$S; cat $STARTS >> $S 2> /dev/null
fr buildcheck --gate build_fix --gates $G 2>&1 | tee -a $S
fr arms $CF --gate cfg --gates $G 2>&1 | tee -a $S
[ "$(gst cfg)" = PASS ] || { say "the arm configs are not P0210x-h + their switches - not started"; exit 1; }
gate nll INFO "information only: kernel_rule3's point NLL printed as INFO, no many-positions arm (Karl 11-05: that bound is revoked)"
for x in ref unfused cpushare; do ln -sfn $Y8/$x $Y40/$x; done      # gap 8's long40 references (as gap a)

# ================================================================ the gap
$KR/port_gap4.sh begin "Basalt prompt-path fix rerun: A, T, C on engine-r23basalt-fix (a test; P028x stays served, nothing switches)" 8>&- 9>&- 2>&1 | tee -a $S
[ -s $WS/tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
echo "$T0 $(date -Is)" > $O/t0.txt
kc open || end_gap
for i in $(seq 60); do [ -z "$(engines_left)" ] && break; sleep 2; done
if [ -n "$(engines_left)" ]; then say "engine processes still running 120 s after 8080 stopped: $(engines_left) - ending the gap"; end_gap; fi
for i in $(seq 24); do [ "$(awk '/^MemAvailable/ {print int($2 / 1048576)}' /proc/meminfo)" -ge 40 ] && break; sleep 5; done
say "8080 down: no engine left, MemAvailable $(awk '/^MemAvailable/ {print int($2 / 1048576)}' /proc/meminfo) GB"

# ---- 2 the base on the fix engine
say "BASELINE: exact7 B vs gap 17's g17-p210a; long40 B vs gap 17's p210"
e7 B r23fx-B $CF/r23-B.json g17-p210a
pfy40 B B40 $CF/r23-B.json
br same $Y40/B40 $Y17/p210 --gate logits_B40 --gates $G | tee -a $S
if [ "$(gst e7_B)" != PASS ] || [ "$(gst logits_B40)" != PASS ]; then
  say "the base is not P0210x-h bit for bit (e7_B $(gst e7_B), logits_B40 $(gst logits_B40)): nothing below is decided - ending the gap"
  end_gap
fi

# ---- 3 A: copy-ahead is exact, at the served chunk, with and without the served share
say "A: tail24 at --prefill $CH --kv int8: B16 / A16, then with the served CPU share B16s / A16s; exact7 A"
pfy B B16 $CF/r23-B.json tail24 $CH int8
fr chunk $Y/B16 --want $CH --gate chunk_B16 --gates $G | tee -a $S
pfy A A16 $CF/r23-A.json tail24 $CH int8
br same $Y/B16 $Y/A16 --gate same_A16 --gates $G | tee -a $S
br ahead $Y/A16 --gate ahead_A16 --gates $G | tee -a $S
fr chunk $Y/A16 --want $CH --gate chunk_A16 --gates $G | tee -a $S
pfy B B16s $CF/r23-B.json tail24 $CH int8 keep-share
fr chunk $Y/B16s --want $CH --gate chunk_B16s --gates $G | tee -a $S
pfy A A16s $CF/r23-A.json tail24 $CH int8 keep-share
br same $Y/B16s $Y/A16s --gate same_A16s --gates $G | tee -a $S
br ahead $Y/A16s --gate ahead_A16s --gates $G | tee -a $S
fr chunk $Y/A16s --want $CH --gate chunk_A16s --gates $G | tee -a $S
ln -sfn B16s $Y/cpushare16    # cpushare16 = B + STRATA_PREFILL_CPU_SHARE=0.4 (_MAX 1792 from the config) = B16s exactly
e7 A r23fx-A $CF/r23-A.json r23fx-B

# ---- 4 T: the tail split (rounding-level) at the served chunk on tail24 AND long40 + the KL rule (and A if it is not exact)
say "T: tail24 unfused16 (B + STRATA_PF_FUSED=0), T16; long40 B40_16, unfused40_16, cpushare40_16, T40_16 - all at --prefill $CH; the KL rule (NLL information only)"
pfy ref unfused16 $CF/r23-B.json tail24 $CH int8 env:STRATA_PF_FUSED=0
pfy T T16 $CF/r23-T.json tail24 $CH int8
fr planlines $Y/T16 --kind tail --chunk $CH --smin 1024 --gate plan_T16 --gates $G | tee -a $S
fr chunk $Y/T16 --want $CH --gate chunk_T16 --gates $G | tee -a $S
pfy B B40_16 $CF/r23-B.json long40 $CH fp16
fr chunk $Y40/B40_16 --want $CH --gate chunk_B40_16 --gates $G | tee -a $S
pfy ref unfused40_16 $CF/r23-B.json long40 $CH fp16 env:STRATA_PF_FUSED=0
pfy ref cpushare40_16 $CF/r23-B.json long40 $CH fp16 keep-share
pfy T T40_16 $CF/r23-T.json long40 $CH fp16
fr planlines $Y40/T40_16 --kind tail --chunk $CH --smin 1024 --gate plan_T40 --gates $G | tee -a $S
fr chunk $Y40/T40_16 --want $CH --gate chunk_T40 --gates $G | tee -a $S
CT="T16:T"; A40=0
if [ "$(gst same_A16)" = FAIL ] || [ "$(gst same_A16s)" = FAIL ] || [ "$(gst e7_A)" = FAIL ]; then
  say "A is not exact: it may go on as rounding-level only by the KL rule (tail24 A16 + long40 A40, gap a's form)"
  CT="$CT,A16:A"; fits $(( T40_MIN + END_MIN )) && { pfy40 A A40 $CF/r23-A.json; A40=1; }
fi
br kl $Y --set tail24 --ref B16 --refs unfused16,cpushare16 --cands $CT --mode new --gates $G 2>&1 | tee $O/kl-tail24.txt | tee -a $S
br kl $Y40 --set long40 --ref B40_16 --refs unfused40_16,cpushare40_16 --cands T40_16:T --mode new --gates $G 2>&1 | tee $O/kl-long40.txt | tee -a $S
[ $A40 = 1 ] && br kl $Y40 --set long40 --ref ref --refs unfused,cpushare --cands A40:A --mode new --gates $G 2>&1 | tee $O/kl-long40-A.txt | tee -a $S

# ---- 5 C: the cap arm on the stack (gap a's S_PARTS + A / T where they passed), the scan at auto:32768
fr decide $O --provisional > /dev/null 2>&1
SP=$($P -I -B $FR stack $O 2> /dev/null)
NC=0
if fits $(( SCAN_MIN + T24_MIN + T40_MIN + END_MIN )); then
  say "C on the stack (${SP:-none}): one start at --prefill auto:32768 + STRATA_PF_FIRST_CHUNK=1 (the scan's chunk N)"
  fr arms $CF --stack "$SP" --scan --gate cfg_s --gates $G 2>&1 | tail -1 | tee -a $S
  if [ "$(gst cfg_s)" = PASS ]; then
    srvrun C r23fx-Cscan $CF/r23-Cscan.json scan $O/cscan.englog "sleep 2"
    NC=$(fr lend $O/cscan.englog --gate c_lend --gates $G | tail -1)
  fi
else
  say "C not started: $(( SCAN_MIN + T24_MIN + T40_MIN + END_MIN )) min do not fit before the deadline (or a kernel check failed)"
fi
if [ "${NC:-0}" -gt $CH ] 2> /dev/null; then
  gate c_parts INFO "${SP:-none} (C = these + --prefill $NC explicit in the yardstick + STRATA_PF_FIRST_CHUNK=1; the scan at auto:32768)"
  fr arms $CF --stack "$SP" --cap $NC --gate cfg_c --gates $G 2>&1 | tail -1 | tee -a $S
  if [ "$(gst cfg_c)" = PASS ]; then
    pfy C C16 $CF/r23-C.json tail24 $NC int8
    fr planlines $Y/C16 --kind first --chunk $NC --smin 1024 --gate plan_C16 --gates $G | tee -a $S
    fr chunk $Y/C16 --want $NC --gate chunk_C16 --gates $G | tee -a $S
    pfy C C40 $CF/r23-C.json long40 $NC fp16
    br vram srv-r23fx-Cscan pfyfx-C16 pfyfx-C40 --gate vram_C --gates $G | tee -a $S
    br kl $Y --set tail24 --ref B16 --refs unfused16,cpushare16 --cands C16:C --mode new --gates $G 2>&1 | tee $O/kl-tail24-C.txt | tee -a $S
    # C40 is judged against step T's 16384 references (Karl 11-05); without them C's long40 part is NOT DECIDED (MISSING),
    # never judged against the 1024 ones. Gap 8's 1024-chunk references: beside it, INFORMATION ONLY (gates *_Cinfo1024_*)
    if [ -f $Y40/B40_16/index.json ] && [ -f $Y40/unfused40_16/index.json ] && [ -f $Y40/cpushare40_16/index.json ]; then
      br kl $Y40 --set long40 --ref B40_16 --refs unfused40_16,cpushare40_16 --cands C40:C --mode new --gates $G 2>&1 | tee $O/kl-long40-C.txt | tee -a $S
    else
      for r in kl2 kl3; do gate ${r}_C_long40 MISSING "the 16384 long40 references (B40_16, unfused40_16, cpushare40_16) did not run: not judged against the 1024 ones"; done
    fi
    br kl $Y40 --set long40 --ref ref --refs unfused,cpushare --cands C40:Cinfo1024 --mode new --gates $G 2>&1 | tee $O/kl-long40-C-1024-info.txt | tee -a $S
  fi
else
  say "C: no chunk above $CH from the scan (c_lend $(gst c_lend), cfg_s $(gst cfg_s)) - C16 / C40 not run"
  [ "$(gst cfg_s)" = PASS ] && br vram srv-r23fx-Cscan --gate vram_C --gates $G | tee -a $S
fi

# ---- 6 the rules, P028x back
end_gap
