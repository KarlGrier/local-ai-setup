#!/bin/bash
# p4s2-start.sh RERUNS_PID - phase 4 stage 2 starts after stage 1's reruns (tools/p4-stage1-reruns.sh): waits for that
# process to end, then starts deep-research-bench.service on queue-plan-p4s2.json (o07, o02, o03 deep medium with items
# 1 + 3) - only if the reruns logged "done" and a clean kernel check. Log: logs/p4-stage1-reruns.log.
WS=/home/USER/ai/deep-research; cd $WS
LOG=$WS/logs/p4-stage1-reruns.log
say() { echo "$(date '+%F %T') p4s2-start: $*" >> $LOG; }
P=${1:?reruns pid}
while [ -d /proc/$P ]; do sleep 30; done
if tail -n 3 $LOG | grep -q "p4-stage1-reruns done" && tail -n 3 $LOG | grep -q "kcheck clean"; then
  say "reruns done, kcheck clean: starting stage 2 (deep-research-bench.service, queue-plan-p4s2.json)"
  systemctl --user start deep-research-bench.service && say "started" || say "systemctl start failed"
else
  say "reruns did not end cleanly - stage 2 NOT started"
fi
