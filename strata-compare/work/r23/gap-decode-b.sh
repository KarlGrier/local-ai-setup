#!/bin/bash
# gap-decode-b.sh - round 23, the exact decode items, part b (Karl 11-04, queued third, one gap between two 7d questions;
# results/r23/decode-timing/GATE-PLAN.md sections 3.4, 3.5, 6). WRITTEN 11-04, NOT RUN. Measurements only: P028x stays
# served, nothing switches, nothing is built. Run: `bash work/r23/gap-decode-b.sh` (no arguments).
#   0 before the gap (no GPU, 8080 untouched): REFUSES (exit 1) unless part a's decision file says the build passed,
#     the exact7 base passed (r23-B = the port, r23-B2 = r23-B) and at least one item is EXACT (decode_rules.py check-a;
#     R23B_SCREEN_ANYWAY=1: at least one item whose exact7 rows passed), and engine-r23decode is still part a's build;
#     refuses too if tmp/gpu-test.lock is held or a model server other than the 8080 queue's P028x runs
#   1 port_gap4.sh begin (the running question finishes, test lock, 8080 down)
#   2 the 9-workload screen (warm-up, W1-W3, agent x2, research4 x4), 3 passes in turned order - pass 1 B L O LO Bs Os,
#     pass 2 Os Bs LO O L B, pass 3 O B Os LO Bs L - over the arms part a allows (B and LO always; L if item L is EXACT;
#     O, Bs, Os if item O is): 18 arm-passes, ~4.3 min each; every engine's environment checked first (g17_rules.py
#     envcheck: the config's env exactly, the 14 pins, STRATA_ROUTE_TAIL_SKIP=0, the GPU count), the switch's start line
#     checked after, fatal lines, the settled PCIe share recorded, a kernel check after every arm-pass
#   3 Basalt's bp90 fixtures, cold, 3 passes: B and LO (decode, pp16k, pp64k; a fresh engine each), ~22 min
#   4 decode_rules.py decide-b -> gap-b/decision.txt (EXACT from part a + no loss + GAIN per item); port_gap4.sh end
# No new step after the deadline (R23B_MAX_MIN, default 125 min after the gap opens). A kernel-check failure stops new
# steps and leaves the gap OPEN (8080 down, exit 3: Karl decides). Exit 0 = done (outcome in decision.txt), 1 = refused
# / not opened (8080 untouched), 4 = port_gap4.sh end failed. Steps: work/r23/GAPS-README.md.
set -u -o pipefail
exec 8>&- 9>&-                     # no inherited lock descriptor (work/r22 lock-fd rule): this script holds none itself
WS=/home/USER/ai-speed-testing/strata-compare
export RB_CACHE=$WS/tmp/r23
source $WS/bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
for v in $(compgen -e | grep '^STRATA_'); do [ "$v" = STRATA_MON_GPU ] || unset "$v"; done   # no stray switch reaches an engine
export PROMPT_DIR=$WS/bringup/out/r20a/prompts EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
P=$WS/.venv/bin/python; KR=$WS/work/r22; RU=$WS/work/r23/decode_rules.py; R17=$KR/g17_rules.py; B90=$KR/basalt-pr90
D=$WS/results/r23/decode-timing; GC=$D/gate-configs
OA=$D/gap-a; O=$D/gap-b; G=$O/gates.txt; R=$O/speed; BO=$O/bp90
S=$D/gap-decode-starts.log         # until the pre-gap checks pass (then $O/summary.txt)
W=$WS/strata-r23decode; E=$WS/engine-r23decode; EXE=$E/strata
P028X_SHA=f4c4f654fb24             # engine-r22p028x/strata, served on 8080 since 10-30
MAXM=${R23B_MAX_MIN:-125}
declare -A CFG=([B]=$GC/r23-B.json [L]=$GC/r23-L.json [O]=$GC/r23-O.json [LO]=$GC/r23-LO.json [Bs]=$GC/r23-Bs.json [Os]=$GC/r23-Os.json)
declare -A NG=([B]=2 [L]=2 [O]=2 [LO]=2 [Bs]=1 [Os]=1)
declare -A WANT=([B]=none [L]=late [O]=one [LO]=late,one [Bs]=none [Os]=one)
mkdir -p $D $WS/tmp/r23
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
gate() { echo "$1 $2 ${*:3} [23b $(date '+%m-%d %H:%M')]" >> $G; say "  gate $*"; }
KFAIL=0; T0=$(date +%s); DEADLINE=$T0
kc() { $WS/bringup/lib/kcheck.sh "r23b-$1" > /dev/null || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; return 1; }; }
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
darm() {   # darm ARM PASS: one screen pass on a fresh server (gap 17's darm without the edit set; gap 18's 9 workloads)
  local a=$1 k=$2 n=$1$2 cfg=${CFG[$1]} ng=${NG[$1]} L off pc
  ok_to_go || { say "skipped screen $n (deadline or kernel check)"; return 1; }
  L=$(elog $cfg); touch $L; off=$(stat -c %s $L)
  say "screen $n ($(basename $cfg), $ng GPU(s))"
  $WS/bringup/lib/with_server.sh r23b-$n $cfg -- "$P -I -B $R17 envcheck $EXE $cfg --ngpu $ng --pins --gate env_$n --gates $G && bash $KR/abarm.sh http://127.0.0.1:8081 $off $R $n ${n}n=normal:1:W1,W2,W3 ${n}a=agent:1 ${n}r=research4:1" 8>&- 9>&- 2>&1 \
    | grep -E "engine pid [0-9]+:|ENV CHECK|tok/s|ready|exited|refus|Error|GUARD|vram" | tee -a $S
  tail -c +$((off + 1)) $L > $R/$n.engine.log      # the whole slice: the switches' lines come with their first use (the warm-up)
  fatalchk $n $L $off r23b-$n
  $P -I -B $RU lines --want ${WANT[$a]} $R/$n.engine.log $(slog r23b-$n) --gate lines_$n --gates $G | tee -a $S
  pc=$(grep -o "PCIe share[^;]*" $R/$n.engine.log 2> /dev/null | tail -1 | cut -c1-100)
  gate pcie_$n INFO "${pc:-no PCIe share line}"
  kc r23b-$n
}
bprun() {   # bprun ARM SET PASS: Basalt's community-1 set, cold (a fresh engine), one pass (gap 17's A6 form)
  local b=$1 set=$2 k=$3 n=bp$1-$2-$3 cfg=${CFG[$1]} L off
  ok_to_go || { say "skipped Basalt $n (deadline or kernel check)"; return 1; }
  L=$(elog $cfg); touch $L; off=$(stat -c %s $L)
  $WS/bringup/lib/with_server.sh r23b-$n $cfg -- "$P -I -B $R17 envcheck $EXE $cfg --ngpu 2 --pins --gate env_$n --gates $G && $P -I -B $B90/bp90_client.py http://127.0.0.1:8081 --label $n --sets $set --passes 1 --first-pass $k --tree $W --out $BO/cold-$b.jsonl" 8>&- 9>&- 2>&1 \
    | grep -E "engine pid [0-9]+:|ENV CHECK| pass |ready|exited|refus|Error|GUARD|Traceback" | tee -a $S
  fatalchk $n $L $off r23b-$n
  tail -c +$((off + 1)) $L > $BO/$n.engine.log
  $P -I -B $RU lines --want ${WANT[$b]} $BO/$n.engine.log > $BO/$n.lines.txt 2>&1   # INFO (a prompt-only run may not decode)
  kc r23b-$n
}
end_gap() {
  if [ $KFAIL = 1 ]; then say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"; exit 3; fi
  $P -I -B $RU decide-b $O --a $OA > /dev/null 2>&1 || say "decode_rules.py decide-b failed - rerun it by hand ($RU decide-b $O --a $OA)"
  [ -f $O/decision.txt ] && tee -a $S < $O/decision.txt
  say "P028x back on 8080 (port_gap4.sh end) - nothing switched"
  if ! $KR/port_gap4.sh end 8>&- 9>&- 2>&1 | tee -a $S; then
    say "port_gap4.sh end FAILED: 8080 and the research queue need a look"; exit 4
  fi
  kc end || { say "the kernel check failed after P028x came back: Karl decides"; exit 3; }
  say "decode gap b done ($(( ($(date +%s) - T0) / 60 )) min with 8080 down)"
  exit 0
}

