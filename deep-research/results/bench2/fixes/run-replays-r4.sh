#!/bin/bash
# run-replays-r4.sh - round 4 of the per-fix replays (10-27): Fix 1 with two engine-folder answers (only the shared
# folders), Fix 3 with the written-out equation checker. Log: results/bench2/fixes/replays.log; kernel check at the end.
set -u
WS=/home/USER/ai/deep-research
PY="$WS/.venv/bin/python -I $WS/tools/fix-replay.py check"
RUN=$WS/results/bench2/codetool/run-full
J24=$WS/results/bench2/codetool/src/jan1024/ds41q/report.md
Q=$WS/results/bench2/codetool/question.txt
LOG=$WS/results/bench2/fixes/replays.log
r() { echo "$(date '+%m-%d %H:%M:%S') start $*" >> $LOG; $PY "$@" 2>&1 | grep -v -i -E 'warn|RequestsDependency' >> $LOG; echo "$(date '+%m-%d %H:%M:%S') end rc ${PIPESTATUS[0]}" >> $LOG; }
r --fix version --label f1-jan1024-r4 --report $J24 --question $Q          # Fix 1's test case (Karl's OK, 10-27)
r --fix version --label f1-rerun-r4 --run $RUN
r --fix arith --label f3-rerun-r4 --run $RUN
r --fix arith --label f3-planted-r4 --run $RUN --report $WS/results/bench2/fixes/planted/report-planted.md
bash /home/USER/ai-speed-testing/strata-compare/bringup/lib/kcheck.sh fix-replays-r4 >> $LOG 2>&1; echo "$(date '+%m-%d %H:%M:%S') kcheck rc $?" >> $LOG
