#!/bin/bash
# gap-shape0213.sh - the v0.2.13 SHAPE GAP (Karl 11-09 ~14:15: "the shape gap GO, as planned (desk prep first, then the gap at
# the next clean boundary; information only)"; plan: results/r23/port-0213/NOTES-0213.md, "The shape gap"). Shows that our
# patched v0.2.13 port (branch r23-port0213) builds, passes upstream's geometry parity programs and loads + answers at
# upstream's synthetic shapes q4_mid / q4_big / q4_deep. INFORMATION ONLY: nothing switches, no config or engine of 8080
# changes, P028x stays served (8080 is down only for the gap's own minutes). Desk prep first: work/r23/shape-gap/shape_prep.sh all
# (under nogap-run) -> results/r23/port-0213/shape-gap-prep/READY.json.
#   0 BEFORE THE GAP (no GPU; 8080 untouched) - REFUSES (nothing changed; exit 1 = busy, retry later; exit 6 = a hard refusal,
#     an alert) unless: the post-Phase-5 chain is not running; the prep's READY.json verifies (the tree on r23-port0213 at the
#     prep's HEAD and clean; every synthetic file, pack file, profile, header and engine with its size and sha256; each engine's
#     SOURCE naming HEAD); the seven builds' records say "build rc 0" at HEAD and ninja -n has nothing to do in each; the
#     ctest lists exist; shape_rules.py's selftest passes; no other gap, no held test lock, no model server but 8080's
#     P028x, nothing on 8081; the kernel-log watcher runs and a kernel check passes.
#   1 port_gap4.sh begin (the research queue held after its running question, the test lock, 8080 down; it waits for a Jan
#     job / a chat being answered / a DeepSeek session / a quiet window), GAP_MAX_MIN set to this gap's length
#   2 per row: flash_next (the reference row: build-flash_next) first, then q4_mid, q4_big, q4_deep (build-<shape>); the order
#     is parity flash_next, parity + smoke q4_mid, parity + smoke q4_big, smoke q4_deep, parity q4_deep (see the loop):
#     a. THE PARITY PROGRAMS: every registered ctest entry whose program is one of build-port0213.sh's GEO_TESTS (82 per
#        q4 build: registered args and env apply, the _q2n / _nt256 / _f16 / _ws / prefill_fused_v2_test variants included),
#        `ctest --test-dir B -R '^(...)$' --timeout 300` (an entry's own TIMEOUT stays), both GPUs visible (the 5080 first);
#        then directly (no ctest entry): prefill_fused_iq_test --edge --no-timing, qsa_prompt_attn_parity, and
#        patch_guard_test (GPUs hidden) on the row's model header (flash_next: ISTA shard 1 + the MTP layer; a q4 shape: its
#        4-layer synthetic file). PASS / SKIP (77) / FAIL per test (junit + the ctest log).
#        NOT run with STRATA_GR_FORK=1 (the plan's "+ STRATA_GR_FORK=1 at q4_deep"): gr_multi_parity never reaches the fork
#        (it tests gr.hpp's gr_read_multi / gr_read, not the fused read the fork lives in), and gr_parity compares the
#        fused multi-token read bitwise against single-token fused_gr_read, which never forks - the fork's other summation
#        order would fail it by design - and passes a non-zeroed xn scratch (the fork's counters must start at 0). The fork
#        at q4_deep is covered by the smoke below (P0213x's STRATA_GR_FORK=1, the engine's own scratch).
#     b. THE SMOKE (q4 rows): a config from configs/P0213x.json (shape_rules.py cfg: engine-r23p0213-<shape>-4l, the
#        synthetic file as --native and as its own --ple-gguf (a small PLE table), its pack and neutral profile, no drafter,
#        no picture reader, no fallback, STRATA_MANIFEST; P0213x's env otherwise unchanged):
#        - a CLI probe (bringup/lib/run.sh: the p2000 prompt, 16 new tokens, STRATA_GUARD_LIST=1): the patch guard lines
#          (the server reads the engine's stdout up to READY and drops it, so a served start cannot show them) - gr_fork
#          OFF with "built for Flash-Next's 2560 / 4 / 320 only" at q4_mid / q4_big, not refused at q4_deep; prefill_v2 on
#          where kV2Shape holds (all three shapes; the experts have IQ4_NL down);
#        - one served start (bringup/lib/with_server.sh on 8081, as gap-u-adopt.sh's bprun): the engine's env against the
#          config, ONE chat request (T 1.0 / 0.95 / 20 / min-p 0.05, presence 0, 32 tokens): completion tokens and a
#          normal finish; no fatal / stall / restart / non-finite line; STRATA_MANIFEST's gdn_tc / gdn_convl2 (pinned 0 / 0);
#        - only if that start fails: one more start with --no-ple (to tell a PLE-path problem from the rest).
#     A kernel check after every part; the foreign-GPU watch around every GPU part (a step starts only on a clear GPU).
#   3 port_gap4.sh end (P028x back on 8080, its sha and the parking policy checked there; the queue resumes)
#   4 -> results/r23/port-0213/shape-gap/ (summary.txt, gates.txt, decision.txt, result.txt, parity/, smoke/), a NOTES.md
#     line, a non-urgent ntfy note.
# DEADLINE: no step starts after SG_MAX_MIN (default 55) minutes with 8080 down, a step starts only if its minimum fits, and
# every ctest / probe / server run is cut at the deadline (8080 is then down for at most ~60 min: the deadline + the end).
# Expected ~35-40 min with 8080 down (results/r22/gap5's full ctest of 153 entries took 222 s; ~5-7 min a build here, ~3
# min a smoke, ~4 min begin + end). A kernel-check failure inside the gap leaves it OPEN (8080 down) for Karl, exit 3.
# Exit 0 done (information recorded), 1 busy (refused, nothing changed), 3 gap left open (kernel check), 4 port_gap4.sh end
# failed, 6 hard refusal (alert), 7 stopped by a signal (the gap may still be open; alert).
# --dry-run: the preflight's file checks (a refusal is printed and the plan goes on) and the plan of every command, printed;
# no lock (not even a test flock), no GPU query, no kernel check, no ninja, no port_gap4; writes only under
# work/r23/shape-gap/scratch/.
set -u -o pipefail
exec 8>&- 9>&-     # no inherited lock descriptor reaches a child (this script holds none itself)
WS=/home/USER/ai-speed-testing/strata-compare
case ${1:-} in ""|--dry-run|--mock) ;; *) echo "usage: gap-shape0213.sh [--dry-run | --mock] (got '${1:-}'): nothing run"; exit 2;; esac   # (review 11-09 #3)
STEPS_ALL="parity:flash_next parity:q4_mid smoke:q4_mid parity:q4_big smoke:q4_big smoke:q4_deep parity:q4_deep"
for st in ${SG_STEPS:-}; do   # (11-09 rerun) SG_STEPS: the rows to run, in this order; any other word refuses
  case " $STEPS_ALL " in *" $st "*) ;; *) echo "SG_STEPS: unknown step '$st' (known: $STEPS_ALL): nothing run"; exit 2;; esac
