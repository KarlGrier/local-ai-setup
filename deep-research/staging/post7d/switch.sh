#!/bin/bash
# switch.sh [--check] [--no-wait] [--between SCRIPT] FROM TO - point the bench queue at the next plan once the current
# one has finished (staged 11-04, staging/post7d; NOT run, NOT installed - Karl OKs the switch).
#   FROM, TO   plan file names in results/bench2/ (as BENCH2_PLAN), e.g. queue-plan-7d.json queue-plan-item8.json
#   --check    every check below that can be made now, read-only (no wait, no kcheck log line, no install, no switch)
#   --no-wait  do not wait: FROM must be finished already
#   --between SCRIPT  run SCRIPT (bash) after FROM has finished and before the switch; the switch only on its exit 0
#              (install-ldr-fixes.sh between queue-plan-7d.json and queue-plan-p4s9.json; replays.sh between
#              queue-plan-item8.json and queue-plan-c3c.json)
# 11-04 (Karl): while tmp/bench2.hold exists (a phase-4 gap holds the queue) it waits before the between script and
# before the switch; the between scripts wait for it themselves too.
# Waits (polling every 2 min; staging/post7d/STOP-switch ends the wait) until FROM is finished: the unit
# deep-research-bench.service is inactive AND `bench2.py next` on FROM says "done" (file state: every run has
# bench.json) AND logs/bench2-queue.log has "queue finished (FROM)". A queue that stopped for another reason (a
# Strata release flag, the watchdog's second hang, three search failures, tmp/bench2.stop) is not "done": the wait goes
# on (one desktop notice) until the queue is started again and finishes.
# Then: the between script; strata-compare's kernel check; the unit must still be on FROM; TO's checks
# (tools/plan_check.py: sets, ids, items, routes, profiles, no run done already; `next --wide` gives a run); what TO
# needs first:
#   queue-plan-c3c.json         profiles/flash-next-c3c.env from staging/post7d/profiles/ (new file; refused if a
#                               different one is there)
#   queue-plan-p5-holdout.json  staging/post7d/GO-p5 whose first word is the sha256 of the plan file (Karl's OK on
#                               exactly that plan, after his adoption calls; in wait mode the wait also waits for it);
#                               p5.py check-engine + check-frozen (staging/post7d/phase5/p5.json); tools/bench2.py <-
#                               staging/post7d/tools/bench2.py (sets p5-harder / p5-o01) under run/bench.lock, only if
#                               the live file is still the one it was based on (bench2.py.orig; backup
#                               tools/bench2.py.before-p5); p5.py swap-mark
# The switch: unit file backed up to tools/deep-research-bench.service.before-<tag> (tag = TO without queue-plan- /
# .json), BENCH2_PLAN and Description rewritten (new file + mv), daemon-reload, start; then verified: unit active, its
# MainPID = the queue's "queue started (pid N)" line, and the first "<run>: running" line (up to $VERIFY_MIN = 45 min;
# a hold file / Jan job / bench lock wait in between is reported, not an error). One line in NOTES.md, a desktop
# notice. Log: logs/post7d-switch.log.
set -u
WS=/home/USER/ai/deep-research
S=$WS/staging/post7d
B=$WS/results/bench2
UNIT_NAME=deep-research-bench.service
UNIT=$HOME/.config/systemd/user/$UNIT_NAME
QLOG=$WS/logs/bench2-queue.log
LOG=${SWITCH_LOG:-$WS/logs/post7d-switch.log}
KC=/home/USER/ai-speed-testing/strata-compare/bringup/lib/kcheck.sh
KDIR=/home/USER/ai-speed-testing/strata-compare/tmp/r19
PY=$WS/.venv/bin/python
STOP=$S/STOP-switch
VERIFY_MIN=${VERIFY_MIN:-45}

CHECK=0; NOWAIT=0; BETWEEN=""
while [ $# -gt 0 ]; do
  case $1 in
    --check) CHECK=1; shift ;;
    --no-wait) NOWAIT=1; shift ;;
    --between) BETWEEN=$2; shift 2 ;;
    -*) echo "unknown option $1"; exit 2 ;;
    *) break ;;
  esac
