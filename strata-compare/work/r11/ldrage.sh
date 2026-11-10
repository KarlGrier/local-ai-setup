#!/bin/bash
# ldrage.sh LABEL CONFIG.json — round 11 C.1 "after an hour": one fresh guarded server (as ldrscreen.sh), warm-up, then
# Round 10's LDR aging pool (prompts/r10/ldr-pool.json, 60 requests from the trace corpus: ~35-40 min of other research
# traffic, label LABEL-age), then the LDR screen on the same server (label LABEL) - the screen after the adaptive tier and
# the chat cache have lived through that traffic. No web search, no SearXNG.
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2
source $WS/work/r11/env.sh
cd $WS
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
.venv/bin/python scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
(setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern '/strata --serve' --out logs/r11/monitor-$L > /dev/null 2>&1 &)
echo "=== $(date -Is) $L start ($CFG, ldr-pool then ldr-screen)"
work/r11/srv.sh start $L "$CFG" || { scripts/stopmon.sh $L; exit 1; }
.venv/bin/python work/r5/warmup.py http://127.0.0.1:8081
.venv/bin/python work/r11/ldrbench.py --config $L-age --engine-log $ELOG --set pool --session $L-age-$(date +%m%dT%H%M)
echo "=== $(date -Is) $L pool done; screen"
.venv/bin/python work/r11/ldrbench.py --config $L --engine-log $ELOG --set screen --session $L-$(date +%m%dT%H%M)
echo "vram at end: $(nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ' ')"
work/r11/srv.sh stop
scripts/stopmon.sh $L
echo "=== $(date -Is) $L done"
