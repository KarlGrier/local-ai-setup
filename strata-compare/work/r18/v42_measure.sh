#!/bin/bash
# v42_measure.sh NAME ENGINE "SWITCH_ENV" "BOTH_ENV" TS - round 18 part 2 on v0.1.42: stock v0.1.42 (tmp/r18/v42-main) against
# main + this patch only, on the RTX 5080 alone, A B B A, each arm a fresh guarded server (page cache dropped), the decode
# screen then the prompt-read screen; both arms run v0.1.42's own server (serve/server.py of the stock tree; the pull
# requests do not touch serve/). TS=on: upstream's defaults (STRATA_ROUTE_TAIL_SKIP=7 on single-GPU serve); TS=0: both arms
# with STRATA_ROUTE_TAIL_SKIP=0. Tables -> results/r18/v42-pr-NAME-one-ts{on,0}-{dec,ttft}.md.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r18 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB LR_MAX SPEED_FILE
NAME=${1:?} ENG=${2:?} SW=${3:?} BOTH=${4:-} TS=${5:?on|0}
PY=.venv/bin/python; SS=$(date -Iseconds | cut -c1-19)
for i in $(seq 60); do pgrep -f '/strata --serve' > /dev/null || break; sleep 1; done
pgrep -af '/strata --serve' > /dev/null && { echo "a model server is running: refusing"; exit 1; }
K=r18v42-pr-$NAME-one-ts$TS
bargs=""; for kv in $BOTH; do bargs="$bargs env.$kv"; done
[ "$TS" = 0 ] && bargs="$bargs env.STRATA_ROUTE_TAIL_SKIP=0"
$PY bringup/lib/mkcfg.py $K-main r18v42-base-one $bargs > /dev/null
args=""; for kv in $SW; do args="$args env.$kv"; done
$PY bringup/lib/mkcfg.py $K-pr $K-main exe=$ENG $args > /dev/null
for arm in main-a pr-a pr-b main-b; do
  C=configs/$K-${arm%-*}.json
  bringup/lib/decscreen.sh $K-D-$arm $C > logs/r18/$K-D-$arm.log 2>&1
  bringup/lib/ttftscreen.sh $K-T-$arm $C > logs/r18/$K-T-$arm.log 2>&1
  ts=$(grep -c "STRATA_ROUTE_TAIL_SKIP=7 is ON" $($PY -c "import json; print(json.load(open('$C'))['log'])") 2>/dev/null)
  echo "$(date -Is) $K $arm done (engine log: tail-skip ON lines so far $ts); $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-140)"
done
SINCE=$SS $PY bringup/lib/ab_table.py MAIN=$K-D-main-a,$K-D-main-b PR=$K-D-pr-a,$K-D-pr-b > results/r18/v42-pr-$NAME-one-ts$TS-dec.md
SINCE=$SS $PY bringup/lib/ttft_table.py MAIN=$K-T-main-a,$K-T-main-b PR=$K-T-pr-a,$K-T-pr-b > results/r18/v42-pr-$NAME-one-ts$TS-ttft.md
echo "== $NAME one ts$TS"; head -4 results/r18/v42-pr-$NAME-one-ts$TS-dec.md | tail -2; cat results/r18/v42-pr-$NAME-one-ts$TS-ttft.md
