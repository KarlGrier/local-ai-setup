#!/bin/bash
# waiter.sh MARK [MAX_MIN] — round 11 (round 16: every release flag checked) (your rule: every queued job gets a waiter): returns when the queue's batch log
# shows "MARK <MARK>" (queued as the batch's last line), when the queue goes idle at a hold or runs dry, when the
# release watcher flags a new release (bringup/out/tmp/NEW-RELEASE-*), when the runner dies, or after MAX_MIN minutes (default
# 110: the harness re-invokes me either way). Prints why it returned and the batch log's last lines.
WS=/home/USER/ai-speed-testing/strata-compare; LOG=$WS/bringup/out/logs/batch.log; M=$1; MAX=${2:-110}
t0=$(date +%s)
while true; do
  if grep -q "MARK $M\$" $LOG 2>/dev/null; then why="mark $M reached"; break; fi
  # round 16 fix: every flag is checked (Round 15's line looked only at the first flag, which was marked seen, so
  # three releases went unreported); a flag counts as reported once release-seen-<flag> exists
  unseen=""; for f in $WS/bringup/out/tmp/NEW-RELEASE-*; do [ -f "$f" ] && [ ! -f $WS/bringup/out/tmp/release-seen-$(basename $f) ] && unseen="$unseen $(cat $f)"; done
  if [ -n "$unseen" ]; then why="NEW RELEASE:$unseen"; break; fi
  if ! pgrep -f 'bringup/lib/queue.sh' > /dev/null; then why="queue runner not running"; break; fi
  if tail -1 $LOG 2>/dev/null | grep -q '=== .* hold .*: waiting'; then why="queue at a hold: $(tail -1 $LOG)"; break; fi
  if [ $(( $(date +%s) - t0 )) -gt 90 ] && [ ! -s $WS/bringup/lib/queue.txt ] && tail -1 $LOG 2>/dev/null | grep -q '^### .* END'; then why="queue empty"; break; fi
  if [ $(( $(date +%s) - t0 )) -ge $(( MAX * 60 )) ]; then why="timeout ${MAX} min"; break; fi
  sleep 20
done
echo "waiter $M: $why at $(date -Is)"
grep -E '^### .* END \([1-9]' $LOG | tail -3 | sed 's/^/nonzero exit: /'
tail -n ${TAILN:-15} $LOG | cut -c1-300
