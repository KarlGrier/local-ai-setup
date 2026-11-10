#!/bin/bash
# gate-after-gap18.sh (11-03): starts the DeepSeek A/B/C gate (work/ds41/gate/gate.sh) after gap 18 (user unit gap18)
# has ended AND item 7d's queue has started its next question - so the gate goes BETWEEN 7d questions (Karl: "7d starts
# as soon as it's built; the measurements fit around it") instead of right after gap 18. gate.sh's port_gap4 begin then
# waits for that question to finish. Waits up to 10 h for gap 18, then up to 20 min for the queue's next "running" line
# (if the queue has nothing left, the gate starts anyway). Log: logs/ds41/gate-after-gap18.log.
L=/home/USER/ai-speed-testing/strata-compare/logs/ds41/gate-after-gap18.log; Q=/home/USER/ai/deep-research/logs/bench2-queue.log
say() { echo "$(date '+%F %T') $*" >> $L; }
say "waiting for gap 18 to end"
for i in $(seq 3600); do systemctl --user is-active -q gap18.service || break; sleep 10; done
systemctl --user is-active -q gap18.service && { say "gap 18 still running after 10 h - the gate is not started"; exit 1; }
t0=$(date '+%F %T'); say "gap 18 ended; waiting for 7d's next question to start"
for i in $(seq 120); do
  last=$(grep -E ': running' $Q | tail -1 | cut -c1-19)
  [[ "$last" > "$t0" ]] && { say "7d is running: $(grep -E ': running' $Q | tail -1 | cut -c1-120)"; break; }
  systemctl --user is-active -q deep-research-bench.service || { say "the bench queue is not active - starting the gate"; break; }
  sleep 10
done
for i in $(seq 180); do systemctl --user is-active -q get-lucebox-dspark.service || break; sleep 10; done
say "starting gate.sh"
exec /bin/bash /home/USER/ai-speed-testing/strata-compare/work/ds41/gate/gate.sh
