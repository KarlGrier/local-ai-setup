#!/bin/bash
# p2_rank.sh BASECFG - round 18 part 2.1: each of our speed patches' gain on the RTX 5080 ALONE (served decode screen,
# your config's sampling): BASECFG's one-card copy (CUDA_VISIBLE_DEVICES = the 5080, no --expert-cache-device1) with all
# switches on, and with one patch switched off at a time; mirrored order base, X1..X7, X7..X1, base (each arm a fresh
# guarded server, cold page cache). Gain of patch X = base vs X-off (ms per verify round for exact / rounding patches;
# decode tok/s for the drafting ones). Two-card gains come from the ledger (Round 14) and Part 1.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r18 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB LR_MAX SPEED_FILE
PY=.venv/bin/python; BASE=${1:?base config name, e.g. Cstar16}; SS=$(date -Iseconds | cut -c1-19)
U5080=GPU-UUID-RTX5080
M="$PY bringup/lib/mkcfg.py"
$M r18-rk-base $BASE env.CUDA_VISIBLE_DEVICES=$U5080 args-=--expert-cache-device1 > /dev/null
declare -A OFF=([spec]=env.STRATA_SPEC_EXACT=0 [side]=env.STRATA_SIDE_MIXER=0 [a2]=env.STRATA_ROUTER_Q8K=0
                [b2]=env.STRATA_QSA_SPLIT_ATTN=0 [b1]=env.STRATA_GR_FORK=0 [gate]=env-STRATA_COST_GATE
                [tab]=env-STRATA_MMVQ_IL_ROWS)
ORDER=${ORDER:-"spec side a2 b2 b1 gate tab"}
for k in $ORDER; do $M r18-rk-$k r18-rk-base ${OFF[$k]} > /dev/null; done
for i in $(seq 60); do pgrep -f '/strata --serve' > /dev/null || break; sleep 1; done   # a server may still be exiting
pgrep -af '/strata --serve' > /dev/null && { echo "a model server is running: refusing"; exit 1; }
REV=$(echo $ORDER | tr ' ' '\n' | tac | tr '\n' ' ')
arm() {
  work/r18/thp_sampler.sh logs/r18/thp-rk-$1.txt & local TP=$!
  bringup/lib/decscreen.sh r18-rk-$1 configs/r18-rk-$2.json > logs/r18/rk-$1.log 2>&1
  kill $TP 2>/dev/null
  echo "$(date -Is) $1 done; $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-150); THP: $(tail -1 logs/r18/thp-rk-$1.txt | cut -d' ' -f4-)"
}
arm base-a base
for k in $ORDER; do arm $k-a $k; done
for k in $REV; do arm $k-b $k; done
arm base-b base
ARGS="BASE=r18-rk-base-a,r18-rk-base-b"; for k in $ORDER; do ARGS="$ARGS ${k^^}_OFF=r18-rk-$k-a,r18-rk-$k-b"; done
SINCE=$SS $PY bringup/lib/ab_table.py $ARGS > results/r18/p2-rank.md; cat results/r18/p2-rank.md
