#!/bin/bash
# screen.sh LABEL CONFIG.json — round-3 screen (= round-2 screen3.sh; server from the config key "server", default the v0.1.12 deploy tree). Fresh server, cold model
# page cache, identical request sequence: warm-up 1K (discarded) · speed 1K r1-r3 · 32K r0 · correctness ×5 (768 tok).
# NO request carries sampling fields → the config's sampling block applies (0.6/0.95/20/0.05), as in Open WebUI.
# SCREEN_EXTRA: lr8k (long-reasoning math, 8,192-token cap), speed120, mtside, edit, reread32 (same 32K doc, new chat)
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2
SRV=$($WS/.venv/bin/python -c "import json; print(json.load(open('$2')).get('server', '$WS/strata-r3-run/serve/server.py'))" 2>/dev/null || echo $WS/strata-r3-run/serve/server.py)
cd $WS
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
.venv/bin/python scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
(setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern 'strata --serve' --out logs/r3/monitor-$L > /dev/null 2>&1 &)
echo "=== $(date -Is) $L start"
scripts/server-C.sh start "$CFG" "$SRV" || { scripts/stopmon.sh $L; exit 1; }
grep -E 'expert cache [0-9a]|VRAM free with|workers|sampling|lent|row cache|PLE on' "$ELOG" | tail -8
# PREWARM=after: read the n-gram shard into the page cache once the server is up (the "table in RAM" arm)
[ "${PREWARM:-}" = after ] && { t=$(date +%s.%N); cat $WS/models/ISTA-GSQ-RCO/IQ3_S/*00002-of-00002.gguf > /dev/null; echo "prewarm $(echo "$(date +%s.%N)-$t"|bc) s; $(grep MemAvailable /proc/meminfo)"; }
echo "vram after load: $(nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader)"
B=".venv/bin/python scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $L-$(date +%m%dT%H%M)"
$B warmup
$B speed --sizes 1k --reps 1,2,3
$B speed --sizes 32k --reps 0
$B correctness
for s in ${SCREEN_EXTRA:-}; do
  case $s in
    lr8k) $B longreason --items math --max-tokens 8192;;
    speed120) $B speed --sizes 120k --reps 0;;
    mtside) $B multiturn --side;;
    edit) $B edit --extra '{"reasoning_effort":"none"}';;
  esac
done
echo "vram at end: $(nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader)"
scripts/server-C.sh stop
scripts/stopmon.sh $L
echo "=== $(date -Is) $L done"
