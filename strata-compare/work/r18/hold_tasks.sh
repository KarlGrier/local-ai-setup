#!/bin/bash
# hold_tasks.sh - round 18: while the C*16.1 pipeline waits at its soak hold (nothing else on the GPUs): (1) the chat-cache
# round trips again on the twin with STRATA_STATE_HASH=1 (the gate's state-hash column), (2) Part 2's single-card
# ranking (work/r18/p2_rank.sh on C*16.1's one-card copy), (3) a phase end. Then I release the hold.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r18 PROMPT_DIR=$WS/bringup/out/r16z/prompts EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
P=.venv/bin/python; L=c161b
echo "=== $(date -Is) round trips with the state hash"
for m in "direct small $L-direct1" "direct small $L-direct2" "park small $L-park" "editref small $L-editref"; do
  bringup/lib/with_server.sh RT-$L configs/R161RT.json -- "$P bringup/lib/roundtrip.py $m" > /dev/null 2>&1
done
$P bringup/lib/rt_compare.py $L > results/r18/g-roundtrip-$L.md 2>&1; grep small results/r18/g-roundtrip-$L.md | cut -c1-200
echo "=== $(date -Is) single-card ranking"
work/r18/p2_rank.sh Cstar161 > logs/r18/p2-rank.log 2>&1; tail -25 logs/r18/p2-rank.log
bringup/lib/phase_end.sh r18-rank 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) hold tasks done"