done
STEPLIST=${SG_STEPS:-$STEPS_ALL}
DRY=0; [ "${1:-}" = --dry-run ] && DRY=1
MOCK=0; [ "${1:-}" = --mock ] && MOCK=1      # (work/r23/shape-gap/gap-mock-test.sh only: every tool a stub under scratch/mock)
M=$WS/work/r23/shape-gap/scratch/mock
export RB_CACHE=$WS/tmp/r23
[ $DRY = 1 ] && export RB_CACHE=$WS/work/r23/shape-gap/scratch/rb-cache
[ $MOCK = 1 ] && { [ -x $M/bin/ctest ] || { echo "--mock needs work/r23/shape-gap/gap-mock-test.sh's stubs"; exit 2; }; export RB_CACHE=$M/rb-cache; }
source $WS/bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE PROF_SAMPLING EXE ENVX NSYS COLD
for v in $(compgen -e | grep '^STRATA_'); do [ "$v" = STRATA_MON_GPU ] || unset "$v"; done   # no stray switch reaches an engine or a test
export PROMPT_DIR=$WS/bringup/out/r20a/prompts
P=$WS/.venv/bin/python; SG=$WS/work/r23/shape-gap; RULES=$SG/shape_rules.py; LIB=$WS/bringup/lib; KR=$WS/work/r22
W=$WS/strata-r23p0213; PREP=$WS/results/r23/port-0213/shape-gap-prep; READY=$PREP/READY.json; RES=$WS/results/r23/port-0213
O=$WS/results/r23/port-0213/shape-gap
[ $DRY = 1 ] && O=$SG/scratch/gap-dry
S=$O/summary.txt; G=$O/gates.txt; FG=$O/foreign
BASE=$WS/configs/P0213x.json; ISTA1=$WS/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf
MTPRT=$WS/strata-v0115/mtp/rt; MOD=$WS/models/q4geo
LOCKPID=$WS/tmp/port-gap.lockpid; HOLD=/home/USER/ai/deep-research/tmp/bench2.hold
NOTE=$WS/configs/usability/bin/ntfy-note.py
P028X_SHA=$(grep -oP '^P021_SHA=\K[0-9a-f]{12}' $KR/port_gap4.sh)       # the served engine port_gap4.sh restores and checks
MAXM=${SG_MAX_MIN:-55}; [ "$MAXM" -gt 90 ] && MAXM=90   # (review 11-09 #7: capped)
WDG=""
SHAPES="q4_mid q4_big q4_deep"; ROWS="flash_next $SHAPES"; LAYERS=4
GEO_TESTS="gguf_geometry_test patch_guard_test prefill_fused_iq_test prefill_fused_moe_test native_dense_parity native_expert_parity
  native_grouped_parity gdn_parity gr_parity gr_multi_parity qsa_parity qsa_prompt_attn_parity router_top10_parity shared_expert_parity
  verify_parity spec_verify_parity"
PAR_MIN=5; SMOKE_MIN=4; NOPLE_MIN=3; CTEST_CAP=25; PROBE_CAP=5; SERVE_CAP=15     # minutes: a step's minimum to start / its cap
LP=sg$(date +%m%d%H%M)
ENGBASE=$WS; PROF=$WS/bringup/out/logs/prof; LOGDIR=$WS/logs; STOPMON=$WS/scripts/stopmon.sh
if [ $MOCK = 1 ]; then   # every tool, folder and lock file under scratch/mock; the real configs/P0213x.json is only read
  O=$M/out; S=$O/summary.txt; G=$O/gates.txt; FG=$O/foreign; LIB=$M/lib; KR=$M/kr; W=$M/tree; PREP=$M/prep; READY=$PREP/READY.json
  RES=$M/res; MOD=$M/models; LOCKPID=$M/lockpid; HOLD=$M/hold; NOTE=$M/lib/ntfy-note.py; ENGBASE=$M/engines; PROF=$M/prof
  LOGDIR=$M/logs; STOPMON=$M/lib/stopmon.sh; export PATH=$M/bin:$PATH; MAXM=${SG_MAX_MIN:-30}; KERR=$M/kernel_error
  rm -rf $O; mkdir -p $LOGDIR
fi
[ $DRY = 0 ] && [ $MOCK = 0 ] && mkdir -p $WS/tmp/r23 $WS/logs
if [ $DRY = 0 ] && [ $MOCK = 0 ] && [ -s $O/driver.pid ] && kill -0 "$(cat $O/driver.pid)" 2> /dev/null; then   # (review 11-09 #8)
  echo "another gap-shape0213.sh (pid $(cat $O/driver.pid)) is running: not started"; exit 1