# ================================================================ before the gap (no GPU; 8080 untouched)
say "start attempt: work/r23/gap-decode-b.sh (pre-gap checks)"
CHK=$($P -I -B $RU check-a $OA 2>&1); rc=$?
if [ $rc != 0 ]; then say "part a did not pass what part b needs - $CHK - not started (nothing touched)"; exit 1; fi
ARMS=$(echo "$CHK" | sed -n 's/^ARMS //p'); SHA_A=$(echo "$CHK" | sed -n 's/^SHA //p')
if [ ! -x $EXE ] || [ "$(sha12 $EXE)" != "$SHA_A" ] || [ "$(cut -c1-12 $E/SHA256 2> /dev/null)" != "$SHA_A" ]; then
  say "engine-r23decode is not part a's build (part a: ${SHA_A:-?}, now: $( [ -x $EXE ] && sha12 $EXE || echo none)) - not started"; exit 1
fi
preflight
[ -f $WS/tmp/r19/kwatch.pid ] && kill -0 "$(cat $WS/tmp/r19/kwatch.pid)" 2> /dev/null || { say "the kernel-log watcher is not running - not started"; exit 1; }
for a in $ARMS; do
  [ -f ${CFG[$a]} ] || { say "missing ${CFG[$a]} - not started"; exit 1; }
  [ "$(exe_of ${CFG[$a]})" = $EXE ] || { say "$(basename ${CFG[$a]})'s exe is not $EXE - not started"; exit 1; }
