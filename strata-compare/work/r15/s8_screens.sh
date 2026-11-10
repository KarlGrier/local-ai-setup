#!/bin/bash
# s8_screens.sh CAND [TAG] — round 15 step 8: the candidate (v0.1.40.2 + our patches) vs C*14 (configs/Cstar14.json),
# A B B A (A = C*14) on the LDR screen, the decode screen and the full screen, each arm a fresh guarded server, your
# config, the 20 GB floor. Tables -> results/r15/s8-{ldr,dec,full}-TAG.md
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
CAND=${1:?candidate config} TAG=${2:-c15}; P=$WS/configs/Cstar14.json; PY=.venv/bin/python
export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
unset GUARD_MEM_GIB GUARD_SWAP_GROW_GIB LR_MAX
mkdir -p logs/r15
SS=$(date -Iseconds | cut -c1-19)
for arm in "c14-a $P" "$TAG-a $CAND" "$TAG-b $CAND" "c14-b $P"; do
  set -- $arm
  bringup/lib/ldrscreen.sh r15-s8-L-$1 $2 > logs/r15/s8-L-$1.log 2>&1
  bringup/lib/decscreen.sh r15-s8-D-$1 $2 > logs/r15/s8-D-$1.log 2>&1
  bringup/lib/fullscreen.sh r15-s8-F-$1 $2 > logs/r15/s8-F-$1.log 2>&1
done
SINCE=$SS $PY bringup/lib/ldr_table.py C14=r15-s8-L-c14-a,r15-s8-L-c14-b ${TAG^^}=r15-s8-L-$TAG-a,r15-s8-L-$TAG-b > results/r15/s8-ldr-$TAG.md 2>&1
SINCE=$SS $PY bringup/lib/ab_table.py C14=r15-s8-D-c14-a,r15-s8-D-c14-b ${TAG^^}=r15-s8-D-$TAG-a,r15-s8-D-$TAG-b > results/r15/s8-dec-$TAG.md 2>&1
SINCE=$SS $PY bringup/lib/ab_table.py C14=r15-s8-F-c14-a,r15-s8-F-c14-b ${TAG^^}=r15-s8-F-$TAG-a,r15-s8-F-$TAG-b > results/r15/s8-full-$TAG.md 2>&1
for t in ldr dec full; do echo "s8 $t: $(grep -iE '^\| *decode' results/r15/s8-$t-$TAG.md | head -1 | tr -s ' ' | cut -c1-200)"; done
