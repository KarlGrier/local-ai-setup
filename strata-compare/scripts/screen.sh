#!/bin/bash
# screen.sh LABEL CONFIG.json [SERVER_PY] — one tuning screen: fresh server, fixed request sequence, stop.
# Sequence (identical for every experiment, so the adaptive expert cache sees the same history):
#   warmup 1k (discarded) · speed 1k r1-r3 · speed 32k r0 · correctness x5 (768 tokens, greedy set)
# Env: SCREEN_EXTRA="..." adds scenarios after the standard ones (e.g. "speed120 mt mtside").
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2 SRV=${3:-$WS/strata/serve/server.py}
cd $WS
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")

.venv/bin/python scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
(setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern 'strata --serve' --out logs/monitor-$L > /dev/null 2>&1 &)
echo "=== $(date -Is) $L start"
scripts/server-C.sh start "$CFG" "$SRV" || { scripts/stopmon.sh $L; exit 1; }
grep -E 'expert cache|VRAM free with everything|KV streaming|pool|workers|arena|hugetlb|HUGEPAGE' "$ELOG" | tail -12
B=".venv/bin/python scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $L-$(date +%m%dT%H%M)"
$B warmup
$B speed --sizes 1k --reps 1,2,3
$B speed --sizes 32k --reps 0
$B correctness
for s in ${SCREEN_EXTRA:-}; do
  case $s in
    speed120) $B speed --sizes 120k --reps 0;;
    speed4) $B speed --sizes 4k;;
    speed64) $B speed --sizes 64k --reps 0;;
    mt) $B multiturn;;
    mtside) $B multiturn --side;;
    longreason) $B longreason;;
    edit) $B edit --extra '{"reasoning_effort":"none"}';;
  esac
done
nvidia-smi --query-gpu=memory.used --format=csv,noheader
scripts/server-C.sh stop
scripts/stopmon.sh $L
echo "=== $(date -Is) $L done"
