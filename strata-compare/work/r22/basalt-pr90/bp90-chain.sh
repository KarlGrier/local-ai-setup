#!/bin/bash
# bp90-chain.sh - the GPU queue behind gap 15 (10-30): 1 the Basalt PR #90 check (bp90.sh; Karl: "after gap 15 finishes,
# before anything else is queued"), 2 the two remaining K4 tries (fix-replay.py check --fix baseline,consist --setup on
# run-full, as night-1029's b-k4-full; pass = K4 caught on 2 of 3) + judge_k4.py. Gap 15 ending with its gap open (a kernel
# error) stops the chain. A Jan research job queued or running: step 2 waits for it. Log: results/r22/basalt-pr90/chain.log.
set -u
SC=/home/USER/ai-speed-testing/strata-compare
DR=/home/USER/ai/deep-research
LOG=$SC/results/r22/basalt-pr90/chain.log
F=$DR/results/bench2/fixes
R=$DR/results/bench2
RLOG=$F/replays.log
mkdir -p "${LOG%/*}"
say() { echo "$(date '+%m-%d %H:%M:%S') $*" >> "$LOG"; }
note() { notify-send -a "GPU queue" "$1" "$2" 2> /dev/null || true; }
r() { echo "$(date '+%m-%d %H:%M:%S') start $*" >> $RLOG; "$@" 2>&1 | grep -v -i -E 'warn|RequestsDependency' >> $RLOG; echo "$(date '+%m-%d %H:%M:%S') end rc ${PIPESTATUS[0]}" >> $RLOG; }
user_jobs() {
  /usr/bin/python3 -I -c "
import sys; sys.path.insert(0, '$DR/tools'); import research_common as rc
sys.exit(0 if any(j.get('state') in rc.ACTIVE or (j.get('state') == 'queued' and not j.get('user_paused') and not j.get('cancel_requested')) for j in rc.all_jobs()) else 1)"
}

say "waiting for gap 15 to end"
until ! systemctl --user is-active --quiet port-gap15.service; do sleep 60; done
if grep -q 'KERNEL CHECK FAILED' $SC/results/r22/gap15/summary.txt 2> /dev/null || [ -s $SC/tmp/port-gap.lockpid ]; then
  say "gap 15 ended with a kernel error or its gap still open - the chain stops here"
  note "GPU queue stopped" "Gap 15 ended with its gap open - see results/r22/gap15/summary.txt"; exit 1
fi
grep -q 'gap 15 done' $SC/results/r22/gap15/summary.txt || say "gap 15 did not finish normally (see its summary) - the Basalt check runs anyway (it only needs the build)"

# 1 the Basalt PR #90 check
say "1 Basalt PR #90 check (bp90.sh)"
bash $SC/work/r22/basalt-pr90/bp90.sh 8>&- 9>&-
rc=$?
say "1 Basalt check ended rc $rc"
[ $rc = 3 ] && { note "GPU queue stopped" "Kernel error in the Basalt check - the gap is open"; exit 3; }
note "Basalt PR #90 check done" "results/r22/basalt-pr90/report.md"

# 2 the two remaining K4 tries
while user_jobs; do say "a Jan research job is queued or running - waiting"; sleep 300; done
say "2 K4 tries 2 and 3 (b-k4-full-2, -3)"
for k in 2 3; do
  r $DR/.venv/bin/python -I $DR/tools/fix-replay.py check --fix baseline,consist --setup --label b-k4-full-$k --run $R/codetool/run-full 8>&- 9>&-
done
$DR/.venv/bin/python -I $DR/staging/k4/tests/judge_k4.py b-k4-full-2:b-f5c-full b-k4-full-3:b-f5c-full > $F/k4-judge-tries23.txt 2>&1
bash $SC/bringup/lib/kcheck.sh bp90-chain-k4 >> $RLOG 2>&1
say "2 K4 tries done (fixes/k4-judge-tries23.txt); chain done"
note "GPU queue: K4 tries done" "fixes/k4-judge-tries23.txt"