fi
PREV=""
if [ $DRY = 0 ] && [ -n "$(ls -A $O/parity $O/smoke 2> /dev/null)" ]; then PREV=$O-prev-$(date +%m%d-%H%M%S); mv $O $PREV; fi   # judge only this attempt
[ $DRY = 1 ] && rm -rf $O
mkdir -p $O $FG
if [ $DRY = 0 ]; then echo $$ > $O/driver.pid; trap 'rm -f $O/driver.pid' EXIT; fi   # cleanup-shape0213.sh refuses while this runs
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
gate() { echo "$1 $2 ${*:3} [sg0213 $(date '+%m-%d %H:%M')]" >> $G; say "  gate $*"; }
gst() { grep "^$1 " $G 2> /dev/null | tail -1 | cut -d' ' -f2; }
rules() { nice -n 19 $P -I -B $RULES "$@" 8>&- 9>&- < /dev/null; }
alert() { [ $DRY = 1 ] || [ $MOCK = 1 ] && { say "(dry run: would alert: $1 - $2)"; return 0; }; notify-send -a Strata -u critical "$1" "$2" 2> /dev/null || true; }
note() { [ $DRY = 1 ] || [ $MOCK = 1 ] && { say "(dry run: would send the ntfy note: $1 - $2)"; return 0; }; $NOTE "$1" "$2" >> $S 2>&1 8>&- 9>&- < /dev/null || say "(the ntfy note did not go out)"; }
notes_line() { [ $DRY = 1 ] || [ $MOCK = 1 ] && { say "(dry run: would add to NOTES.md: $1)"; return 0; }; printf -- '- %s SHAPE GAP 0213 (Karl 11-09; work/r23/shape-gap/gap-shape0213.sh, results/r23/port-0213/shape-gap/): %s\n' "$(date '+%m-%d %H:%M')" "$1" >> $WS/NOTES.md; }
KFAIL=0; GAPOPEN=0; T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
[ $MOCK = 1 ] || KERR=$WS/tmp/r19/KERNEL_ERROR   # kwatch's marker of a kernel error (never taken from the environment; never cleared here)
kc() { $LIB/kcheck.sh "sg0213-$1" > /dev/null 8>&- 9>&- < /dev/null || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; gate kfail FAIL "after $1"; return 1; }; }
left() { echo $(( DEADLINE - $(date +%s) )); }
ok_to_go() { [ $KFAIL = 0 ] && [ $(left) -gt 0 ]; }
fits() { ok_to_go && [ $(left) -ge $(( $1 * 60 )) ]; }
cap() { local c=$(( $1 * 60 )) l=$(( $(left) - 30 )); [ $l -lt $c ] && c=$l; [ $c -lt 60 ] && c=60; echo $c; }   # seconds for a run: its cap, cut at the deadline
sha12() { sha256sum "$1" | cut -c1-12; }
jget() { nice -n 19 $P -I -B -c "import json, sys; print(json.load(open(sys.argv[1]))$2)" "$1"; }
slog() { ls -t $WS/bringup/out/logs/server_$1_*.log 2> /dev/null | head -1; }
ppid_of() { local s; s=$(cat /proc/$1/stat 2> /dev/null) || return 0; s=${s##*) }; set -- $s; echo "${2:-}"; }
memav() { awk '/^MemAvailable/ {printf "%d", $2 / 1048576}' /proc/meminfo; }
engines_left() { [ $MOCK = 1 ] && return 0; local x out=""; for x in strata strata-host strata-vision strata-dsv41 llama-server ollama; do pgrep -x $x > /dev/null && out="$out $x"; done; echo $out; }
ours() { case "$1" in $ENGBASE/engine-r23p0213-*/*|$W/build-*/*) return 0;; esac; return 1; }   # this gap's binaries
kill_ours() {   # an engine of this gap still running after its step (exact process names; matched by its binary's path)
  local p ex n=0
  [ $MOCK = 1 ] && return 0
  for p in $( { pgrep -x strata; pgrep -x strata-host; } | sort -un); do
    ex=$(readlink /proc/$p/exe 2> /dev/null) || continue
    ours "$ex" || continue
    kill -TERM $p 2> /dev/null && n=$((n + 1))
  done
  [ $n = 0 ] && return 0
  sleep 10
  for p in $( { pgrep -x strata; pgrep -x strata-host; } | sort -un); do
    ex=$(readlink /proc/$p/exe 2> /dev/null) || continue; ours "$ex" && kill -KILL $p 2> /dev/null
  done
  say "  stopped $n engine process(es) of this gap left after its step"
}

test_cleanup() {   # review 11-09 #1: after any test-server run, however it ended - the guard and server.py (their own sessions),
  # srv.sh stop, the monitor, this gap's engines. A start cut before 8081 listened left them, and the test lock, behind.
  local lab=$1 gp c pg me sig
  if [ $MOCK = 1 ]; then PORT=8081 $LIB/srv.sh stop > /dev/null 2>&1; $STOPMON $lab > /dev/null 2>&1; return 0; fi
  me=$(ps -o pgid= -p $$ 2> /dev/null | tr -d ' ')
  gp=$(cat $WS/bringup/out/logs/srv.pid 2> /dev/null)
  if [ -n "$gp" ] && kill -0 "$gp" 2> /dev/null && tr '\0' ' ' < /proc/$gp/cmdline 2> /dev/null | grep -qF "srv-$lab"; then
    for sig in TERM KILL; do
      for c in $(pgrep -P $gp); do
        pg=$(ps -o pgid= -p $c 2> /dev/null | tr -d ' ')
        [ -n "$pg" ] && [ "$pg" != "$me" ] && kill -$sig -- -$pg 2> /dev/null; kill -$sig $c 2> /dev/null
      done
      [ $sig = TERM ] && sleep 5
    done
    kill -TERM $gp 2> /dev/null; sleep 2; kill -0 $gp 2> /dev/null && kill -KILL $gp 2> /dev/null
    say "  stopped the test server's guard ($gp) and its server, left after the run"
  fi
  PORT=8081 $LIB/srv.sh stop 8>&- 9>&- < /dev/null > /dev/null 2>&1
  $STOPMON $lab 8>&- 9>&- < /dev/null > /dev/null 2>&1
  kill_ours
}
lock_sweep() {   # review 11-09 #1 / #5: before port_gap4 end, nothing of this gap may still run or hold the test lock (strata-ensure
  # refuses while anyone holds it): this gap's programs are killed, its monitors / guards stopped, anything else is named
  local p f ex cmd lp pp bad=""
  [ $MOCK = 1 ] && return 0
  lp=$(cat $LOCKPID 2> /dev/null); pp=$(ppid_of ${lp:-0})
  for p in $(ls /proc | grep -E '^[0-9]+$'); do
    [ "$p" = $$ ] && continue
    ex=$(readlink /proc/$p/exe 2> /dev/null) || continue
    if ours "$ex"; then kill -KILL $p 2> /dev/null; bad="$bad $p(${ex##*/}: this gap's, killed)"; continue; fi
    for f in /proc/$p/fd/*; do
      [ "$(readlink $f 2> /dev/null)" = $WS/tmp/gpu-test.lock ] || continue
      { [ "$p" = "$lp" ] || [ "$p" = "$pp" ]; } && break   # the gap's own lock holder
      cmd=$(tr '\0' ' ' < /proc/$p/cmdline 2> /dev/null | cut -c1-200)
      case $cmd in *monitor-$LP-*|*srv-$LP-*) kill -TERM $p 2> /dev/null; bad="$bad $p(this gap's leftover, stopped)";;
        *) bad="$bad $p($(cat /proc/$p/comm 2> /dev/null) holds the test lock)";; esac
      break
    done
  done
  [ -n "$bad" ] && { say "  lock sweep before the end:$bad"; sleep 3; }
  return 0
}
preflight() {   # the reviewed rule (gap-u-adopt.sh): no measurement on the GPU lock, no other gap, no model server but 8080's P028x
  local l p q apps bad=""
  if [ -s $LOCKPID ] && kill -0 "$(cat $LOCKPID)" 2> /dev/null; then
    refuse busy "another gap holds the test lock (tmp/port-gap.lockpid $(cat $LOCKPID))"
  fi
  if ! flock -n -x $WS/tmp/gpu-test.lock true 2> /dev/null; then
    refuse busy "tmp/gpu-test.lock is held (a measurement or a test server)"
  fi
  l=$(ss -H -ltnp "( sport = :8080 )" 2> /dev/null | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2)
  apps=$(timeout -k 5 20 nvidia-smi --query-compute-apps=pid --format=csv,noheader 2> /dev/null) || refuse busy "nvidia-smi did not answer within 20 s"
  for p in $( { for x in strata strata-host strata-vision strata-dsv41 llama-server ollama; do pgrep -x "$x"; done; echo "$apps"; } \
              | tr -d ' ' | grep -E '^[0-9]+$' | sort -un); do
    q=$p; while [ -n "$q" ] && [ "$q" -gt 1 ] && [ "$q" != "${l:-none}" ]; do q=$(ppid_of $q); done
    if [ -n "$l" ] && [ "$q" = "$l" ]; then
      case $(cat /proc/$p/comm 2> /dev/null) in
        strata|strata-host) [ "$(sha12 /proc/$p/exe 2> /dev/null)" = "$P028X_SHA" ] || bad="$bad 8080-engine:$p($(readlink /proc/$p/exe))";;
        strata-vision) ;;
        *) bad="$bad 8080:$p($(cat /proc/$p/comm 2> /dev/null))";;
      esac
    else bad="$bad $p($(cat /proc/$p/comm 2> /dev/null))"; fi
  done
  ss -H -ltn "( sport = :8081 )" 2> /dev/null | grep -q . && bad="$bad listener-on-8081(a-test-server)"
  [ -z "$bad" ] || refuse busy "a model server other than the 8080 queue's P028x is running:$bad"
}
fatalchk() {   # fatalchk GATE LABEL FILE...: a fatal GPU error / stall / engine restart / non-finite line in the files
  local g=$1 lab=$2 hits; shift 2
  hits=$(cat "$@" 2> /dev/null | grep -c -E "fatal GPU error|no progress for [0-9]+ s during a request|the engine had stopped \(exit code|became non-finite")
  if [ "$hits" = 0 ]; then gate $g PASS "no fatal / stall / restart / non-finite line ($lab)"
  else gate $g FAIL "$hits line(s): fatal GPU error / stall / engine restart / non-finite ($lab: $*)"; fi
}
foreign() {   # GPU users that are not this gap's: an engine process (exact names) or an NVIDIA compute process holding >= 512 MiB
  # (or an unknown amount) whose binary is not one of this gap's (engine-r23p0213-*/, strata-r23p0213/build-*/)
  local p m x ex c
  [ $MOCK = 1 ] && return 0
  { for x in strata strata-host strata-vision strata-dsv41 llama-server ollama; do pgrep -x $x | sed 's/$/,engine/'; done
    timeout -k 5 20 nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits 2> /dev/null || echo 'NVSMIFAIL,0'; } | tr -d ' ' \
  | while IFS=, read -r p m; do
      [ "$p" = NVSMIFAIL ] && { echo 'nvidia-smi did not answer within 20 s (taken as: not clear)'; continue; }   # (review 11-09 #2)
      [[ $p =~ ^[0-9]+$ ]] && [ -e /proc/$p ] || continue
      [[ $m =~ ^[0-9]+$ ]] && [ $m -lt 512 ] && continue
      ex=$(readlink /proc/$p/exe 2> /dev/null) || ex=""; c=$(cat /proc/$p/comm 2> /dev/null)
      case $c in strata-dsv41|llama-server|ollama) ;; *) [ -n "$ex" ] || continue; ours "$ex" && continue;; esac
      echo "pid $p ($c, ${ex:-?}, $m$([[ $m =~ ^[0-9]+$ ]] && echo ' MiB'))"
    done | sort -u
}
kerr_poll() {   # (Karl 11-09: any new Xid or kernel error -> stop at once) this gap's programs are killed at once
  local p ex
  [ -e $KERR ] && [ ! -e $O/kerr.seen ] || return 0
  touch $O/kerr.seen
  [ $MOCK = 1 ] && return 0
  for p in $(ls /proc | grep -E '^[0-9]+$'); do ex=$(readlink /proc/$p/exe 2> /dev/null) || continue; ours "$ex" && kill -KILL $p 2> /dev/null; done
}
gwatch() { while [ -e $1 ] && kill -0 $$ 2> /dev/null; do foreign | sed "s/^/$(date +%T) /" >> $2; kerr_poll; sleep 5; done; }
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
DRYREF=0
refuse() {   # refuse busy|hard WHY - before the gap, nothing changed. busy: exit 1 (retry later); hard: an alert, exit 6
  if [ $DRY = 1 ]; then DRYREF=$((DRYREF + 1)); say "DRY RUN: the real run would REFUSE ($1) here: $2"; return 1; fi
  echo "not started ($1): $2 - nothing changed" > $O/result.txt
  say "NOT STARTED ($1): $2 - nothing changed"
  if [ "$1" = hard ]; then
    notes_line "not started: $2 - nothing changed"
    alert "Shape gap not started" "$(echo "$2" | cut -c1-120); nothing changed"; exit 6
  fi
  exit 1
}
build_of() { [ $1 = flash_next ] && echo $W/build-flash_next || echo $W/build-$1; }
model_of() { [ $1 = flash_next ] && echo "$ISTA1 $MTPRT" || echo "$MOD/$1-${LAYERS}l.gguf"; }

