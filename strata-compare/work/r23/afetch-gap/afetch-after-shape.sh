#!/bin/bash
# afetch-after-shape.sh - Karl 11-09 (backlog I): "queue ADAPT_FETCH's gap after the v0.2.13 shape gap"; the priority rule:
# open Qwen4 Flash weights first. Started by Claude as a user unit (no argument):
#   systemd-run --user --unit=afetch-after-shape --description="ADAPT_FETCH gap after the shape gap" /bin/bash <this file>
# 1 refuses (exit 6, an alert) unless work/r23/afetch-gap/gap-afetch.sh.ready (Claude's review) names the current sha256
#   (first 12 hex) of the driver ("sha256 <12>"), afetch_rules.py ("rules <12>", the whole file), sq_client.py ("client
#   <12>") and spec-adaptfetch.json ("spec <12>"), and bash -n passes;
# 2 waits (every 60 s, up to 24 h, then an alert) until the shape gap has RUN (results/r23/port-0213/shape-gap/result.txt
#   starts "DONE": afetch_rules.py shapecheck; a kernel error, a failed end, an interruption, a refusal or a not-run attempt
#   keep it waiting - Karl looks at those first), its unit shape-gap0213 is inactive, and no gap is open
#   (tmp/port-gap.lockpid); then 30 s for its last lines (a research-queue hold that is not this gap's: the driver refuses
#   busy, retried below);
# 3 runs a snapshot copy of the driver (results/r23/run-copies/, cp -p; the snapshot's own sha256 must be the reviewed one)
#   with 8>&- 9>&- and stdin from /dev/null, checking the .ready again before each try. Exit 1 with a fresh "not started"
#   result (busy: a lock, a gap, another model server, the shape gap, an unreadable watch state) -> again 15 min later, for
#   up to 6 h from the first try, then an alert. Exit 8 (the priority rule: held before the gap, or the gap ended early) is
#   FINAL (the driver alerted). Exit 5 (engines still running after 8080 stopped: nothing measured) -> an alert, no retry.
#   Exit 9 (another driver instance runs) -> an alert, no retry. A try that writes no result line (a crash) -> an alert,
#   exit 3, no retry. Any other exit is final (the driver alerts itself).
# Holds no lock; children get no fd 8 / 9. Log: results/r23/adaptfetch/starter.log (the gap's own:
# results/r23/adaptfetch/gap/summary.txt). Exit: the driver's last exit, 6 not reviewed / changed, 1 gave up waiting /
# busy, 3 no result.
# Test overrides (work/r23/afetch-gap/gap-mock-test.sh only; unset in the real run): AFS_DRIVER, AFS_RULES, AFS_CLIENT,
# AFS_SPEC, AFS_SHAPE_RES, AFS_SHAPE_UNIT, AFS_LOCKPID, AFS_LOG, AFS_COPIES, AFS_RESULT, AFS_POLL_S, AFS_RETRY_S,
# AFS_RETRY_FOR_S, AFS_WAIT_SHAPE_S, AFS_SETTLE_S, AFS_NOTIFY, AFS_TEST_CORRUPT_SNAPSHOT.
set -u
exec 8>&- 9>&-
WS=/home/USER/ai-speed-testing/strata-compare; AG=$WS/work/r23/afetch-gap
DRV=${AFS_DRIVER:-$AG/gap-afetch.sh}; RULES=${AFS_RULES:-$AG/afetch_rules.py}
CLIENT=${AFS_CLIENT:-$WS/work/r23/sampled-qwen/sq_client.py}; SPECF=${AFS_SPEC:-$WS/work/r23/sampled-qwen/spec-adaptfetch.json}
SHAPE_RES=${AFS_SHAPE_RES:-$WS/results/r23/port-0213/shape-gap/result.txt}; SHAPE_UNIT=${AFS_SHAPE_UNIT:-shape-gap0213}
LOCKPID=${AFS_LOCKPID:-$WS/tmp/port-gap.lockpid}
LOG=${AFS_LOG:-$WS/results/r23/adaptfetch/starter.log}; COPIES=${AFS_COPIES:-$WS/results/r23/run-copies}
RESULT=${AFS_RESULT:-$WS/results/r23/adaptfetch/gap/result.txt}
POLL=${AFS_POLL_S:-60}; RETRY_S=${AFS_RETRY_S:-900}; RETRY_FOR_S=${AFS_RETRY_FOR_S:-21600}; WAIT_SHAPE_S=${AFS_WAIT_SHAPE_S:-86400}
SETTLE=${AFS_SETTLE_S:-30}; NOTIFY=${AFS_NOTIFY:-notify-send}
P=$WS/.venv/bin/python
mkdir -p $(dirname $LOG) $COPIES
say() { echo "$(date '+%F %T') afetch-after-shape: $*" >> $LOG; }
alert() { say "ALERT: $1 - $2"; $NOTIFY -a "Strata gaps" -u critical "$1" "$2" 2> /dev/null || say "(notify-send failed)"; }
sha12() { sha256sum "$1" | cut -c1-12; }
named() { grep -qE "$1 $(sha12 $2)([^0-9a-f]|$)" "$DRV.ready"; }   # named KEY FILE: the .ready names FILE's current sha under KEY
ready_ok() { [ -f "$DRV.ready" ] && bash -n "$DRV" 2> /dev/null && named sha256 $DRV && named rules $RULES && named client $CLIENT \
             && named spec $SPECF; }
