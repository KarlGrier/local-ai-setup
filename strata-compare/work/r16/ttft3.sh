#!/bin/bash
# ttft3.sh LABEL CONFIG.json — round 16 step 2: time to first token at 8K / 32K / 120K on a fresh guarded server, cold model
# page cache, the 9.5K warm-up, your sampling: 8K r0, 32K r1 + r2, 120K r1 (prompts/r15/speed-r15.json; the full screen
# reads 32K r0 and 120K r0, so every prompt of an arm is a different text), 768 tokens after each.
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2
source $WS/bringup/lib/env.sh
cd $WS
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
.venv/bin/python scripts/evict.py ${EVICT_GLOB:-$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf} > /dev/null
echo "=== $(date -Is) $L start ($CFG)"
bringup/lib/srv.sh start $L "$CFG" || exit 1
.venv/bin/python work/r5/warmup.py http://127.0.0.1:8081
B=".venv/bin/python scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $L-$(date +%m%dT%H%M)"
export SPEED_FILE=r15/speed-r15
$B speed --sizes 8k --reps 0
$B speed --sizes 32k --reps 1,2
$B speed --sizes 120k --reps 1
grep -ciE 'error|stall|no progress|watchdog' "$ELOG" | sed 's/^/engine log error-ish lines: /'
bringup/lib/srv.sh stop
echo "=== $(date -Is) $L done"
