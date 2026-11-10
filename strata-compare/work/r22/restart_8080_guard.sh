#!/bin/bash
# restart_8080_guard.sh OLD_GUARD_PID - round 22 (10-19 evening, floor 16 -> 12): the standing 8080 guard follows
# engine restarts and keeps the floor it started with, so a new floor needs a new guard. Starts one exactly as
# bringup/lib/phase_end.sh does for a kept server (label PHASE-END-ondemand), then stops the old one by PID.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
OLD=${1:?old guard pid}
CFG=$(grep -o 'CFG=\${STRATA_CONFIG:-[^}]*}' switch-model.sh | head -1 | sed 's/.*:-//; s/}//; s#\$WS#'$WS'#')
EXE=$(.venv/bin/python -c "import json,sys; print(json.load(open(sys.argv[1]))['exe'])" "$CFG")
(GUARD_VRAM_MODE=${GUARD_8080_VRAM_MODE:-warn60} GUARD_FOLLOW_PORT=8080 \
 setsid nohup .venv/bin/python bringup/lib/guard.py PHASE-END-ondemand --watch-pattern "$EXE --serve" > /dev/null 2>&1 < /dev/null &)
sleep 3
kill "$OLD" 2> /dev/null && echo "old guard $OLD stopped"
