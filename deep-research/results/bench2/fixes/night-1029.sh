#!/bin/bash
# night-1029.sh - the GPU work queued behind gap 13 (10-29 evening), so the GPU is not idle overnight:
#   1 install staging/k4/checks.py (= Fix 1b's version check + the K4 consistency change; backup checks.py.before-fix1b-k4;
#     patches regenerated) - only the fixes' code paths change, which Karl's research runner (setup + critic) never runs;
#   2 Fix 1b replays: 5 x fix-replay.py check --fix version, then staging/fix1b/tests/compare_replays.py;
#   3 K4 replays: 2 x fix-replay.py check --fix baseline,consist --setup, then staging/k4/tests/judge_k4.py;
#   4 item 8: the report stage on the three merged stores (staging/item8/merged/oNN-3), ~1 h each.
# Waits until gap 13 has ended (its units inactive, the port-gap lock released). Nothing is graded here. A Jan research
# job queued or running: the step waits for it. A file STOP-night-1029 stops it before each step.
# Logs: results/bench2/fixes/chain.log (steps), replays.log (the replays).
set -u
WS=/home/USER/ai/deep-research
SC=/home/USER/ai-speed-testing/strata-compare
F=$WS/results/bench2/fixes
R=$WS/results/bench2
LOG=$F/chain.log
RLOG=$F/replays.log
STOP=$F/STOP-night-1029
P=$WS/.venv/lib/python3.12/site-packages/local_deep_research/deep
PY="$WS/.venv/bin/python -I $WS/tools/fix-replay.py"
KC=$SC/bringup/lib/kcheck.sh
say() { echo "$(date '+%m-%d %H:%M:%S') night-1029: $*" >> "$LOG"; }
stop_here() { [ -e "$STOP" ] && { say "STOP file present - stopped before $1"; exit 0; }; return 0; }
r() { echo "$(date '+%m-%d %H:%M:%S') start $*" >> $RLOG; "$@" 2>&1 | grep -v -i -E 'warn|RequestsDependency' >> $RLOG; echo "$(date '+%m-%d %H:%M:%S') end rc ${PIPESTATUS[0]}" >> $RLOG; }
user_jobs() {   # a Jan job queued (not paused by Karl) or active - the bench queue's own check
  /usr/bin/python3 -I -c "
import sys; sys.path.insert(0, '$WS/tools'); import research_common as rc
sys.exit(0 if any(j.get('state') in rc.ACTIVE or (j.get('state') == 'queued' and not j.get('user_paused') and not j.get('cancel_requested')) for j in rc.all_jobs()) else 1)"
}

say "waiting for gap 13 to end"
until ! systemctl --user is-active --quiet port-gap13-wait.service && ! systemctl --user is-active --quiet port-gap13.service \
      && [ ! -s $SC/tmp/port-gap.lockpid ]; do sleep 120; done
grep -q 'gap 13 done' $SC/results/r22/gap13/summary.txt 2> /dev/null || say "gap 13 did not finish normally (see its summary) - going on: the GPU work below does not depend on it"
stop_here "the install"
while user_jobs; do say "a Jan research job is queued or running - waiting"; sleep 300; done

# 1 the install (bench lock held so no run starts meanwhile)
exec 7> "$WS/run/bench.lock"
flock -w 3600 7 || { say "bench lock busy for an hour - stopped"; exit 1; }
[ -e "$P/checks.py.before-fix1b-k4" ] && { say "checks.py.before-fix1b-k4 exists - not overwriting; stopped"; exit 1; }
cp -p "$P/checks.py" "$P/checks.py.before-fix1b-k4" && cp "$WS/staging/k4/checks.py" "$P/checks.py" \
  && "$WS/.venv/bin/python" -m py_compile "$P/checks.py" && cmp -s "$WS/staging/k4/checks.py" "$P/checks.py"
rc=$?
cp -p "$WS/patches/ldr/0001-deep-package.patch" "$WS/patches/ldr/0001-deep-package.patch.before-fix1b-k4"
bash "$WS/patches/ldr/make-patches.sh" >> "$LOG" 2>&1
exec 7>&-
say "1 checks.py (Fix 1b + K4) installed: rc $rc"
[ "$rc" = 0 ] || exit 1

# 2 Fix 1b replays
stop_here "the Fix 1b replays"
r $PY check --fix version --label b-f1b-jan1024 --report $R/codetool/src/jan1024/ds41q/report.md --question $R/codetool/question.txt 8>&- 9>&-
r $PY check --fix version --label b-f1b-full --run $R/codetool/run-full 8>&- 9>&-
r $PY check --fix version --label b-f1b-fixes --run $R/codetool/run-full-fixes 8>&- 9>&-
r $PY check --fix version --label b-f1b-p4s6o01-code --run $R/runs/screen-deep-p4s6/o01 8>&- 9>&-
r $PY check --fix version --label b-f1b-p4s6o02-code --run $R/runs/screen-deep-p4s6/o02 8>&- 9>&-
$WS/.venv/bin/python -I $WS/staging/fix1b/tests/compare_replays.py > $F/fix1b-compare.txt 2>&1
say "2 Fix 1b replays done (fixes/fix1b-compare.txt)"

# 3 K4 replays
stop_here "the K4 replays"
r $PY check --fix baseline,consist --setup --label b-k4-full --run $R/codetool/run-full 8>&- 9>&-
r $PY check --fix baseline,consist --setup --label b-k4-fixes --run $R/codetool/run-full-fixes 8>&- 9>&-
$WS/.venv/bin/python -I $WS/staging/k4/tests/judge_k4.py b-k4-full:b-f5c-full b-k4-fixes:b-f5c-fixes > $F/k4-judge.txt 2>&1
say "3 K4 replays done (fixes/k4-judge.txt)"

# 4 item 8: the merged stores' reports
stop_here "the item 8 reports"
for q in o01 o02 o03; do
  r $PY write --fix all,read,claims --setup --critic --budget-left 3045 --label i8-merge3-$q --run $WS/staging/item8/merged/$q-3 8>&- 9>&-
done
bash "$KC" night-1029 >> $RLOG 2>&1
echo "$(date '+%m-%d %H:%M:%S') kcheck rc $? - night-1029 done" >> $RLOG
say "4 item 8 merged reports done; night-1029 done"
