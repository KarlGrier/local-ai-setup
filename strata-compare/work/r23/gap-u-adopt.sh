#!/bin/bash
# gap-u-adopt.sh - Karl 11-09 (after the Basalt speed gap): "U: adopt it today. After D2 and the end of the chain, put
# STRATA_HC_UPMIX=1 into P028x's config together with the mismatch guard install, so it's one restart. Keep a dated backup
# of the config for rollback. Run the usual post-restart checks (exact7 and the short speed check) and tell me the result."
# U = STRATA_HC_UPMIX=1, upstream's opt-in switch already in P028x's engine (f4c4f654fb24). Speed gap 11-09: EXACT on P028x
# (exact7 7/7 MATCHED, long40 0 of 40 differ), pp16k +3.3 %, pp64k +4.5 %, B2 / B3 vs P PASS. Started by
# work/r23/u-adopt-after-chain.sh once the post-Phase-5 chain has ended. Config steps + checks: work/r23/u_adopt.py.
#   0 BEFORE THE GAP (no GPU, 8080 untouched) - REFUSES (nothing changed; exit 1 = busy, the waiter retries; exit 6 = a
#     hard refusal, an alert) unless: the chain unit has ended and its
#     log says "mismatch guard installed"; u_adopt.py plan passes (the guard key in configs/P028x.json, no U yet or exactly
#     "1" from an earlier attempt, and P028x.json + U without the picture reader = x28h.json + U key by key); the engine is
#     P028x with the switch; P028x's stored exact7 x28h-e7a and this morning's P / PU bp90 files exist; no other gap, no
#     held test lock, no model server but 8080's P028x, nothing on 8081.
#   1 port_gap4.sh begin (the research queue held, the test lock, 8080 down; it waits for a running question, an active
#     Jan job and a chat being answered on 8080)
#   2 configs/P028x.json -> P028x.json.before-upmix-1109 (kept for rollback), + env STRATA_HC_UPMIX=1, nothing else
#     (checked); the test config S = the new file without the picture reader / fallback / guard key (= x28h + U, checked)
#   3 exact7 S at pin 2500 against P028x's stored x28h-e7a (7/7, slots MATCHED), the CLI engines' env checked
#   4 the short speed check, a fresh engine each, its env checked: pp16k, pp64k, decode (conv / struct / prose), 1 pass,
#     against this morning's P and PU (results/r23/basalt-prompt/gap-speed/bp90); reported, a FLAG when a prompt set is
#     more than 3 % below P
#   5 a FAIL in 2-3 (the edit, the env checks, exact7, a fatal line) -> the backup goes back (P028x as before: the guard
#     kept, no U) and a critical alert; the restart below then brings P028x back as it was
#   6 port_gap4.sh end = THE ONE RESTART: configs/P028x.json (U + the guard) on 8080, its sha and the parking policy
#     checked there
#   7 after it: the 8080 engine is f4c4f654fb24 and has STRATA_HC_UPMIX=1 in its environment (that key only); the guard
#     answers a request naming DeepSeek's model with its 400; one short chat answers; a kernel check
# -> results/r23/u-adopt/ (summary.txt, gates.txt, result.txt), a NOTES.md line, a non-urgent ntfy note (an alert on a FAIL).
# A kernel-check failure inside the gap, or a failed restore, leaves it OPEN (8080 down) for Karl. Exit 0 adopted, 1 busy
# (refused, retried), 2 rolled back (P028x as before), 3 gap left open, 4 port_gap4.sh end failed, 5 served checks failed
# after the restart, 6 hard refusal (nothing changed, alert), 7 stopped by a signal (U restored if it had gone in).
# Review 11-09 (one fresh reviewer): failed restore never restarts; env gates must PASS; refusals alert; kernel pre-check;
# FAIL-WRITTEN restores; plan checks the backup and the guard text; a signal trap; per-attempt labels.
set -u -o pipefail
exec 8>&- 9>&-     # no inherited lock descriptor reaches a child (this script holds none itself)
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
for v in $(compgen -e | grep '^STRATA_'); do [ "$v" = STRATA_MON_GPU ] || unset "$v"; done   # no stray switch reaches an engine
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r23 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
P=$WS/.venv/bin/python; UA=$WS/work/r23/u_adopt.py; FR=$WS/work/r23/basalt_fix_rules.py; KR=$WS/work/r22
LIB=$WS/bringup/lib; B90=$KR/basalt-pr90
O=$WS/results/r23/u-adopt; S=$O/summary.txt; G=$O/gates.txt; BO=$O/bp90; EL=$O/englog; FG=$O/foreign
CFG=$WS/configs/P028x.json; BAK=$WS/configs/P028x.json.before-upmix-1109; X28=$WS/configs/x28h.json; SC=$O/S.json
MORNING=$WS/results/r23/basalt-prompt/gap-speed/bp90
W28=$WS/strata-r22p028x; E28=$WS/engine-r22p028x; E7REF=x28h-e7a; PROF=$WS/bringup/out/logs/prof
LOCKPID=$WS/tmp/port-gap.lockpid; HOLD=/home/USER/ai/deep-research/tmp/bench2.hold
CHAINLOG=$WS/results/r23/post-p5-chain.log
NOTE=$WS/configs/usability/bin/ntfy-note.py
P028X_SHA=f4c4f654fb24
MAXM=${UA_MAX_MIN:-45}
LP=r23ua$(date +%m%d%H%M)
PREV=""; if [ -n "$(ls -A $O/bp90 $O/englog 2> /dev/null)" ]; then PREV=$O-prev-$(date +%m%d-%H%M%S); mv $O $PREV; fi   # judge only this attempt
mkdir -p $O $BO $EL $FG $WS/logs $WS/tmp/r23
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
gate() { echo "$1 $2 ${*:3} [23ua $(date '+%m-%d %H:%M')]" >> $G; say "  gate $*"; }
gst() { grep "^$1 " $G 2> /dev/null | tail -1 | cut -d' ' -f2; }
br() { $P -I -B $FR br "$@" 8>&- 9>&- < /dev/null; }
ua() { nice -n 19 $P -I -B $UA "$@" 8>&- 9>&- < /dev/null; }
alert() { notify-send -a Strata -u critical "$1" "$2" 2> /dev/null || true; }
note() { $NOTE "$1" "$2" >> $S 2>&1 8>&- 9>&- < /dev/null || say "(the ntfy note did not go out)"; }
KFAIL=0; T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
kc() { $LIB/kcheck.sh "r23ua-$1" > /dev/null 8>&- 9>&- < /dev/null || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; return 1; }; }
left() { echo $(( DEADLINE - $(date +%s) )); }
ok_to_go() { [ $KFAIL = 0 ] && [ $(left) -gt 0 ]; }
fits() { ok_to_go && [ $(left) -ge $(( $1 * 60 )) ]; }
sha12() { sha256sum "$1" | cut -c1-12; }
elog() { $P -I -c "import json, sys; print(json.load(open(sys.argv[1]))['log'])" "$1"; }
exe_of() { $P -I -c "import json, sys; print(json.load(open(sys.argv[1]))['exe'])" "$1"; }
slog() { ls -t $WS/bringup/out/logs/server_$1_*.log 2> /dev/null | head -1; }
ppid_of() { local s; s=$(cat /proc/$1/stat 2> /dev/null) || return 0; s=${s##*) }; set -- $s; echo "${2:-}"; }
memav() { awk '/^MemAvailable/ {printf "%d", $2 / 1048576}' /proc/meminfo; }
engines_left() { local x out=""; for x in strata strata-host strata-vision strata-dsv41 llama-server ollama; do pgrep -x $x > /dev/null && out="$out $x"; done; echo $out; }
srv8080_engine() {   # the engine process under the server listening on 8080 ("" if none)
  local l p q
  l=$(ss -H -ltnp "( sport = :8080 )" 2> /dev/null | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2)
  [ -n "$l" ] || return 0
  for p in $( { pgrep -x strata-host; pgrep -x strata; } | sort -un); do
    q=$p; while [ -n "$q" ] && [ "$q" -gt 1 ] && [ "$q" != "$l" ]; do q=$(ppid_of $q); done
    [ "$q" = "$l" ] && { echo $p; return 0; }
  done
}

preflight() {   # the speed gap's rule: no measurement on the GPU lock, no other gap, no model server but 8080's P028x
  local l p q apps bad=""
  if [ -s $LOCKPID ] && kill -0 "$(cat $LOCKPID)" 2> /dev/null; then
    refuse busy "another gap holds the test lock (tmp/port-gap.lockpid $(cat $LOCKPID))"
  fi
  if ! flock -n -x $WS/tmp/gpu-test.lock true 2> /dev/null; then
    refuse busy "tmp/gpu-test.lock is held (a measurement or a test server)"
  fi
  l=$(ss -H -ltnp "( sport = :8080 )" 2> /dev/null | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2)
  apps=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2> /dev/null) || refuse busy "nvidia-smi did not answer"
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
  [ -z "$bad" ] || refuse busy "a model server other than the 8080 queue's P028x is running:$bad"
}
fatalchk() {   # fatalchk GATE ENGINE_LOG OFFSET LABEL
  local L=$2 off=$3 sl hits
  sl=$(slog $4)
  hits=$( { tail -c +$((off + 1)) $L 2> /dev/null; [ -n "$sl" ] && cat $sl; } | grep -c -E "fatal GPU error|no progress for [0-9]+ s during a request|the engine had stopped \(exit code|became non-finite")
  [ "$hits" = 0 ] || gate $1 FAIL "$hits line(s): fatal GPU error / stall / engine restart / non-finite ($L from byte $off; $sl)"
}
foreign() {   # GPU users that are not this gap's engine: an engine process (exact names) or an NVIDIA compute process
  # holding >= 512 MiB (or an unknown amount) whose binary is not in engine-r22p028x/
  local p m x ex c
  { for x in strata strata-host strata-vision strata-dsv41 llama-server ollama; do pgrep -x $x | sed 's/$/,engine/'; done
    nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits 2> /dev/null; } | tr -d ' ' \
  | while IFS=, read -r p m; do
      [[ $p =~ ^[0-9]+$ ]] && [ -e /proc/$p ] || continue
      [[ $m =~ ^[0-9]+$ ]] && [ $m -lt 512 ] && continue
      ex=$(readlink /proc/$p/exe 2> /dev/null) || ex=""; c=$(cat /proc/$p/comm 2> /dev/null)
      case $c in strata-dsv41|llama-server|ollama) ;; *) [ -n "$ex" ] || continue
        case $ex in $E28/*) continue;; esac;; esac
      echo "pid $p ($c, ${ex:-?}, $m$([[ $m =~ ^[0-9]+$ ]] && echo ' MiB'))"
    done | sort -u
}
gwatch() { while [ -e $1 ] && kill -0 $$ 2> /dev/null; do foreign | sed "s/^/$(date +%T) /" >> $2; sleep 5; done; }
gpu_clear() {
  local i f
  for i in $(seq 12); do f=$(foreign); [ -z "$f" ] && return 0; sleep 5; done
  gate foreign_$1 FAIL "not started: $(echo "$f" | head -1) still on the GPU after 60 s"
  return 1
}
WGP=""
wstart() { rm -f $FG/$1.foreign; touch $FG/$1.watching; gwatch $FG/$1.watching $FG/$1.foreign 8>&- 9>&- < /dev/null & WGP=$!; }
wstop() {
  rm -f $FG/$1.watching; [ -n "$WGP" ] && wait $WGP 2> /dev/null; WGP=""
  [ -s $FG/$1.foreign ] && gate foreign_$1 FAIL "seen during $1 ($(wc -l < $FG/$1.foreign) sample(s)): $(head -1 $FG/$1.foreign | cut -c1-160)"
  return 0
}
bprun() {   # bprun SET: one fresh test server from S, its env checked, Basalt's fixture SET, 1 pass -> bp90/S-SET-1.jsonl
  local set=$1 lab=$LP-S-$1 out=$BO/S-$1-1.jsonl L off exe
  fits 4 || { say "skipped $set (under 4 min to the deadline, or a kernel check failed)"; return 0; }
  gpu_clear S_$set || { say "$lab NOT started (a foreign GPU user)"; return 0; }
  exe=$(exe_of $SC); L=$(elog $SC); touch $L; off=$(stat -c %s $L)
  say "server $lab (S.json)"
  wstart S_$set
  $LIB/with_server.sh $lab $SC -- "$P -I -B $FR br envcheck $exe $SC --gate env_S_$set --gates $G && $P -I -B $B90/bp90_client.py http://127.0.0.1:8081 --label $lab --sets $set --passes 1 --first-pass 1 --tree $W28 --out $out" 8>&- 9>&- < /dev/null 2>&1 \
    | grep -E "engine pid [0-9]+:|ENV CHECK| pass |tok/s|ready|exited|refus|Error|GUARD|Traceback" | tee -a $S
  wstop S_$set
  tail -c +$((off + 1)) $L > $EL/$lab.englog
  fatalchk fatal_S_$set $L $off $lab
  if [ "$(gst foreign_S_$set)" = FAIL ]; then mkdir -p $BO/void; [ -e $out ] && mv $out $BO/void/; fi
  kc $lab
  return 0
}
e7() {   # exact7 S at pin 2500 against the stored x28h-e7a, every item's engine env checked
  local jp
  fits 6 || { say "skipped exact7 (under 6 min to the deadline, or a kernel check failed)"; return 1; }
  say "exact7 $LP-S (S.json against $E7REF, pin 2500)"
  ( PIN_CACHE=2500 REF=$E7REF $LIB/exact7.sh $LP-S $SC 2>&1 | tail -9 | tee -a $S ) 8>&- 9>&- < /dev/null &
  jp=$!
  br envcli $(exe_of $SC) $SC --job $jp --mode e7 --kill --gate env_S_e7 --gates $G 2>&1 | tee -a $S
  wait $jp
  br e7gate $S $LP-S --gate e7_S --gates $G | tee -a $S
  kc e7-$LP-S
}
EDITED=0; ROLLED=0; RESTARTING=0
cfgstate() {   # what configs/P028x.json is now, for the result lines
  if [ -e $BAK ] && cmp -s $CFG $BAK; then echo "configs/P028x.json = its backup (the guard, no U)"
  elif [ $EDITED = 1 ]; then echo "configs/P028x.json STILL HAS U (not restored)"
  else echo "configs/P028x.json not changed"; fi
}
served_u() {   # yes / no / none: STRATA_HC_UPMIX=1 in the 8080 engine's environment (that key only)
  local ep; ep=$(srv8080_engine); [ -n "$ep" ] || { echo none; return 0; }
  tr '\0' '\n' < /proc/$ep/environ 2> /dev/null | grep -qx 'STRATA_HC_UPMIX=1' && echo yes || echo no
}
refuse() {   # refuse busy|hard WHY - before the gap, nothing changed. busy: exit 1 (the waiter retries); hard: an alert, exit 6
  echo "not started ($1): $2 - nothing changed" > $O/result.txt
  say "NOT STARTED ($1): $2 - nothing changed"
  if [ "$1" = hard ]; then
    printf -- '- %s U ADOPTION not started: %s - nothing changed (work/r23/gap-u-adopt.sh)\n' "$(date '+%m-%d %H:%M')" "$2" >> $WS/NOTES.md
    alert "U adoption not started" "$(echo "$2" | cut -c1-120); nothing changed"; exit 6
  fi
  exit 1
}
on_signal() {   # the driver stopped from outside (unit stop, shutdown): the backup back if U is in and no restart began
  trap - TERM INT HUP
  say "SIGNAL: the driver was stopped"
  [ $EDITED = 1 ] && [ $RESTARTING = 0 ] && [ $ROLLED = 0 ] && rollback "the driver was stopped"
  echo "INTERRUPTED: $(cfgstate); the gap may still be open (tmp/port-gap.lockpid)" > $O/result.txt
  printf -- '- %s U ADOPTION INTERRUPTED: %s; the gap may still be open\n' "$(date '+%m-%d %H:%M')" "$(cfgstate)" >> $WS/NOTES.md
  alert "U adoption interrupted" "the driver was stopped; the gap may still be open; the config was restored if U had gone in"
  exit 7
}
rollback() {   # $1 = why: the backup back, before the restart (only once the edit has run)
  [ $EDITED = 1 ] || { say "no rollback needed ($1): configs/P028x.json was not changed"; ROLLED=1; return 0; }
  say "ROLLBACK ($1): configs/P028x.json back to its backup"
  if ua restore $CFG $BAK | tee -a $S | grep -q '^restored'; then ROLLED=1
  else say "THE RESTORE FAILED - configs/P028x.json needs a look before 8080 starts"; ROLLED=9; fi
}
finish() {   # $1 = the result line, $2 = exit code
  echo "$1" > $O/result.txt
  say "RESULT: $1"
  printf -- '- %s U ADOPTION (Karl 11-09; work/r23/gap-u-adopt.sh, results/r23/u-adopt/): %s\n' "$(date '+%m-%d %H:%M')" "$1" >> $WS/NOTES.md
  exit $2
}

# ================================================================ 0 before the gap (no GPU; 8080 untouched)
: > $G
[ -n "$PREV" ] && say "an earlier attempt's outputs moved to $PREV"
say "U ADOPTION GAP (work/r23/gap-u-adopt.sh, Karl 11-09): STRATA_HC_UPMIX=1 into configs/P028x.json with the mismatch guard, one restart; exact7 + the short speed check"
if systemctl --user is-active -q post-p5-chain 2> /dev/null; then refuse busy "the post-Phase-5 chain is still running"; fi
grep -qF 'post-p5-chain: mismatch guard installed' $CHAINLOG 2> /dev/null || refuse hard "the chain log has no 'mismatch guard installed'"
PL=$(ua plan $CFG $X28 $BAK); say "  $PL"
case $PL in "PLAN OK:"*) ;; *) refuse hard "the config check: $PL";; esac
SRVPY=$($P -I -c "import json, sys; print(json.load(open(sys.argv[1]))['server'])" $CFG)
grep -q 'model_not_running' "$SRVPY" 2> /dev/null || refuse hard "the served server ($SRVPY) has no model_not_running code"
for f in $UA $FR $WS/work/r23/basalt_rules.py $LIB/with_server.sh $LIB/exact7.sh $LIB/kcheck.sh $B90/bp90_client.py \
         $KR/port_gap4.sh $NOTE $W28/serve/server.py; do
  [ -e $f ] || refuse hard "missing: $f"
done
[ "$(ls $PROF/$E7REF-*.out 2> /dev/null | wc -l)" = 7 ] || refuse hard "P028x's stored exact7 $E7REF is incomplete"
for a in P PU; do for st in pp16k-1 pp16k-2 pp16k-3 pp64k-1 pp64k-2 pp64k-3 decode-1; do
  [ -s $MORNING/$a-$st.jsonl ] || refuse hard "this morning's $a-$st.jsonl is missing"
done; done
[ -x $E28/strata ] && [ "$(sha12 $E28/strata)" = $P028X_SHA ] || refuse hard "engine-r22p028x is not P028x ($P028X_SHA)"
$P -I -c "import sys; sys.exit(0 if b'STRATA_HC_UPMIX\0' in open(sys.argv[1], 'rb').read() else 1)" $E28/strata \
  || refuse hard "engine-r22p028x has no STRATA_HC_UPMIX"
free=$(df --output=avail -B1G $WS/results | tail -1 | tr -d ' ')
[ "${free:-0}" -ge 5 ] || refuse hard "only ${free} GB free on results/"
ST=$O/selftest-$(date +%m%d%H%M%S)
ua selftest $ST > $ST.out 2>&1 || refuse hard "u_adopt.py selftest failed ($(tail -1 $ST.out))"
say "  u_adopt.py selftest: $(tail -1 $ST.out)"; rm -rf $ST $ST.out
preflight
[ -f $WS/tmp/r19/kwatch.pid ] && kill -0 "$(cat $WS/tmp/r19/kwatch.pid)" 2> /dev/null || refuse hard "the kernel-log watcher is not running"
$LIB/kcheck.sh r23ua-pre > /dev/null 8>&- 9>&- < /dev/null || refuse hard "a kernel check fails before the gap"
trap on_signal TERM INT HUP

# ================================================================ 1 the gap
$KR/port_gap4.sh begin "U adoption: STRATA_HC_UPMIX=1 into P028x's config with the mismatch guard (Karl 11-09), exact7 + a short speed check, then one restart" 8>&- 9>&- < /dev/null 2>&1 | tee -a $S
[ -s $LOCKPID ] && kill -0 "$(cat $LOCKPID)" 2> /dev/null || { rm -f $HOLD; refuse busy "the gap did not open (hold removed)"; }
T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
for i in $(seq 60); do [ -z "$(engines_left)" ] && [ "$(memav)" -ge 40 ] && break; sleep 2; done
say "8080 down: engines left:$(engines_left | sed 's/^/ /;s/^ $/ none/') MemAvailable $(memav) GB"
end_gap() {   # port_gap4.sh end = the one restart (configs/P028x.json as it now is); never with a failed restore
  if [ $KFAIL = 1 ]; then
    [ $ROLLED = 0 ] && rollback "a kernel check failed"
    say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"
    alert "U adoption: gap left open" "a kernel check failed inside the gap; 8080 is down"
    finish "kernel check FAILED inside the gap - the gap is left OPEN (8080 down); $(cfgstate)" 3
  fi
  if [ $ROLLED = 9 ]; then
    say "the gap stays OPEN (8080 down): the restore failed after a failed check - Karl decides"
    alert "U adoption: gap left open" "the config restore failed after a failed check; 8080 stays down until the config is fixed"
    finish "restore FAILED after a failed check - the gap is left OPEN (8080 down); $(cfgstate); backup configs/P028x.json.before-upmix-1109" 3
  fi
  RESTARTING=1
  say "6 port_gap4.sh end: 8080 restarts on configs/P028x.json ($([ $ROLLED = 0 ] && echo 'U + the guard' || echo 'the backup: the guard, no U'))"
  if ! $KR/port_gap4.sh end 8>&- 9>&- < /dev/null 2>&1 | tee -a $S; then
    say "port_gap4.sh end FAILED: 8080 and the research queue need a look"
    alert "U adoption: 8080 not back" "port_gap4 end failed after the U adoption gap; 8080 and the research queue need a look"
    finish "port_gap4.sh end FAILED - 8080 and the research queue need a look" 4
  fi
}
kc open || end_gap
[ -z "$(engines_left)" ] || { say "engine processes still running 120 s after 8080 stopped: $(engines_left) - nothing changed"; ROLLED=1; end_gap; finish "not adopted: engines still running after 8080 stopped (nothing changed)" 2; }

# ---- 2 the config
say "2 the config: backup $(basename $BAK), + env STRATA_HC_UPMIX=1"
ED=$(ua edit $CFG $BAK); say "  $ED"
case $ED in edited:*|already:*) EDITED=1; gate edit PASS "$ED";; FAIL-WRITTEN:*) EDITED=1; gate edit FAIL "$ED";; *) gate edit FAIL "$ED";; esac
if [ "$(gst edit)" = PASS ]; then
  DV=$(ua derive $CFG $X28 $SC $WS/logs/engine-r23ua-S.log); say "  $DV"
  case $DV in *": OK") gate derive PASS "$DV";; *) gate derive FAIL "$DV";; esac
fi
if [ "$(gst edit)" != PASS ] || [ "$(gst derive)" != PASS ]; then
  rollback "the config step: edit $(gst edit), derive $(gst derive)"
  end_gap; finish "not adopted: the config step failed ($(gst edit) / $(gst derive)); $(cfgstate); served engine has U: $(served_u)" 2
fi

# ---- 3 exact7
say "3 exact7 S (P028x.json + U, without the picture reader) at pin 2500 against P028x's stored $E7REF"
e7
if [ "$(gst e7_S)" != PASS ] || [ "$(gst env_S_e7)" != PASS ]; then
  E7G=$(gst e7_S); E7E=$(gst env_S_e7); rollback "exact7 ${E7G:-missing}, env ${E7E:-missing}"
  alert "U adoption rolled back" "exact7 did not pass (7/7 matched wanted); P028x restarts as before, without U"
  end_gap; finish "ROLLED BACK: exact7 ${E7G:-?} (env ${E7E:-?}); $(cfgstate); served engine has U: $(served_u)" 2
fi

# ---- 4 the short speed check
say "4 the short speed check (a fresh engine each, 1 pass): pp16k, pp64k, decode"
for set in pp16k pp64k decode; do [ $KFAIL = 1 ] && break; bprun $set; done
NUP=0; BADS=""   # a start blocked or spoiled by a foreign GPU user is left out; every other start must pass its env check
for set in pp16k pp64k decode; do
  [ "$(gst foreign_S_$set)" = FAIL ] && { say "  $set: left out (a foreign GPU user)"; continue; }
  if [ "$(gst env_S_$set)" = PASS ] && [ "$(gst fatal_S_$set)" != FAIL ]; then NUP=$((NUP + 1))
  else e=$(gst env_S_$set); f=$(gst fatal_S_$set); BADS="$BADS $set(env ${e:-missing}, fatal ${f:-ok})"; fi
done
if [ -n "$BADS" ] || [ $NUP = 0 ]; then
  WHY=${BADS:+ failed:$BADS}; [ $NUP = 0 ] && WHY="$WHY; no speed-check server came up with its env checked"
  rollback "the speed check$WHY"
  alert "U adoption rolled back" "a speed-check server did not come up or failed its env or fatal-line check; P028x restarts as before, without U"
  end_gap; finish "ROLLED BACK: the speed check$WHY; $(cfgstate); served engine has U: $(served_u)" 2
fi
SP=$(ua speed $BO $MORNING); echo "$SP" | sed 's/^/  /' | tee -a $S
end_gap

# ---- 7 after the restart
say "7 after the restart: the served engine, the guard, one chat"
EP=$(srv8080_engine)
SHA=$([ -n "$EP" ] && sha12 /proc/$EP/exe 2> /dev/null)
HAS_U=$([ -n "$EP" ] && tr '\0' '\n' < /proc/$EP/environ 2> /dev/null | grep -cx 'STRATA_HC_UPMIX=1')
say "  8080 engine pid ${EP:-none}: sha ${SHA:-?} (want $P028X_SHA), STRATA_HC_UPMIX=1 in its environment: $([ "${HAS_U:-0}" -ge 1 ] && echo yes || echo NO)"
MODEL=$($P -I -c "import json, sys; print(json.load(open(sys.argv[1]))['model_name'])" $CFG)
SV=$(ua served http://127.0.0.1:8080 "$MODEL"); SVRC=$?
echo "$SV" | sed 's/^/  /' | tee -a $S
kc served
ENVS=$(br envcheck $E28/strata $CFG --gate env_served --gates $G 2>&1 | tail -1); say "  (info) the served engine's env against configs/P028x.json: $ENVS"
SPL=$(echo "$SP" | grep -E '^pp16k|^pp64k' | sed -E 's/ tok\/s//; s/; vs this morning.s /, /g' | tr '\n' ';' | sed 's/;$//')
if [ "$SHA" != $P028X_SHA ] || [ "${HAS_U:-0}" -lt 1 ] || [ $SVRC != 0 ] || [ $KFAIL = 1 ]; then
  alert "U adoption: check after restart" "the served checks after the restart did not all pass; see the U adoption summary"
  finish "U set and 8080 restarted, but the served checks did not all pass (sha ${SHA:-?}, U in env ${HAS_U:-0}, guard/chat rc $SVRC, kernel $([ $KFAIL = 1 ] && echo FAIL || echo ok)); rollback: cp configs/P028x.json.before-upmix-1109 configs/P028x.json + a restart" 5
fi
RES="ADOPTED: 8080 = P028x + STRATA_HC_UPMIX=1 + the mismatch guard (one restart). exact7 7/7 MATCHED vs x28h-e7a; speed (1 pass): $SPL; $(echo "$SP" | tail -1); guard 400 + chat PASS. Rollback: configs/P028x.json.before-upmix-1109"
note "U adopted on 8080" "P028x now runs with the HC upmix switch and the model guard, after one restart. exact7 7 of 7 matched. $(echo "$SP" | tail -1 | cut -c1-80). Rollback backup kept."
finish "$RES" 0