done
for f in $RU $R17 $KR/port_gap4.sh $KR/abarm.sh $WS/bringup/lib/with_server.sh $B90/bp90_client.py $W/serve/server.py; do
  [ -f $f ] || { say "missing $f - not started"; exit 1; }
done
PREV=""
if [ -e $O ]; then PREV=$D/gap-b-prev-$(date +%m%d-%H%M%S); mv $O $PREV; fi   # the rules judge only this attempt's files
mkdir -p $O $R $BO
S=$O/summary.txt
say "DECODE ITEMS GAP B (work/r23/gap-decode-b.sh): the 9-workload screen + Basalt's bp90 fixtures (GATE-PLAN.md 3.4, 3.5) - measurements only, P028x stays served, nothing switches (Karl 11-04)"
[ -n "$PREV" ] && say "an earlier attempt's outputs moved to $PREV"
say "part a: $(echo "$CHK" | sed -n 's/^WHY //p'); engine-r23decode $SHA_A; arms screened: $ARMS"
keep() { local x out=""; for x in $1; do case " $ARMS " in *" $x "*) out="$out $x";; esac; done; echo $out; }

# ================================================================ the gap
$KR/port_gap4.sh begin "r23 decode items gap b: the 9-workload screen + bp90 (measurements only; P028x stays served, nothing switches - Karl 11-04)" 8>&- 9>&- 2>&1 | tee -a $S
[ -s $WS/tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
echo "$T0 $(date -Is)" > $O/t0.txt
wait_mem
kc open || end_gap

# ---- 2 the screen, 3 passes in turned order (GATE-PLAN 3.4)
say "2 the 9-workload screen, 3 passes in turned order: $(keep "B L O LO Bs Os") | $(keep "Os Bs LO O L B") | $(keep "O B Os LO Bs L")"
for k in 1 2 3; do
  case $k in 1) order=$(keep "B L O LO Bs Os");; 2) order=$(keep "Os Bs LO O L B");; 3) order=$(keep "O B Os LO Bs L");; esac
  for a in $order; do darm $a $k; done
done
labs=$(ls $R/*.jsonl 2> /dev/null | xargs -n1 basename 2> /dev/null | sed 's/\.jsonl$//' | grep -E '^(B|L|O|LO|Bs|Os)[123][nar]$' | sort | tr '\n' ' ')
[ -n "$labs" ] && $P /home/USER/ai-speed-testing/basalt-ab/scripts/abreport.py --dir $R $labs > $O/speed-table.md 2>&1

# ---- 3 Basalt's bp90 fixtures, cold, 3 passes, B and LO (GATE-PLAN 3.5)
say "3 Basalt's fixtures, cold, 3 passes: B and LO (decode, pp16k, pp64k)"
for k in 1 2 3; do
  case $k in 2) order="LO B";; *) order="B LO";; esac
  for b in $order; do for set in decode pp16k pp64k; do bprun $b $set $k; done; done
done
end_gap
