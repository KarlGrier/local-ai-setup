#!/bin/bash
# soakdec.sh LABEL CONFIG.json — round 10 Phase E: the decode screen's requests (long reasoning math + code at 4,096, the
# correctness set, one 32K prompt + 768) sent to the server ALREADY RUNNING on 127.0.0.1:8080 (the soaked C*12, after the
# 2-hour soak) — no restart, no warm-up, no cache eviction. Compare with decscreen.sh on a fresh server (ab_table.py).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
L=$1 CFG=$2
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
curl -sf http://127.0.0.1:8080/health > /dev/null || { echo "soakdec: nothing answers on 8080"; exit 1; }
echo "=== $(date -Is) $L start (8080 as it is; engine log $ELOG)"
B=".venv/bin/python scripts/bench.py --config $L --base http://127.0.0.1:8080 --model x --engine-log $ELOG --session $L-$(date +%m%dT%H%M)"
$B longreason --items math,code --max-tokens 4096
$B correctness
$B speed --sizes 32k --reps 1
echo "=== $(date -Is) $L done"
