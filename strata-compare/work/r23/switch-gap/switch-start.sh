#!/bin/bash
# switch-start.sh - the starter of the v0.2.13 switch-check gap (Karl 11-10; work/r23/switch-gap/gap-switch0213.sh; the form
# of work/r23/afetch-gap/afetch-after-shape.sh, reviewed 11-09). Started by Claude as a user unit (no argument):
#   systemd-run --user --unit=switch-gap0213 --description="v0.2.13 switch checks" /bin/bash <this file>
# 1 refuses (exit 6, an alert) unless work/r23/switch-gap/gap-switch0213.sh.ready (Claude's review) names the current
#   sha256 (first 12 hex) of the driver ("sha256 <12>"), switch_rules.py ("rules <12>"), c2_client.py ("c2 <12>"),
#   c4_web.py ("c4 <12>"), fixtures_client.py ("fx <12>"), spec-port0213.json ("spec <12>"), the harness's sq.py ("sq
#   <12>"), sq_client.py ("client <12>") and sq_stat.py ("stat <12>"), and this starter itself ("starter <12>", review
#   M8), and bash -n passes;
# 2 waits (every 60 s, up to 24 h, then an alert) until the build unit build-p0213-switch is inactive and no gap is open
#   (tmp/port-gap.lockpid); then 30 s;
# 3 runs a snapshot copy of the driver (results/r23/run-copies/, cp -p; the snapshot's own sha256 must be the reviewed
#   one) with 8>&- 9>&- and stdin from /dev/null, checking the .ready again before each try. Exit 1 with a fresh "not
#   started" result (busy: a lock, a gap, another model server, the build unit, an unreadable watch state) -> again 15 min
#   later, for up to 6 h from the first try, then an alert. Exit 8 (the priority rule) is FINAL (the driver alerted). Exit
#   5 (engines still running after 8080 stopped) -> an alert, no retry. Exit 9 (another driver instance) -> an alert, no
#   retry. A try that writes no result line (a crash) -> an alert, exit 3, no retry. Any other exit is final (the driver
#   alerts itself; a pre-gap C1 failure no longer stops the gap: it is C1 FAIL in the decision).
# Holds no lock; children get no fd 8 / 9. Log: results/r23/port-0213/switch-starter.log (the gap's own:
# results/r23/port-0213/switch-gap/summary.txt). Exit: the driver's last exit, 6 not reviewed / changed, 1 gave up
# waiting / busy, 3 no result.
# Test overrides (work/r23/switch-gap/gap-mock-test.sh only; unset in the real run): SWS_DRIVER, SWS_RULES, SWS_C2, SWS_C4,
# SWS_FX, SWS_SPEC, SWS_SQ, SWS_CLIENT, SWS_STAT, SWS_STARTER, SWS_BUILD_UNIT, SWS_LOCKPID, SWS_LOG, SWS_COPIES, SWS_RESULT, SWS_POLL_S,
# SWS_RETRY_S, SWS_RETRY_FOR_S, SWS_WAIT_S, SWS_SETTLE_S, SWS_NOTIFY, SWS_TEST_CORRUPT_SNAPSHOT.
set -u
exec 8>&- 9>&-
WS=/home/USER/ai-speed-testing/strata-compare; SG=$WS/work/r23/switch-gap; Q=$WS/work/r23/sampled-qwen
DRV=${SWS_DRIVER:-$SG/gap-switch0213.sh}; RULES=${SWS_RULES:-$SG/switch_rules.py}; C2=${SWS_C2:-$SG/c2_client.py}
C4=${SWS_C4:-$SG/c4_web.py}; FX=${SWS_FX:-$SG/fixtures_client.py}; SPECF=${SWS_SPEC:-$SG/spec-port0213.json}
SQF=${SWS_SQ:-$Q/sq.py}; CLIENT=${SWS_CLIENT:-$Q/sq_client.py}; STATF=${SWS_STAT:-$Q/sq_stat.py}
SELF=${SWS_STARTER:-$(readlink -f "$0")}   # (review M8) the starter checks its own sha too
BUILD_UNIT=${SWS_BUILD_UNIT:-build-p0213-switch}; LOCKPID=${SWS_LOCKPID:-$WS/tmp/port-gap.lockpid}
LOG=${SWS_LOG:-$WS/results/r23/port-0213/switch-starter.log}; COPIES=${SWS_COPIES:-$WS/results/r23/run-copies}
RESULT=${SWS_RESULT:-$WS/results/r23/port-0213/switch-gap/result.txt}
POLL=${SWS_POLL_S:-60}; RETRY_S=${SWS_RETRY_S:-900}; RETRY_FOR_S=${SWS_RETRY_FOR_S:-21600}; WAIT_S=${SWS_WAIT_S:-86400}
SETTLE=${SWS_SETTLE_S:-30}; NOTIFY=${SWS_NOTIFY:-notify-send}
mkdir -p $(dirname $LOG) $COPIES
say() { echo "$(date '+%F %T') switch-start: $*" >> $LOG; }
alert() { say "ALERT: $1 - $2"; $NOTIFY -a "Strata gaps" -u critical "$1" "$2" 2> /dev/null || say "(notify-send failed)"; }
sha12() { sha256sum "$1" | cut -c1-12; }
named() { grep -qE "$1 $(sha12 $2)([^0-9a-f]|$)" "$DRV.ready"; }   # named KEY FILE: the .ready names FILE's current sha under KEY
ready_ok() { [ -f "$DRV.ready" ] && bash -n "$DRV" 2> /dev/null && named sha256 $DRV && named rules $RULES && named c2 $C2 \
             && named c4 $C4 && named fx $FX && named spec $SPECF && named sq $SQF && named client $CLIENT \
             && named stat $STATF && named starter $SELF; }
