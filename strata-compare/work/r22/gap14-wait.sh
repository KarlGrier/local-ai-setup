#!/bin/bash
# gap14-wait.sh - starts work/r22/gap14.sh (Karl 10-29: the per-switch check) once tonight's GPU work is over: the
# night-1029 chain and the toggle replays (units ldr-night-1029, ldr-toggle-1029) have ended. Log: logs/r22/gap14-wait.log.
set -u
LOG=/home/USER/ai-speed-testing/strata-compare/logs/r22/gap14-wait.log
say() { echo "$(date '+%F %T') $*" >> $LOG; }
say "waiting for night-1029 and toggle-1029 to end"
until ! systemctl --user is-active --quiet ldr-night-1029.service && ! systemctl --user is-active --quiet ldr-toggle-1029.service; do sleep 120; done
say "both ended; starting gap 14"
systemd-run --user --unit=port-gap14 --description="v0.2.7 port: gap 14, the per-switch check (work/r22/gap14.sh)" /bin/bash /home/USER/ai-speed-testing/strata-compare/work/r22/gap14.sh >> $LOG 2>&1
say "gap 14 unit started"