# ---------------------------------------------------------------- 2a the parity programs of one build
direct() {   # direct ROW NAME SECONDS ENVSPEC CMD...: one program run directly (no ctest entry); a line in direct.txt
  local row=$1 n=$2 t=$3 ev=$4 d=$O/parity/$1 rc t1 st; shift 4
  t1=$(date +%s)
  env $ev timeout --kill-after=20 $t "$@" 8>&- 9>&- < /dev/null > $d/direct-$n.log 2>&1; rc=$?
  case $rc in 0) st=PASS;; 77) st=SKIP;; 124|137) st=FAIL; rc="$rc(timeout ${t} s)";; *) st=FAIL;; esac
  echo "$n $st rc=$rc $(( $(date +%s) - t1 )) s ($*)" >> $d/direct.txt
}
parity() {   # parity ROW
  local row=$1 B d re n t rc
  B=$(build_of $row); d=$O/parity/$row; mkdir -p $d
  fits $PAR_MIN || { say "skipped the parity programs of $row (under $PAR_MIN min to the deadline, or a kernel check failed)"; gate parity_$row SKIPPED "deadline / kernel"; return 0; }
  gpu_clear parity_$row || { say "parity $row NOT started (a foreign GPU user)"; return 0; }
  cp $PREP/names-$row.txt $d/names.txt
  rules ctestlist $B --out $d/names-now.txt > $d/ctestlist.txt 2>&1
  cmp -s $d/names.txt $d/names-now.txt || gate list_$row INFO "the registered entries differ from the prep's list (the prep's is run): $(diff $d/names.txt $d/names-now.txt | grep -c '^[<>]') line(s)"
  re=$(paste -sd'|' $d/names.txt)
  n=$(wc -l < $d/names.txt); t=$(cap $CTEST_CAP)
  say "2a $row: $n ctest entries (build $(basename $B), timeout ${t} s for all) + 3 direct programs"
  wstart parity_$row
  env CUDA_VISIBLE_DEVICES=$GPUS timeout --kill-after=30 $t ctest --test-dir $B -R "^($re)\$" --timeout 300 --no-tests=error \
    --output-junit $d/junit.xml 8>&- 9>&- < /dev/null > $d/ctest.log 2>&1; rc=$?
  say "  ctest rc $rc: $(grep -E 'tests passed|tests failed' $d/ctest.log | tail -1)"
  : > $d/direct.txt
  if fits 2; then direct $row prefill_fused_iq_test_edge $(cap 10) "CUDA_VISIBLE_DEVICES=$GPUS" $B/prefill_fused_iq_test --edge --no-timing
  else echo "prefill_fused_iq_test_edge NOTRUN deadline" >> $d/direct.txt; fi
  if fits 2; then direct $row qsa_prompt_attn_parity $(cap 5) "CUDA_VISIBLE_DEVICES=$GPUS" $B/qsa_prompt_attn_parity
  else echo "qsa_prompt_attn_parity NOTRUN deadline" >> $d/direct.txt; fi
  if fits 3; then direct $row patch_guard_test 120 "CUDA_VISIBLE_DEVICES=" $B/patch_guard_test $(model_of $row)   # (review 11-09 #6)
  else echo "patch_guard_test NOTRUN deadline" >> $d/direct.txt; fi
  wstop parity_$row
  rules parity $d --names $d/names.txt --label $row | tee -a $S
  gate parity_$row INFO "$(tail -1 $d/results.txt | sed 's/^# //')"
  kc parity-$row
  return 0
}

