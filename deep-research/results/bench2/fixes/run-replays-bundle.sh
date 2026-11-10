#!/bin/bash
# run-replays-bundle.sh - the bundle's replays (10-28, after the install; BUNDLE-1028.md step 3), on the GPU freed by gap
# 12. Checks first (Fix 1 / Fix 3 / Fix 5 + consistency), then items 5 + 6: the whole report stage again on p4s6 o01-o03,
# without (the six fixes, as p4s6 ran) and with read + claims (on the read pass's evidence), for a blind 2-way grading.
# fix-replay.py holds run/bench.lock per process (Jan jobs wait). Log: results/bench2/fixes/replays.log.
set -u
WS=/home/USER/ai/deep-research
PY="$WS/.venv/bin/python -I $WS/tools/fix-replay.py"
R=$WS/results/bench2
FULL=$R/codetool/run-full; FIXD=$R/codetool/run-full-fixes
J24=$R/codetool/src/jan1024/ds41q/report.md; Q=$R/codetool/question.txt
LOG=$R/fixes/replays.log; RP=$R/fixes/readpass
r() { echo "$(date '+%m-%d %H:%M:%S') start $*" >> $LOG; "$@" 2>&1 | grep -v -i -E 'warn|RequestsDependency' >> $LOG; echo "$(date '+%m-%d %H:%M:%S') end rc ${PIPESTATUS[0]}" >> $LOG; }
# 0 the read pass for items 5 + 6 runs alongside the GPU checks (network only, no model), so the GPU never waits for it
( for q in o01 o02 o03; do
    r $WS/.venv/bin/python -I $WS/tools/read-pass.py $R/runs/screen-deep-p4s6/$q --out $RP/$q --max-minutes 30
  done ) &
RPPID=$!
# 1 Fix 1 (version): the 10-24 report's real flags must stay; p4s6 o01's 5 false flags must clear
r $PY check --fix version --label b-f1-jan1024 --report $J24 --question $Q
r $PY check --fix version --label b-f1-full --run $FULL
r $PY check --fix version --label b-f1-fixes --run $FIXD
r $PY check --fix version --label b-f1-p4s6o01 --run $R/runs/screen-deep-p4s6/o01
# 2 Fix 3 (arith), incl. the model-listed half: planted 3/3, the fixes run's one real error
r $PY check --fix arith --label b-f3-full --run $FULL
r $PY check --fix arith --label b-f3-fixes --run $FIXD
r $PY check --fix arith --label b-f3-planted --run $FULL --report $R/fixes/planted/report-planted.md
# 3 Fix 5 + consistency with the setup facts (K4 must be caught)
r $PY check --fix baseline,consist --setup --label b-f5c-full --run $FULL
r $PY check --fix baseline,consist --setup --label b-f5c-fixes --run $FIXD
# 4 items 5 + 6: the read pass (network only), then the report stage written again, without and with
wait $RPPID      # the read pass (started at the top, network only) must be done before the "with" writes
for q in o01 o02 o03; do
  r $PY write --fix all --setup --critic --budget-left 3045 --label b-w-base-$q --run $R/runs/screen-deep-p4s6/$q
  r $PY write --fix all,read,claims --setup --critic --budget-left 3045 --label b-w-bundle-$q --run $R/runs/screen-deep-p4s6/$q --evidence $RP/$q
done
bash /home/USER/ai-speed-testing/strata-compare/bringup/lib/kcheck.sh bundle-replays >> $LOG 2>&1; echo "$(date '+%m-%d %H:%M:%S') kcheck rc $? - bundle replays done" >> $LOG
