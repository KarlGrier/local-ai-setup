#!/bin/bash
# chain-after.sh PREV_UNIT LOG CMD... (11-03): runs CMD after the user unit PREV_UNIT has ended AND item 7d's queue has
# started its next question - so the gap CMD opens goes BETWEEN 7d questions (Karl: "7d starts as soon as it's built;
# the measurements fit around it"; gap 17 "parts a and b in separate gaps, between 7d questions"). CMD's port_gap4 begin
# then waits for that question to finish. Up to 14 h for PREV_UNIT, then up to 20 min for the queue's next "running"
# line (if the queue has nothing left, CMD starts anyway).
PREV=$1 L=$2; shift 2; Q=/home/USER/ai/deep-research/logs/bench2-queue.log
say() { echo "$(date '+%F %T') $*" >> $L; }
say "waiting for $PREV to end, then: $*"
for i in $(seq 5040); do systemctl --user is-active -q $PREV.service || break; sleep 10; done
systemctl --user is-active -q $PREV.service && { say "$PREV still running after 14 h - not started"; exit 1; }
t0=$(date '+%F %T'); say "$PREV ended; waiting for 7d's next question to start"
for i in $(seq 120); do
  last=$(grep -E ': running' $Q | tail -1 | cut -c1-19)
  [[ "$last" > "$t0" ]] && { say "7d is running: $(grep -E ': running' $Q | tail -1 | cut -c1-110)"; break; }
  systemctl --user is-active -q deep-research-bench.service || { say "the bench queue is not active - starting now"; break; }
  sleep 10
done
say "starting: $*"
exec "$@"
