#!/bin/bash
# final_run.sh LABEL CONFIG.json SERVER_PY — the full suite on the final configuration. Requests carry no sampling
# fields (like Open WebUI), so the config's "sampling" block applies (temperature 0.6, top-p 0.95, top-k 20,
# min-p 0.05); the correctness set sends temperature 0 (greedy).
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2 SRV=$3
cd $WS
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
.venv/bin/python scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
(setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern 'strata --serve' --out logs/monitor-$L > /dev/null 2>&1 &)
echo "=== $(date -Is) $L start"
scripts/server-C.sh start "$CFG" "$SRV" || { scripts/stopmon.sh $L; exit 1; }
grep -E 'expert cache [0-9]|VRAM free with|workers|sampling' "$ELOG" logs/server-C_*.log 2>/dev/null | tail -5
B=".venv/bin/python scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $L"
for s in ${STEPS:-warmup speed mt mtside correctness longreason quality edit compat}; do
  echo "=== $(date -Is) $L $s"
  case $s in
    warmup) $B warmup;;
    speed) $B speed;;
    mt) $B multiturn;;
    mtside) $B multiturn --side;;
    correctness) $B correctness --extra '{"temperature":0}';;
    longreason) $B longreason;;
    quality) $B quality;;
    edit) $B edit --extra '{"reasoning_effort":"none"}';;
    compat) timeout 1200 .venv/bin/python scripts/compat.py --base http://127.0.0.1:8081 --config $L \
              --strata-template $WS/strata-v0111/packs/iq3_s/tokenizer/chat_template.jinja > logs/compat-$L.log 2>&1; tail -3 logs/compat-$L.log;;
  esac
done
nvidia-smi --query-gpu=memory.used --format=csv,noheader
scripts/server-C.sh stop
scripts/stopmon.sh $L
echo "=== $(date -Is) $L done"