done
[ $# -eq 2 ] || { echo "usage: switch.sh [--check] [--no-wait] [--between SCRIPT] FROM TO"; exit 2; }
FROM=$1; TO=$2
TAG=${TO#queue-plan-}; TAG=${TAG%.json}
case $TAG in
  p4s9)       DESC="fresh baseline since $(date +%m-%d): $TO - p4s8's setup + the subagent step fix (fix:steps), o01-o03, SearXNG only" ;;
  item8)      DESC="item 8 stage 2 since $(date +%m-%d): $TO - o01 + o03, three 62-min runs each (p8a / p8b / p8c), SearXNG only" ;;
  c3c)        DESC="C3c since $(date +%m-%d): $TO - o01-o03 on model profile flash-next-c3c (pc3c), SearXNG only" ;;
  p5-holdout) DESC="Phase 5 holdout since $(date +%m-%d): $TO - baseline p5 + final p5final; o04-o06, the harder four, the 25 checkables" ;;
  *)          DESC="since $(date +%m-%d): $TO" ;;
esac
DESC="Deep research measurements ($DESC; ~/ai/deep-research/tools/bench2-queue.sh)"

say() { echo "$(date '+%F %T') switch $FROM -> $TO: $*" | tee -a "$LOG"; }
notice() { [ $CHECK = 1 ] || notify-send -a "Deep research" $1 "$2" "$3" 2> /dev/null || true; }
die() { say "NOT SWITCHED: $*"; notice "-u critical" "Bench queue not switched to $TO" "$*"; exit 1; }
plan_next() { BENCH2_PLAN=$1 "$PY" -I -B "$WS/tools/bench2.py" next ${2:-} 2>&1; }
cur_plan() { sed -n 's/^Environment=BENCH2_PLAN=//p' "$UNIT"; }
finished() {   # FROM finished: unit inactive, every run done, the queue's own end line
  ! systemctl --user is-active -q $UNIT_NAME && [ "$(plan_next "$FROM")" = done ] && grep -qF "queue finished ($FROM)" "$QLOG"
}
kcheck_ro() {  # kcheck.sh's tests without its log line (for --check)
  local t bad; t=$(cat /proc/sys/kernel/tainted); bad=$(( t & (128 | 16 | 32 | 16384 | 512) ))
  [ -f $KDIR/KERNEL_ERROR ] && { echo "kernel error flag: $(head -c 200 $KDIR/KERNEL_ERROR)"; return 1; }
  [ $bad -ne 0 ] && { echo "tainted $t (bits $bad)"; return 1; }
  { [ -f $KDIR/kwatch.pid ] && kill -0 "$(cat $KDIR/kwatch.pid)" 2> /dev/null; } || { echo "kernel-log watcher not running"; return 1; }
  echo "ok (tainted $t)"
}
wait_hold() {  # Karl 11-04: never collide with a phase-4 gap - while tmp/bench2.hold exists, wait
  local n=0; while [ -e "$WS/tmp/bench2.hold" ]; do
    [ $n = 0 ] && say "hold file present ($(head -c 160 "$WS/tmp/bench2.hold" 2> /dev/null)) - waiting before $1"; n=1
    [ -e "$STOP" ] && { say "STOP-switch present - stopped (nothing changed)"; exit 3; }; sleep 60; done
  [ $n = 1 ] && say "hold released - going on with $1"; return 0
}
go_ok() {      # Phase 5 only: GO-p5's first word = sha256 of the plan as it is now
  [ -s "$S/GO-p5" ] && [ "$(awk 'NR == 1 {print $1}' "$S/GO-p5")" = "$(sha256sum < "$B/$TO" | cut -d' ' -f1)" ]
}

# -- one switch at a time ------------------------------------------------------------------------------------------
exec 6> "$S/switch.lock"
flock -n 6 || { echo "another switch.sh holds staging/post7d/switch.lock"; exit 1; }
say "start (pid $$)$([ $CHECK = 1 ] && echo ' - CHECK ONLY: nothing is changed')"

