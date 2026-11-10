#!/bin/bash
# ttftscreen.sh LABEL CONFIG.json — round 10 (v0.1.36 A/Bs): prompts of 1K x3, 4K x3, 32K x2, 120K x2 (speed set, each a different text, 768 decoded tokens after each) on a fresh guarded server, cold page cache, warm-up, your settings: TTFT per size and the decode after each size (cluster kernels, fused prompt experts).
# Decode figures come from the engine (accepted output tokens / decode time) via results/runs.jsonl; ttft_table.py.
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2
source $WS/work/r10/env.sh
cd $WS
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
.venv/bin/python scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
(setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern '/strata --serve' --out logs/r10/monitor-$L > /dev/null 2>&1 &)
echo "=== $(date -Is) $L start ($CFG)"
work/r10/srv.sh start $L "$CFG" || { scripts/stopmon.sh $L; exit 1; }
EP=$(pgrep -f "$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['exe'])") --serve" | head -1); grep -E 'prompt chunk|fused|cluster' "$ELOG" | tail -3
.venv/bin/python work/r5/warmup.py http://127.0.0.1:8081
B=".venv/bin/python scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $L-$(date +%m%dT%H%M)"
$B speed --sizes 1k --reps 1,2,3
$B speed --sizes 4k --reps 0,1,2
$B speed --sizes 32k --reps 0,1
$B speed --sizes 120k --reps 0,1
work/r10/srv.sh stop
scripts/stopmon.sh $L
echo "=== $(date -Is) $L done"
