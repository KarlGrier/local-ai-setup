#!/bin/bash
# gap12-wait.sh - starts work/r22/gap12.sh (the v0.2.7 port's first GPU gap) once stage 3 p4s6 has finished: all 8 of
# its questions have bench.json (or bench-fail.json) and the bench service has stopped. Karl's plan v2 (10-27): Wed
# morning, in the gap while p4s6 is graded. Log: logs/r22/gap12-wait.log.
set -u
B=/home/USER/ai/deep-research/results/bench2/runs
LOG=/home/USER/ai-speed-testing/strata-compare/logs/r22/gap12-wait.log
say() { echo "$(date '+%F %T') $*" >> $LOG; }
say "waiting for stage 3 p4s6 to finish"
while true; do
  n=$(ls $B/screen-deep-p4s6/*/bench.json $B/screen-deep-p4s6/*/bench-fail.json $B/hard-screen-deep-p4s6/*/bench.json \
        $B/hard-screen-deep-p4s6/*/bench-fail.json 2> /dev/null | wc -l)
  if [ "$n" -ge 8 ] && ! systemctl --user is-active --quiet deep-research-bench.service; then break; fi
  sleep 120
done
say "p4s6 done ($n of 8 recorded); starting gap 12"
systemd-run --user --unit=port-gap12 --description="v0.2.7 port: gap 12 (work/r22/gap12.sh)" /bin/bash /home/USER/ai-speed-testing/strata-compare/work/r22/gap12.sh >> $LOG 2>&1
say "gap 12 unit started"
