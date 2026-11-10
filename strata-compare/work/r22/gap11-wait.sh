#!/bin/bash
# gap11-wait.sh - waits until phase 4's item 4 stage 2 queue (deep-research-bench.service on queue-plan-p4s4.json) has
# started and then finished, then runs work/r22/gap11.sh (the corrected tool-call check on P021m, for the record).
L=/home/USER/ai-speed-testing/strata-compare/logs/r22/gap11-wait.log
echo "$(date '+%F %T') waiting for the p4s4 queue to start" >> $L
until systemctl --user is-active -q deep-research-bench.service; do sleep 60; done
echo "$(date '+%F %T') p4s4 queue running; waiting for it to finish" >> $L
while systemctl --user is-active -q deep-research-bench.service; do sleep 120; done
echo "$(date '+%F %T') p4s4 queue finished; gap 11" >> $L
cd /home/USER/ai-speed-testing/strata-compare && exec work/r22/gap11.sh > logs/r22/gap11.out 2>&1
