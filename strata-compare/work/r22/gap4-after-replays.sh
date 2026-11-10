#!/bin/bash
# gap4-after-replays.sh - starts work/r22/gap4.sh once deep-research's level replays (tmp/replays-0900.sh) have ended and
# no research job from Jan is queued or running (the user's research goes first). Log: logs/r22/gap4-start.log
LOG=/home/USER/ai-speed-testing/strata-compare/logs/r22/gap4-start.log
say() { echo "$(date '+%F %T') $*" >> $LOG; }
user_jobs() {
  /usr/bin/python3 -I -c "
import sys; sys.path.insert(0, '/home/USER/ai/deep-research/tools'); import research_common as rc
sys.exit(0 if any(j.get('state') in rc.ACTIVE or (j.get('state') == 'queued' and not j.get('user_paused') and not j.get('cancel_requested')) for j in rc.all_jobs()) else 1)"
}
say "waiting for the level replays to end"
while pgrep -f "tmp/[r]eplays-0900.sh" > /dev/null; do sleep 60; done
say "replays ended: $(tail -1 /home/USER/ai/deep-research/logs/replays-2026-10-20.log)"
while user_jobs; do sleep 120; done
say "starting gap 4"
cd /home/USER/ai-speed-testing/strata-compare && work/r22/gap4.sh >> logs/r22/gap4.log 2>&1
say "gap 4 ended rc $?"
