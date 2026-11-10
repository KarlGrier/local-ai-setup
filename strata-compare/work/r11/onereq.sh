#!/bin/bash
# onereq.sh LABEL CONFIG.json IDS [SET] — round 11: a few LDR-shaped requests (ldrbench --ids) on a fresh guarded server
# (cold page cache, warm-up), then the engine log's per-request lines (decode time, the host's wait for the helper).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source work/r11/env.sh
L=$1 CFG=$2 IDS=$3 SET=${4:-screen}
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
.venv/bin/python scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
work/r11/srv.sh start $L "$CFG" || exit 1
L0=$(wc -l < "$ELOG")
.venv/bin/python work/r5/warmup.py http://127.0.0.1:8081
.venv/bin/python work/r11/ldrbench.py --config $L --engine-log $ELOG --set $SET --ids $IDS --session $L-$(date +%m%dT%H%M)
work/r11/srv.sh stop
tail -n +$L0 "$ELOG" | grep -E 'generated in|CUDA1:|strata decode timing' | cut -c1-260
