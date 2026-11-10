#!/bin/bash
# s1_c15ref.sh — round 16 step 1, a reference beside the share A/B: C*15 (configs/Cstar15.json, v0.1.40.2: no CPU share)
# on the same short-prompt set (two arms, fresh guarded servers, the same warm-ups), to see whether v0.1.41 with the share
# off reads short prompts as fast as v0.1.40.2 did. Rows in results/runs.jsonl as r16-s1-c15-a / -b; table appended to
# results/r16/s1-share.md.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
PY=.venv/bin/python
export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
unset GUARD_MEM_GIB GUARD_SWAP_GROW_GIB
SS=$(date -Iseconds | cut -c1-19)
for arm in c15-a c15-b; do
  L=r16-s1-$arm; CFG=$WS/configs/Cstar15.json
  ELOG=$($PY -c "import json; print(json.load(open('$CFG'))['log'])")
  $PY scripts/evict.py $EVICT_GLOB > /dev/null
  bringup/lib/srv.sh start $L "$CFG" || exit 1
  $PY work/r5/warmup.py http://127.0.0.1:8081
  B="$PY scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $L-$(date +%m%dT%H%M) --max-tokens 64"
  SPEED_FILE=r16/ttft-short $B speed --sizes w600
  SPEED_FILE=r16/ttft-short $B speed --sizes 512,1000
  bringup/lib/srv.sh stop
done
{ echo; echo "C*15 (v0.1.40.2) reference vs C*16 share off and on (all arms of the day):"
  SINCE=2026-10-08T14:59 $PY work/r16/s1_table.py C15=r16-s1-c15-a,r16-s1-c15-b OFF=r16-s1-off-a,r16-s1-off-b
  SINCE=2026-10-08T14:59 $PY work/r16/s1_table.py C15=r16-s1-c15-a,r16-s1-c15-b ON=r16-s1-on-a,r16-s1-on-b; } >> results/r16/s1-share.md
tail -9 results/r16/s1-share.md
