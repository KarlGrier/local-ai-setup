#!/bin/bash
# gap-decpath.sh - r23 (Karl 11-05): THE DECODE-PATH CHECK, first in work/r23/gap-series.sh (after 7d's last question,
# before the Basalt prompt-port gaps). WRITTEN 11-05, NOT RUN. Measurements only: P028x stays served, NOTHING SWITCHES,
# nothing is built. Run: `bash work/r23/gap-decpath.sh` (no arguments; every path absolute).
# Karl: "Score the same positions token by token through the decode path. For each prompt variant (default fused,
# unfused, CPU share, v2 kernels, GDN on), report its distance from the decode path, by prompt length. If the default
# fused path is the outlier: tell me how big the effect is on real long-prompt work and what turning it off would cost
# in prompt speed, before changing anything." Rules (written before any run): results/r23/decpath/rules.txt =
# work/r23/decpath_rules.py's docstring (runner, env check, compare and decide are in that file too).
#   0 before the gap (no GPU, 8080 untouched) - REFUSES (exit 1) on: tmp/gpu-test.lock held, another gap's lock, a model
#     server other than the 8080 queue's P028x, a listener on 8081, no kernel watcher, engine-r22p028x not f4c4f654fb24,
#     the variants' rows missing or not clean in their gaps (decpath_rules.py pre), the derived configs not = their
#     templates + the declared change (configs --check), rules.txt not the script's, < 20 GB free on results/
#   1 port_gap4.sh begin (the running question finishes, test lock, 8080 down); wait for the memory; a kernel check
#   1b Karl 11-05: pillow 13.0.0 into .venv (record 12.3.0 + pip freeze, install --no-deps, freeze compare: only pillow
#     may change), the two image unit tests of the served tree, a matplotlib check, one JPEG + one PNG through vision on
#     a test server (8081) from configs/P028x.json's copy; pass -> requirements.lock.txt; any failure -> back to 12.3.0
#     and "ROLLED BACK" with the reason. This step cannot fail the gap's measurements (~4-6 min)
#   2 arm dec (REQUIRED): engine-r22p028x / x28h, every token of up to 8 texts through 2-row verify windows with
#     STRATA_LOGPOS top 64 (decpath_rules.py run --kind logpos --plan main), budget DECPATH_DEC_MIN (50) min, capped so
#     20 min stay before the deadline; env checked as it starts (envwatch --kill); a watchdog; a kernel check
#   3 optional (if 14 min fit): prompt speed, Basalt's pp16k + pp64k cold, a fresh engine each, x28h as served /
#     + STRATA_PF_FUSED=0 / + STRATA_PREFILL_CPU_SHARE=0, 2 passes in turned order (12 engine starts); a kernel check each
#   4 optional (if 9 min fit): arm dec1 - 1-row windows (engine-r22p028xm, force=N + STRATA_FORCE_T1=1) on ldrsyn20k
#   5 optional (if 9 min fit): arm s210dec - stock v0.2.10's decode path (s0210-h), as dec, on ldrsyn20k
#   6 optional (if they fit): decode gap b's Basalt arm-passes that failed 11-05 06:50-06:51 (decpath_rules.py
#     bp90-missing; 7 at writing), on engine-r23decode with gap b's configs, into results/r23/decpath/bp90-rerun
#   7 port_gap4.sh end (P028x back) + a kernel check; after the gap (CPU only, nice 19, DECPATH_THREADS=4 BLAS threads,
#     MemAvailable >= 20 GB): compare (~10-20 min), merge-b + decode_rules.py decide-b -> decision-b-merged.txt,
#     decide -> results/r23/decpath/decision.txt
# No new step after the deadline (DECPATH_MAX_MIN, default 120 min after the gap opens). A kernel-check failure stops new
# steps and leaves the gap OPEN (8080 down, exit 3: Karl decides). Exit 0 = done (outcome in decision.txt), 1 = refused /
# not opened (8080 untouched), 3 = kernel check failed, 4 = port_gap4.sh end failed. Steps: work/r23/GAPS-README.md (8).
set -u -o pipefail
exec 8>&- 9>&-                     # no inherited lock descriptor (work/r22 lock-fd rule): this script holds none itself
WS=/home/USER/ai-speed-testing/strata-compare
export RB_CACHE=$WS/tmp/r23
source $WS/bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
for v in $(compgen -e | grep '^STRATA_'); do [ "$v" = STRATA_MON_GPU ] || unset "$v"; done   # no stray switch reaches an engine
export PROMPT_DIR=$WS/bringup/out/r20a/prompts EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
P=$WS/.venv/bin/python; C=$WS/configs; KR=$WS/work/r22; LIB=$WS/bringup/lib
RU=$WS/work/r23/decpath_rules.py; DR=$WS/work/r23/decode_rules.py; R17=$KR/g17_rules.py; B90=$KR/basalt-pr90
O=$WS/results/r23/decpath; GD=$O/gap; G=$GD/gates.txt; CF=$O/cfg; PD=$O/pillow; SO=$GD/speed; RB=$O/bp90-rerun
S=$O/gap-decpath-starts.log      # until the pre-gap checks pass (then $GD/summary.txt)
GA=$WS/results/r23/decode-timing/gap-a; GB=$WS/results/r23/decode-timing/gap-b; GC=$WS/results/r23/decode-timing/gate-configs
XEXE=$WS/engine-r22p028x/strata; TEXE=$WS/engine-r22p028xm/strata; SEXE=$WS/engine-v0210stock/strata; E23=$WS/engine-r23decode/strata
P028X_SHA=f4c4f654fb24; TWIN_SHA=d716ab8217c2; STOCK_SHA=c8fe72abe45a   # served P028x / its measurement twin / stock v0.2.10
X_CFG=$C/x28h.json; ST_CFG=$C/s0210-h.json; TW_CFG=$CF/x28h-twin.json; VIS_CFG=$CF/vistest.json
W028=$WS/strata-r22p028x; W23=$WS/strata-r23decode
MAXM=${DECPATH_MAX_MIN:-120}; DEC_MIN=${DECPATH_DEC_MIN:-50}; NT=${DECPATH_THREADS:-4}; MEM_GB=20
declare -A WANT=([B]=none [LO]=late,one)
mkdir -p $O $WS/tmp/r23
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
gate() { echo "$1 $2 ${*:3} [decpath $(date '+%m-%d %H:%M')]" >> $G; say "  gate $*"; }
gstat() { grep "^$1 " $G 2> /dev/null | tail -1 | cut -d' ' -f2; }
KFAIL=0; T0=$(date +%s); DEADLINE=$T0; TWIN_OK=0; STOCK_OK=0; B23_OK=0
kc() { $LIB/kcheck.sh "r23dp-$1" > /dev/null 8>&- 9>&- || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; echo "kfail FAIL after $1" >> $G; return 1; }; }
left() { echo $(( DEADLINE - $(date +%s) )); }
ok_to_go() { [ $KFAIL = 0 ] && [ $(left) -gt 0 ]; }
fits() { ok_to_go && [ $(left) -ge $(( $1 * 60 )) ]; }   # an optional step starts only if it ends before the deadline
sha12() { sha256sum "$1" | cut -c1-12; }
elog() { $P -I -c "import json, sys; print(json.load(open(sys.argv[1]))['log'])" "$1"; }
slog() { ls -t $WS/bringup/out/logs/server_$1_*.log 2> /dev/null | head -1; }   # the newest server log of a with_server label
ppid_of() { local s; s=$(cat /proc/$1/stat 2> /dev/null) || return 0; s=${s##*) }; set -- $s; echo "${2:-}"; }
memavail() { awk '/^MemAvailable/ {printf "%d", $2 / 1048576}' /proc/meminfo; }
ok_arm() { [ "$(gstat run_$1)" = PASS ] && [ "$(gstat env_$1)" = PASS ]; }

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
fatalchk() {   # fatalchk NAME ENGINE_LOG OFFSET LABEL GATES (gap 17): a fatal GPU error / stall / engine restart / non-finite
  local n=$1 L=$2 off=$3 sl hits
  sl=$(slog $4)
  hits=$( { tail -c +$((off + 1)) $L 2> /dev/null; [ -n "$sl" ] && cat $sl; } | grep -c -E "fatal GPU error|no progress for [0-9]+ s during a request|the engine had stopped \(exit code|became non-finite")
  [ "$hits" = 0 ] || { echo "fatal_$n FAIL $hits line(s): fatal GPU error / stall / engine restart / non-finite (engine log $L from byte $off; $sl) [decpath $(date '+%m-%d %H:%M')]" >> $5; say "  gate fatal_$n FAIL ($hits line(s))"; }
}

decarm() {   # decarm NAME CONFIG KIND PLAN BUDGET_MIN [K=V ...]: one engine, the plan's texts read token by token through
  # the decode path's windows (decpath_rules.py run), its environment checked as it starts, a watchdog, a kernel check
  local n=$1 cfg=$2 kind=$3 plan=$4 bm=$5 e envs="" jp wd rc; shift 5
  for e in "$@"; do envs="$envs --env $e"; done
  ok_to_go || { say "skipped arm $n (deadline or kernel check)"; return 1; }
  say "arm $n ($(basename $cfg), $kind, plan $plan, budget $bm min${envs:+;$envs})"
  rm -f $GD/$n.rc $GD/$n.watchdog
  ( $P $LIB/guard.py dp23-$n -- $P -I -B $RU run $cfg $GD/$n --kind $kind --plan $plan --budget-min $bm $envs > $GD/$n.run.txt 2>&1
    echo $? > $GD/$n.rc ) 8>&- 9>&- &
  jp=$!
  watchdog $jp $(( bm + 12 )) $n 8>&- 9>&- &
  wd=$!
  $P -I -B $RU envwatch $jp $cfg --kind $kind --plan $plan $envs --kill --gate env_$n --gates $G 8>&- 9>&- 2>&1 | tee -a $S
  wait $jp
  kill $wd 2> /dev/null; wait $wd 2> /dev/null
  [ -f $GD/$n.watchdog ] && say "  $(cat $GD/$n.watchdog)"
  rc=$(cat $GD/$n.rc 2> /dev/null || echo none)
  grep -E "tokens in [0-9]+ s|^skipped|texts read|^PROBLEM" $GD/$n.run.txt | sed "s/^/  $n: /" | tee -a $S
  if [ "$rc" = 0 ] && [ -f $GD/$n/index.json ]; then
    gate run_$n PASS "rc 0: $(grep -E 'texts read' $GD/$n.run.txt | tail -1)"
  elif [ "$rc" = 2 ] && [ -f $GD/$n/index.json ]; then   # stopped inside a text (watchdog): the finished texts stand
    gate run_$n PASS "rc 2 (partial: the last text was stopped; the finished texts are kept): $(grep -E '^PROBLEM' $GD/$n.run.txt | head -1 | cut -c1-160)"
  else
    gate run_$n FAIL "rc $rc: $(grep -E '^PROBLEM|SystemExit|Error|answered|ended before|GUARD' $GD/$n.run.txt | head -3 | tr '\n' ' ' | cut -c1-250)"
  fi
  kc arm-$n
}
spdrun() {   # spdrun ARM SET PASS: one Basalt fixture cold (a fresh engine, two cards), P028x as served +/- one switch
  local arm=$1 set=$2 k=$3 n=sp-$1-$2-$3 cfg=$CF/spd-$1.json L off
  ok_to_go || { say "skipped speed $n (deadline or kernel check)"; return 1; }
  L=$(elog $cfg); touch $L; off=$(stat -c %s $L)
  $LIB/with_server.sh r23dp-$n $cfg -- "$P -I -B $R17 envcheck $XEXE $cfg --ngpu 2 --pins --gate env_$n --gates $G && $P -I -B $B90/bp90_client.py http://127.0.0.1:8081 --label $n --sets $set --passes 1 --first-pass $k --tree $W028 --out $SO/cold-$arm.jsonl" 8>&- 9>&- 2>&1 \
    | grep -E "engine pid [0-9]+:|ENV CHECK| pass |ready|exited|refus|Error|GUARD|Traceback" | tee -a $S
  fatalchk $n $L $off r23dp-$n $G
  tail -c +$((off + 1)) $L > $SO/$n.engine.log
  kc $n
}
bprerun() {   # bprerun ARM SET PASS: decode gap b's bprun unchanged (engine-r23decode, its configs), into $RB
  local b=$1 set=$2 k=$3 n=bp$1-$2-$3 cfg=$GC/r23-$1.json L off
  ok_to_go || { say "skipped rerun $n (deadline or kernel check)"; return 1; }
  L=$(elog $cfg); touch $L; off=$(stat -c %s $L)
  $LIB/with_server.sh r23dp-$n $cfg -- "$P -I -B $R17 envcheck $E23 $cfg --ngpu 2 --pins --gate env_$n --gates $RB/gates.txt && $P -I -B $B90/bp90_client.py http://127.0.0.1:8081 --label $n --sets $set --passes 1 --first-pass $k --tree $W23 --out $RB/cold-$b.jsonl" 8>&- 9>&- 2>&1 \
    | grep -E "engine pid [0-9]+:|ENV CHECK| pass |ready|exited|refus|Error|GUARD|Traceback" | tee -a $S
  fatalchk $n $L $off r23dp-$n $RB/gates.txt
  tail -c +$((off + 1)) $L > $RB/$n.engine.log
  $P -I -B $DR lines --want ${WANT[$b]} $RB/$n.engine.log > $RB/$n.lines.txt 2>&1   # INFO (a prompt-only run may not decode)
  kc rerun-$n
}

pillow_step() {   # 1b (Karl 11-05): pillow 13.0.0 into .venv while 8080 is down. Never exits, never touches the gates of
  # the measurements; any failure -> back to 12.3.0 and "ROLLED BACK" with the reason (RESULT.txt and the summary)
  local why="" v0 v1 rc t0
  t0=$(date +%s)
  mkdir -p $PD/tmp $PD/mplconfig
  say "1b pillow 13.0.0 in .venv (Karl 11-05): install, the two image unit tests, matplotlib, a JPEG and a PNG through vision"
  v0=$($P -I -c "import importlib.metadata as m; print(m.version('pillow'))" 2> /dev/null | tail -1)
  $P -I -m pip freeze > $PD/freeze-before.txt 2> $PD/pip.txt || why="pip freeze failed before the install"
  echo "pillow step $(date '+%F %T'): before ${v0:-unknown}" > $PD/RESULT.txt
  if [ -z "$why" ] && [ "$v0" != 12.3.0 ]; then
    say "  pillow is ${v0:-unknown}, not the recorded 12.3.0: nothing installed (NOT RUN - Karl decides)"
    echo "NOT RUN: pillow is ${v0:-unknown} before the step, not 12.3.0; nothing changed" >> $PD/RESULT.txt; return 0
  fi
  [ -n "$why" ] && { echo "NOT RUN: $why; nothing changed" >> $PD/RESULT.txt; say "  pillow step NOT RUN: $why"; return 0; }
  timeout 300 nice -n 19 $P -I -m pip install --disable-pip-version-check --no-input --no-deps pillow==13.0.0 >> $PD/pip.txt 2>&1 \
    || why="pip install pillow==13.0.0 failed: $(grep -E 'ERROR|error' $PD/pip.txt | head -1 | cut -c1-160)"
  $P -I -m pip freeze > $PD/freeze-after.txt 2>> $PD/pip.txt
  v1=$($P -I -c "import importlib.metadata as m; print(m.version('pillow'))" 2> /dev/null | tail -1)
  $P -I -B $RU freeze-diff $PD/freeze-before.txt $PD/freeze-after.txt --allow pillow --want pillow==13.0.0 > $PD/freeze-diff.txt 2>&1 \
    || why="${why:+$why; }freeze: $(tail -1 $PD/freeze-diff.txt | cut -c1-200)"
  [ "$v1" = 13.0.0 ] || why="${why:+$why; }pillow is ${v1:-unknown} after the install"
  if [ -z "$why" ]; then
    TMPDIR=$PD/tmp timeout 300 nice -n 19 $P -I -B $RU unittests --tree $W028 --out $PD/unittests.txt > $PD/unittests.line 2>&1 \
      || why="unit tests: $(tail -1 $PD/unittests.line | cut -c1-200)"
    say "  $(tail -1 $PD/unittests.line | cut -c1-200)"
    MPLCONFIGDIR=$PD/mplconfig timeout 120 nice -n 19 $P -I -B $RU mpl-check --out $PD > $PD/mpl.line 2>&1 \
      || why="${why:+$why; }matplotlib: $(tail -1 $PD/mpl.line | cut -c1-200)"
    say "  $(tail -1 $PD/mpl.line | cut -c1-200)"
  fi
  if [ -z "$why" ] && ok_to_go; then   # one picture request through vision: a test server on 8081 from P028x.json's copy
    rm -f $PD/vision.rc
    $LIB/with_server.sh r23dp-vision $VIS_CFG -- "$P -I -B $R17 envcheck $XEXE $VIS_CFG --ngpu 2 --pins --gate env_vision --gates $G; $P -I -B $RU vision-check http://127.0.0.1:8081 --out $PD > $PD/vision.line 2>&1; echo \$? > $PD/vision.rc" 8>&- 9>&- 2>&1 \
      | grep -E "engine pid [0-9]+:|ENV CHECK|ready|exited|refus|Error|GUARD|Traceback" | tee -a $S
    sed "s/^/  /" $PD/vision.line 2> /dev/null | tee -a $S
    rc=$(cat $PD/vision.rc 2> /dev/null || echo none)
    if [ "$rc" != 0 ]; then
      if [ -s $PD/vision.line ]; then why="vision (rc $rc): $(grep -E 'FAIL|Error' $PD/vision.line | head -1 | cut -c1-200)"
      else why="vision: no answer from the test server (rc $rc; see the summary)"; fi
    fi
    kc pillow-vision
  elif [ -z "$why" ]; then why="vision check not run (deadline or kernel check)"; fi
  if [ -z "$why" ]; then
    { echo "# strata-compare/.venv - pip freeze after pillow 13.0.0 (Karl 11-05; work/r23/gap-decpath.sh step 1b, $(date '+%F %T')): unit tests, matplotlib and vision passed"
      cat $PD/freeze-after.txt; } > $WS/requirements.lock.txt
    echo "PASS: pillow 13.0.0 installed (only pillow changed), unit tests + matplotlib + vision (JPEG, PNG) passed; pinned in requirements.lock.txt ($(( ($(date +%s) - t0) / 60 )) min)" >> $PD/RESULT.txt
    say "  pillow 13.0.0: PASS, pinned in requirements.lock.txt"
    return 0
  fi
  if [ "$v1" = 12.3.0 ] && $P -I -B $RU freeze-diff $PD/freeze-before.txt $PD/freeze-after.txt --allow pillow > /dev/null 2>&1; then
    echo "NOT CHANGED (still 12.3.0, freeze = before): $why" >> $PD/RESULT.txt
    say "  pillow 13.0.0 not installed, nothing changed (still 12.3.0): $why"; return 0
  fi
  say "  pillow 13.0.0 FAILED ($why) - rolling back to 12.3.0"
  timeout 300 nice -n 19 $P -I -m pip install --disable-pip-version-check --no-input --no-deps pillow==12.3.0 > $PD/rollback.txt 2>&1; rc=$?
  $P -I -m pip freeze > $PD/freeze-rollback.txt 2>> $PD/rollback.txt
  if [ $rc = 0 ] && $P -I -B $RU freeze-diff $PD/freeze-before.txt $PD/freeze-rollback.txt --allow pillow > $PD/freeze-diff-rollback.txt 2>&1; then
    echo "ROLLED BACK to 12.3.0 (freeze = before): $why" >> $PD/RESULT.txt
    say "  ROLLED BACK to pillow 12.3.0 (pip freeze = before): $why"
  else
    echo "ROLLBACK INCOMPLETE (pip rc $rc; $(tail -1 $PD/freeze-diff-rollback.txt 2> /dev/null | cut -c1-200)) after: $why - .venv needs a look" >> $PD/RESULT.txt
    say "  ROLLBACK INCOMPLETE (pip rc $rc) after: $why - .venv needs a look (Karl decides)"
  fi
  return 0
}

after_gap() {   # CPU only, nice 19, 8080 back: compare, the merged decide-b, decide
  local i rc extra=""
  say "after the gap (CPU, nice 19, $NT BLAS threads): compare, decide"
  for i in $(seq 60); do [ "$(memavail)" -ge $MEM_GB ] && break; sleep 10; done   # one offline head (~3.5 GB) above the 12 GB floor
  if ls $RB/cold-*.jsonl > /dev/null 2>&1; then
    $P -I -B $RU merge-b --gap-b $GB --rerun $RB --merged $O/decb-merged 2>&1 | tee -a $S
    if $P -I -B $DR decide-b $O/decb-merged --a $GA > /dev/null 2>&1 && [ -f $O/decb-merged/decision.txt ]; then
      { echo "decode gap b with this gap's rerun of its failed Basalt arm-passes ($(date '+%F %T'); merged records in decb-merged/; gap b's own files unchanged)"
        cat $O/decb-merged/decision.txt; } > $O/decision-b-merged.txt
      grep -E "^=> item|bp90" $O/decision-b-merged.txt | sed "s/^/  /" | tee -a $S
    else say "decode_rules.py decide-b on the merged data failed - by hand: $DR decide-b $O/decb-merged --a $GA"; fi
  fi
  if [ "$(memavail)" -lt $MEM_GB ]; then
    say "MemAvailable $(memavail) GB < $MEM_GB after 10 min: compare NOT run - by hand later ($RU compare --dec $GD/dec --json $GD/result.json --rows-out $GD/rows.tsv --threads $NT)"
  elif ok_arm dec; then
    ok_arm dec1 && extra="$extra --dec1 $GD/dec1"
    ok_arm s210dec && extra="$extra --stock $GD/s210dec"
    say "compare: the prompt variants' rows against the decode path (dec)${extra:+, with$extra}"
    nice -n 19 $P -I -B $RU compare --dec $GD/dec $extra --json $GD/result.json --rows-out $GD/rows.tsv --threads $NT > $GD/compare.txt 2>&1; rc=$?
    if [ $rc = 0 ] && [ -s $GD/result.json ]; then gate compare PASS "result.json, rows.tsv"
    else gate compare FAIL "rc $rc: $(tail -2 $GD/compare.txt | tr '\n' ' ' | cut -c1-200)"; fi
  else say "not compared: the dec arm did not run cleanly"; fi
  rm -f $O/decision.txt
  $P -I -B $RU decide $O --result $GD/result.json > /dev/null 2>&1
  if [ -f $O/decision.txt ]; then
    cat $O/decision.txt >> $S
    grep -E "^=>|^\[|pp16k|pp64k|pillow" $O/decision.txt | head -30 | sed "s/^/  /"
  else say "decpath_rules.py decide failed - rerun it by hand ($RU decide $O --result $GD/result.json)"; fi
}
end_gap() {
  if [ $KFAIL = 1 ]; then
    say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"
    $P -I -B $RU decide $O --result $GD/result.json > /dev/null 2>&1 || true; exit 3
  fi
  say "P028x back on 8080 (port_gap4.sh end) - nothing switched"
  if ! $KR/port_gap4.sh end 8>&- 9>&- 2>&1 | tee -a $S; then
    say "port_gap4.sh end FAILED: 8080 and the research queue need a look"; exit 4
  fi
  kc end || { say "the kernel check failed after P028x came back: Karl decides"; exit 3; }
  say "decode-path gap: $(( ($(date +%s) - T0) / 60 )) min with 8080 down"
  after_gap
  say "decode-path gap done"
  exit 0
}

# ================================================================ before the gap (no GPU; 8080 untouched)
say "start attempt: work/r23/gap-decpath.sh (pre-gap checks)"
preflight
[ -f $WS/tmp/r19/kwatch.pid ] && kill -0 "$(cat $WS/tmp/r19/kwatch.pid)" 2> /dev/null || { say "the kernel-log watcher is not running - not started"; exit 1; }
for f in $X_CFG $ST_CFG $RU $DR $R17 $KR/port_gap4.sh $KR/pf_yardstick.py $LIB/guard.py $LIB/kcheck.sh $LIB/with_server.sh \
         $B90/bp90_client.py $WS/work/r23/nll-many/score.py $WS/work/r23/nll_rules.py $W028/serve/server.py \
         $WS/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf; do
  [ -f $f ] || { say "missing $f - not started"; exit 1; }
done
[ -x $XEXE ] && [ "$(sha12 $XEXE)" = $P028X_SHA ] || { say "engine-r22p028x is not P028x ($P028X_SHA) - not started"; exit 1; }
PRE=$($P -I -B $RU pre 2>&1); [ $? = 0 ] || { say "REFUSED: $(echo "$PRE" | tail -1 | cut -c1-400) - not started"; exit 1; }
CFC=$($P -I -B $RU configs --check 2>&1); [ $? = 0 ] || { say "REFUSED: $(echo "$CFC" | tail -1 | cut -c1-400) - not started"; exit 1; }
[ -x $TEXE ] && [ "$(sha12 $TEXE)" = $TWIN_SHA ] && [ "$(cut -c1-12 $WS/engine-r22p028xm/SHA256 2> /dev/null)" = $TWIN_SHA ] && TWIN_OK=1
[ -x $SEXE ] && [ "$(sha12 $SEXE)" = $STOCK_SHA ] && STOCK_OK=1
CHK=$($P -I -B $DR check-a $GA 2>&1) && SHA_A=$(echo "$CHK" | sed -n 's/^SHA //p') && [ -x $E23 ] && [ "$(sha12 $E23)" = "$SHA_A" ] \
  && [ -f $GC/r23-B.json ] && [ -f $GC/r23-LO.json ] && [ -f $W23/serve/server.py ] && B23_OK=1
free=$(df --output=avail -B1G $WS/results | tail -1 | tr -d ' ')
[ "${free:-0}" -ge 20 ] || { say "only ${free} GB free on results/ - not started"; exit 1; }
PREV=""
if [ -e $GD ] || [ -e $O/decision.txt ] || [ -e $PD ] || [ -e $RB ] || [ -e $O/decb-merged ]; then   # the rules judge only this attempt's files
  PREV=$O/prev-$(date +%m%d-%H%M%S); mkdir -p $PREV
  for f in $GD $PD $RB $O/decb-merged $O/decision.txt $O/decision.json $O/decision-b-merged.txt; do [ -e $f ] && mv $f $PREV/; done
fi
mkdir -p $GD $SO $PD $RB
S=$GD/summary.txt
say "DECODE-PATH CHECK (work/r23/gap-decpath.sh): the prompt variants against the decode path, by prompt length - measurements only, P028x stays served, nothing switches (Karl 11-05)"
[ -n "$PREV" ] && say "an earlier attempt's outputs moved to $PREV"
gate pre PASS "$(echo "$PRE" | tail -1 | cut -c1-500)"
gate configs PASS "$(echo "$CFC" | tail -1 | cut -c1-300)"
say "optional engines: twin (1-row windows) $([ $TWIN_OK = 1 ] && echo ok || echo 'NOT as recorded - dec1 skipped'); stock $([ $STOCK_OK = 1 ] && echo ok || echo 'NOT as recorded - s210dec skipped'); engine-r23decode $([ $B23_OK = 1 ] && echo 'is the part-a build' || echo 'is NOT the part-a build - the bp90 rerun is skipped')"

# ================================================================ the gap
$KR/port_gap4.sh begin "r23 decode-path check (Karl 11-05: the prompt variants against the decode path, + prompt speed; measurements only, P028x stays served, nothing switches)" 8>&- 9>&- 2>&1 | tee -a $S
[ -s $WS/tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
echo "$T0 $(date -Is)" > $GD/t0.txt
wait_mem
kc open || end_gap

pillow_step                          # 1b: cannot fail the gap (a kernel-check failure after its test server still counts)
ok_to_go || end_gap

BM=$(( $(left) / 60 - 20 )); [ $BM -gt $DEC_MIN ] && BM=$DEC_MIN
if [ $BM -ge 10 ]; then
  say "2 arm dec: the decode path (x28h, 2-row verify windows, STRATA_LOGPOS top 64), budget $BM min ($(( $(left) / 60 )) min to the deadline)"
  decarm dec $X_CFG logpos main $BM
else say "2 arm dec NOT run: only $(( $(left) / 60 )) min to the deadline (it needs 30: 10 for the arm, 20 kept for the end)"; fi

if fits 14; then
  say "3 prompt speed, cold, pp16k + pp64k, P028x as served / PF_FUSED=0 / CPU share 0, 2 passes in turned order"
  for k in 1 2; do
    case $k in 1) order="def unf sh0";; 2) order="sh0 unf def";; esac
    for arm in $order; do for set in pp16k pp64k; do spdrun $arm $set $k; done; done
  done
else say "3 prompt speed not started (14 min do not fit before the deadline, or a stop)"; fi

if [ $TWIN_OK = 1 ] && fits 9; then
  say "4 arm dec1: 1-row windows (engine-r22p028xm, force=N + STRATA_FORCE_T1=1) on ldrsyn20k"
  decarm dec1 $TW_CFG force t1 7 STRATA_FORCE_T1=1
else say "4 arm dec1 not started (twin not as recorded, 9 min do not fit, or a stop)"; fi

if [ $STOCK_OK = 1 ] && fits 9; then
  say "5 arm s210dec: stock v0.2.10's decode path (s0210-h) on ldrsyn20k"
  decarm s210dec $ST_CFG logpos stock 7
else say "5 arm s210dec not started (stock engine not as recorded, 9 min do not fit, or a stop)"; fi

MISS=$($P -I -B $RU bp90-missing --bp90 $GB/bp90 2>&1)
NM=$(echo "$MISS" | grep -c '^MISSING')
if [ $B23_OK = 1 ] && [ $NM -gt 0 ] && fits $(( NM * 3 / 2 + 2 )); then
  say "6 decode gap b's failed Basalt arm-passes, rerun ($NM): $(echo "$MISS" | grep '^MISSING' | cut -d' ' -f2- | tr '\n' ',' ) $(echo "$MISS" | grep '^INFO' | cut -c6-)"
  echo "$MISS" > $RB/missing.txt
  mapfile -t ML < <(echo "$MISS" | grep '^MISSING')   # (read first: nothing in a test server's tree may eat the list)
  for x in "${ML[@]}"; do read -r _ b set k <<< "$x"; fits 2 && bprerun $b $set $k < /dev/null; done
else say "6 the bp90 rerun not started ($NM missing; engine-r23decode $([ $B23_OK = 1 ] && echo ok || echo 'is not the part-a build'); or it does not fit)"; fi

end_gap
