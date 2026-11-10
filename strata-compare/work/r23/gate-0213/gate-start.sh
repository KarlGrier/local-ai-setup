#!/bin/bash
# gate-start.sh - the starter of the v0.2.13 port's baseline gate (Karl 11-10; work/r23/gate-0213/gap-gate0213.sh; the form
# of work/r23/switch-gap/switch-start.sh, reviewed 11-10). Started by Claude as a user unit (no argument):
#   systemd-run --user --unit=gate0213 --description="v0.2.13 baseline gate" /bin/bash <this file>
# 1 refuses (exit 6, an alert) unless work/r23/gate-0213/gap-gate0213.sh.ready (Claude's review) names the current sha256
#   (first 12 hex) of the driver ("sha256 <12>"), gate0213_rules.py ("rules <12>"), make_configs0213.py ("mkcfg <12>"),
#   switch_rules.py ("switch <12>"), port0211_rules.py ("ru <12>"), work/r22/g17_rules.py ("g17 <12>"),
#   configs/P0213x-single.json ("single <12>") and this starter itself ("starter <12>"), and bash -n passes;
# 2 waits (every 60 s, up to 24 h, then an alert) until the build unit build-p0213-stock is inactive and no gap is open
#   (tmp/port-gap.lockpid); then 30 s;
# 3 runs a snapshot copy of the driver (results/r23/run-copies/, cp -p; the snapshot's own sha256 must be the reviewed
#   one) with 8>&- 9>&- and stdin from /dev/null, checking the .ready again before each try. Exit 1 with a fresh "not
#   started" result (busy: a lock, a gap, another model server, the build unit, a held queue) -> again 15 min later, for up
#   to 6 h from the first try, then an alert. Exit 8 (the priority rule) is FINAL (the driver alerted). Exit 5 (engines
#   still running after 8080 stopped) -> an alert, no retry. Exit 9 (another driver instance) -> an alert, no retry. A
#   try that writes no result line (a crash) -> an alert, exit 3, no retry. Any other exit is final (the driver alerts
#   itself).
# Holds no lock; children get no fd 8 / 9. Log: results/r23/port-0213/gate-starter.log (the gap's own:
# results/r23/port-0213/gate/summary.txt). Exit: the driver's last exit, 6 not reviewed / changed, 1 gave up waiting /
# busy, 3 no result.
# Test overrides (work/r23/gate-0213/gap-mock-test.sh only; unset in the real run): GTS_DRIVER, GTS_RULES, GTS_MKCFG,
# GTS_SWITCH, GTS_RU, GTS_G17, GTS_SINGLE, GTS_STARTER, GTS_BUILD_UNIT, GTS_LOCKPID, GTS_LOG, GTS_COPIES, GTS_RESULT,
# GTS_POLL_S, GTS_RETRY_S, GTS_RETRY_FOR_S, GTS_WAIT_S, GTS_SETTLE_S, GTS_NOTIFY, GTS_TEST_CORRUPT_SNAPSHOT.
set -u
exec 8>&- 9>&-
WS=/home/USER/ai-speed-testing/strata-compare; GD=$WS/work/r23/gate-0213
DRV=${GTS_DRIVER:-$GD/gap-gate0213.sh}; RULES=${GTS_RULES:-$GD/gate0213_rules.py}; MKCFG=${GTS_MKCFG:-$GD/make_configs0213.py}
SWITCH=${GTS_SWITCH:-$WS/work/r23/switch-gap/switch_rules.py}; RUF=${GTS_RU:-$WS/work/r23/port0211_rules.py}
G17F=${GTS_G17:-$WS/work/r22/g17_rules.py}; SINGLE=${GTS_SINGLE:-$WS/configs/P0213x-single.json}
SELF=${GTS_STARTER:-$(readlink -f "$0")}   # the starter checks its own sha too
BUILD_UNIT=${GTS_BUILD_UNIT:-build-p0213-stock}; LOCKPID=${GTS_LOCKPID:-$WS/tmp/port-gap.lockpid}
LOG=${GTS_LOG:-$WS/results/r23/port-0213/gate-starter.log}; COPIES=${GTS_COPIES:-$WS/results/r23/run-copies}
RESULT=${GTS_RESULT:-$WS/results/r23/port-0213/gate/result.txt}
POLL=${GTS_POLL_S:-60}; RETRY_S=${GTS_RETRY_S:-900}; RETRY_FOR_S=${GTS_RETRY_FOR_S:-21600}; WAIT_S=${GTS_WAIT_S:-86400}
SETTLE=${GTS_SETTLE_S:-30}; NOTIFY=${GTS_NOTIFY:-notify-send}
mkdir -p $(dirname $LOG) $COPIES
say() { echo "$(date '+%F %T') gate-start: $*" >> $LOG; }
alert() { say "ALERT: $1 - $2"; $NOTIFY -a "Strata gaps" -u critical "$1" "$2" 2> /dev/null || say "(notify-send failed)"; }
sha12() { sha256sum "$1" | cut -c1-12; }
named() { [ -f "$2" ] && grep -qE "(^|[ ,(:])$1 $(sha12 $2)([^0-9a-f]|$)" "$DRV.ready"; }   # named KEY FILE: the .ready names FILE's current sha under KEY
ready_ok() { [ -f "$DRV.ready" ] && bash -n "$DRV" 2> /dev/null && named sha256 $DRV && named rules $RULES && named mkcfg $MKCFG \
             && named switch $SWITCH && named ru $RUF && named g17 $G17F && named single $SINGLE && named starter $SELF; }
