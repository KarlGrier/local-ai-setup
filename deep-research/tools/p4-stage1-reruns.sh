#!/bin/bash
# p4-stage1-reruns.sh - phase 4 stage 1 follow-up 3 (the user, 10-21): the runs stage 1 lost, run again.
#   item 2 (notyet-check.py), with SearXNG 8889 up this time (stage 1's ran with every search failing):
#     f  the saved o03 reports: deep medium (10-19) and the two report replays (both said "pending")
#     g  false alarms: the o01, o02 and o07 deep medium reports
#   item 1 a: the setup checks stage 1 overwrote (every saved report is report.md, so o07 overwrote o01's three runs
#     and o03's run overwrote o07's run 1): o01 x3 and o07 run 1, now under distinct names (o01-report.setupcheck-k)
#     and with an output that cannot be lost to the cap (60,000 tokens; on finish=length or no JSON the check runs
#     again listing only contradicted / unsupported statements, marked mode "flagged-only")
# Same harness as p4-stage1.sh: Jan jobs first, 8080 on demand, then every service a step uses checked before it
# (tools/services_check.py: SearXNG 8889 / 8890 / 8888 + strata-proxy 8090), one step at a time, each holding
# run/bench.lock. New labels (s1r-), so stage 1's files stay as they are.  Log: logs/p4-stage1-reruns.log.
# tmp/p4-stage1-reruns.stop stops it between steps.
set -u
WS=/home/USER/ai/deep-research; cd $WS
LOG=$WS/logs/p4-stage1-reruns.log
SC=/home/USER/ai-speed-testing/strata-compare
PY=$WS/.venv/bin/python
R=results/bench2/runs; RP=results/bench2/replays
SETUP=$WS/user-setup.md
say() { echo "$(date '+%F %T') $*" >> $LOG; }
user_jobs() {
  /usr/bin/python3 -I -c "
import sys; sys.path.insert(0, '$WS/tools'); import research_common as rc
sys.exit(0 if any(j.get('state') in rc.ACTIVE or (j.get('state') == 'queued' and not j.get('user_paused') and not j.get('cancel_requested')) for j in rc.all_jobs()) else 1)"
}
proxy_ok() { [ "$(curl -s -m 10 -o /dev/null -w '%{http_code}' http://127.0.0.1:8090/v1/models)" = 200 ]; }
step() {   # step NAME CMD...: Jan first, 8080 up, every service checked, then the command (its own bench.lock)
  local name=$1; shift
  [ -e tmp/p4-stage1-reruns.stop ] && { say "stop file: stopping before $name"; exit 0; }
  if user_jobs; then say "a Jan job is queued or running: waiting"; while user_jobs; do sleep 120; done; fi
  env -u HTTP_PROXY -u HTTPS_PROXY $SC/configs/usability/bin/strata-ensure.sh "phase 4 stage 1 reruns" >> $LOG 2>&1 || { say "Strata not ready - stopping"; exit 1; }
  proxy_ok || { ./run-ldr.sh proxy >> $LOG 2>&1; proxy_ok; } || { say "strata-proxy not answering - stopping"; exit 1; }
  /usr/bin/python3 -I tools/services_check.py --proxy >> $LOG 2>&1 || { say "a service is down before $name (above) - stopping"; exit 1; }
  say "$name: $*"
  "$@" >> $LOG 2>&1 || say "$name: exit $?"
}

O7=$R/screen-extra-deep-medium/o07
say "p4-stage1-reruns started (pid $$)"
while [ -e tmp/bench2.hold ]; do sleep 60; done
step 2f $PY tools/notyet-check.py $R/screen-deep-medium/o03/report.md $RP/report/o03/report-medium.md \
  $RP/report/o03/report-xhigh.md --date 2026-10-19 --label s1r- --out $RP/notyet
step 2g $PY tools/notyet-check.py $R/screen-deep-medium/o01/report.md $R/screen-deep-medium/o02/report.md $O7/report.md \
  --label s1r- --out $RP/notyet
step 1a-o01 $PY tools/level-replay.py setupcheck $R/screen-deep-medium/o01/report.md --setup $SETUP --n 3 --out $RP/setup/saved
step 1a-o07 $PY tools/level-replay.py setupcheck $O7/report.md --setup $SETUP --n 1 --out $RP/setup/saved
bash $SC/bringup/lib/kcheck.sh p4-stage1-reruns >> $LOG 2>&1 && say "kcheck clean" || say "KCHECK FAILED"
say "p4-stage1-reruns done"
