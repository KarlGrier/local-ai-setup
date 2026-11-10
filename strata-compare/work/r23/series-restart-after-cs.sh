#!/bin/bash
# series-restart-after-cs.sh (11-05 21:2x, Claude) - one shot, from series-restart-after-bb.sh. Karl 11-05: a refused gap
# gets one retry at the next question boundary, then it is skipped with an alert. gap-series.sh has that rule on disk
# (question_since, SERIES_RETRIED / SERIES_RETRY_AT); the running series (started 20:3x) does not. gap-ud31.sh's .ready
# was moved to .ready.held, so after the C rerun (csample) the running series waits at ud31's .ready (no driver
# running). This waits for "gap-csample.sh exit N": 0 -> anchor = csample's launch, steps ud31, ud31-dec, port0211,
# basalt-fix; 1 (refused; the old series skipped it) -> csample again first as its ONE retry (SERIES_RETRIED, after a
# question started after its refusal), anchor = Basalt b's launch; any other exit -> the series stopped itself: no
# restart, a notice. Then as series-restart-after-bb: no open gap, no child, STOP the series, restore the .ready, start.
set -u
SC=/home/USER/ai-speed-testing/strata-compare; W=$SC/work/r23; L=$SC/results/r23/gap-series.log; F=$W/gap-series.sh
C=$SC/work/r23/gap-ud31.sh; CS=work/ds41/gate/gap-csample.sh
log() { echo "$(date '+%F %T') restart-waiter-cs: $*" | tee -a $L; }
alert() { log "$1"; echo "$(date '+%m-%d %H:%M') GAP SERIES restart-waiter-cs: $1" >> $SC/NOTES.md
          notify-send -a "Strata gaps" -u critical "Gap series" "$1" 2> /dev/null || true; }
log "waiting for the C rerun (csample) to finish (then: stop the series, restore gap-ud31.sh's .ready, start the series with the one-retry rule)"
# 11-05 21:5x fix: only an exit line logged AFTER csample's latest launch counts - an earlier C run's "exit" line is in
# the log too (the first version of this waiter matched it at once and gave up at 21:28)
TS=$(grep "starting $CS" $L | tail -1 | cut -c1-19)
[[ "$TS" =~ ^20[0-9]{2}-[0-9]{2}-[0-9]{2}\ [0-9:]{8}$ ]] || { alert "no launch line of $CS in the series log - NOT waiting"; exit 1; }
exitline() { awk -v t="$TS" -v c="$CS exit" '/^20[0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9] / && substr($0, 1, 19) >= t && index($0, c) {l = $0} END {print l}' $L; }
log "csample was launched at $TS - waiting for its exit line after that"
for i in $(seq 5760); do [ -n "$(exitline)" ] && break; sleep 15; done
rc=$(exitline | awk '{print $NF}')
case "$rc" in
  0) t0=$(grep "starting $CS" $L | tail -1 | cut -c1-19); NEWSTEPS="work/r23/gap-ud31.sh work/r23/gap-ud31-dec.sh work/r23/gap-port0211.sh work/r23/gap-basalt-fix.sh"; RTD=""; RAT="" ;;
  1) # csample refused under the old series (skipped there): Karl 11-05 - its one retry at the next question boundary
     t0=$(grep 'starting work/r23/gap-basalt-b.sh' $L | tail -1 | cut -c1-19)
     RAT=$(exitline | cut -c1-19); RTD=$CS
     NEWSTEPS="$CS work/r23/gap-ud31.sh work/r23/gap-ud31-dec.sh work/r23/gap-port0211.sh work/r23/gap-basalt-fix.sh" ;;
  *) alert "csample exit '${rc:-none}' - the series stopped itself; NOT restarted (gap-ud31.sh's .ready stays held)"; exit 1 ;;
esac
[[ "$t0" =~ ^20[0-9]{2}-[0-9]{2}-[0-9]{2}\ [0-9:]{8}$ ]] || { alert "no anchor time for the restart (rc $rc, '$t0') - NOT restarted"; exit 1; }
sp=$(systemctl --user show -p MainPID --value gap-series)
kids() { pgrep -P "$sp" | while read -r k; do [ "$(ps -o comm= -p "$k" 2> /dev/null)" = sleep ] || echo "$k"; done; }
for i in $(seq 120); do ! [ -s $SC/tmp/port-gap.lockpid ] && [ "$sp" != 0 ] && [ -z "$(kids)" ] && break; sleep 5; done
[ "$sp" = 0 ] && { alert "the series is not running after csample - NOT restarted"; exit 1; }
[ -s $SC/tmp/port-gap.lockpid ] && { alert "a gap is still open 10 min after csample - NOT restarted"; exit 1; }
[ -n "$(kids)" ] && { alert "the series (pid $sp) still runs a child ($(kids | tr '\n' ' ')) - NOT restarted"; exit 1; }
grep -q '^STEPS=(work/ds41/gate/gap-csample.sh ' $F || { alert "gap-series.sh's STEPS line is not the expected one - NOT restarted"; exit 1; }
cp -p $F $F.before-cs-restart && cp -p $F $F.new
sed -i "s#^STEPS=.*#STEPS=($NEWSTEPS)#" $F.new   # gap-basalt-fix.sh runs only once Claude reviewed it and wrote its .ready
bash -n $F.new || { alert "bash -n failed on the new series - NOT restarted"; exit 1; }
grep -qF "'/^20[0-9][0-9]-" $F.new && grep -q '^question_since()' $F.new || { alert "the new series lacks the timestamp fix or the one-retry rule - NOT restarted"; exit 1; }
mv $F.new $F
systemctl --user stop gap-series.service; sleep 3
[ -s $SC/tmp/port-gap.lockpid ] && { alert "a gap opened during the stop?! - the series is NOT started again (gap-ud31.sh's .ready stays held)"; exit 1; }
mv $C.ready.held $C.ready || { alert "gap-ud31.sh's held .ready is missing - the series is NOT started again"; exit 1; }
systemd-run --user --unit=gap-series --collect --setenv=GAP19_T0="$t0" --setenv=SERIES_RETRIED="$RTD" --setenv=SERIES_RETRY_AT="$RAT" --description="r23 gap series (v3.1, v3.1 follow-up, v0.2.11 port gate, Basalt fix rerun)" /bin/bash $F > /dev/null 2>&1
sleep 5
log "series restarted (pid $(systemctl --user show -p MainPID --value gap-series)), anchored at $t0 (csample exit $rc${RAT:+; its one retry after $RAT}); steps: $(grep '^STEPS' $F | cut -c7-)"