# -- what can be checked before FROM ends --------------------------------------------------------------------------
[ -e "$B/$FROM" ] || die "no plan results/bench2/$FROM"
[ -e "$B/$TO" ] || die "no plan results/bench2/$TO"
if [ "$(cur_plan)" != "$FROM" ]; then
  [ $CHECK = 1 ] || die "the unit runs BENCH2_PLAN=$(cur_plan), not $FROM"
  say "note (check only): the unit runs BENCH2_PLAN=$(cur_plan) now; at switch time it must run $FROM"
fi
[ -z "$BETWEEN" ] || bash -n "$BETWEEN" || die "the between script $BETWEEN does not parse"
P2=$WS/tools/bench2.py; PDIR=$WS/profiles; NEED_B2=0; NEED_PROF=0
case $TAG in
  c3c)
    if [ -e "$WS/profiles/flash-next-c3c.env" ]; then
      cmp -s "$WS/profiles/flash-next-c3c.env" "$S/profiles/flash-next-c3c.env" || die "profiles/flash-next-c3c.env exists and differs from the staged one"
    else NEED_PROF=1; PDIR=$S/profiles; fi
    env -i HOME=$HOME PATH=/usr/bin:/bin "$PY" -I -B "$WS/.venv/lib/python3.12/site-packages/local_deep_research/deep/modelprofile.py" \
      --check "$S/profiles/flash-next-c3c.env" >> "$LOG" 2>&1 || die "the C3c profile does not pass modelprofile.py --check" ;;
  p5-holdout)
    if ! cmp -s "$WS/tools/bench2.py" "$S/tools/bench2.py"; then
      cmp -s "$WS/tools/bench2.py" "$S/tools/bench2.py.orig" \
        || die "tools/bench2.py changed since staging/post7d/tools/bench2.py was based on it - re-base the p5 hunks (diff bench2.py.orig bench2.py)"
      NEED_B2=1; P2=$S/tools/bench2.py
    fi
    "$PY" -I -B "$WS/staging/phase5/p5.py" --config "$S/phase5/p5.json" check-frozen >> "$LOG" 2>&1 || die "p5.py check-frozen failed" ;;
esac
# 11-04: plans name the step fix "fix:steps"; until install-ldr-fixes.sh has run, only the staged bench2-queue.sh knows it
QF=$WS/tools/bench2-queue.sh; grep -qF '*,fix:steps,*)' "$QF" || QF=$S/tools/bench2-queue.sh
"$PY" -I -B "$S/tools/plan_check.py" --bench2 "$P2" --profiles-dir "$PDIR" --queue "$QF" "$TO" >> "$LOG" 2>&1 || die "tools/plan_check.py found problems in $TO (see $LOG)"
FIRST=$(plan_next "$TO" --wide); case $FIRST in done|wait|"") die "$TO gives no run ($FIRST)";; esac
say "checks so far ok: $TO's first run: $FIRST$([ $NEED_PROF = 1 ] && echo '; will install profiles/flash-next-c3c.env')$([ $NEED_B2 = 1 ] && echo '; will install tools/bench2.py (p5 sets)')"
if [ $CHECK = 1 ]; then
  say "FROM state: unit $(systemctl --user is-active $UNIT_NAME), next on $FROM: $(plan_next "$FROM" --wide), finished: $(finished && echo yes || echo no)"
  say "kernel (read-only): $(kcheck_ro)"
  [ $TAG = p5-holdout ] && say "GO-p5 for this plan: $(go_ok && echo yes || echo 'no (needed before the switch)')"
  say "check only: done (a real run waits for $FROM, runs ${BETWEEN:-no between script}, then switches)"
  exit 0
fi

