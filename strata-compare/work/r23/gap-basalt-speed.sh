#!/bin/bash
# gap-basalt-speed.sh - r23 (written 2026-11-08, NOT RUN, no .ready file): THE SPEED GAP for the Basalt prompt-path parts
# (results/BACKLOG-1027.md section H; Karl 11-07: "yes, after Phase 5's queue, P028x as the reference"). It prices A, T,
# U and the C-stack on engine-r23basalt-fix against B on the same build and against P028x (the served build), and U on
# P028x itself (P028x + STRATA_HC_UPMIX=1) once its exactness there is shown. Measurements only: P028x stays served,
# nothing switches, nothing is built, no config of the served setup changes. The rules, fixed before any run and frozen
# into the gap's rules.txt: work/r23/basalt_speed_rules.py's docstring (Basalt gap b's B1 / B2 / B3 and thresholds,
# under the 11-07 measurement amendment). Output: results/r23/basalt-prompt/gap-speed/ (summary.txt, gates.txt,
# rules.txt, configs/, bp90/, speed/, pfy40/, chat/, englog/, decision.txt / .json).
# Run by a chain as `bash <snapshot copy> 8>&- 9>&-` (no argument; every path here is absolute).
#   0 BEFORE THE GAP (no GPU, 8080 untouched). It REFUSES (exit 1) when:
#     - tmp/gpu-test.lock is held, another gap holds the test lock, a model server other than the 8080 queue's P028x
#       runs (engines by exact name + NVIDIA compute processes, by their ancestry to the 8080 listener), or something
#       listens on 8081; nvidia-smi does not answer; the kernel-log watcher is not running, or a kernel check fails;
#     - a file is missing (the rules and tools, configs/P0210x-h.json and x28h.json, gap fix's and gap a's decisions,
#       P028x's stored exact7 x28h-e7a (7 items) and long40 results/r22/gap16/pfy/x28h (40 logit files), gap 17's bp90
#       noise files, the Basalt fixtures);
#     - an engine does not check out: engine-r23basalt-fix (basalt_fix_rules.py buildcheck: SHA256, SOURCE at
#       b8128327d, GATES, TESTS) is not the build gap fix's decision names; engine-r22p028x is not P028x (f4c4f654fb24)
#       or has no STRATA_HC_UPMIX;
#     - basalt_speed_rules.py pre (gap fix's BUILD and BASELINE PASS, something to price) or its selftest fails;
#     - the arm configs (basalt_speed_rules.py arms + cfgcheck) do not check out; under 5 GB free.
#     The research queue's state is logged as INFO only: the chain starts this after the queue finished its plan, and
#     port_gap4.sh begin still waits for a running question, an active Jan job and a chat being answered on 8080.
#   1 port_gap4.sh begin (the queue held, the test lock, 8080 down); its engines gone and MemAvailable >= 40 GB (120 s
#     at most); a kernel check
#   2 PU's exactness on P028x: exact7 P (pin 2500) vs the stored x28h-e7a; exact7 PU vs this gap's P; long40 PU40 vs gap
#     16's stored x28h long40 (P40 as well, only when e7_P or that comparison is not PASS). puexact EXACT lets PU in
#   3 B1 Basalt's cold pp16k / pp64k, a fresh engine per measurement, 3 passes: B A T U C P PU / reversed / as first
#   4 B2 Basalt's decode fixtures, 1 pass: B C P PU
#   5 B3 the 9-workload screen (abarm.sh), 3 passes: B C P PU / PU P C B / P B PU C
#   6 B4 the chat-cache trade of T and C, REPORTED (Bc Tc Cc; GS_B4=0 skips it)
#   7 vram_C over every C start; basalt_speed_rules.py decide -> decision.txt / .json; port_gap4.sh end (P028x back); a
#     kernel check
#   (arms whose class is not EXACT / ROUNDING-LEVEL, a C that gap fix did not pass, a PU that is not EXACT: left out)
# Every test server: no foreign GPU user before it starts (60 s wait, else the start is skipped) and none during it (a
# 5 s watch; one sighting = the start is left out); its engine's environment checked by basalt_rules.py envcheck before
# it measures (the config's env exactly, no part / diagnostic switch behind it, STRATA_ROUTE_TAIL_SKIP=0, 2 GPUs,
# --kv-resident 32768, --prefill); its prompt-chunk line (C: must be gap fix's C_CHUNK, else that start is left out);
# the fatal-line check; a kernel check. CLI jobs (exact7, pf_yardstick): envcli on the job's tree by /proc/PID/exe, a
# mismatching engine stopped by its PID. Children run with 8>&- 9>&- and stdin from /dev/null; processes are found by
# PID, pid file or exact name only.
# A kernel-check failure stops new steps and leaves the gap OPEN (8080 down, exit 3: Karl decides). No new step after
# GS_MAX_MIN (default 150) minutes with 8080 down, and each step starts only if it fits (B1 / B2 start 2-3 min, a screen
# pass 5, exact7 5, long40 10).
# Time with 8080 down (gap b's and gap fix's measured step times): open ~2, exactness ~15 (+9 when P40 runs), B1 ~42 (42
# starts of ~1 min), B2 ~7 (4 x ~1.6), B3 ~45 (12 arm-passes of ~3.7), B4 ~3, close ~3 -> ~1.9 h (~2.1 h with P40).
# Deadline 150 min: the last step started before it ends ~5 min later, then the close: ~2.7 h at most.
# Exit 0 = done (the outcome is in decision.txt), 1 = refused / not opened (8080 untouched), 3 = kernel check failed
# (gap open), 4 = port_gap4.sh end failed.
set -u -o pipefail
exec 8>&- 9>&-     # no inherited lock descriptor reaches a child (this script holds none itself)
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
for v in $(compgen -e | grep '^STRATA_'); do [ "$v" = STRATA_MON_GPU ] || unset "$v"; done   # no stray switch reaches an engine
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r23 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
P=$WS/.venv/bin/python; SR=$WS/work/r23/basalt_speed_rules.py; FR=$WS/work/r23/basalt_fix_rules.py; KR=$WS/work/r22
LIB=$WS/bringup/lib; B90=$KR/basalt-pr90; BPD=/home/USER/ai-speed-testing/basalt-pr90-data
R=$WS/results/r23/basalt-prompt; O=$R/gap-speed; CF=$O/configs; S=$O/summary.txt; G=$O/gates.txt
BO=$O/bp90; SPD=$O/speed; CH=$O/chat; EL=$O/englog; Y40=$O/pfy40; FG=$O/foreign
W=$WS/strata-r23basalt; E23=$WS/engine-r23basalt-fix; W28=$WS/strata-r22p028x; E28=$WS/engine-r22p028x
DFIX=$R/gap-fix/decision-fix.txt; DA=$R/gap-a/decision-a.txt
Y16=$WS/results/r22/gap16/pfy/x28h; E7REF=x28h-e7a; PROF=$WS/bringup/out/logs/prof
LOCKPID=$WS/tmp/port-gap.lockpid; HOLD=/home/USER/ai/deep-research/tmp/bench2.hold
P028X_SHA=f4c4f654fb24             # engine-r22p028x/strata, served on 8080 since 10-30
MAXM=${GS_MAX_MIN:-150}
LP=r23sp$(date +%m%d%H%M)          # this attempt's exact7 labels (bringup/out/logs/prof/$LP-P-*, $LP-PU-*)
STARTS=$R/gap-speed-starts.log     # until the pre-gap checks pass (then $S)
mkdir -p $R $WS/logs $WS/tmp/r23
say() { echo "=== $(date '+%F %T') $*" | tee -a ${SAY_TO:-$STARTS}; }
gate() { echo "$1 $2 ${*:3} [23sp $(date '+%m-%d %H:%M')]" >> $G; say "  gate $*"; }
gst() { grep "^$1 " $G 2> /dev/null | tail -1 | cut -d' ' -f2; }   # a gate's last status ("" = not written)
sr() { $P -I -B $SR "$@" 8>&- 9>&- < /dev/null; }      # basalt_speed_rules.py
br() { $P -I -B $FR br "$@" 8>&- 9>&- < /dev/null; }   # basalt_rules.py's subcommands (through basalt_fix_rules.py)
KFAIL=0; T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
kc() { $LIB/kcheck.sh "r23sp-$1" > /dev/null 8>&- 9>&- < /dev/null || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; return 1; }; }
left() { echo $(( DEADLINE - $(date +%s) )); }
ok_to_go() { [ $KFAIL = 0 ] && [ $(left) -gt 0 ]; }
fits() { ok_to_go && [ $(left) -ge $(( $1 * 60 )) ]; }   # a step starts only if it ends before the deadline
sha12() { sha256sum "$1" | cut -c1-12; }
elog() { $P -I -c "import json, sys; print(json.load(open(sys.argv[1]))['log'])" "$1"; }
exe_of() { $P -I -c "import json, sys; print(json.load(open(sys.argv[1]))['exe'])" "$1"; }
slog() { ls -t $WS/bringup/out/logs/server_$1_*.log 2> /dev/null | head -1; }   # the newest server log of a with_server label
ppid_of() { local s; s=$(cat /proc/$1/stat 2> /dev/null) || return 0; s=${s##*) }; set -- $s; echo "${2:-}"; }
memav() { awk '/^MemAvailable/ {printf "%d", $2 / 1048576}' /proc/meminfo; }

preflight() {   # refuse (exit 1, nothing touched) when a measurement holds the GPU lock, another gap is open, or a model
  # server other than the 8080 queue's P028x runs: every engine process (exact names) and every NVIDIA compute process
  # must belong to the server listening on 8080, whose engine must be P028x (its vision helper allowed); nothing may
  # listen on the test port 8081
  local l p q apps bad=""
  if [ -s $LOCKPID ] && kill -0 "$(cat $LOCKPID)" 2> /dev/null; then
    say "another gap holds the test lock (tmp/port-gap.lockpid $(cat $LOCKPID)) - not started"; exit 1
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

fatalchk() {   # fatalchk GATE ENGINE_LOG OFFSET LABEL: a fatal GPU error / stall / engine restart / non-finite in the slice
  local L=$2 off=$3 sl hits
  sl=$(slog $4)
  hits=$( { tail -c +$((off + 1)) $L 2> /dev/null; [ -n "$sl" ] && cat $sl; } | grep -c -E "fatal GPU error|no progress for [0-9]+ s during a request|the engine had stopped \(exit code|became non-finite")
  [ "$hits" = 0 ] || gate $1 FAIL "$hits line(s): fatal GPU error / stall / engine restart / non-finite ($L from byte $off; $sl)"
}
foreign() {   # the GPU users that are not one of this gap's two engines (gap-screen-rerun.sh's rule): an engine process
  # (exact names) or an NVIDIA compute process holding >= 512 MiB (or an unknown amount) whose binary is in neither engine
  # folder
  local p m x ex c
  { for x in strata strata-host strata-vision strata-dsv41 llama-server ollama; do pgrep -x $x | sed 's/$/,engine/'; done
    nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits 2> /dev/null; } | tr -d ' ' \
  | while IFS=, read -r p m; do
      [[ $p =~ ^[0-9]+$ ]] && [ -e /proc/$p ] || continue
      [[ $m =~ ^[0-9]+$ ]] && [ $m -lt 512 ] && continue
      ex=$(readlink /proc/$p/exe 2> /dev/null) || ex=""; c=$(cat /proc/$p/comm 2> /dev/null)
      case $c in strata-dsv41|llama-server|ollama) ;; *) [ -n "$ex" ] || continue
        case $ex in $E23/*|$E28/*) continue;; esac;; esac
      echo "pid $p ($c, ${ex:-?}, $m$([[ $m =~ ^[0-9]+$ ]] && echo ' MiB'))"
    done | sort -u
}
gwatch() {   # gwatch FLAG OUT: while FLAG exists (and this driver runs), every 5 s: foreign GPU users >> OUT
  while [ -e $1 ] && kill -0 $$ 2> /dev/null; do foreign | sed "s/^/$(date +%T) /" >> $2; sleep 5; done
}
gpu_clear() {   # gpu_clear NAME: no foreign GPU user before the start (up to 60 s); else foreign_NAME FAIL, not started
  local i f
  for i in $(seq 12); do f=$(foreign); [ -z "$f" ] && return 0; sleep 5; done
  gate foreign_$1 FAIL "not started: $(echo "$f" | head -1) still on the GPU after 60 s"
  return 1
}
WGP=""
wstart() { rm -f $FG/$1.foreign; touch $FG/$1.watching; gwatch $FG/$1.watching $FG/$1.foreign 8>&- 9>&- < /dev/null & WGP=$!; }
wstop() {    # one foreign GPU user seen during the start = foreign_NAME FAIL (the start is left out)
  rm -f $FG/$1.watching; [ -n "$WGP" ] && wait $WGP 2> /dev/null; WGP=""
  [ -s $FG/$1.foreign ] && gate foreign_$1 FAIL "seen during $1 ($(wc -l < $FG/$1.foreign) sample(s)): $(head -1 $FG/$1.foreign | cut -c1-160) - left out"
  return 0
}

CLABS=""     # the guard labels of every C start (vram_C)
srvrun() {   # srvrun ARM STEP LABEL CONFIG WANT CMD: one fresh test server (with_server.sh: cold page cache, the memory
  # guard, the shared test lock), its engine's env checked, then CMD; WANT = the chunk C must get, or info:N; the engine
  # log slice -> englog/LABEL.englog; gates env_/fatal_/foreign_/chunk_ARM_STEP; a kernel check
  local arm=$1 st=$2 lab=$3 cfg=$4 want=$5 cmd=$6 L off exe
  ok_to_go || { say "skipped $lab (deadline or kernel check)"; return 1; }
  gpu_clear ${arm}_$st || { say "$lab NOT started (a foreign GPU user)"; return 1; }
  exe=$(exe_of $cfg); L=$(elog $cfg); touch $L; off=$(stat -c %s $L)
  say "server $lab ($(basename $cfg))"
  wstart ${arm}_$st
  $LIB/with_server.sh $lab $cfg -- "$P -I -B $FR br envcheck $exe $cfg --gate env_${arm}_$st --gates $G && $cmd" 8>&- 9>&- < /dev/null 2>&1 \
    | grep -E "engine pid [0-9]+:|ENV CHECK| pass |request [123]:|tok/s|ready|exited|refus|Error|GUARD|Traceback" | tee -a $S
  wstop ${arm}_$st
  tail -c +$((off + 1)) $L > $EL/$lab.englog
  fatalchk fatal_${arm}_$st $L $off $lab
  case $want in
    info:*) sr chunk $EL/$lab.englog --want ${want#info:} --info --gate chunk_${arm}_$st --gates $G > /dev/null;;
    *) sr chunk $EL/$lab.englog --want $want --gate chunk_${arm}_$st --gates $G | tee -a $S; CLABS="$CLABS srv-$lab";;
  esac
  kc $lab
}
tree_of() { case $1 in P|PU) echo $W28;; *) echo $W;; esac; }
want_of() { case $1 in C|Cc) echo $CC;; *) echo info:16384;; esac; }

bprun() {   # bprun ARM SET PASS: Basalt's community-1 fixture SET, cold (a fresh engine), one pass -> bp90/ARM-SET-PASS.jsonl
  local a=$1 set=$2 k=$3 out=$BO/$1-$2-$3.jsonl
  fits 3 || { say "skipped bp90 $a $set pass $k (under 3 min to the deadline, or a kernel check failed)"; return 0; }
  srvrun $a bp$k$set r23sp-bp$a-$set-$k $CF/$a.json $(want_of $a) \
    "$P -I -B $B90/bp90_client.py http://127.0.0.1:8081 --label r23sp-$a-$set-$k --sets $set --passes 1 --first-pass $k --tree $(tree_of $a) --out $out" || true
  if [ "$(gst foreign_${a}_bp$k$set)" = FAIL ] || [ "$(gst chunk_${a}_bp$k$set)" = FAIL ]; then
    mkdir -p $BO/void; [ -e $out ] && mv $out $BO/void/
  fi
  return 0
}

darm() {   # darm ARM PASS: one screen pass on a fresh server - warm-up, W1-W3, the 2 agent turns, the 4 research replays
  local a=$1 k=$2 n=$1$2 cfg=$CF/$1.json L off f
  fits 5 || { say "skipped screen $n (under 5 min to the deadline, or a kernel check failed)"; return 0; }
  L=$(elog $cfg); touch $L; off=$(stat -c %s $L)
  srvrun $a scr$k r23sp-$n $cfg $(want_of $a) "bash $KR/abarm.sh http://127.0.0.1:8081 $off $SPD $n ${n}n=normal:1:W1,W2,W3 ${n}a=agent:1 ${n}r=research4:1" || true
  if [ "$(gst foreign_${a}_scr$k)" = FAIL ] || [ "$(gst chunk_${a}_scr$k)" = FAIL ]; then
    mkdir -p $SPD/void; for f in $SPD/${n}n.* $SPD/${n}a.* $SPD/${n}r.* $SPD/$n.*; do [ -e "$f" ] && mv "$f" $SPD/void/; done
  fi
  return 0
}

chatrun() {   # chatrun ARM: B4 on a fresh server with STRATA_TRACE=1 (config ARMc): requests 1-3 of basalt_rules.py chat3
  local a=$1
  fits 2 || { say "skipped B4 $a (under 2 min to the deadline, or a kernel check failed)"; return 0; }
  srvrun $a chat r23sp-chat$a $CF/${a}c.json $(want_of ${a}c) \
    "$P -I -B $FR br chat3 http://127.0.0.1:8081 --label r23sp-chat$a --out $CH/chat-$a.jsonl --tree $W" || true
  cp $EL/r23sp-chat$a.englog $CH/chat-$a.englog 2> /dev/null
  return 0
}

e7() {   # e7 ARM LABEL CONFIG REF: exact7 at pin 2500 against REF's hashes and slots, every item's engine checked
  local arm=$1 L=$2 cfg=$3 ref=$4 jp
  fits 5 || { say "skipped exact7 $L (under 5 min to the deadline, or a kernel check failed)"; return 1; }
  say "exact7 $L ($(basename $cfg) against $ref, pin 2500)"
  ( PIN_CACHE=2500 REF=$ref $LIB/exact7.sh $L $cfg 2>&1 | tail -9 | tee -a $S ) 8>&- 9>&- < /dev/null &
  jp=$!
  br envcli $(exe_of $cfg) $cfg --job $jp --mode e7 --kill --gate env_${arm}_e7 --gates $G 2>&1 | tee -a $S
  wait $jp
  br e7gate $S $L --gate e7_$arm --gates $G | tee -a $S
  kc e7-$L
}

pfy40() {   # pfy40 ARM NAME CONFIG: work/r22/pf_yardstick.py run --set long40 (gap 16's / gap a's form: bare auto, fp16)
  local arm=$1 n=$2 cfg=$3 jp
  fits 10 || { say "skipped pf_yardstick long40 $n (under 10 min to the deadline, or a kernel check failed)"; return 1; }
  say "pf_yardstick long40 $n ($(basename $cfg))"
  ( $P $LIB/guard.py pfysp-$n -- $P -I -B $KR/pf_yardstick.py run $cfg $Y40/$n --set long40 2>&1 | grep -v "^engine:" | tail -3 | sed "s/^/pfy $n: /" | tee -a $S ) 8>&- 9>&- < /dev/null &
  jp=$!
  br envcli $(exe_of $cfg) $cfg --job $jp --mode pfy --kill --gate env_${arm}_pfy-$n --gates $G 2>&1 | tee -a $S
  wait $jp
  kc pfy-$n
}

judge() {   # the rules (CPU only, nice 19)
  nice -n 19 $P -I -B $SR decide $O 8>&- 9>&- < /dev/null > /dev/null 2>&1
  [ -f $O/decision.txt ] && tee -a $S < $O/decision.txt || say "basalt_speed_rules.py decide failed - rerun it by hand ($P -I -B $SR decide $O)"
}
end_gap() {
  if [ $HAVE_C = 1 ] && [ -n "$CLABS" ] && [ -z "$(gst vram_C)" ]; then br vram $CLABS --gate vram_C --gates $G | tee -a $S; fi
  if [ $KFAIL = 1 ]; then say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"; judge; exit 3; fi
  judge
  say "P028x back on 8080 (port_gap4.sh end) - nothing switched"
  if ! $KR/port_gap4.sh end 8>&- 9>&- < /dev/null 2>&1 | tee -a $S; then
    say "port_gap4.sh end FAILED: 8080 and the research queue need a look"; exit 4
  fi
  kc end || { say "the kernel check failed after P028x came back: Karl decides"; exit 3; }
  say "Basalt speed gap done ($(( ($(date +%s) - T0) / 60 )) min with 8080 down)"
  exit 0
}

# ================================================================ 0 before the gap (no GPU; 8080 untouched)
HAVE_C=0; HAVE_PU=0
say "start attempt: work/r23/gap-basalt-speed.sh (pre-gap checks)"
systemctl --user is-active -q deep-research-bench.service && QS=active || QS=inactive
say "  (info) the research queue (deep-research-bench.service) is $QS; port_gap4.sh begin waits for a running question, an active Jan job and a chat on 8080"
preflight
[ -f $WS/tmp/r19/kwatch.pid ] && kill -0 "$(cat $WS/tmp/r19/kwatch.pid)" 2> /dev/null || { say "the kernel-log watcher is not running - not started"; exit 1; }
$LIB/kcheck.sh r23sp-pre > /dev/null 8>&- 9>&- < /dev/null || { say "a kernel check fails before the gap - not started"; exit 1; }
for f in $SR $FR $WS/work/r23/basalt_rules.py $KR/g17_rules.py $KR/pf_yardstick.py $KR/abarm.sh $KR/port_gap4.sh \
         $B90/bp90_client.py $LIB/with_server.sh $LIB/exact7.sh $LIB/guard.py $LIB/kcheck.sh $W/serve/server.py \
         $W28/serve/server.py $WS/configs/P0210x-h.json $WS/configs/x28h.json $DFIX $DA $Y16/index.json \
         $WS/results/r22/gap17/bp90/cold-H.jsonl $WS/results/r22/gap17/bp90/cold-M.jsonl $BPD/prefill.ids \
         /home/USER/ai-speed-testing/basalt-ab/scripts/abrun.py; do
  [ -f $f ] || { say "missing $f - not started"; exit 1; }
done
[ "$(ls $PROF/$E7REF-*.out 2> /dev/null | wc -l)" = 7 ] || { say "P028x's stored exact7 $E7REF is incomplete - not started"; exit 1; }
[ "$(ls $Y16/first.* 2> /dev/null | wc -l)" = 40 ] || { say "P028x's stored long40 ($Y16) does not have its 40 logit files - not started"; exit 1; }
BC=$($P -I -B $FR buildcheck 2>&1 < /dev/null | tail -1)
case $BC in "BUILD CHECK OK:"*) ;; *) say "engine-r23basalt-fix does not check out: $BC - not started"; exit 1;; esac
if ! PRE=$(sr pre --decision-fix $DFIX --decision-a $DA 2>&1); then
  say "REFUSED: $(echo "$PRE" | head -1 | cut -c1-300) - not started"; exit 1
fi
val() { echo "$PRE" | sed -n "s/^$1=//p"; }
FIX_SHA=$(val FIX_SHA); FIXARMS=$(val ARMS_FIX); CP=$(val C_PARTS); CC=$(val C_CHUNK)
[ "$(sha12 $E23/strata)" = "$FIX_SHA" ] || { say "engine-r23basalt-fix ($(sha12 $E23/strata)) is not the build gap fix gated ($FIX_SHA) - not started"; exit 1; }
[ -x $E28/strata ] && [ "$(sha12 $E28/strata)" = $P028X_SHA ] || { say "engine-r22p028x is not P028x ($P028X_SHA) - not started"; exit 1; }
$P -I -c "import sys; sys.exit(0 if b'STRATA_HC_UPMIX\0' in open(sys.argv[1], 'rb').read() else 1)" $E28/strata \
  || { say "engine-r22p028x has no STRATA_HC_UPMIX - not started"; exit 1; }
case " $FIXARMS " in *" C "*) HAVE_C=1;; esac
free=$(df --output=avail -B1G $WS/results | tail -1 | tr -d ' ')
[ "${free:-0}" -ge 5 ] || { say "only ${free} GB free on results/ - not started"; exit 1; }
ST=$R/gap-speed-selftest-$(date +%m%d%H%M%S)
if ! nice -n 19 $P -I -B $SR selftest $ST > $ST.out 2>&1 < /dev/null; then
  say "basalt_speed_rules.py selftest failed ($(tail -1 $ST.out | cut -c1-160)) - not started (its output: $ST.out)"; exit 1
fi
say "  $(tail -1 $ST.out)"; rm -rf $ST $ST.out
PREV=""
if [ -e $O ]; then PREV=$R/gap-speed-prev-$(date +%m%d-%H%M%S); mv $O $PREV; fi   # the rules judge only this attempt's files
mkdir -p $O $CF $BO $SPD $CH $EL $Y40 $FG
SAY_TO=$S; cat $STARTS >> $S 2> /dev/null
[ -n "$PREV" ] && say "an earlier attempt's outputs moved to $PREV"
say "  $(echo "$PRE" | head -1 | cut -c1-400)"
if [ $HAVE_C = 1 ]; then sr arms $CF --cparts "$CP" --cchunk $CC --gate cfg --gates $G 2>&1 | tail -1 | tee -a $S
else sr arms $CF --gate cfg --gates $G 2>&1 | tail -1 | tee -a $S; fi
[ "$(gst cfg)" = PASS ] || { say "the arm configs are not P0210x-h / x28h + their switches - not started"; exit 1; }
sr rules $O/rules.txt | tee -a $S
say "BASALT SPEED GAP (work/r23/gap-basalt-speed.sh): on engine-r23basalt-fix $FIX_SHA: $FIXARMS$([ $HAVE_C = 1 ] && echo " (C = $CP + FIRST_CHUNK at auto:32768, gated chunk $CC)"); on P028x: P, PU (after its exactness); deadline $MAXM min - measurements only, P028x stays served, nothing switches"

# ================================================================ 1 the gap
$KR/port_gap4.sh begin "Basalt speed gap: A, T, U, C-stack on engine-r23basalt-fix and U on P028x, priced against B and P028x (measurements only; P028x stays served, nothing switches)" 8>&- 9>&- < /dev/null 2>&1 | tee -a $S
[ -s $LOCKPID ] && kill -0 "$(cat $LOCKPID)" 2> /dev/null || { rm -f $HOLD; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
echo "$T0 $(date -Is)" > $O/t0.txt
for i in $(seq 60); do [ -z "$(engines_left)" ] && [ "$(memav)" -ge 40 ] && break; sleep 2; done
say "8080 down: engines left:$(engines_left | sed 's/^/ /;s/^ $/ none/') MemAvailable $(memav) GB"
kc open || end_gap
[ -z "$(engines_left)" ] || { say "engine processes still running 120 s after 8080 stopped: $(engines_left) - ending the gap"; end_gap; }

# ---- 2 PU's exactness on P028x (it gates PU's speed arms)
say "2 PU's exactness on P028x: exact7 P vs the stored $E7REF, exact7 PU vs this gap's P; long40 PU40 vs gap 16's stored x28h"
e7 P $LP-P $CF/P.json $E7REF
E7P=$(gst e7_P)   # PASS or FAIL: P's exact7 ran (a FAIL = P028x moved since x28h-e7a: a FLAG, PU is judged against this P)
if [ "$(gst env_P_e7)" = PASS ] && { [ "$E7P" = PASS ] || [ "$E7P" = FAIL ]; }; then
  e7 PU $LP-PU $CF/PU.json $LP-P
  if [ "$(gst e7_PU)" = PASS ] && pfy40 PU PU40 $CF/PU.json; then
    br same $Y40/PU40 $Y16 --gate logits_PU40 --gates $G | tee -a $S
    if [ "$(gst env_PU_pfy-PU40)" = PASS ] && { [ "$(gst e7_P)" != PASS ] || [ "$(gst logits_PU40)" != PASS ]; }; then
      say "P40: this gap's own P long40 (e7_P $(gst e7_P), logits_PU40 $(gst logits_PU40)): P028x today or U?"
      if pfy40 P P40 $CF/P.json; then
        br same $Y40/P40 $Y16 --gate logits_P40 --gates $G | tee -a $S
        br same $Y40/PU40 $Y40/P40 --gate logits_PU40_P40 --gates $G | tee -a $S
      fi
    fi
  fi
fi
[ $KFAIL = 1 ] && end_gap
PUX=$(sr puexact $O --gate pu_exact --gates $G | tee -a $S | tail -1)
[ "$PUX" = EXACT ] && HAVE_PU=1
say "PU (P028x + STRATA_HC_UPMIX=1): $PUX - its speed arms $([ $HAVE_PU = 1 ] && echo run || echo 'are NOT run')"

# ---- 3 B1 Basalt's cold fixtures, prompts: 3 passes in turned order
ARMS1="$FIXARMS P"; [ $HAVE_PU = 1 ] && ARMS1="$ARMS1 PU"
REV=$(echo $ARMS1 | tr ' ' '\n' | tac | tr '\n' ' ')
say "3 B1 Basalt's cold pp16k / pp64k, a fresh engine per measurement, 3 passes: $ARMS1 / $REV/ $ARMS1"
for k in 1 2 3; do
  case $k in 2) order=$REV;; *) order=$ARMS1;; esac
  for a in $order; do for set in pp16k pp64k; do [ $KFAIL = 1 ] && break 3; bprun $a $set $k; done; done
done
[ $KFAIL = 1 ] && end_gap

# ---- 4 B2 Basalt's decode fixtures, 1 pass
SCR="B"; [ $HAVE_C = 1 ] && SCR="$SCR C"; SCR="$SCR P"; [ $HAVE_PU = 1 ] && SCR="$SCR PU"
say "4 B2 Basalt's decode fixtures (conv, struct, prose), 1 pass: $SCR"
for a in $SCR; do [ $KFAIL = 1 ] && break; bprun $a decode 1; done
[ $KFAIL = 1 ] && end_gap

# ---- 5 B3 the 9-workload screen, 3 passes in turned order
say "5 B3 the 9-workload screen, 3 passes in turned order (B C P PU / PU P C B / P B PU C) over: $SCR"
for k in 1 2 3; do
  case $k in 1) order="B C P PU";; 2) order="PU P C B";; 3) order="P B PU C";; esac
  for a in $order; do [ $KFAIL = 1 ] && break 2; case " $SCR " in *" $a "*) darm $a $k;; esac; done
done
[ $KFAIL = 1 ] && end_gap

# ---- 6 B4 the chat-cache trade of T and C (reported; Karl decides the trade)
if [ "${GS_B4:-1}" = 1 ]; then
  say "6 B4 the chat-cache trade (#693): B, T, C with STRATA_TRACE=1; request 2 shares ~16,500 tokens with request 1 (reported)"
  for a in B T C; do
    [ $KFAIL = 1 ] && break
    case " $FIXARMS " in *" $a "*) chatrun $a;; *) say "  $a not in B4 (not priced)";; esac
  done
  [ -s $CH/chat-B.jsonl ] && br chatrep $CH --gate chat_trade --gates $G | tee -a $S
else
  say "6 B4 skipped (GS_B4=0)"
fi

# ---- 7 the rules, P028x back
[ $HAVE_C = 1 ] && [ -n "$CLABS" ] && br vram $CLABS --gate vram_C --gates $G | tee -a $S
end_gap
