#!/bin/bash
# queue.sh — round 4: runs work/r4/queue.txt line by line (each line a shell command, run from the workspace), output
# appended to logs/r4/batch.log. Lines can be appended while it runs; "STOP" ends it; an empty queue waits.
WS=/home/USER/ai-speed-testing/strata-compare; Q=$WS/work/r4/queue.txt; LOG=$WS/logs/r4/batch.log
cd $WS; touch $Q; source $WS/work/r4/env.sh
while true; do
  line=$(head -1 $Q)
  if [ -z "$line" ]; then
    if [ "$(wc -l < $Q)" -gt 0 ]; then sed -i 1d $Q; continue; fi
    sleep 5; continue
  fi
  sed -i 1d $Q
  [ "$line" = STOP ] && { echo "=== $(date -Is) queue STOP" >> $LOG; exit 0; }
  echo "### $(date -Is) RUN: $line" >> $LOG
  bash -c "$line" >> $LOG 2>&1
  echo "### $(date -Is) END ($?): $line" >> $LOG
done