# -- wait for FROM to finish (and, for Phase 5, Karl's GO on this plan) -----------------------------------------------
told=0
until finished && { [ $TAG != p5-holdout ] || go_ok; }; do
  [ $NOWAIT = 1 ] && die "$FROM is not finished$([ $TAG = p5-holdout ] && ! go_ok && echo ' / no GO-p5 for this plan')"
  [ -e "$STOP" ] && { say "STOP-switch present - stopped waiting (nothing changed)"; exit 3; }
  if [ $told = 0 ]; then
    say "waiting for $FROM to finish$([ $TAG = p5-holdout ] && echo ' and for GO-p5 (Karl) on this plan')"; told=1
  elif [ $told = 1 ] && ! systemctl --user is-active -q $UNIT_NAME && [ "$(plan_next "$FROM")" != done ]; then
    say "the queue stopped before $FROM was done (last line: $(tail -1 "$QLOG" | cut -c1-200)) - still waiting"
    notice "-u normal" "Bench queue stopped early" "$FROM is not done; switch.sh keeps waiting (start $UNIT_NAME again to finish it)"; told=2
  fi
  sleep 120
done
say "$FROM finished: $(grep -F "queue finished ($FROM)" "$QLOG" | tail -1 | cut -c1-19)"

# -- between script -----------------------------------------------------------------------------------------------------
if [ -n "$BETWEEN" ]; then
  wait_hold "the between script"
  say "between: bash $BETWEEN"
  bash "$BETWEEN" 6>&- 7>&- 8>&- 9>&-; rc=$?
  [ $rc = 0 ] || die "the between script ended with rc $rc (see its log)"
  say "between script done"
  finished || die "$FROM is no longer finished after the between script (the unit was started by hand?)"
fi

# -- last checks + what TO needs ------------------------------------------------------------------------------------------
wait_hold "the switch"
[ -e "$WS/tmp/bench2.stop" ] && die "tmp/bench2.stop exists (the queue would stop at once)"
[ "$(cur_plan)" = "$FROM" ] || die "the unit runs BENCH2_PLAN=$(cur_plan) now, not $FROM"
bash "$KC" "post7d-switch-$TAG" >> "$LOG" 2>&1 || die "kernel check failed (strata-compare bringup/lib/kcheck.sh)"
if [ $NEED_PROF = 1 ]; then
  cp -p "$S/profiles/flash-next-c3c.env" "$WS/profiles/flash-next-c3c.env.new" && mv "$WS/profiles/flash-next-c3c.env.new" "$WS/profiles/flash-next-c3c.env" \
    && cmp -s "$S/profiles/flash-next-c3c.env" "$WS/profiles/flash-next-c3c.env" || die "installing profiles/flash-next-c3c.env failed"
  say "installed profiles/flash-next-c3c.env (new file; remove it to undo)"
fi
if [ $TAG = p5-holdout ]; then
  go_ok || die "GO-p5 does not match the plan any more"
  "$PY" -I -B "$WS/staging/phase5/p5.py" --config "$S/phase5/p5.json" check-engine >> "$LOG" 2>&1 || die "p5.py check-engine: 8080 / the promoted config is not p5.json's engine"
  "$PY" -I -B "$WS/staging/phase5/p5.py" --config "$S/phase5/p5.json" check-frozen >> "$LOG" 2>&1 || die "p5.py check-frozen failed"
  if [ $NEED_B2 = 1 ]; then
    exec 7> "$WS/run/bench.lock"
    flock -w 600 7 || die "run/bench.lock busy for 10 min (a replay or Jan job?)"
    cmp -s "$WS/tools/bench2.py" "$S/tools/bench2.py.orig" || die "tools/bench2.py changed meanwhile"
    [ -e "$WS/tools/bench2.py.before-p5" ] && die "tools/bench2.py.before-p5 exists - not overwriting it"
    cp -p "$WS/tools/bench2.py" "$WS/tools/bench2.py.before-p5" || die "backup of tools/bench2.py failed"
    cp -p "$S/tools/bench2.py" "$WS/tools/bench2.py.new-p5" && mv "$WS/tools/bench2.py.new-p5" "$WS/tools/bench2.py" \
      && "$PY" -I -B -c 'import ast, sys; ast.parse(open(sys.argv[1]).read())' "$WS/tools/bench2.py" \
      || { cp -p "$WS/tools/bench2.py.before-p5" "$WS/tools/bench2.py"; die "installing tools/bench2.py failed (the old one is back)"; }
    exec 7>&-
    say "installed tools/bench2.py (p5 sets; backup tools/bench2.py.before-p5)"
  fi
  "$PY" -I -B "$WS/staging/phase5/p5.py" --config "$S/phase5/p5.json" swap-mark >> "$LOG" 2>&1 || say "p5.py swap-mark failed (status will not show the swap change)"
