#!/bin/bash
# p1_567.sh CAND - round 18 part 1: is our #567 transplant (rows 18-21) still slower than v0.1.41's own tokenizer path?
# Cached-turn TTFT (work/r18/ttft567b.py: a ~31K and a ~98K chat, 6 follow-ups each, history sent back), A B B A on CAND:
# NEW = as configured (our encoder), OLD = STRATA_PROMPT_ENCODER_OLD=1 (v0.1.41's own path, a full encode with its piece
# cache). Fresh guarded server per arm, cold page cache. Table -> results/r18/p1-567.md.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r18 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
P=.venv/bin/python; CAND=${1:?candidate config name}
$P bringup/lib/mkcfg.py r18-567-new $CAND > /dev/null
$P bringup/lib/mkcfg.py r18-567-old $CAND env.STRATA_PROMPT_ENCODER_OLD=1 > /dev/null
for arm in new-a old-a old-b new-b; do
  L=r18-567-$arm; CFG=configs/r18-567-${arm%-*}.json
  $P scripts/evict.py $EVICT_GLOB > /dev/null
  echo "=== $(date -Is) $L start"
  bringup/lib/srv.sh start $L "$CFG" > /dev/null || { echo "$L DID NOT START"; continue; }
  $P work/r5/warmup.py http://127.0.0.1:8081 > /dev/null
  timeout 1800 $P work/r18/ttft567b.py http://127.0.0.1:8081 $L 2>&1 | grep -E 'chat: first read'
  bringup/lib/srv.sh stop > /dev/null
  tail -1 bringup/out/logs/guard/summary.txt | cut -c1-150
done
$P work/r18/ttft567_table.py NEW=r18-567-new-a,r18-567-new-b OLD=r18-567-old-a,r18-567-old-b > results/r18/p1-567.md 2>&1; cat results/r18/p1-567.md
