#!/bin/bash
# screen.sh LABEL CONFIG.json — round-5 screen (= round 4 + switch test by default). Fresh server on 127.0.0.1:8081 (server from the config's
# "server" key), cold model page cache, identical request sequence, NO sampling fields in any request (the config's
# sampling block applies: 0.6/0.95/20/0.05, as for the chat page / Open WebUI):
#   warm-up 1K (discarded) · 1K r1-r3 · 32K r0 · 64K r0 · 120K r0 (each prompt + 768 decoded tokens = decode at depth)
#   · long reasoning math + code (8,192-token cap) · correctness ×5 (768 tokens)
# SCREEN_EXTRA: switch (round-3 chat-switch test, chatsoak.py switch)
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2
source $WS/work/r5/env.sh
SRV=$($WS/.venv/bin/python -c "import json; print(json.load(open('$CFG'))['server'])")
cd $WS
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
.venv/bin/python scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
(setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern 'strata --serve' --out logs/r5/monitor-$L > /dev/null 2>&1 &)
echo "=== $(date -Is) $L start ($CFG)"
scripts/server-C.sh start "$CFG" "$SRV" || { scripts/stopmon.sh $L; exit 1; }
grep -E 'expert cache [0-9a]|VRAM free with|workers|sampling|borrows|chunk auto|row cache|engine 0' "$ELOG" | tail -8
echo "vram after load: $(nvidia-smi -i GPU-UUID-RTX5080 --query-gpu=memory.used,memory.free --format=csv,noheader)"
B=".venv/bin/python scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $L-$(date +%m%dT%H%M)"
$B warmup
$B speed --sizes 1k --reps 1,2,3
$B speed --sizes 32k --reps 0
$B speed --sizes 64k --reps 0
$B speed --sizes 120k --reps 0
$B longreason --items math,code --max-tokens 8192
$B correctness
for s in ${SCREEN_EXTRA-switch}; do
  case $s in
    switch) .venv/bin/python work/r3/chatsoak.py switch --base http://127.0.0.1:8081 --label $L-switch --engine-log $ELOG;;
  esac
done
echo "vram at end: $(nvidia-smi -i GPU-UUID-RTX5080 --query-gpu=memory.used,memory.free --format=csv,noheader)"
grep -ciE 'error|stall|no progress|watchdog' "$ELOG" | sed 's/^/engine log error-ish lines: /'
scripts/server-C.sh stop
scripts/stopmon.sh $L
echo "=== $(date -Is) $L done"
