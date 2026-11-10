#!/bin/bash
# p4s3-start.sh GAP8_PID - phase 4 stage 3 (the user, 10-22: "Stage 3 starts after the gap, on whichever build is live,
# with the setup profile + check + critic (verifier off)"): waits for strata-compare's gap 8 to end, then starts
# deep-research-bench.service on queue-plan-p4s3.json (the screen set: o01-o03 + the hard five, deep medium, citation
# check xhigh, items setup + critic) - only when gap 8 ended normally ("gap 8 done", no exactness stop, no kernel-check
# failure) and 8080 answers. Log: logs/p4-stage3-start.log.
WS=/home/USER/ai/deep-research; cd $WS
LOG=$WS/logs/p4-stage3-start.log
G8=/home/USER/ai-speed-testing/strata-compare/results/r22/gap8/summary.txt
say() { echo "$(date '+%F %T') p4s3-start: $*" >> $LOG; }
nostart() { say "$* - stage 3 NOT started"; notify-send -u critical "phase 4 stage 3 not started" "$*" 2> /dev/null || true; exit 1; }
P=${1:?gap 8 pid}
say "waiting for gap 8 (pid $P)"
while [ -d /proc/$P ]; do sleep 30; done
last=$(tail -n 60 $G8)
grep -q "gap 8 done after" <<< "$last" || nostart "gap 8 did not finish normally (no 'gap 8 done' line)"
grep -qE "EXACTNESS STOP|KERNEL CHECK FAILED|KCHECK FAILED" <<< "$last" && nostart "gap 8 ended with a stop or a kernel-check failure"
grep -q "switch logged at" <<< "$last" && build="P021n (the backport, switched in gap 8)" || build="P021 (c9fe314316c4; no switch)"
curl -s -m 15 -o /dev/null http://127.0.0.1:8080/v1/models || nostart "8080 does not answer after the gap"
say "gap 8 ended normally; 8080 = $build: starting stage 3 (queue-plan-p4s3.json)"
systemctl --user start deep-research-bench.service && say "started" || say "systemctl start failed"
