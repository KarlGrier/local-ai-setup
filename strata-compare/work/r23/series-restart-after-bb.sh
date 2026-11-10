#!/bin/bash
# series-restart-after-bb.sh (11-05 18:5x, Claude) - one shot, on the 11-05 audit (staging/post7d/AUDIT-1105.md #6): the
# running series' started_after_gap counted an old untimestamped "LDR (...): running" status line as a question, so the
# step after Basalt b (DeepSeek C rerun) would start straight after Basalt b's gap. gap-series.sh is fixed on disk
# (timestamped lines only; an exit 1 with the gap still open stops the series). gap-csample.sh's .ready was moved to
# .ready.held, so after Basalt b the running series waits at csample's .ready (no driver running). This waits for
# "gap-basalt-b.sh exit N" in the series log: exit 0 -> anchor = Basalt b's launch; exit 1 (refused, 8080 untouched) ->
# anchor = the series' own anchor (GAP19_T0); any other exit -> the series stopped itself: no restart, a notice. Then:
# no open gap, the series has no child process (waiting at the .ready), STOP the series first, then restore the .ready,
# then start the fixed series with the remaining steps (no race: the old series cannot see the .ready).
set -u
SC=/home/USER/ai-speed-testing/strata-compare; W=$SC/work/r23; L=$SC/results/r23/gap-series.log; F=$W/gap-series.sh
C=$SC/work/ds41/gate/gap-csample.sh
log() { echo "$(date '+%F %T') restart-waiter-bb: $*" | tee -a $L; }
alert() { log "$1"; echo "$(date '+%m-%d %H:%M') GAP SERIES restart-waiter-bb: $1" >> $SC/NOTES.md
          notify-send -a "Strata gaps" -u critical "Gap series" "$1" 2> /dev/null || true; }
log "waiting for Basalt b to finish (then: stop the series, restore csample's .ready, start the fixed series)"
for i in $(seq 5760); do grep -q 'work/r23/gap-basalt-b.sh exit' $L && break; sleep 15; done
rc=$(grep 'work/r23/gap-basalt-b.sh exit' $L | tail -1 | awk '{print $NF}')
case "$rc" in
  0) t0=$(grep 'starting work/r23/gap-basalt-b.sh' $L | tail -1 | cut -c1-19) ;;
  1) t0=$(grep 'starting work/r23/gap-basalt-a.sh' $L | tail -1 | cut -c1-19) ;;   # a refusal keeps the series' anchor (Basalt a's launch)
  *) alert "Basalt b exit '${rc:-none}' - the series stopped itself; NOT restarted (csample's .ready stays held)"; exit 1 ;;
esac
[[ "$t0" =~ ^20[0-9]{2}-[0-9]{2}-[0-9]{2}\ [0-9:]{8}$ ]] || { alert "no anchor time for the restart (rc $rc, '$t0') - NOT restarted"; exit 1; }
sp=$(systemctl --user show -p MainPID --value gap-series)
kids() { pgrep -P "$sp" | while read -r k; do [ "$(ps -o comm= -p "$k" 2> /dev/null)" = sleep ] || echo "$k"; done; }
for i in $(seq 120); do ! [ -s $SC/tmp/port-gap.lockpid ] && [ "$sp" != 0 ] && [ -z "$(kids)" ] && break; sleep 5; done
[ "$sp" = 0 ] && { alert "the series is not running after Basalt b - NOT restarted"; exit 1; }
[ -s $SC/tmp/port-gap.lockpid ] && { alert "a gap is still open 10 min after Basalt b - NOT restarted"; exit 1; }
[ -n "$(kids)" ] && { alert "the series (pid $sp) still runs a child ($(kids | tr '\n' ' ')) - NOT restarted"; exit 1; }
grep -q '^STEPS=(work/r23/gap-basalt-b.sh ' $F || { alert "gap-series.sh's STEPS line is not the expected one - NOT restarted"; exit 1; }
cp -p $F $F.before-bb-restart && cp -p $F $F.new
sed -i "s#^STEPS=.*#STEPS=(work/ds41/gate/gap-csample.sh work/r23/gap-ud31.sh work/r23/gap-ud31-dec.sh work/r23/gap-port0211.sh work/r23/gap-basalt-fix.sh)#" $F.new   # gap-basalt-fix.sh runs only once Claude reviewed it and wrote its .ready
bash -n $F.new || { alert "bash -n failed on the new series - NOT restarted"; exit 1; }
grep -qF "'/^20[0-9][0-9]-" $F.new || { alert "the new series lacks the timestamp fix - NOT restarted"; exit 1; }
mv $F.new $F
systemctl --user stop gap-series.service; sleep 3
[ -s $SC/tmp/port-gap.lockpid ] && { alert "a gap opened during the stop?! - the series is NOT started again (csample's .ready stays held)"; exit 1; }
mv $C.ready.held $C.ready || { alert "csample's held .ready is missing - the series is NOT started again"; exit 1; }
systemd-run --user --unit=gap-series --collect --setenv=GAP19_T0="$t0" --description="r23 gap series (C rerun, v3.1, v3.1 follow-up, v0.2.11 port gate)" /bin/bash $F > /dev/null 2>&1
sleep 5
log "series restarted (pid $(systemctl --user show -p MainPID --value gap-series)), anchored at $t0 (Basalt b exit $rc); steps: $(grep '^STEPS' $F | cut -c7-)"