# ---------------------------------------------------------------- 2b the smoke of one shape
SMK=""
smoke_set() { echo "$1=$2" >> $SMK; }
serve_once() {   # serve_once SHAPE CFG TAG: one served start + envcheck + one chat; sets STARTED / CHATOK / ENVOK
  local s=$1 cfg=$2 tag=$3 d=$O/smoke/$1 lab=$LP-$1$3 L off exe t
  exe=$(jget $cfg "['exe']"); L=$(jget $cfg "['log']"); touch $L; off=$(stat -c %s $L)
  t=$(cap $SERVE_CAP)
  say "  served start $lab ($(basename $cfg); cut at ${t} s)"
  wstart serve_$s$tag
  EVICT_GLOB=$MOD/$s-${LAYERS}l.gguf timeout --kill-after=60 $t $LIB/with_server.sh $lab $cfg -- \
    "nice -n 19 $P -I -B $RULES envcheck $exe $cfg --out $d/env$tag.txt; nice -n 19 $P -I -B $RULES chat http://127.0.0.1:8081 --out $d/chat$tag.json --max-tokens 32" \
    8>&- 9>&- < /dev/null > $d/with_server$tag.txt 2>&1; WSRC=$?
  wstop serve_$s$tag
  test_cleanup $lab   # (review 11-09 #1: always, not only when 8081 still listens)
  tail -c +$((off + 1)) $L > $d/engine$tag.log 2> /dev/null
  grep -E "server ready|engine pid|ENV CHECK|chat:|server exited|Traceback|=== " $d/with_server$tag.txt | cut -c1-240 | sed 's/^/    /' | tee -a $S
  STARTED=0; CHATOK=0; ENVOK=0
  grep -q '^server ready' $d/with_server$tag.txt && STARTED=1
  grep -q 'CHAT OK' $d/with_server$tag.txt && CHATOK=1
  grep -q '^ENV CHECK OK' $d/with_server$tag.txt && ENVOK=1
  fatalchk fatal_serve_$s$tag "$lab" $d/engine$tag.log $(slog $lab)
}
smoke() {   # smoke SHAPE
  local s=$1 d=$O/smoke/$1 exe gg pk prf lab t rc why=""
  mkdir -p $d/run; SMK=$d/smoke.txt; : > $SMK
  fits $SMOKE_MIN || { say "skipped the smoke of $s (under $SMOKE_MIN min to the deadline, or a kernel check failed)"; smoke_set answers "not run (deadline)"; return 0; }
  gpu_clear smoke_$s || { smoke_set answers "not run (a foreign GPU user)"; return 0; }
  exe=$ENGBASE/engine-r23p0213-$s-${LAYERS}l/strata; gg=$MOD/$s-${LAYERS}l.gguf; pk=$MOD/pack-$s-${LAYERS}l
  prf=$(ls $pk/expert-profile-*.bin 2> /dev/null | head -1)
  rules cfg $s --exe $exe --gguf $gg --pack $pk --profile $prf --log $LOGDIR/engine-sg0213-$s.log --cwd $d/run \
    --manifest $d/manifest.json --out $d/cfg.json | tee -a $S
  [ ${PIPESTATUS[0]} = 0 ] || { gate cfg_$s FAIL "the derived config did not pass its check"; smoke_set answers "no"; smoke_set why "config check failed"; return 0; }
  # -- the CLI probe: the guard lines (STRATA_GUARD_LIST=1 also prints the guards that pass)
  lab=$LP-$s-probe; t=$(cap $PROBE_CAP)
  say "2b $s: CLI probe $lab (p2000, 16 new tokens; cut at ${t} s)"
  wstart probe_$s
  EVICT_GLOB=$gg ENVX="STRATA_GUARD_LIST=1 STRATA_MANIFEST=$d/manifest-probe.json" timeout --kill-after=30 $t $LIB/run.sh $lab $d/cfg.json p2000 16 \
    8>&- 9>&- < /dev/null > $d/probe-run.txt 2>&1; rc=$?
  wstop probe_$s
  kill_ours
  cp $PROF/$lab.out $d/probe.out 2> /dev/null; cp $PROF/$lab.err $d/probe.err 2> /dev/null
  say "  probe: rc $rc, $(grep -E '^exit ' $d/probe-run.txt | tail -1)"
  rules guards $d/probe.out --shape $s --out $d/guards.txt | tee -a $S
  smoke_set guards "$(tail -1 $d/guards.txt 2> /dev/null)"
  smoke_set probe "$(grep -E '^exit ' $d/probe-run.txt | tail -1 || echo "rc $rc")"
  fatalchk fatal_probe_$s "$lab" $d/probe.out $d/probe.err
  kc probe-$s || { smoke_set answers "not run (kernel check)"; return 0; }
  # -- the served start + one chat
  fits 6 || { smoke_set answers "not run (deadline after the probe)"; return 0; }   # (review 11-09 #4: a cold load needs minutes)
  gpu_clear serve_$s || { smoke_set answers "not run (a foreign GPU user)"; return 0; }
  fits 6 || { smoke_set answers "not run (deadline after the GPU check)"; return 0; }
  serve_once $s $d/cfg.json ""
  rules manifest $d/manifest.json --out $d/manifest.txt | tee -a $S
  smoke_set manifest "$(tail -1 $d/manifest.txt 2> /dev/null)"
  if [ $STARTED = 1 ]; then
    smoke_set env "$([ $ENVOK = 1 ] && echo 'ENV CHECK OK' || echo "ENV CHECK FAILED ($(grep -o 'MISMATCH.*\|no running engine.*' $d/env.txt 2> /dev/null | cut -c1-160))")"
    [ $ENVOK = 1 ] || gate env_$s FAIL "$(grep -o 'MISMATCH.*\|no running engine.*' $d/env.txt 2> /dev/null | cut -c1-200)"
  else smoke_set env "not checked (the server did not start)"; fi
  if [ $STARTED = 1 ] && [ $CHATOK = 1 ] && [ "$(gst fatal_serve_$s)" = PASS ] && [ "$(gst foreign_serve_$s)" != FAIL ]; then
    smoke_set answers yes
    gate smoke_$s PASS "started, one chat answered ($(grep -o 'chat: .*' $d/with_server.txt | head -1 | cut -c1-140))"
  else
    [ $STARTED = 1 ] || why="the server did not start ($(grep -E 'server exited|error|Error' $d/with_server.txt | head -1 | cut -c1-120))"
    [ $STARTED = 0 ] && { [ "${WSRC:-0}" = 124 ] || [ "${WSRC:-0}" = 137 ]; } && why="cut at its time cap before it was ready (rc $WSRC)"
    [ $STARTED = 1 ] && [ $CHATOK = 0 ] && why="the chat failed ($(grep -o 'CHAT FAIL.*' $d/with_server.txt | head -1 | cut -c1-140))"
    [ "$(gst fatal_serve_$s)" = FAIL ] && why="${why:+$why; }a fatal / stall / non-finite line"
    [ "$(gst foreign_serve_$s)" = FAIL ] && why="${why:+$why; }a foreign GPU user during the start"
    smoke_set answers no; smoke_set why "$why"
    gate smoke_$s FAIL "$why"
    # -- only when the PLE-on start did not come up: once more with --no-ple, to tell a PLE-path problem from the rest
    if [ $STARTED = 0 ] && fits $NOPLE_MIN && gpu_clear serve_${s}_nople; then
      rules cfg $s --exe $exe --gguf $gg --pack $pk --profile $prf --log $LOGDIR/engine-sg0213-$s.log --cwd $d/run \
        --manifest $d/manifest-nople.json --out $d/cfg-nople.json --no-ple | tee -a $S
      serve_once $s $d/cfg-nople.json -nople
      smoke_set nople "with --no-ple: started $([ $STARTED = 1 ] && echo yes || echo no), env $([ $ENVOK = 1 ] && echo OK || echo 'not OK'), chat $([ $CHATOK = 1 ] && echo OK || echo FAIL), fatal lines $([ "$(gst fatal_serve_$s-nople)" = PASS ] && echo none || echo SOME)"
      gate smoke_${s}_nople INFO "$(grep '^nople=' $SMK | cut -d= -f2-)"
    fi
  fi
  kc serve-$s
  return 0
}

