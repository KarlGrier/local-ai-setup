#!/bin/bash
# ldrscreen.sh LABEL CONFIG.json [SET] — round 10: the LDR-shaped screen (prompts/r10/ldr-SET.json, default screen) on a
# fresh GUARDED server (work/r11/srv.sh) with a cold model page cache: warm-up (discarded), then the set's requests in
# order at your settings (the config's shared settings). Decode = the engine's accepted output tokens / decode time.
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2 SET=holdout11   # round 11 G: the NEW LDR-shaped holdout (prompts/r11/ldr-holdout11.json, frozen)
source $WS/work/r11/env.sh
cd $WS
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
.venv/bin/python scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
(setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern '/strata --serve' --out logs/r11/monitor-$L > /dev/null 2>&1 &)
echo "=== $(date -Is) $L start ($CFG, ldr-$SET)"
work/r11/srv.sh start $L "$CFG" || { scripts/stopmon.sh $L; exit 1; }
.venv/bin/python work/r5/warmup.py http://127.0.0.1:8081
.venv/bin/python work/r11/ldrbench.py --config $L --engine-log $ELOG --set $SET --file prompts/r11/ldr-holdout11.json --session $L-$(date +%m%dT%H%M)
echo "vram at end: $(nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ' ')"
work/r11/srv.sh stop
scripts/stopmon.sh $L
echo "=== $(date -Is) $L done"
