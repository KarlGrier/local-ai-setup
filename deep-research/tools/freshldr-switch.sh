#!/bin/bash
# freshldr-switch.sh - 2026-11-01 (Karl): a fresh LDR before every question. tools/bench2-queue.sh was replaced at 11:26
# (backup .before-freshldr); the running queue still runs the old file, so at the boundary after p7c o03 (tmp/bench2.hold,
# placed 11:25) this restarts the bench unit once (KillMode=process: only the waiting queue shell; LDR and 8080 stay),
# waits for the new queue to reach the same hold, releases it and checks that the next question starts on a fresh LDR.
# Waits key on log line offsets and file state, never on local time strings (DST). Log: logs/freshldr-switch.log
set -u
W=/home/USER/ai/deep-research
QLOG=$W/logs/bench2-queue.log
LOG=$W/logs/freshldr-switch.log
HOLD=$W/tmp/bench2.hold
say() { echo "$(date '+%F %T %z') $*" >> $LOG; }
fail() { say "STOPPED: $*$([ -e $HOLD ] && echo ' (the hold file is left in place)')"; notify-send -a "Deep research" -u critical "Fresh-LDR switch stopped" "$* (logs/freshldr-switch.log)" 2> /dev/null || true; exit 1; }
after() { tail -n +$(( $1 + 1 )) $QLOG; }          # queue log lines after line $1
wait_for() {   # $1 line offset, $2 grep -E pattern, $3 max seconds: 0 when a line after the offset matches
  local i
  for i in $(seq $(( $3 / 15 ))); do after $1 | grep -q -E "$2" && return 0; sleep 15; done
  return 1
}

[ -e $HOLD ] || fail "no hold file"
grep -q 'WHY="a fresh LDR for every question"' $W/tools/bench2-queue.sh || fail "tools/bench2-queue.sh is not the fresh-LDR version"
N0=$(wc -l < $QLOG)
say "start (pid $$): waiting for p7c o03 to end and the queue to reach the hold (queue log line $N0)"

# 1 the old queue at the hold, with no bench2 run
wait_for $N0 'hold file: waiting' 21600 || fail "the queue did not reach the hold within 6 h"
flock -n $W/run/bench.lock true || fail "run/bench.lock is held at the hold"
say "old queue waiting at the hold: $(after $N0 | grep -E 'o03: rc|not completed' | tail -1)"

# 2 restart the unit; the new queue reaches the same hold
N1=$(wc -l < $QLOG)
systemctl --user restart deep-research-bench.service || fail "systemctl restart failed"
wait_for $N1 'queue started \(pid' 300 || fail "the new queue did not start"
wait_for $N1 'hold file: waiting' 900 || fail "the new queue did not reach the hold"
say "new queue at the hold: $(after $N1 | grep -E 'queue started' | tail -1)"

# 3 release; the next question starts on a fresh LDR
N2=$(wc -l < $QLOG)
mv $HOLD $W/tmp/bench2.hold.released-$(date +%m%d-%H%M)-freshldr
say "hold released"
wait_for $N2 'a fresh LDR for every question|a research job from Jan is queued' 1800 || fail "no LDR restart line within 30 min"
say "$(after $N2 | grep -E 'LDR -> |a research job from Jan' | head -1)"
wait_for $N2 ': running \(item 7' 2700 || fail "no question started within 45 min of the release"
say "$(after $N2 | grep -E ': running \(item 7' | head -1)"
say "done"