STOPPING=0
on_signal() {   # the driver stopped from outside: no new step; the test server stopped; the gap left as it is (Karl / Claude decide)
  trap - TERM INT HUP
  STOPPING=1
  say "SIGNAL: the driver was stopped"
  test_cleanup "$LP-"
  local st="the gap may still be open (tmp/port-gap.lockpid); close it with work/r22/port_gap4.sh end"
  if [ $GAPOPEN = 0 ]; then
    st="the gap was not open"
    # stopped inside port_gap4.sh begin: a hold this gap set is lifted again; a lock it may already have taken leaves it "maybe open"
    if grep -qF 'v0.2.13 shape gap' $HOLD 2> /dev/null; then
      if [ -s $LOCKPID ] && kill -0 "$(cat $LOCKPID)" 2> /dev/null; then st="the gap may have opened as it was stopped (lock held): close it with work/r22/port_gap4.sh end"; GAPOPEN=1
      else rm -f $HOLD; st="the gap was not open (this gap's research-queue hold lifted)"; fi
    fi
  fi
  ss -H -ltn "( sport = :8080 )" 2> /dev/null | grep -q . || st="$st; 8080 is NOT listening"   # (review 11-09 #12)
  [ -n "$WDG" ] && kill $WDG 2> /dev/null
  echo "INTERRUPTED: $st; nothing switched" > $O/result.txt
  notes_line "INTERRUPTED: $st; nothing switched"
  alert "Shape gap interrupted" "the driver was stopped; $( [ $GAPOPEN = 1 ] && echo 'the gap may still be open: 8080 down' || echo 'the gap was not open')"
  exit 7
}
finish() {   # $1 = the result line, $2 = exit code
  [ -n "$WDG" ] && kill $WDG 2> /dev/null
  echo "$1" > $O/result.txt
  say "RESULT: $1"
  notes_line "$1"
  exit $2
}

# ================================================================ 0 before the gap (no GPU; 8080 untouched)
: > $G
[ -n "$PREV" ] && say "an earlier attempt's outputs moved to $PREV"
say "SHAPE GAP 0213 (work/r23/shape-gap/gap-shape0213.sh, Karl 11-09): parity programs at flash_next / q4_mid / q4_big / q4_deep, one smoke per q4 shape - information only$([ $DRY = 1 ] && echo ' [DRY RUN]')$([ $MOCK = 1 ] && echo ' [MOCK RUN: every tool a stub under scratch/mock]')"
if [ $MOCK = 1 ]; then
  GPUS=mock-gpu0,mock-gpu1; HEAD=mock
  rules selftest $O/selftest > $O/selftest.out 2>&1 || refuse hard "shape_rules.py selftest failed"; rm -rf $O/selftest
  cp $PREP/builds.txt $O/builds.txt
else
for f in $RULES $LIB/with_server.sh $LIB/srv.sh $LIB/run.sh $LIB/kcheck.sh $LIB/guard.py $KR/port_gap4.sh $NOTE $BASE \
         $PROMPT_DIR/p2000.tokens $W/serve/server.py $WS/scripts/stopmon.sh $ISTA1 $MTPRT; do
  [ -e $f ] || refuse hard "missing: $f"
