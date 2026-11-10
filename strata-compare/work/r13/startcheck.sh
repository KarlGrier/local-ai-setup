#!/bin/bash
# startcheck.sh LABEL CONFIG.json — round 9: does a config start under the memory guard (work/r13/srv.sh), how much VRAM is
# left, what did the engine size (cache slots, chunk, draft head), and does it answer one short request? Then stops it.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source work/r13/env.sh
L=$1 CFG=$2
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
echo "=== $(date -Is) startcheck $L ($CFG); before: MemAvailable $(awk '/MemAvailable/ {printf "%.1f GiB", $2/1048576}' /proc/meminfo), GPUs $(nvidia-smi --query-gpu=index,memory.free --format=csv,noheader | tr '\n' ' ')"
work/r13/srv.sh start $L "$CFG" || exit 1
sleep 3
echo "after load: GPUs used/free $(nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ' '); MemAvailable $(awk '/MemAvailable/ {printf "%.1f GiB", $2/1048576}' /proc/meminfo)"
grep -E 'expert cache|VRAM|free|draft|chunk|reserve|slots|arena|workers|KV|pcie|helper|CUDA1|vocab' "$ELOG" | tail -25
curl -s -m 300 http://127.0.0.1:8081/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"x","messages":[{"role":"user","content":"What is 17 * 23? Answer with the number only."}],"max_tokens":2048}' | \
  .venv/bin/python -c "import json,sys; d=json.load(sys.stdin); c=d['choices'][0]; print('answered:', c.get('finish_reason'), d.get('usage'), repr((c['message'].get('content') or '')[-80:]))"
echo "after request: GPUs used/free $(nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ' ')"
work/r13/srv.sh stop
echo "=== $(date -Is) startcheck $L done"
