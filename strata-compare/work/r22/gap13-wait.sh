#!/bin/bash
# gap13-wait.sh - starts work/r22/gap13.sh (the hand-ported v0.2.7 port's gates) once the second 10-24 bundle rerun has
# ended (deep-research results/bench2/fixes/chain.log: "after-stage3: second rerun ended: rc 0, kernel check rc 0") and the
# after-stage3 unit has stopped. Karl 10-29: port gates after the rerun. A rerun that did not end cleanly: nothing starts
# (logged, desktop notice). Log: logs/r22/gap13-wait.log.
set -u
CH=/home/USER/ai/deep-research/results/bench2/fixes/chain.log
LOG=/home/USER/ai-speed-testing/strata-compare/logs/r22/gap13-wait.log
say() { echo "$(date '+%F %T') $*" >> $LOG; }
say "waiting for the second 10-24 rerun to end"
until grep -q 'after-stage3: second rerun ended' $CH && ! systemctl --user is-active --quiet ldr-after-stage3.service; do sleep 60; done
if ! grep -q 'after-stage3: second rerun ended: rc 0, kernel check rc 0' $CH; then
  say "the rerun did not end cleanly ($(grep 'second rerun ended' $CH | tail -1)) - gap 13 not started"
  notify-send -a "Strata port" "Gap 13 not started" "The second 10-24 rerun did not end cleanly - see deep-research fixes/chain.log" 2> /dev/null || true
  exit 1
fi
say "rerun ended cleanly; starting gap 13"
systemd-run --user --unit=port-gap13 --description="v0.2.7 port: gap 13, the hand-port's gates (work/r22/gap13.sh)" /bin/bash /home/USER/ai-speed-testing/strata-compare/work/r22/gap13.sh >> $LOG 2>&1
say "gap 13 unit started"
