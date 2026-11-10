#!/bin/bash
# s1_share.sh — round 16 step 1: v0.1.41's CPU prompt-read share (STRATA_PREFILL_CPU_SHARE unset = upstream's default:
# auto for chunks below 1,024 tokens, on here) vs off (=0), on the candidate (configs/Cstar16.json: v0.1.41 + patches/r16p27, C*15's flags):
# A B B A (A = on), each arm a fresh guarded server, cold model page cache, the 9.5K warm-up + two ~600-token warm-ups
# (not counted), then 6 prompts of 512 and 6 of 1,000 tokens (prompts/r16/ttft-short.json; each a different text), 64
# tokens each, your sampling. Table -> results/r16/s1-share.md (client TTFT and the engine's prompt read time).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
PY=.venv/bin/python
export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
unset GUARD_MEM_GIB GUARD_SWAP_GROW_GIB
$PY bringup/lib/mkcfg.py r16-s1-on Cstar16 env-STRATA_PREFILL_CPU_SHARE > /dev/null
$PY bringup/lib/mkcfg.py r16-s1-off Cstar16 env.STRATA_PREFILL_CPU_SHARE=0 > /dev/null
SS=$(date -Iseconds | cut -c1-19)
for arm in on-a off-a off-b on-b; do
  L=r16-s1-$arm; CFG=$WS/configs/r16-s1-${arm%-*}.json
  ELOG=$($PY -c "import json; print(json.load(open('$CFG'))['log'])")
  $PY scripts/evict.py $EVICT_GLOB > /dev/null
  echo "=== $(date -Is) $L start ($CFG)"
  bringup/lib/srv.sh start $L "$CFG" || exit 1
  grep -E 'CPU share|share' "$ELOG" | tail -2
  $PY work/r5/warmup.py http://127.0.0.1:8081
  B="$PY scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $L-$(date +%m%dT%H%M) --max-tokens 64"
  SPEED_FILE=r16/ttft-short $B speed --sizes w600
  SPEED_FILE=r16/ttft-short $B speed --sizes 512,1000
  grep -ciE 'cpu gate|share' "$ELOG" | sed 's/^/engine log share lines: /'
  bringup/lib/srv.sh stop
done
SINCE=$SS $PY work/r16/s1_table.py ON=r16-s1-on-a,r16-s1-on-b OFF=r16-s1-off-a,r16-s1-off-b > results/r16/s1-share.md 2>&1
cat results/r16/s1-share.md
