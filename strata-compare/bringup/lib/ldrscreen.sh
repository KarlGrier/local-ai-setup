#!/bin/bash
# ldrscreen.sh LABEL CONFIG.json [SET] — round 10: the LDR-shaped screen (prompts/r10/ldr-SET.json, default screen) on a
# fresh GUARDED server (bringup/lib/srv.sh) with a cold model page cache: warm-up (discarded), then the set's requests in
# order at your settings (the config's shared settings). Decode = the engine's accepted output tokens / decode time.
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2 SET=${3:-screen}
source $WS/bringup/lib/env.sh
cd $WS
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
.venv/bin/python scripts/evict.py ${EVICT_GLOB:-$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf} > /dev/null
(setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern '/strata --serve' --out bringup/out/logs/monitor-$L > /dev/null 2>&1 &)
echo "=== $(date -Is) $L start ($CFG, ldr-$SET)"
bringup/lib/srv.sh start $L "$CFG" || { scripts/stopmon.sh $L; exit 1; }
.venv/bin/python work/r5/warmup.py http://127.0.0.1:8081
.venv/bin/python bringup/lib/ldrbench.py --config $L --engine-log $ELOG --set $SET --session $L-$(date +%m%dT%H%M)
echo "vram at end: $(nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ' ')"
bringup/lib/srv.sh stop
scripts/stopmon.sh $L
echo "=== $(date -Is) $L done"
