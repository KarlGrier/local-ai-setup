#!/bin/bash
# d7_speed.sh CAND [TAG] - round 19 Part D (copy of b6_screens.sh): CAND against A_CFG (default C*17, configs/Cstar17.json)
# as served, A B B A (A = A_CFG), each arm a fresh guarded server, your config and
# sampling, the 20 GB floor: the LDR screen, the decode screen and the full screen per arm.
# Tables -> results/r19/d7-{ldr,dec,full}-TAG.md. Ends with the promoted build on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
CAND=${1:?candidate config} TAG=${2:-c171}; A=$WS/${A_CFG:-configs/Cstar17.json}; AT=${A_TAG:-c17}; PY=.venv/bin/python
export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB LR_MAX SPEED_FILE
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
SS=$(date -Iseconds | cut -c1-19)
for arm in "$AT-a $A" "$TAG-a $CAND" "$TAG-b $CAND" "$AT-b $A"; do
  set -- $arm
  bringup/lib/ldrscreen.sh r19-d7-L-$1 $2 > logs/r19/d7-L-$1.log 2>&1
  bringup/lib/decscreen.sh r19-d7-D-$1 $2 > logs/r19/d7-D-$1.log 2>&1
  bringup/lib/fullscreen.sh r19-d7-F-$1 $2 > logs/r19/d7-F-$1.log 2>&1
  echo "=== $(date -Is) arm $1 done: $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-120)"
done
U=${TAG^^}
SINCE=$SS $PY bringup/lib/ldr_table.py ${AT^^}=r19-d7-L-$AT-a,r19-d7-L-$AT-b $U=r19-d7-L-$TAG-a,r19-d7-L-$TAG-b > results/r19/d7-ldr-$TAG.md 2>&1
SINCE=$SS $PY bringup/lib/ab_table.py ${AT^^}=r19-d7-D-$AT-a,r19-d7-D-$AT-b $U=r19-d7-D-$TAG-a,r19-d7-D-$TAG-b > results/r19/d7-dec-$TAG.md 2>&1
SINCE=$SS $PY bringup/lib/ab_table.py ${AT^^}=r19-d7-F-$AT-a,r19-d7-F-$AT-b $U=r19-d7-F-$TAG-a,r19-d7-F-$TAG-b > results/r19/d7-full-$TAG.md 2>&1
for f in results/r19/d7-*-$TAG.md; do echo "$f: $(grep -iE '^\| *(decode|ms per|ttft)' $f | head -4 | tr -s ' ' | tr '\n' ' ' | cut -c1-300)"; done
bringup/lib/phase_end.sh r19-d7 keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) d7 done"
