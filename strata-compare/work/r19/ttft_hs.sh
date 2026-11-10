#!/bin/bash
# ttft_hs.sh LABEL CONFIG.json - round 19 step 4: time to first token at 8K / 32K / 120K on a fresh guarded server, cold model
# page cache, the 9.5K warm-up, your sampling: 8K r0, 32K r1 + r2, 120K r0 + r1 (prompts/r15/speed-r15.json, each a
# different text), 768 tokens after each; the engine's per-request "prefill helper source" lines are counted.
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2
source $WS/bringup/lib/env.sh
cd $WS
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
N0=$(wc -l < $ELOG 2>/dev/null || echo 0)
.venv/bin/python scripts/evict.py ${EVICT_GLOB:-$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf} > /dev/null
echo "=== $(date -Is) $L start ($CFG)"
bringup/lib/srv.sh start $L "$CFG" || exit 1
.venv/bin/python work/r5/warmup.py http://127.0.0.1:8081
B=".venv/bin/python scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $L-$(date +%m%dT%H%M)"
export SPEED_FILE=r15/speed-r15
$B speed --sizes 8k --reps 0
$B speed --sizes 32k --reps 1,2
$B speed --sizes 120k --reps 0,1
tail -n +$((N0 + 1)) $ELOG | grep -E 'HELPER_SOURCE|helper cache holds' | head -2 | cut -c1-200
echo "prefill helper source lines: $(tail -n +$((N0 + 1)) $ELOG | grep -c 'prefill helper source:'); last: $(tail -n +$((N0 + 1)) $ELOG | grep 'prefill helper source:' | tail -1 | cut -c1-160)"
grep -ciE 'error|stall|no progress|watchdog' "$ELOG" | sed 's/^/engine log error-ish lines: /'
bringup/lib/srv.sh stop
echo "=== $(date -Is) $L done"