build_active() { systemctl --user is-active -q $BUILD_UNIT 2> /dev/null; }
gap_open() { [ -s $LOCKPID ] && kill -0 "$(cat $LOCKPID)" 2> /dev/null; }

say "start (pid $$): driver $DRV; waiting for the build unit $BUILD_UNIT to be inactive and for no gap being open"
ready_ok || { alert "v0.2.13 switch checks not started" "the review file does not name the current sha256 of the driver, the rules, the clients, the spec, the harness (sq.py, sq_client.py, sq_stat.py) and this starter (or bash -n fails); nothing started"; exit 6; }
t0=$(date +%s); n=0
while :; do
  ! build_active && ! gap_open && break
  if [ $(( $(date +%s) - t0 )) -ge $WAIT_S ]; then
    alert "v0.2.13 switch checks not started" "the build unit stayed active or a gap stayed open after $(( WAIT_S / 3600 )) h of waiting; nothing started"
    exit 1
  fi
  n=$((n + 1)); [ $((n % 30)) = 1 ] && say "waiting ($(( ($(date +%s) - t0) / 60 )) min): build unit $(build_active && echo active || echo 'not active'); a gap open: $(gap_open && echo yes || echo no)"
  sleep $POLL
done
say "the build unit is inactive and no gap is open - starting in $SETTLE s"
sleep $SETTLE
first=$(date +%s); try=0
while :; do
  try=$((try + 1))
  ready_ok || { alert "v0.2.13 switch checks not started" "the driver, the rules, a client, the spec or the harness changed after the review (try $try); nothing started"; exit 6; }
  snap=$COPIES/gap-switch0213-$(date +%m%d-%H%M%S).sh; cp -p "$DRV" "$snap"
  [ "${SWS_TEST_CORRUPT_SNAPSHOT:-0}" = 1 ] && echo "# (test: the snapshot changed)" >> "$snap"
  grep -qE "sha256 $(sha12 "$snap")([^0-9a-f]|$)" "$DRV.ready" || { alert "v0.2.13 switch checks not started" "the driver's snapshot is not the reviewed file (try $try); nothing started"; exit 6; }
  say "try $try: running the snapshot $snap (reviewed: $(head -c 200 "$DRV.ready" | tr '\n' ' '))"
  tt=$(date +%s)
  bash "$snap" 8>&- 9>&- < /dev/null >> $LOG 2>&1; rc=$?
  if [ $rc = 9 ]; then
    alert "v0.2.13 switch checks not started" "another switch-check driver is running (its pid file is in tmp/); this one touched nothing - check what started it"
    exit 9
  fi
  fresh=0; [ -f $RESULT ] && [ $(stat -c %Y $RESULT) -ge $tt ] && fresh=1
  say "try $try: exit $rc ($([ $fresh = 1 ] && head -1 $RESULT | cut -c1-240 || echo 'NO result line from this try'))"
  if [ $fresh = 0 ]; then
    alert "v0.2.13 switch checks: no result" "the driver ended (exit $rc) without a result line - it may have crashed; check the gap's summary and tmp/port-gap.lockpid before anything else"
    exit 3
  fi
  case $rc in
    1) if head -1 $RESULT | grep -q '^not started'; then
         if [ $(( $(date +%s) - first + RETRY_S )) -gt $RETRY_FOR_S ]; then
           alert "v0.2.13 switch checks not started" "the PC stayed busy for $(( RETRY_FOR_S / 3600 )) h of retries (a test lock, a gap, another model server, or the build unit); nothing changed"
           exit 1
         fi
         say "busy: the next try in $(( RETRY_S / 60 )) min"; sleep $RETRY_S; continue
       fi
       alert "v0.2.13 switch checks: not run" "the driver ended with exit 1 after the gap had opened ($(head -1 $RESULT | cut -c1-100)); no retry"
       exit 1;;
    5) alert "v0.2.13 switch checks not run" "engine processes were still running after 8080 stopped: nothing was measured, the daily is back; no retry"
       exit 5;;
    8) say "the priority rule (final; the driver alerted): no retry - the day-one work goes first"; exit 8;;
    *) say "done (exit $rc): no retry"; exit $rc;;
  esac
done
