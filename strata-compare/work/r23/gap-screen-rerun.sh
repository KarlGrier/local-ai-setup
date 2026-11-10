#!/bin/bash
# gap-screen-rerun.sh - r23 (11-05): decode gap b's 9-workload-screen arm-passes that a DeepSeek engine killed at start,
# rerun; then decode part b decided from the merged data. WRITTEN 11-05, NOT RUN. Measurements only: P028x stays served,
# nothing switches, nothing is built. Run: `bash work/r23/gap-screen-rerun.sh` (no arguments; every path absolute).
# 11-05 ~06:50:33 a DeepSeek engine (strata-dsv41, pid 1135004, 15.0 GiB on the 5080) started inside gap b: pass 3's last
# three arm-passes LO3 (06:50:34), Bs3 (06:50:39) and L3 (06:50:42) died with "cudaMalloc ... out of memory ... other
# programs on it: strata-dsv41" (gap-b/speed/*.engine.log), so gap-b/decision.txt has L, LO and Bs at 2 of 3 clean
# passes (items L, O, L+O NOT DECIDED). Rules (written before any run): work/r23/screen_rerun_rules.py's docstring.
#   0 before the gap (no GPU, 8080 untouched) - REFUSES (exit 1) on: decode_rules.py check-a (gap b's own pre-check),
#     engine-r23decode not part a's build, tmp/gpu-test.lock held, another gap's lock, a model server other than the
#     8080 queue's P028x, a listener on 8081, no kernel watcher, a missing file / config, or nothing to rerun
#     (screen_rerun_rules.py missing: gap b's uncounted arm-passes WITH both collision lines in their engine log - LO3,
#     Bs3, L3 at writing; R23S_ONLY="LO3 L3" limits the list)
#   1 port_gap4.sh begin (the running question finishes, test lock, 8080 down); wait for the memory; a kernel check
#   2 the rerun in the original pass's positions (pass 3 "O B Os LO Bs L" -> LO Bs L): gap b's darm unchanged
#     (with_server.sh + abarm.sh: warm-up, W1-W3, agent x2, research4 x4; g17_rules.py envcheck --pins --ngpu; the
#     switch's start line(s); fatal lines; the PCIe share, INFO; a kernel check) + NEW: no foreign GPU user before the
#     arm (an engine process by exact name, or a compute process >= 512 MiB, whose binary is not in engine-r23decode/;
#     waits 60 s, else the arm is not started) and none during it (every 5 s; one seen = foreign_N FAIL = the arm-pass
#     is VOID, never merged). An arm starts only if 5 min remain before the deadline (~3.7 min each in gap b)
#   3 port_gap4.sh end (P028x back) + a kernel check; after the gap (CPU, nice 19): screen_rerun_rules.py final = the
#     decode-path gap's merge-b unchanged (gap b + its bp90 rerun in results/r23/decpath/bp90-rerun, if it ran) + this
#     gap's arm-passes, then decode_rules.py decide-b unchanged -> screen-rerun/decision-b-final.txt (gap b untouched)
# No new step after the deadline (R23S_MAX_MIN, default 25 min after the gap opens). A kernel-check failure stops new
# steps and leaves the gap OPEN (8080 down, exit 3: Karl decides). Exit 0 = done (outcome in decision-b-final.txt),
# 1 = refused / not opened (8080 untouched), 3 = kernel check failed, 4 = port_gap4.sh end failed. Steps:
# work/r23/GAPS-README.md (9).
set -u -o pipefail
exec 8>&- 9>&-                     # no inherited lock descriptor (work/r22 lock-fd rule): this script holds none itself
WS=/home/USER/ai-speed-testing/strata-compare
export RB_CACHE=$WS/tmp/r23
source $WS/bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
for v in $(compgen -e | grep '^STRATA_'); do [ "$v" = STRATA_MON_GPU ] || unset "$v"; done   # no stray switch reaches an engine
export PROMPT_DIR=$WS/bringup/out/r20a/prompts EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
P=$WS/.venv/bin/python; KR=$WS/work/r22; LIB=$WS/bringup/lib
DR=$WS/work/r23/decode_rules.py; RU=$WS/work/r23/screen_rerun_rules.py; R17=$KR/g17_rules.py
D=$WS/results/r23/decode-timing; GC=$D/gate-configs; GA=$D/gap-a; GB=$D/gap-b
O=$D/screen-rerun; G=$O/gates.txt; R=$O/speed
S=$O/starts.log                    # until the pre-gap checks pass (then $O/summary.txt)
W=$WS/strata-r23decode; E=$WS/engine-r23decode; EXE=$E/strata
P028X_SHA=f4c4f654fb24             # engine-r22p028x/strata, served on 8080 since 10-30
MAXM=${R23S_MAX_MIN:-25}; ONLY=${R23S_ONLY:-}
declare -A CFG=([B]=$GC/r23-B.json [L]=$GC/r23-L.json [O]=$GC/r23-O.json [LO]=$GC/r23-LO.json [Bs]=$GC/r23-Bs.json [Os]=$GC/r23-Os.json)
declare -A NG=([B]=2 [L]=2 [O]=2 [LO]=2 [Bs]=1 [Os]=1)
declare -A WANT=([B]=none [L]=late [O]=one [LO]=late,one [Bs]=none [Os]=one)
mkdir -p $O $WS/tmp/r23
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
gate() { echo "$1 $2 ${*:3} [23sr $(date '+%m-%d %H:%M')]" >> $G; say "  gate $*"; }
KFAIL=0; T0=$(date +%s); DEADLINE=$T0
kc() { $LIB/kcheck.sh "r23sr-$1" > /dev/null 8>&- 9>&- || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; return 1; }; }
left() { echo $(( DEADLINE - $(date +%s) )); }
ok_to_go() { [ $KFAIL = 0 ] && [ $(left) -gt 0 ]; }
fits() { ok_to_go && [ $(left) -ge $(( $1 * 60 )) ]; }   # an arm starts only if it ends before the deadline
sha12() { sha256sum "$1" | cut -c1-12; }
elog() { $P -I -c "import json, sys; print(json.load(open(sys.argv[1]))['log'])" "$1"; }
exe_of() { $P -I -c "import json, sys; print(json.load(open(sys.argv[1]))['exe'])" "$1"; }
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
foreign() {   # the GPU users that are not engine-r23decode's: an engine process (exact names) or an NVIDIA compute process
  # holding >= 512 MiB (or an unknown amount) whose binary is not in engine-r23decode/ - one line each. strata-dsv41 /
  # llama-server / ollama count by name; any other process only with a readable binary (an exiting engine has none)
  local p m x ex c
  { for x in strata strata-host strata-vision strata-dsv41 llama-server ollama; do pgrep -x $x | sed 's/$/,engine/'; done
    nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits 2> /dev/null; } | tr -d ' ' \
  | while IFS=, read -r p m; do
      [[ $p =~ ^[0-9]+$ ]] && [ -e /proc/$p ] || continue
      [[ $m =~ ^[0-9]+$ ]] && [ $m -lt 512 ] && continue
      ex=$(readlink /proc/$p/exe 2> /dev/null) || ex=""; c=$(cat /proc/$p/comm 2> /dev/null)
      case $c in strata-dsv41|llama-server|ollama) ;; *) [ -n "$ex" ] || continue; case $ex in $E/*) continue;; esac;; esac
      echo "pid $p ($c, ${ex:-?}, $m$([[ $m =~ ^[0-9]+$ ]] && echo ' MiB'))"
    done | sort -u
}
gwatch() {   # gwatch FLAG OUT: while FLAG exists (and this driver runs), every 5 s: foreign GPU users >> OUT
  while [ -e $1 ] && kill -0 $$ 2> /dev/null; do foreign | sed "s/^/$(date +%T) /" >> $2; sleep 5; done
}
gpu_clear() {   # gpu_clear NAME: no foreign GPU user before the arm (up to 60 s); else foreign_NAME FAIL, not started
  local i f
  for i in $(seq 12); do f=$(foreign); [ -z "$f" ] && return 0; sleep 5; done
  gate foreign_$1 FAIL "not started: $(echo "$f" | head -1) still on the GPU after 60 s"
  return 1
}
darm() {   # darm ARM PASS: gap b's darm (one screen pass on a fresh server) + the foreign-GPU-user checks
  local a=$1 k=$2 n=$1$2 cfg=${CFG[$1]} ng=${NG[$1]} L off pc gw
  fits 5 || { say "skipped screen $n (under 5 min to the deadline, or a kernel check failed)"; return 1; }
  gpu_clear $n || { say "screen $n NOT started (a foreign GPU user)"; return 1; }
  L=$(elog $cfg); touch $L; off=$(stat -c %s $L)
  say "screen $n ($(basename $cfg), $ng GPU(s))"
  rm -f $O/$n.foreign; touch $O/$n.watching
  gwatch $O/$n.watching $O/$n.foreign 8>&- 9>&- &
  gw=$!
  $LIB/with_server.sh r23sr-$n $cfg -- "$P -I -B $R17 envcheck $EXE $cfg --ngpu $ng --pins --gate env_$n --gates $G && bash $KR/abarm.sh http://127.0.0.1:8081 $off $R $n ${n}n=normal:1:W1,W2,W3 ${n}a=agent:1 ${n}r=research4:1" 8>&- 9>&- 2>&1 \
    | grep -E "engine pid [0-9]+:|ENV CHECK|tok/s|ready|exited|refus|Error|GUARD|vram" | tee -a $S
  rm -f $O/$n.watching; wait $gw 2> /dev/null
  tail -c +$((off + 1)) $L > $R/$n.engine.log      # the whole slice: the switches' lines come with their first use (the warm-up)
  fatalchk $n $L $off r23sr-$n
  $P -I -B $DR lines --want ${WANT[$a]} $R/$n.engine.log $(slog r23sr-$n) --gate lines_$n --gates $G | tee -a $S
  pc=$(grep -o "PCIe share[^;]*" $R/$n.engine.log 2> /dev/null | tail -1 | cut -c1-100)
  gate pcie_$n INFO "${pc:-no PCIe share line}"
  [ -s $O/$n.foreign ] && gate foreign_$n FAIL "seen during the arm ($(wc -l < $O/$n.foreign) sample(s)): $(head -1 $O/$n.foreign | cut -c1-160) - VOID, not merged"
  kc $n
}
after_gap() {   # CPU only, nice 19, 8080 back: this gap's speed table, the merge + decode_rules.py decide-b
  local labs
  labs=$(ls $R/*.jsonl 2> /dev/null | xargs -n1 basename 2> /dev/null | sed 's/\.jsonl$//' | grep -E '^(B|L|O|LO|Bs|Os)[123][nar]$' | sort | tr '\n' ' ')
  [ -n "$labs" ] && nice -n 19 $P /home/USER/ai-speed-testing/basalt-ab/scripts/abreport.py --dir $R $labs > $O/speed-table.md 2>&1
  if nice -n 19 $P -I -B $RU final > $O/final.txt 2>&1 && [ -f $O/decision-b-final.txt ]; then
    sed 's/^/  /' $O/final.txt | tee -a $S
  else say "screen_rerun_rules.py final failed - by hand: $P -I -B $RU final ($(tail -1 $O/final.txt 2> /dev/null | cut -c1-200))"; fi
}
end_gap() {
  if [ $KFAIL = 1 ]; then say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"; exit 3; fi
  say "P028x back on 8080 (port_gap4.sh end) - nothing switched"
  if ! $KR/port_gap4.sh end 8>&- 9>&- 2>&1 | tee -a $S; then
    say "port_gap4.sh end FAILED: 8080 and the research queue need a look"; exit 4
  fi
  kc end || { say "the kernel check failed after P028x came back: Karl decides"; exit 3; }
  say "screen rerun gap: $(( ($(date +%s) - T0) / 60 )) min with 8080 down"
  after_gap
  say "screen rerun gap done"
  exit 0
}

# ================================================================ before the gap (no GPU; 8080 untouched)
say "start attempt: work/r23/gap-screen-rerun.sh (pre-gap checks)"
CHK=$($P -I -B $DR check-a $GA 2>&1); rc=$?
if [ $rc != 0 ]; then say "part a did not pass what part b needs - $CHK - not started (nothing touched)"; exit 1; fi
ARMS=$(echo "$CHK" | sed -n 's/^ARMS //p'); SHA_A=$(echo "$CHK" | sed -n 's/^SHA //p')
if [ ! -x $EXE ] || [ "$(sha12 $EXE)" != "$SHA_A" ] || [ "$(cut -c1-12 $E/SHA256 2> /dev/null)" != "$SHA_A" ]; then
  say "engine-r23decode is not part a's build (part a: ${SHA_A:-?}, now: $( [ -x $EXE ] && sha12 $EXE || echo none)) - not started"; exit 1
fi
preflight
[ -f $WS/tmp/r19/kwatch.pid ] && kill -0 "$(cat $WS/tmp/r19/kwatch.pid)" 2> /dev/null || { say "the kernel-log watcher is not running - not started"; exit 1; }
for f in $DR $RU $R17 $WS/work/r23/decpath_rules.py $KR/port_gap4.sh $KR/abarm.sh $LIB/with_server.sh $LIB/kcheck.sh \
         $W/serve/server.py $GB/gates.txt $GA/decision.json; do
  [ -f $f ] || { say "missing $f - not started"; exit 1; }
done
MISS=$($P -I -B $RU missing ${ONLY:+--only "$ONLY"} 2>&1) || { say "screen_rerun_rules.py missing failed: $(echo "$MISS" | tail -1 | cut -c1-300) - not started"; exit 1; }
mapfile -t ML < <(echo "$MISS" | grep '^RERUN')
[ ${#ML[@]} -gt 0 ] || { say "nothing to rerun ($(echo "$MISS" | tail -1 | cut -c1-200)) - not started"; exit 1; }
for x in "${ML[@]}"; do
  read -r _ n a k <<< "$x"
  case " $ARMS " in *" $a "*) ;; *) say "$n: arm $a is not one part a allows ($ARMS) - not started"; exit 1;; esac
  [ -f ${CFG[$a]} ] || { say "missing ${CFG[$a]} - not started"; exit 1; }
  [ "$(exe_of ${CFG[$a]})" = $EXE ] || { say "$(basename ${CFG[$a]})'s exe is not $EXE - not started"; exit 1; }
done
PREV=""
if ls -A $O | grep -v -x -E 'starts\.log|prev-.*' | grep -q .; then   # the rules judge only this attempt's files
  PREV=$O/prev-$(date +%m%d-%H%M%S); mkdir -p $PREV
  for f in $O/*; do case $(basename $f) in starts.log|prev-*) ;; *) mv $f $PREV/;; esac; done
fi
mkdir -p $R
S=$O/summary.txt
say "DECODE B SCREEN RERUN (work/r23/gap-screen-rerun.sh): gap b's arm-passes killed by the 11-05 06:50 DeepSeek start, rerun on engine-r23decode, then part b decided on the merged data - measurements only, P028x stays served, nothing switches"
[ -n "$PREV" ] && say "an earlier attempt's outputs moved to $PREV"
echo "$MISS" > $O/missing.txt
NK=$(echo "$MISS" | grep -c '^KEPT')
say "part a: $(echo "$CHK" | sed -n 's/^WHY //p'); engine-r23decode $SHA_A; to rerun: $(echo "$MISS" | grep '^RERUN' | cut -d' ' -f2 | tr '\n' ' ')$( [ $NK -gt 0 ] && echo "; $NK other(s) KEPT as gap b judged them (missing.txt)")"

# ================================================================ the gap
$KR/port_gap4.sh begin "r23 decode b screen rerun: $(echo "$MISS" | grep '^RERUN' | cut -d' ' -f2 | tr '\n' ' ')(measurements only; P028x stays served, nothing switches)" 8>&- 9>&- 2>&1 | tee -a $S
[ -s $WS/tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
echo "$T0 $(date -Is)" > $O/t0.txt
wait_mem
kc open || end_gap

say "2 the rerun in the original pass's positions: $(echo "$MISS" | grep '^RERUN' | cut -d' ' -f2 | tr '\n' ' ')(deadline $MAXM min)"
for x in "${ML[@]}"; do read -r _ n a k <<< "$x"; darm $a $k < /dev/null; done
end_gap
