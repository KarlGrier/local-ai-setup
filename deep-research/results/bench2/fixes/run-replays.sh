#!/bin/bash
# run-replays.sh - phase 4's per-fix replays (10-27): one check per replay on saved reports, through the proxy, each
# holding run/bench.lock (tools/fix-replay.py). Log: results/bench2/fixes/replays.log; kernel-log check at the end.
set -u
WS=/home/USER/ai/deep-research
PY="$WS/.venv/bin/python -I $WS/tools/fix-replay.py check"
RUN=$WS/results/bench2/codetool/run-full
J24=$WS/results/bench2/codetool/src/jan1024/ds41q/report.md
Q=$WS/results/bench2/codetool/question.txt
LOG=$WS/results/bench2/fixes/replays.log
r() { echo "$(date '+%m-%d %H:%M:%S') start $*" >> $LOG; $PY "$@" 2>&1 | grep -v -i -E 'warn|RequestsDependency' >> $LOG; echo "$(date '+%m-%d %H:%M:%S') end rc ${PIPESTATUS[0]}" >> $LOG; }
r --fix version --label f1-jan1024 --report $J24 --question $Q          # Fix 1's test case (Karl's OK, 10-27)
r --fix version --label f1-rerun --run $RUN
r --fix arith --label f3-rerun --run $RUN
r --fix consist --label fc-rerun --run $RUN
r --fix baseline --setup --label f5-rerun --run $RUN
r --fix inline --critic --verify 40 --label f2-rerun --run $RUN
r --fix cite --label f4-rerun --run $RUN
r --fix all --setup --critic --verify 120 --budget-left 1500 --label f6-rerun-25min --run $RUN
bash /home/USER/ai-speed-testing/strata-compare/bringup/lib/kcheck.sh fix-replays >> $LOG 2>&1; echo "$(date '+%m-%d %H:%M:%S') kcheck rc $?" >> $LOG