done
[[ $P028X_SHA =~ ^[0-9a-f]{12}$ ]] || refuse hard "could not read the served engine's sha from work/r22/port_gap4.sh"
GPUS=$(jget $BASE "['env']['CUDA_VISIBLE_DEVICES']")
[ -n "$GPUS" ] || refuse hard "no CUDA_VISIBLE_DEVICES in configs/P0213x.json"
if systemctl --user is-active -q post-p5-chain 2> /dev/null; then refuse busy "the post-Phase-5 chain is still running"; fi
ST=$O/selftest; rules selftest $ST > $O/selftest.out 2>&1 || refuse hard "shape_rules.py selftest failed ($(tail -1 $O/selftest.out))"
say "  shape_rules.py selftest: $(tail -1 $O/selftest.out)"; rm -rf $ST
if [ -s $READY ]; then
  export SG_RECIPE=$(jget $READY "['recipe']")
  VF=$(rules verify $READY 2>&1); echo "$VF" | sed 's/^/  /' >> $S
  echo "$VF" | tail -1 | grep -q '^VERIFY OK' || refuse hard "the prep record does not match the disk: $(echo "$VF" | grep 'VERIFY:' | head -2 | tr '\n' ' ' | cut -c1-200)"
  say "  $(echo "$VF" | tail -1)"
else refuse hard "no prep record $READY (run work/r23/shape-gap/shape_prep.sh all under nogap-run first)"; fi
HEAD=$(git -C $W rev-parse HEAD)
for r in geo-flash_next geo-q4_mid geo-q4_big geo-q4_deep geofile-q4_mid-${LAYERS}l geofile-q4_big-${LAYERS}l geofile-q4_deep-${LAYERS}l; do
  head -1 $RES/$r.txt 2> /dev/null | grep -q 'build rc 0' && head -1 $RES/$r.txt | grep -q "$HEAD" || refuse hard "results/r23/port-0213/$r.txt is not a clean build at HEAD ${HEAD:0:12}"
done
NJOK=1
for r in $ROWS; do
  [ -s $PREP/names-$r.txt ] || refuse hard "no ctest list $PREP/names-$r.txt"
  B=$(build_of $r)
  for x in prefill_fused_iq_test qsa_prompt_attn_parity patch_guard_test; do [ -x $B/$x ] || refuse hard "missing $B/$x"; done
  if [ $DRY = 1 ]; then say "  (dry run: would check: ninja -C $B -n strata <GEO_TESTS> says 'no work to do')"; continue; fi
  NJ=$(ninja -C $B -n strata $GEO_TESTS 2>&1 | tail -1)
  [ "$NJ" = "ninja: no work to do." ] || { NJOK=0; refuse hard "$(basename $B) is not up to date with the tree (ninja -n: $(echo "$NJ" | cut -c1-120))"; }
done
for s in $SHAPES; do
  B=$W/build-$s-${LAYERS}l
  if [ $DRY = 1 ]; then say "  (dry run: would check: ninja -C $B -n strata patch_guard_test says 'no work to do')"
  else
    NJ=$(ninja -C $B -n strata patch_guard_test 2>&1 | tail -1)
    [ "$NJ" = "ninja: no work to do." ] || { NJOK=0; refuse hard "$(basename $B) is not up to date with the tree (ninja -n: $(echo "$NJ" | cut -c1-120))"; }
  fi
  [ -x $B/strata ] && [ "$(sha12 $B/strata)" = "$(sha12 $WS/engine-r23p0213-$s-${LAYERS}l/strata 2> /dev/null)" ] \
    || refuse hard "engine-r23p0213-$s-${LAYERS}l is not build-$s-${LAYERS}l's strata (or one is missing)"
done
say "  build records, ninja and engine copies checked (HEAD ${HEAD:0:12})"
cp $PREP/builds.txt $O/builds.txt 2> /dev/null || refuse hard "no $PREP/builds.txt"
free=$(df --output=avail -B1G $WS/results | tail -1 | tr -d ' ')
[ "${free:-0}" -ge 5 ] || refuse hard "only ${free} GB free on results/"
if [ $DRY = 1 ]; then
  say "DRY RUN: would check that no other gap / test lock / model server but P028x ($P028X_SHA) / 8081 listener is there, that the kernel-log watcher runs, and a kernel check"
  say "DRY RUN: the gap would now run:"
  say "  GAP_MAX_MIN=$((MAXM + 25)) $KR/port_gap4.sh begin \"...\"; deadline $MAXM min after it opens; then per row:"
  for r in $ROWS; do
    B=$(build_of $r)
    say "  parity $r: env CUDA_VISIBLE_DEVICES=$GPUS timeout --kill-after=30 <<= $CTEST_CAP min> ctest --test-dir $B -R '^(<$(cat $PREP/names-$r.txt 2> /dev/null | wc -l) names of $PREP/names-$r.txt>)\$' --timeout 300 --no-tests=error --output-junit $O/parity/$r/junit.xml"
    say "    + env CUDA_VISIBLE_DEVICES=$GPUS $B/prefill_fused_iq_test --edge --no-timing; env CUDA_VISIBLE_DEVICES=$GPUS $B/qsa_prompt_attn_parity; env CUDA_VISIBLE_DEVICES= $B/patch_guard_test $(model_of $r)"
    say "    + shape_rules.py parity $O/parity/$r --names ... --label $r; kcheck"
    if [ $r != flash_next ]; then
      d=$O/smoke/$r; mkdir -p $d/run
      prf=$(ls $MOD/pack-$r-${LAYERS}l/expert-profile-*.bin 2> /dev/null | head -1)
      rules cfg $r --exe $WS/engine-r23p0213-$r-${LAYERS}l/strata --gguf $MOD/$r-${LAYERS}l.gguf --pack $MOD/pack-$r-${LAYERS}l \
        --profile ${prf:-$MOD/pack-$r-${LAYERS}l/expert-profile-4xN.bin} --log $WS/logs/engine-sg0213-$r.log --cwd $d/run \
        --manifest $d/manifest.json --out $d/cfg.json | sed 's/^/    /' | tee -a $S
      say "  smoke $r: EVICT_GLOB=$MOD/$r-${LAYERS}l.gguf ENVX=\"STRATA_GUARD_LIST=1 STRATA_MANIFEST=$d/manifest-probe.json\" timeout <<= $PROBE_CAP min> $LIB/run.sh $LP-$r-probe $d/cfg.json p2000 16"
      say "    + shape_rules.py guards $d/probe.out --shape $r"
      say "    + EVICT_GLOB=... timeout <<= $SERVE_CAP min> $LIB/with_server.sh $LP-$r $d/cfg.json -- \"<python> shape_rules.py envcheck <exe> <cfg> --out ...; <python> shape_rules.py chat http://127.0.0.1:8081 --out ... --max-tokens 32\""
      say "    + shape_rules.py manifest $d/manifest.json; fatal-line check; kcheck; only if the start failed: the same with cfg-nople.json (--no-ple)"
    fi
  done
  say "  $KR/port_gap4.sh end; shape_rules.py verdict $O; NOTES.md line; ntfy note"
  say "DRY RUN done: $DRYREF refusal(s) would stop the real run now (expected before the prep: no READY.json, no builds)"
  exit 0
