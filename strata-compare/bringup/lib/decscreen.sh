#!/bin/bash
# decscreen.sh LABEL CONFIG.json — round 9 A.6: a decode-focused screen (cheaper than screen.sh) for speculation settings:
# fresh guarded server (bringup/lib/srv.sh), cold page cache, warm-up, then at your settings (the config's shared settings:
# T 1.0 / 0.95 / 20, min-p 0.05): long reasoning math + code (4,096-token cap), correctness x5, one 32K prompt + 768
# decoded tokens. Decode figures come from the engine (accepted output tokens / decode time) via results/runs.jsonl.
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2
source $WS/bringup/lib/env.sh
cd $WS
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
.venv/bin/python scripts/evict.py ${EVICT_GLOB:-$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf} > /dev/null
(setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern '/strata --serve' --out bringup/out/logs/monitor-$L > /dev/null 2>&1 &)
echo "=== $(date -Is) $L start ($CFG)"
bringup/lib/srv.sh start $L "$CFG" || { scripts/stopmon.sh $L; exit 1; }
EP=$(pgrep -f "$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['exe'])") --serve" | head -1); echo "engine args: $(tr '\0' ' ' < /proc/$EP/cmdline | grep -oE -- '--(spec|spec-split|spec-min-p|mtp-window) [^ ]*|--spec-split' | tr '\n' ' ')"
.venv/bin/python work/r5/warmup.py http://127.0.0.1:8081
B=".venv/bin/python scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $L-$(date +%m%dT%H%M)"
$B longreason --items math,code --max-tokens ${LR_MAX:-4096}   # round 15: LR_MAX=1536 on the stand-ins (~12 tok/s)
$B correctness
[ "${NO32K:-0}" = 1 ] || $B speed --sizes 32k --reps 1   # round 10: NO32K=1 on a 32K-context server (the prompt + 768 does not fit)
bringup/lib/srv.sh stop
scripts/stopmon.sh $L
echo "=== $(date -Is) $L done"