build_active() { systemctl --user is-active -q $BUILD_UNIT 2> /dev/null; }
gap_open() { [ -s $LOCKPID ] && kill -0 "$(cat $LOCKPID)" 2> /dev/null; }

say "start (pid $$): driver $DRV; waiting for the build unit $BUILD_UNIT to be inactive and for no gap being open"
ready_ok || { alert "v0.2.13 baseline gate not started" "the review file does not name the current sha256 of the driver, the rules, the config maker, switch_rules.py, port0211_rules.py, g17_rules.py, P0213x-single.json and this starter (or bash -n fails); nothing started"; exit 6; }
t0=$(date +%s); n=0
while :; do
  ! build_active && ! gap_open && break
  if [ $(( $(date +%s) - t0 )) -ge $WAIT_S ]; then
    alert "v0.2.13 baseline gate not started" "the build unit stayed active or a gap stayed open after $(( WAIT_S / 3600 )) h of waiting; nothing started"
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
  ready_ok || { alert "v0.2.13 baseline gate not started" "the driver, the rules, the config maker, a shared rules file, the single-card config or this starter changed after the review (try $try); nothing started"; exit 6; }
  snap=$COPIES/gap-gate0213-$(date +%m%d-%H%M%S).sh; cp -p "$DRV" "$snap"
  [ "${GTS_TEST_CORRUPT_SNAPSHOT:-0}" = 1 ] && echo "# (test: the snapshot changed)" >> "$snap"
  grep -qE "sha256 $(sha12 "$snap")([^0-9a-f]|$)" "$DRV.ready" || { alert "v0.2.13 baseline gate not started" "the driver's snapshot is not the reviewed file (try $try); nothing started"; exit 6; }
  say "try $try: running the snapshot $snap (reviewed: $(head -c 200 "$DRV.ready" | tr '\n' ' '))"
  tt=$(date +%s)
  bash "$snap" 8>&- 9>&- < /dev/null >> $LOG 2>&1; rc=$?
  if [ $rc = 9 ]; then
    alert "v0.2.13 baseline gate not started" "another baseline-gate driver is running (its pid file is in tmp/); this one touched nothing - check what started it"
    exit 9
  fi
  fresh=0; [ -f $RESULT ] && [ $(stat -c %Y $RESULT) -ge $tt ] && fresh=1
  say "try $try: exit $rc ($([ $fresh = 1 ] && head -1 $RESULT | cut -c1-240 || echo 'NO result line from this try'))"
  if [ $fresh = 0 ]; then
    alert "v0.2.13 baseline gate: no result" "the driver ended (exit $rc) without a result line - it may have crashed; check the gap's summary and tmp/port-gap.lockpid before anything else"
    exit 3
  fi
  case $rc in
    1) if head -1 $RESULT | grep -q '^not started'; then
         if [ $(( $(date +%s) - first + RETRY_S )) -gt $RETRY_FOR_S ]; then
           alert "v0.2.13 baseline gate not started" "the PC stayed busy for $(( RETRY_FOR_S / 3600 )) h of retries (a test lock, a gap, another model server, or the build unit); nothing changed"
           exit 1
         fi
         say "busy: the next try in $(( RETRY_S / 60 )) min"; sleep $RETRY_S; continue
       fi
       alert "v0.2.13 baseline gate: not run" "the driver ended with exit 1 after the gap had opened ($(head -1 $RESULT | cut -c1-100)); no retry"
       exit 1;;
    5) alert "v0.2.13 baseline gate not run" "engine processes were still running after 8080 stopped: nothing was measured, the daily is back; no retry"
       exit 5;;
    8) say "the priority rule (final; the driver alerted): no retry - the day-one work goes first"; exit 8;;
    *) say "done (exit $rc): no retry"; exit $rc;;
  esac
done
