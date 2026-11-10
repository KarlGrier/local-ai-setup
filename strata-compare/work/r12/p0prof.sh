#!/bin/bash
# p0prof.sh LABEL CONFIG.json — round 11 Phase 0.2: the served profile. A fresh GUARDED server (srv.sh, 8081), cold model
# page cache, the warm-up, then the LDR-shaped screen (prompts/r10/ldr-screen.json, 12 requests in file order) and long
# reasoning math + code (4,096 cap) at your settings. With the profile build's env (STRATA_R11_LAYERPROF /
# STRATA_VERIFY_PROFILE / STRATA_DECODE_TIMING) the engine log gets, per request, upstream's decode timing, the GPU stage
# stamps and the per-layer profile; work/r12/layer_table.py reads them.
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2
source $WS/work/r12/env.sh
cd $WS
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
.venv/bin/python scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
(setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern '/strata --serve' --out logs/r12/monitor-$L > /dev/null 2>&1 &)
echo "=== $(date -Is) $L start ($CFG)"
work/r12/srv.sh start $L "$CFG" || { scripts/stopmon.sh $L; exit 1; }
LINE0=$(wc -l < "$ELOG"); echo "engine log $ELOG from line $LINE0"
.venv/bin/python work/r5/warmup.py http://127.0.0.1:8081
.venv/bin/python work/r12/ldrbench.py --config $L --engine-log $ELOG --set screen --session $L-$(date +%m%dT%H%M)
B=".venv/bin/python scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $L-$(date +%m%dT%H%M)"
$B longreason --items math,code --max-tokens 4096
echo "vram at end: $(nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ' ')"
work/r12/srv.sh stop
scripts/stopmon.sh $L
tail -n +$LINE0 "$ELOG" > logs/r12/prof-$L.engine.log
echo "=== $(date -Is) $L done (engine log part: logs/r12/prof-$L.engine.log)"