shape_ran() { nice -n 19 $P -I -B $RULES shapecheck --result $SHAPE_RES 8>&- 9>&- < /dev/null 2>&1 | tail -1; return ${PIPESTATUS[0]}; }
shape_active() { systemctl --user is-active -q $SHAPE_UNIT 2> /dev/null; }
gap_open() { [ -s $LOCKPID ] && kill -0 "$(cat $LOCKPID)" 2> /dev/null; }

say "start (pid $$): driver $DRV; waiting for the v0.2.13 shape gap's result and for no gap being open"
ready_ok || { alert "ADAPT_FETCH gap not started" "the review file does not name the current sha256 of the driver, the rules, the sampled client and the spec (or bash -n fails); nothing started"; exit 6; }
t0=$(date +%s); n=0
while :; do
  SR=$(shape_ran); src=$?
  [ $src = 0 ] && ! shape_active && ! gap_open && break
  if [ $(( $(date +%s) - t0 )) -ge $WAIT_SHAPE_S ]; then
    alert "ADAPT_FETCH gap not started" "the shape gap had not run to an end, or a gap stayed open, after $(( WAIT_SHAPE_S / 3600 )) h of waiting; nothing started"
    exit 1
  fi
  n=$((n + 1)); [ $((n % 30)) = 1 ] && say "waiting ($(( ($(date +%s) - t0) / 60 )) min): $SR; shape unit $(shape_active && echo active || echo 'not active'); a gap open: $(gap_open && echo yes || echo no)"
  sleep $POLL
done
say "the shape gap has run ($SR); no gap open - starting in $SETTLE s"
sleep $SETTLE
first=$(date +%s); try=0
while :; do
  try=$((try + 1))
  ready_ok || { alert "ADAPT_FETCH gap not started" "the driver, the rules, the sampled client or the spec changed after the review (try $try); nothing started"; exit 6; }
  snap=$COPIES/gap-afetch-$(date +%m%d-%H%M%S).sh; cp -p "$DRV" "$snap"
  [ "${AFS_TEST_CORRUPT_SNAPSHOT:-0}" = 1 ] && echo "# (test: the snapshot changed)" >> "$snap"
  grep -qE "sha256 $(sha12 "$snap")([^0-9a-f]|$)" "$DRV.ready" || { alert "ADAPT_FETCH gap not started" "the driver's snapshot is not the reviewed file (try $try); nothing started"; exit 6; }
  say "try $try: running the snapshot $snap (reviewed: $(head -c 200 "$DRV.ready" | tr '\n' ' '))"
  tt=$(date +%s)
  bash "$snap" 8>&- 9>&- < /dev/null >> $LOG 2>&1; rc=$?
  if [ $rc = 9 ]; then
    alert "ADAPT_FETCH gap not started" "another ADAPT_FETCH driver is running (its pid file is in tmp/); this one touched nothing - check what started it"
    exit 9
  fi
  fresh=0; [ -f $RESULT ] && [ $(stat -c %Y $RESULT) -ge $tt ] && fresh=1
  say "try $try: exit $rc ($([ $fresh = 1 ] && head -1 $RESULT | cut -c1-240 || echo 'NO result line from this try'))"
  if [ $fresh = 0 ]; then
    alert "ADAPT_FETCH gap: no result" "the driver ended (exit $rc) without a result line - it may have crashed; check the gap's summary and tmp/port-gap.lockpid before anything else"
    exit 3
  fi
  case $rc in
    1) if head -1 $RESULT | grep -q '^not started'; then
         if [ $(( $(date +%s) - first + RETRY_S )) -gt $RETRY_FOR_S ]; then
           alert "ADAPT_FETCH gap not started" "the PC stayed busy for $(( RETRY_FOR_S / 3600 )) h of retries (a test lock, a gap, another model server, or the shape gap); nothing changed"
           exit 1
         fi
         say "busy: the next try in $(( RETRY_S / 60 )) min"; sleep $RETRY_S; continue
       fi
       alert "ADAPT_FETCH gap: not run" "the driver ended with exit 1 after the gap had opened ($(head -1 $RESULT | cut -c1-100)); no retry"
       exit 1;;
    5) alert "ADAPT_FETCH gap not run" "engine processes were still running after 8080 stopped: nothing was measured, P028x is back; no retry"
       exit 5;;
    8) say "the priority rule (final; the driver alerted): no retry - the day-one work goes first"; exit 8;;
    *) say "done (exit $rc): no retry"; exit $rc;;
  esac
done
