#!/bin/bash
# copyscreen.sh LABEL CONFIG.json — round 10 D.1: the copy-heavy screen (prompts/r10/copy-screen.json: two files returned
# with a rename, two answers that quote their sources word for word) on a fresh guarded server, cold page cache, warm-up,
# your settings. Tables: work/r12/ldr_table.py (scenario ldr-copy; kinds copy / quote).
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2
source $WS/work/r12/env.sh
cd $WS
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
.venv/bin/python scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
(setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern '/strata --serve' --out logs/r12/monitor-$L > /dev/null 2>&1 &)
echo "=== $(date -Is) $L start ($CFG, copy screen)"
work/r12/srv.sh start $L "$CFG" || { scripts/stopmon.sh $L; exit 1; }
grep -E 'expert cache [0-9]+ slots' "$ELOG" | tail -1
.venv/bin/python work/r5/warmup.py http://127.0.0.1:8081
.venv/bin/python work/r12/ldrbench.py --config $L --engine-log $ELOG --set copy --file prompts/r10/copy-screen.json --session $L-$(date +%m%dT%H%M)
work/r12/srv.sh stop
scripts/stopmon.sh $L
echo "=== $(date -Is) $L done"
