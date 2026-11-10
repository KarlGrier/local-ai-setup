#!/bin/bash
# holdscreen.sh LABEL CONFIG.json — round 9 Phase C: the fresh holdout (work/r9/holdout.py: prompts no screen or
# decision used) on a fresh guarded server (work/r9/srv.sh), cold page cache, warm-up, your settings (the config's
# shared settings). Decode figures come from the engine (accepted output tokens / decode time) via results/runs.jsonl.
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2
source $WS/work/r9/env.sh
cd $WS
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
.venv/bin/python scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
(setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern '/strata --serve' --out logs/r9/monitor-$L > /dev/null 2>&1 &)
echo "=== $(date -Is) $L start ($CFG)"
work/r9/srv.sh start $L "$CFG" || { scripts/stopmon.sh $L; exit 1; }
EP=$(pgrep -f "$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['exe'])") --serve" | head -1); echo "engine args: $(tr '\0' ' ' < /proc/$EP/cmdline | grep -oE -- '--(spec|spec-split|spec-min-p|mtp-window) [^ ]*|--spec-split' | tr '\n' ' ')"
.venv/bin/python work/r5/warmup.py http://127.0.0.1:8081
.venv/bin/python work/r9/holdout.py $L http://127.0.0.1:8081 $ELOG
work/r9/srv.sh stop
scripts/stopmon.sh $L
echo "=== $(date -Is) $L done"
