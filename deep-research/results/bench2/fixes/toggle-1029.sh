#!/bin/bash
# toggle-1029.sh - Karl 10-29: the clean test of items 5 and 6 at the report stage. After night-1029.sh ends, the report
# stage four times on the SAME evidence (the second 10-24 bundle rerun, run-full-bundle-verpin): neither item
# (--fix all), item 6 only (all,read), item 5 only (all,claims), both (all,read,claims). Graded blind afterwards in one
# round (answer key, wrong-engine names, overall); if either item hurts on the same evidence, Karl hears before any
# default changes. Items 5 + 6 stay in the deep defaults meanwhile (Karl 10-29).
# A file STOP-toggle-1029 stops it before each replay. Log: results/bench2/fixes/replays.log (+ chain.log lines).
set -u
WS=/home/USER/ai/deep-research
F=$WS/results/bench2/fixes
C=$WS/results/bench2/codetool
LOG=$F/chain.log
RLOG=$F/replays.log
STOP=$F/STOP-toggle-1029
PY="$WS/.venv/bin/python -I $WS/tools/fix-replay.py"
KC=/home/USER/ai-speed-testing/strata-compare/bringup/lib/kcheck.sh
say() { echo "$(date '+%m-%d %H:%M:%S') toggle-1029: $*" >> "$LOG"; }
r() { echo "$(date '+%m-%d %H:%M:%S') start $*" >> $RLOG; "$@" 2>&1 | grep -v -i -E 'warn|RequestsDependency' >> $RLOG; echo "$(date '+%m-%d %H:%M:%S') end rc ${PIPESTATUS[0]}" >> $RLOG; }
say "waiting for night-1029 to end"
until ! systemctl --user is-active --quiet ldr-night-1029.service; do sleep 120; done   # ended, however it ended
grep -q 'night-1029: .*night-1029 done' "$LOG" || say "night-1029 did not finish normally (see above) - the toggle replays run anyway" 
for arm in none:all read:all,read claims:all,claims both:all,read,claims; do
  [ -e "$STOP" ] && { say "STOP file present - stopped before $arm"; exit 0; }
  r $PY write --fix "${arm#*:}" --setup --critic --budget-left 3600 --label b-w-tog-${arm%%:*} --run $C/run-full-bundle-verpin \
    --question $C/question.txt 8>&- 9>&-
done
bash "$KC" toggle-1029 >> $RLOG 2>&1
echo "$(date '+%m-%d %H:%M:%S') kcheck rc $? - toggle-1029 done" >> $RLOG
say "four toggle replays done (fixes/replays/b-w-tog-{none,read,claims,both}) - grade blind in one round"
