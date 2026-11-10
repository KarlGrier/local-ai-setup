#!/bin/bash
# run-replays-r2.sh - round 2 of the per-fix replays (10-27, after the round-2 corrections: Fix 1 engine folders, Fix 3
# unit rule, Fix 5 task precedence). Log: results/bench2/fixes/replays.log; kernel-log check at the end.
set -u
WS=/home/USER/ai/deep-research
PY="$WS/.venv/bin/python -I $WS/tools/fix-replay.py check"
RUN=$WS/results/bench2/codetool/run-full
J24=$WS/results/bench2/codetool/src/jan1024/ds41q/report.md
Q=$WS/results/bench2/codetool/question.txt
LOG=$WS/results/bench2/fixes/replays.log
r() { echo "$(date '+%m-%d %H:%M:%S') start $*" >> $LOG; $PY "$@" 2>&1 | grep -v -i -E 'warn|RequestsDependency' >> $LOG; echo "$(date '+%m-%d %H:%M:%S') end rc ${PIPESTATUS[0]}" >> $LOG; }
r --fix version --label f1-jan1024-r2 --report $J24 --question $Q          # Fix 1's test case (Karl's OK, 10-27)
r --fix version --label f1-rerun-r2 --run $RUN
r --fix arith --label f3-rerun-r2 --run $RUN
r --fix arith --label f3-planted --run $RUN --report $WS/results/bench2/fixes/planted/report-planted.md
r --fix baseline --setup --label f5-rerun-r2 --run $RUN
bash /home/USER/ai-speed-testing/strata-compare/bringup/lib/kcheck.sh fix-replays-r2 >> $LOG 2>&1; echo "$(date '+%m-%d %H:%M:%S') kcheck rc $?" >> $LOG