fi
preflight
[ -f $WS/tmp/r19/kwatch.pid ] && kill -0 "$(cat $WS/tmp/r19/kwatch.pid)" 2> /dev/null || refuse hard "the kernel-log watcher is not running"
$LIB/kcheck.sh sg0213-pre > /dev/null 8>&- 9>&- < /dev/null || refuse hard "a kernel check fails before the gap"
fi
trap on_signal TERM INT HUP

# ================================================================ 1 the gap
GAP_MAX_MIN=$((MAXM + 25)) $KR/port_gap4.sh begin "v0.2.13 shape gap: our port's parity programs and a smoke start at q4_mid / q4_big / q4_deep (Karl 11-09; information only, nothing switches)" 8>&- 9>&- < /dev/null 2>&1 | tee -a $S
[ -s $LOCKPID ] && kill -0 "$(cat $LOCKPID)" 2> /dev/null || { grep -qF 'v0.2.13 shape gap' $HOLD 2> /dev/null && rm -f $HOLD; refuse busy "the gap did not open (our hold removed)"; }   # (review #9)
GAPOPEN=1; T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
# (review 11-09 #2) the watchdog: still open 20 min past the deadline -> one critical alert (a hang the deadline cannot cut)
if [ $MOCK = 0 ]; then
  ( exec 8>&- 9>&- < /dev/null > /dev/null 2>&1; sleep $(( MAXM * 60 + 1200 )); kill -0 $$ 2> /dev/null && [ -s $LOCKPID ] && kill -0 "$(cat $LOCKPID)" 2> /dev/null \
      && notify-send -a Strata -u critical "Shape gap overrun" "the shape gap is still open 20 min past its deadline: 8080 may be down" ) &
  WDG=$!
fi
# (review 11-09 #10) begin may have waited hours: the tree once more
HEADMOVED=0; [ $MOCK = 1 ] || [ "$(git -C $W rev-parse HEAD)" = "$HEAD" ] || { say "the tree moved while begin waited"; HEADMOVED=1; }
for i in $(seq 60); do [ -z "$(engines_left)" ] && [ "$(memav)" -ge 40 ] && break; sleep 2; done
say "8080 down: engines left:$(engines_left | sed 's/^/ /;s/^ $/ none/') MemAvailable $(memav) GB; deadline $(date -d @$DEADLINE '+%H:%M') ($MAXM min)"
end_gap() {   # port_gap4.sh end: P028x back on 8080 (nothing of it was changed); never after a kernel-check failure
  if [ $KFAIL = 1 ]; then   # (Karl 11-09 rerun: any new Xid or kernel error -> stop at once, P028x back, an alert; kwatch NOT cleared)
    say "KERNEL ERROR during the gap: stopping and bringing P028x back; kwatch is not cleared"
    [ -e $KERR ] && head -c 300 $KERR | sed 's/^/  /' | tee -a $S > /dev/null
    lock_sweep
    if $KR/port_gap4.sh end 8>&- 9>&- < /dev/null 2>&1 | tee -a $S; then
      GAPOPEN=0
      alert "Shape gap stopped: kernel error" "a kernel error during the shape gap; it stopped at once and P028x is back on 8080; kwatch not cleared"
    else
      alert "Shape gap: kernel error, 8080 not back" "a kernel error during the shape gap and port_gap4 end failed: 8080 and the research queue need a look"
    fi
    rules verdict $O > /dev/null 2>&1
    finish "KERNEL ERROR during the gap - stopped at once, $([ $GAPOPEN = 0 ] && echo 'P028x back on 8080' || echo '8080 NOT back'); kwatch not cleared; partial results in decision.txt" 3
  fi
  lock_sweep
  say "3 port_gap4.sh end: P028x back on 8080"
  if ! $KR/port_gap4.sh end 8>&- 9>&- < /dev/null 2>&1 | tee -a $S; then
    say "port_gap4.sh end FAILED: 8080 and the research queue need a look"
    alert "Shape gap: 8080 not back" "port_gap4 end failed after the shape gap; 8080 and the research queue need a look"
    rules verdict $O > /dev/null 2>&1
    finish "port_gap4.sh end FAILED - 8080 and the research queue need a look; the shape results are in decision.txt" 4
  fi
  GAPOPEN=0
}
kc open || end_gap
[ $HEADMOVED = 1 ] && { end_gap; finish "not run: the tree moved while the gap waited (nothing run)" 2; }
[ -z "$(engines_left)" ] || { say "engine processes still running 120 s after 8080 stopped: $(engines_left) - nothing run"; end_gap; finish "not run: engines still running after 8080 stopped (nothing changed)" 2; }

# ---- 2 the rows. q4_deep's smoke goes before its parity programs: q4_deep's kernels have Flash-Next's shape constants (only
# the layer count differs), so its parity row should repeat the reference row, while its smoke is the one start with the
# GR_FORK read on at a new layer count - if the deadline cuts something, it cuts the least informative step
say "steps: $STEPLIST"
for st in $STEPLIST; do
  [ -e $KERR ] && { KFAIL=1; say "a kernel error is recorded ($(head -c 160 $KERR 2> /dev/null)): no further step"; }
  [ $KFAIL = 1 ] && break
  ${st%%:*} ${st#*:}
done
DOWN_WORK=$(( ($(date +%s) - T0) / 60 ))
say "the gap's work took $DOWN_WORK min (deadline $MAXM)"
end_gap
DOWN=$(( ($(date +%s) - T0) / 60 ))

# ---- 4 the verdict (information only)
rules verdict $O | tee -a $S
KA=ok; kc after || KA=FAILED
say "8080 was down for about $DOWN min; kernel check after the gap: $KA"
VL=$(cat $O/verdict-line.txt 2> /dev/null)
NF=$(awk '/^FAILS/ {f=1; next} f && /^  / && !/^  none/ {n++} /^$/ {f=0} END {print n + 0}' $O/decision.txt)
note "Shape gap done" "v0.2.13 port at the q4 shapes, information only: $(echo "$VL" | sed -E 's/parity programs //g; s/loads and answers/answers/g' | cut -c1-150). $NF failure line(s); 8080 back after $DOWN min."
[ $KA = ok ] || alert "Shape gap: kernel check" "the kernel check after the shape gap failed (8080 is back); see kwatch.log"
finish "DONE (information only, nothing switched; 8080 down $DOWN min; kernel check after: $KA): $VL; $NF failure line(s) in decision.txt" 0
