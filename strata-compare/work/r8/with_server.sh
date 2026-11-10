#!/bin/bash
# with_server.sh LABEL CONFIG.json -- CMD...   round 8 (copy of round 7, copy of round 6): start a GUARDED test server on 127.0.0.1:8081 from CONFIG (cold
# model page cache, resource monitor; work/r8/srv.sh = the memory guard is its parent), run CMD (it gets $ELOG = the
# engine log), stop the server and the monitor.  WEB=1: start the local SearXNG for the test and stop it after.
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2; shift 3
cd $WS
source $WS/work/r8/env.sh
export ELOG=$($WS/.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
.venv/bin/python scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
(setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern '/strata --serve' --out logs/r8/monitor-$L > /dev/null 2>&1 &)
[ "${WEB:-0}" = 1 ] && websearch/searxng.sh start
echo "=== $(date -Is) $L start ($CFG)"
work/r8/srv.sh start $L "$CFG" || { scripts/stopmon.sh $L; exit 1; }
echo "vram after load: $(nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ' ')"
EP=$(pgrep -f "$($WS/.venv/bin/python -c "import json; print(json.load(open('$CFG'))['exe'])") --serve" | head -1); echo "engine pid $EP pinned/locked: $(grep -E 'VmPin|VmLck|VmRSS' /proc/$EP/status 2>/dev/null | tr -s ' \t' ' ' | tr '\n' ' ')"
bash -c "$*"
echo "vram at end: $(nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ' ')"
work/r8/srv.sh stop
[ "${WEB:-0}" = 1 ] && websearch/searxng.sh stop
scripts/stopmon.sh $L
echo "=== $(date -Is) $L done"
