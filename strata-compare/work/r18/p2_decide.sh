#!/bin/bash
# p2_decide.sh - round 18 part 2: upstream already has speculative rejection sampling (STRATA_SPEC_PROB, opt-in), the same
# exact algorithm as our STRATA_SPEC_EXACT. Before writing those pull requests: on the RTX 5080 alone (the community
# report's stock flags), served decode screen, each arm a fresh guarded server, mirrored order:
#   def   = stock main            prob = stock main + STRATA_SPEC_PROB=1
#   ours  = main + our exact sampling (pr18/spec) + STRATA_SPEC_EXACT=1
#   gate  = main + the cost gate (pr18/gate) + STRATA_SPEC_PROB=1 + STRATA_COST_GATE=data/cost_gate_flash_next_mtp.txt
#   df    = stock main + STRATA_DF_BRANCH=1 (upstream's own mixer branches)   side = main + our side mixer (pr18/side) =2
# (the side mixer would move into the top 3 if exact sampling is superseded; upstream's DF_BRANCH is the same idea)
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r18 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB LR_MAX SPEED_FILE
PY=.venv/bin/python; SS=$(date -Iseconds | cut -c1-19); M="$PY bringup/lib/mkcfg.py"
cp work/r17/cfg/cb-stock-5080.json configs/r18-dc-def.json; cp work/r17/cfg/cb-stock-5080.shared-settings.json configs/r18-dc-def.shared-settings.json
$M r18-dc-def r18-dc-def > /dev/null
$M r18-dc-prob r18-dc-def env.STRATA_SPEC_PROB=1 > /dev/null
$M r18-dc-ours r18-dc-def exe=tmp/r18/pr-spec/build/strata env.STRATA_SPEC_EXACT=1 > /dev/null
$M r18-dc-gate r18-dc-def exe=tmp/r18/pr-gate/build/strata env.STRATA_SPEC_PROB=1 env.STRATA_COST_GATE=$WS/tmp/r18/pr-gate/data/cost_gate_flash_next_mtp.txt > /dev/null
$M r18-dc-df r18-dc-def env.STRATA_DF_BRANCH=1 > /dev/null
$M r18-dc-side r18-dc-def exe=tmp/r18/pr-side/build/strata env.STRATA_SIDE_MIXER=2 > /dev/null
for i in $(seq 60); do pgrep -f '/strata --serve' > /dev/null || break; sleep 1; done
pgrep -af '/strata --serve' > /dev/null && { echo "a model server is running: refusing"; exit 1; }
for a in def-a prob-a ours-a gate-a df-a side-a side-b df-b gate-b ours-b prob-b def-b; do
  work/r18/thp_sampler.sh logs/r18/thp-dc-$a.txt & TP=$!
  bringup/lib/decscreen.sh r18-dc-$a configs/r18-dc-${a%-*}.json > logs/r18/dc-$a.log 2>&1
  kill $TP 2>/dev/null; echo "$(date -Is) $a done; $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-120)"
done
SINCE=$SS $PY bringup/lib/ab_table.py DEF=r18-dc-def-a,r18-dc-def-b PROB=r18-dc-prob-a,r18-dc-prob-b OURS=r18-dc-ours-a,r18-dc-ours-b GATE_PROB=r18-dc-gate-a,r18-dc-gate-b DF_BRANCH=r18-dc-df-a,r18-dc-df-b SIDE=r18-dc-side-a,r18-dc-side-b > results/r18/p2-decide.md; cat results/r18/p2-decide.md
bringup/lib/phase_end.sh r18-p2-decide 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