fi
"$PY" -I -B "$S/tools/plan_check.py" "$TO" >> "$LOG" 2>&1 || die "tools/plan_check.py on the live tools found problems in $TO (see $LOG)"

# -- the switch -----------------------------------------------------------------------------------------------------------
BK=$WS/tools/deep-research-bench.service.before-$TAG; [ -e "$BK" ] && BK=$BK-$(date +%m%d-%H%M%S)
cp -p "$UNIT" "$BK" || die "unit backup failed"
/usr/bin/python3 -I - "$UNIT" "$TO" "$DESC" <<'EOF' || die "rewriting the unit file failed (backup $BK)"
import os, sys
unit, plan, desc = sys.argv[1:4]
lines = open(unit).read().splitlines()
out, n = [], 0
for l in lines:
    if l.startswith("Environment=BENCH2_PLAN="):
        l, n = f"Environment=BENCH2_PLAN={plan}", n + 1
    elif l.startswith("Description="):
        l = f"Description={desc}"
    out.append(l)
if n != 1:
    sys.exit(f"{n} BENCH2_PLAN lines")
open(unit + ".new", "w").write("\n".join(out) + "\n")
os.replace(unit + ".new", unit)
EOF
[ "$(cur_plan)" = "$TO" ] || die "the unit file does not say BENCH2_PLAN=$TO after the rewrite (backup $BK)"
systemctl --user daemon-reload
OFF=$(wc -l < "$QLOG")
systemctl --user start $UNIT_NAME || die "systemctl start failed (unit on $TO; backup $BK)"
say "unit on $TO (backup ${BK#$WS/}), started"

# -- verify: active, its pid, the first running line ------------------------------------------------------------------
sleep 5
systemctl --user is-active -q $UNIT_NAME || die "the unit is not active after the start ($(systemctl --user is-active $UNIT_NAME))"
MP=$(systemctl --user show -p MainPID --value $UNIT_NAME)
QP=""; for i in $(seq 30); do QP=$(tail -n +$((OFF + 1)) "$QLOG" | sed -n 's/.* queue started (pid \([0-9]*\)).*/\1/p' | tail -1); [ -n "$QP" ] && break; sleep 2; done
[ -n "$QP" ] && [ "$QP" = "$MP" ] || die "the queue's start line (pid ${QP:-none}) does not match the unit's MainPID $MP"
say "queue running: MainPID $MP = 'queue started (pid $QP)'"
RUN=""; WAITS=""; end=$(( $(date +%s) + VERIFY_MIN * 60 ))
while [ $(date +%s) -lt $end ]; do
  NEW=$(tail -n +$((OFF + 1)) "$QLOG")
  RUN=$(grep -F ': running' <<< "$NEW" | head -1)
  [ -n "$RUN" ] && break
  WAITS=$(grep -E 'hold file: waiting|Jan job|holds run/bench.lock|Strata not ready|LDR start failed|a service is down' <<< "$NEW" | tail -1)
  systemctl --user is-active -q $UNIT_NAME || die "the queue stopped before its first run (last line: $(tail -1 "$QLOG" | cut -c1-200))"
  sleep 20
done
if [ -n "$RUN" ]; then
  say "first run: ${RUN:0:200}"
  RES="first run ${RUN:11:150}"
else
  say "no 'running' line after $VERIFY_MIN min - the queue is active and waiting: ${WAITS:-$(tail -1 "$QLOG" | cut -c1-200)}"
  RES="active, waiting (${WAITS:-see logs/bench2-queue.log})"
fi
echo "* $(date '+%F %H:%M') BENCH PLAN SWITCH (staging/post7d/switch.sh, Karl's OK): $FROM finished -> $UNIT_NAME on $TO (unit backup ${BK#$WS/}); queue pid $MP; $RES." >> "$WS/NOTES.md"
notice "-u normal" "Bench queue on $TO" "$FROM finished; queue pid $MP; $RES"
say "done"
exit 0
