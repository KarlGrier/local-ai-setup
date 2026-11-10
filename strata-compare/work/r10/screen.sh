#!/bin/bash
# screen.sh LABEL CONFIG.json — round 9 (copy of round 7, copy of round 6) A/B screen = round 5's (work/r5/screen.sh) on the GUARDED server (work/r10/srv.sh):
# fresh server on 127.0.0.1:8081, cold model page cache, identical requests, no sampling fields (the config's
# 0.6/0.95/20/0.05 apply): warm-up 1K (discarded) · 1K r1-r3 · 32K r0 · 64K r0 · 120K r0 (each + 768 decoded tokens)
# · long reasoning math + code (8,192 cap) · correctness ×5 · the chat-switch test (chatsoak.py switch).
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
grep -E 'expert cache [0-9a]|VRAM free with|workers|sampling|borrows|chunk auto|row cache|engine 0|CUDA1|arena' "$ELOG" | tail -10
echo "vram after load: $(nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ' ')"
EP=$(pgrep -f "$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['exe'])") --serve" | head -1); echo "engine pid $EP pinned/locked: $(grep -E 'VmPin|VmLck|VmRSS' /proc/$EP/status 2>/dev/null | tr -s ' \t' ' ' | tr '\n' ' ')"
B=".venv/bin/python scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $L-$(date +%m%dT%H%M)"
$B warmup
$B speed --sizes 1k --reps 1,2,3
$B speed --sizes 32k --reps 0
$B speed --sizes 64k --reps 0
$B speed --sizes 120k --reps 0
$B longreason --items math,code --max-tokens 8192
$B correctness
.venv/bin/python work/r3/chatsoak.py switch --base http://127.0.0.1:8081 --label $L-switch --engine-log $ELOG
echo "vram at end: $(nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ' ')"
grep -ciE 'error|stall|no progress|watchdog' "$ELOG" | sed 's/^/engine log error-ish lines: /'
work/r10/srv.sh stop
scripts/stopmon.sh $L
echo "=== $(date -Is) $L done"
