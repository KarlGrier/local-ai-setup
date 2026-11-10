#!/bin/bash
# waiter.sh MARK [MAX_MIN] — round 11 (your rule: every queued job gets a waiter): returns when the queue's batch log
# shows "MARK <MARK>" (queued as the batch's last line), when the queue goes idle at a hold or runs dry, when the
# release watcher flags a new release (tmp/r11/NEW-RELEASE-*), when the runner dies, or after MAX_MIN minutes (default
# 110: the harness re-invokes me either way). Prints why it returned and the batch log's last lines.
WS=/home/USER/ai-speed-testing/strata-compare; LOG=$WS/logs/r11/batch.log; M=$1; MAX=${2:-110}
t0=$(date +%s)
while true; do
  if grep -q "MARK $M\$" $LOG 2>/dev/null; then why="mark $M reached"; break; fi
  if ls $WS/tmp/r11/NEW-RELEASE-* > /dev/null 2>&1 && [ ! -f $WS/tmp/r11/release-seen-$(ls $WS/tmp/r11/NEW-RELEASE-* | head -1 | xargs basename) ]; then why="NEW RELEASE: $(cat $WS/tmp/r11/NEW-RELEASE-*)"; break; fi
  if ! pgrep -f 'work/r11/queue.sh' > /dev/null; then why="queue runner not running"; break; fi
  if tail -1 $LOG 2>/dev/null | grep -q '=== .* hold .*: waiting'; then why="queue at a hold: $(tail -1 $LOG)"; break; fi
  if [ $(( $(date +%s) - t0 )) -gt 90 ] && [ ! -s $WS/work/r11/queue.txt ] && tail -1 $LOG 2>/dev/null | grep -q '^### .* END'; then why="queue empty"; break; fi
  if [ $(( $(date +%s) - t0 )) -ge $(( MAX * 60 )) ]; then why="timeout ${MAX} min"; break; fi
  sleep 20
done
echo "waiter $M: $why at $(date -Is)"
grep -E '^### .* END \([1-9]' $LOG | tail -3 | sed 's/^/nonzero exit: /'
tail -n ${TAILN:-15} $LOG | cut -c1-300
