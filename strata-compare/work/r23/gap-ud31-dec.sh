#!/bin/bash
# gap-ud31-dec.sh - r23 (Karl 11-05): THE v3.1 GAP'S DECODE-PATH FOLLOW-UP, the step after work/r23/gap-ud31.sh in
# work/r23/gap-series.sh. WRITTEN 11-05, NOT RUN. Measurements only: P028x stays served, NOTHING SWITCHES, nothing is
# built. Run: `bash work/r23/gap-ud31-dec.sh` (no arguments; every path absolute).
# Karl 11-05: "if U fails the NLL bound or lands inside its margin, record it as 'includes pack rounding', not as a
# verdict on the file. Before deciding, queue a decode-path teacher-forced score of U with HC_Q8=1, using the
# decode-path gap's scorer." 11-05, after the NLL bound was revoked: "carry my frozen rule over to whatever replaces
# the bound. If U comes out worse than P, or inside the margin on the KL rules, record 'includes pack rounding' and set
# the follow-up flag the same way." Rules (written before any run): work/r23/ud31_rules.py's docstring, sections THE
# PACK-ROUNDING RULE and THE DECODE-PATH FOLLOW-UP. The scorer: work/r23/decpath_rules.py's runner and env check,
# unchanged, called through ud31_rules.py dec-run / dec-envwatch (they hand it the decode-path gap's dec reads: the same
# texts, cuts and --max-context / --short-read). P is NOT rerun: its rows are that gap's dec arm (x28h as served).
#   0 before the gap (no GPU, 8080 untouched) - REFUSES (exit 1: the series skips it) unless: the v3.1 decision
#     (results/r23/ud31/decision.json + .txt) says "=> U DECODE-PATH FOLLOW-UP: WANTED" (U's text-level KL verdict
#     against R anything but BETTER THAN P), the decode-path gap's dec arm exists
#     (results/r23/decpath/gap/dec: rows, run_dec + env_dec PASS, >= 5 texts, x28h, logpos), U's config / pack / shards as the v3.1 gap used them (dec-pre); no gpu-test.lock / other gap
#     / model server other than the 8080 queue's P028x / 8081 listener; the kernel watcher; engine-r22p028x = P028x;
#     >= 5 GB free on results/. An earlier attempt's outputs move to results/r23/ud31/dec/prev-*
#   1 port_gap4.sh begin (the running question finishes, test lock, 8080 down); wait for the memory; a kernel check
#   2 arm U: decpath's runner (--kind logpos: STRATA_LOGPOS top 64 through 2-row verify windows, the yardstick's
#     settings) on results/r23/ud31/configs/ud31-U.json (STRATA_HC_Q8=1), dec's texts / cuts / length, budget
#     UD31DEC_ARM_MIN (52) min capped so that 16 min remain; its env checked as it starts (dec-envwatch --kill); a
#     watchdog at budget + 10 min (a stop inside a text keeps the finished ones: rc 2); then dec-args (U's engine args =
#     dec's except U's three paths) and hcline (the engine's "STRATA_HC_Q8=1: 0.63 GiB" = the file's own Q8_0 hc); a
#     kernel check
#   3 port_gap4.sh end (P028x back) + a kernel check; after the gap (CPU, nice 19): dec-compare (U's rows vs dec's at
#     dec's compare positions, + the v3.1 gap's prompt-path rows.tsv at the same positions) and dec-decide ->
#     results/r23/ud31/dec/decision.txt: Karl's rule (11-05) - U vs P on decode-path text NLL, by consistency across
#     the texts both have: U lower in >= 6 of 8 and higher in <= 1 = BETTER, the mirror = WORSE, else INCONCLUSIVE
#     ("if the file choice hinges on it, Karl decides on a separate R decode-path gap"); fewer texts scaled as the
#     decode-path check: N 7 >= 6 / <= 0, N 6 >= 5 / <= 0, N 5 >= 4 / <= 0, under 5 NOT JUDGED; a tie counts as
#     neither. Whole-text interval beside it, the 2,048-block figure labelled "not used for the verdict". INFO only:
#     the rounding cost per text, (U decode - U prompt) - (P decode - P prompt), U prompt from the v3.1 gap's rows.tsv,
#     P prompt from the NLL gap's ref rows (results/r23/nll-many/gap/rows.tsv). No R; no extra engine time
# No new step after the deadline (UD31DEC_MAX_MIN, default 70 min after the gap opens; expected ~60 with 8080 down).
# A kernel-check failure stops new steps and leaves the gap OPEN (8080 down, exit 3: Karl decides). Exit 0 = done
# (outcome in decision.txt), 1 = refused / not opened (8080 untouched), 3 = kernel check failed, 4 = port_gap4.sh end
# failed. Steps: work/r23/GAPS-README.md, section 10.
set -u -o pipefail
exec 8>&- 9>&-                     # no inherited lock descriptor (work/r22 lock-fd rule): this script holds none itself
WS=/home/USER/ai-speed-testing/strata-compare
export RB_CACHE=$WS/tmp/r23
source $WS/bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
for v in $(compgen -e | grep '^STRATA_'); do [ "$v" = STRATA_MON_GPU ] || unset "$v"; done   # no stray switch reaches an engine
IS=$WS/models/ISTA-GSQ-RCO/IQ3_S; UD=$WS/models/unsloth-v31/UD-IQ3_XXS
export PROMPT_DIR=$WS/bringup/out/r20a/prompts EVICT_GLOB="$IS/*.gguf $UD/*.gguf"
P=$WS/.venv/bin/python; KR=$WS/work/r22; LIB=$WS/bringup/lib
RU=$WS/work/r23/ud31_rules.py; DPR=$WS/work/r23/decpath_rules.py
R=$WS/results/r23/ud31; DD=$R/dec; GD=$DD/gap; G=$GD/gates.txt
PDEC=$WS/results/r23/decpath/gap/dec; CU=$R/configs/ud31-U.json
S=$DD/gap-ud31-dec-starts.log      # until the pre-gap checks pass (then $GD/summary.txt)
EXE=$WS/engine-r22p028x/strata; P028X_SHA=f4c4f654fb24          # engine-r22p028x/strata, served on 8080 since 10-30
MAXM=${UD31DEC_MAX_MIN:-70}; ARM_MIN=${UD31DEC_ARM_MIN:-52}; NT=${UD31DEC_THREADS:-4}
mkdir -p $DD $WS/tmp/r23
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
gate() { echo "$1 $2 ${*:3} [ud31dec $(date '+%m-%d %H:%M')]" >> $G; say "  gate $*"; }
gstat() { grep "^$1 " $G 2> /dev/null | tail -1 | cut -d' ' -f2; }
KFAIL=0; T0=$(date +%s); DEADLINE=$T0
kc() { $LIB/kcheck.sh "u31dec-$1" > /dev/null 8>&- 9>&- || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; echo "kfail FAIL after $1" >> $G; return 1; }; }
left() { echo $(( DEADLINE - $(date +%s) )); }
ok_to_go() { [ $KFAIL = 0 ] && [ $(left) -gt 0 ]; }
sha12() { sha256sum "$1" | cut -c1-12; }
ppid_of() { local s; s=$(cat /proc/$1/stat 2> /dev/null) || return 0; s=${s##*) }; set -- $s; echo "${2:-}"; }
memavail() { awk '/^MemAvailable/ {printf "%d", $2 / 1048576}' /proc/meminfo; }

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
    m=$(memavail)
    [ -z "$left_p" ] && [ "$m" -ge 40 ] && break
    sleep 2
  done
  say "8080 down: engines left:${left_p:- none}, MemAvailable ${m} GB"
}
watchdog() {   # watchdog JOB MINUTES NAME: an arm past MINUTES is hung - stop the engine in the job's own process tree by
  # its PID (guard.py does not pass a TERM on to its child's session); the runner keeps the texts it finished
  local j=$1 m=$2 n=$3 t p q
  t=$(( $(date +%s) + m * 60 ))
  while kill -0 $j 2> /dev/null; do
    if [ $(date +%s) -ge $t ]; then
      for p in $( { pgrep -x strata; pgrep -x strata-host; } | sort -un); do
        q=$p; while [ -n "$q" ] && [ "$q" -gt 1 ] && [ "$q" != $j ]; do q=$(ppid_of $q); done
        [ "$q" = $j ] && kill -TERM $p 2> /dev/null && echo "watchdog: $n ran past $m min - its engine (pid $p) was stopped" >> $GD/$n.watchdog
      done
      return 0
    fi
    sleep 5
  done
}

decarm() {   # decarm BUDGET_MIN: U's decode path, dec's reads (ud31_rules.py dec-run = decpath_rules.py run with dec's plan)
  local bm=$1 jp wd rc
  ok_to_go || { say "skipped arm U (deadline or kernel check)"; return 1; }
  say "2 arm U: the decode path with STRATA_HC_Q8=1 ($(basename $CU), logpos, the decode-path gap's dec texts and cuts), budget $bm min ($(( $(left) / 60 )) min to the deadline)"
  rm -f $GD/U.rc $GD/U.watchdog
  ( $P $LIB/guard.py u31dec-U -- $P -I -B $RU dec-run $CU $GD/U --pdec $PDEC --budget-min $bm > $GD/U.run.txt 2>&1
    echo $? > $GD/U.rc ) 8>&- 9>&- &
  jp=$!
  watchdog $jp $(( bm + 10 )) U 8>&- 9>&- &
  wd=$!
  $P -I -B $RU dec-envwatch $jp $CU --pdec $PDEC --kill --gate env_decU --gates $G 8>&- 9>&- 2>&1 | tee -a $S
  wait $jp
  kill $wd 2> /dev/null; wait $wd 2> /dev/null
  [ -f $GD/U.watchdog ] && say "  $(cat $GD/U.watchdog)"
  rc=$(cat $GD/U.rc 2> /dev/null || echo none)
  grep -E "^plan |tokens in [0-9]+ s|^skipped|texts read|^PROBLEM" $GD/U.run.txt | cut -c1-250 | sed "s/^/  U: /" | tee -a $S
  if [ "$rc" = 0 ] && [ -f $GD/U/index.json ]; then
    gate run_decU PASS "rc 0: $(grep -E 'texts read' $GD/U.run.txt | tail -1)"
  elif [ "$rc" = 2 ] && [ -f $GD/U/index.json ]; then   # stopped inside a text (watchdog): the finished texts stand
    gate run_decU PASS "rc 2 (partial: the last text was stopped; the finished texts are kept): $(grep -E '^PROBLEM' $GD/U.run.txt | head -1 | cut -c1-160)"
  else
    gate run_decU FAIL "rc $rc: $(grep -E '^PROBLEM|SystemExit|Error|answered|ended before|GUARD' $GD/U.run.txt | head -3 | tr '\n' ' ' | cut -c1-250)"
  fi
  if [ -f $GD/U/index.json ]; then
    $P -I -B $RU dec-args $GD/U --pdec $PDEC --cfg $CU --gate dec_args --gates $G 8>&- 9>&- 2>&1 | tail -1 | tee -a $S
    $P -I -B $RU hcline $GD/U/stderr.txt $CU --want on --gate hcq8_dec_U --gates $G 8>&- 9>&- 2>&1 | tail -1 | tee -a $S
  fi
  kc arm-U
}
finish() {   # dec-decide -> results/r23/ud31/dec/decision.txt (+ .json)
  rm -f $DD/decision.txt $DD/decision.json
  $P -I -B $RU dec-decide $DD > /dev/null 2>&1 8>&- 9>&- || say "ud31_rules.py dec-decide failed - rerun it by hand ($RU dec-decide $DD)"
  if [ -f $DD/decision.txt ]; then
    cat $DD/decision.txt >> $S
    grep -E "^=>|^\[" $DD/decision.txt | cut -c1-220 | sed "s/^/  /"
  fi
}
after_gap() {   # CPU only, nice 19, 8080 back: dec-compare (two TSVs at dec's compare positions; small), dec-decide
  local i rc
  say "after the gap (CPU, nice 19): dec-compare, dec-decide"
  for i in $(seq 30); do [ "$(memavail)" -ge 14 ] && break; sleep 10; done   # a few hundred MB above the 12 GB floor
  if [ "$(memavail)" -lt 14 ]; then
    say "MemAvailable $(memavail) GB < 14 after 5 min: dec-compare NOT run - by hand later ($RU dec-compare $GD/U --json $GD/result.json --gate compare --gates $G; then $RU dec-decide $DD)"
  elif [ "$(gstat run_decU)" = PASS ] && [ -f $GD/U/score.tsv ]; then
    rm -f $GD/result.json
    nice -n 19 $P -I -B $RU dec-compare $GD/U --pdec $PDEC --rows $R/gap/rows.tsv --prows $WS/results/r23/nll-many/gap/rows.tsv \
      --json $GD/result.json --threads $NT --gate compare --gates $G > $GD/compare.txt 2>&1; rc=$?
    [ $rc = 0 ] && [ -s $GD/result.json ] || gate compare FAIL "rc $rc: $(tail -2 $GD/compare.txt | tr '\n' ' ' | cut -c1-200)"
    tail -1 $GD/compare.txt | sed "s/^/  /" | tee -a $S
  else say "not compared: U's decode-path arm did not run cleanly (run_decU $(gstat run_decU))"; fi
  finish
}
end_gap() {
  if [ $KFAIL = 1 ]; then say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"; finish; exit 3; fi
  say "P028x back on 8080 (port_gap4.sh end) - nothing switched"
  if ! $KR/port_gap4.sh end 8>&- 9>&- 2>&1 | tee -a $S; then
    say "port_gap4.sh end FAILED: 8080 and the research queue need a look"; exit 4
  fi
  kc end || { say "the kernel check failed after P028x came back: Karl decides"; exit 3; }
  say "v3.1 follow-up gap: $(( ($(date +%s) - T0) / 60 )) min with 8080 down"
  after_gap
  say "v3.1 follow-up done"
  exit 0
}

# ================================================================ before the gap (no GPU; 8080 untouched)
say "start attempt: work/r23/gap-ud31-dec.sh (pre-gap checks)"
for f in $RU $DPR $CU $LIB/guard.py $LIB/kcheck.sh $KR/port_gap4.sh $WS/work/r23/nll-many/score.py $WS/work/r23/nll_rules.py; do
  [ -f $f ] || { say "missing $f - not started"; exit 1; }
done
PRE=$($P -I -B $RU dec-pre --ud31 $R --pdec $PDEC --cfg $CU 2>&1); [ $? = 0 ] || { say "REFUSED: $(echo "$PRE" | tail -1 | cut -c1-500) - not started"; exit 1; }
preflight
[ -f $WS/tmp/r19/kwatch.pid ] && kill -0 "$(cat $WS/tmp/r19/kwatch.pid)" 2> /dev/null || { say "the kernel-log watcher is not running - not started"; exit 1; }
[ -x $EXE ] && [ "$(sha12 $EXE)" = $P028X_SHA ] && [ "$(cut -c1-12 $WS/engine-r22p028x/SHA256)" = $P028X_SHA ] || { say "engine-r22p028x is not P028x ($P028X_SHA) - not started"; exit 1; }
free=$(df --output=avail -B1G $WS/results | tail -1 | tr -d ' ')
[ "${free:-0}" -ge 5 ] || { say "only ${free} GB free on results/ - not started"; exit 1; }
PREV=""
if [ -e $GD ] || [ -e $DD/decision.txt ]; then   # the rules judge only this attempt's files
  PREV=$DD/prev-$(date +%m%d-%H%M%S); mkdir -p $PREV
  for f in $GD $DD/decision.txt $DD/decision.json; do [ -e $f ] && mv $f $PREV/; done
fi
mkdir -p $GD
S=$GD/summary.txt
say "v3.1 FOLLOW-UP (work/r23/gap-ud31-dec.sh): U's decode-path teacher-forced score with STRATA_HC_Q8=1 against the decode-path gap's P rows, judged at the text level (Karl 11-05) - measurements only, P028x stays served, nothing switches"
[ -n "$PREV" ] && say "an earlier attempt's outputs moved to $PREV"
gate pre PASS "$(echo "$PRE" | tail -1 | cut -c1-400)"
say "$(grep -E '^=> U DECODE-PATH FOLLOW-UP' $R/decision.txt | cut -c1-300)"

# ================================================================ the gap
$KR/port_gap4.sh begin "r23 v3.1 follow-up: U's decode-path teacher-forced score with STRATA_HC_Q8=1 (Karl 11-05; measurements only, P028x stays served, nothing switches)" 8>&- 9>&- 2>&1 | tee -a $S
[ -s $WS/tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
echo "$T0 $(date -Is)" > $GD/t0.txt
wait_mem
kc open || end_gap

BM=$(( $(left) / 60 - 16 )); [ $BM -gt $ARM_MIN ] && BM=$ARM_MIN
if [ $BM -ge 10 ]; then decarm $BM
else say "2 arm U NOT run: only $(( $(left) / 60 )) min to the deadline (it needs 26: 10 for the arm, 16 kept for the end)"; fi

end_gap
