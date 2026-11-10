#!/bin/bash
# s8_screens.sh CAND — round 14 step 8: C*14 (CAND) vs C*13.1 (configs/Cstar131.json), A B B A (A = C*13.1) on the LDR
# screen, the decode screen, the full screen and Round 12's two holdouts nobody ran before: the general one
# (work/r12/holdout12.py, sha256 0166287e...) and the LDR-shaped one (prompts/r12/ldr-holdout12.json, sha256 b1b69f98...).
# Tables -> results/r14/s8-{ldr,dec,full,hold,ldrhold}.md
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
CAND=${1:?candidate config}; P=$WS/configs/Cstar131.json; PY=.venv/bin/python
export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
sha256sum -c <<< "0166287ea93eade1ab420eb355771fad57bbac54d2eb1a34368b873466e48319  work/r12/holdout12.py" || exit 1
sha256sum -c <<< "b1b69f98c533d4ddbcf2c3add3bf0b7903bb9a2c1fdf7e5b33be182ad155c645  prompts/r12/ldr-holdout12.json" || exit 1
hold() {   # hold LABEL CFG : the general holdout on a fresh guarded server
  local L=$1 C=$2 E; E=$($PY -c "import json; print(json.load(open('$C'))['log'])")
  bringup/lib/with_server.sh $L $C -- "$PY work/r5/warmup.py http://127.0.0.1:8081; $PY work/r12/holdout12.py $L http://127.0.0.1:8081 $E"
}
ldrhold() {   # ldrhold LABEL CFG : the LDR-shaped holdout (12 requests) on a fresh guarded server
  local L=$1 C=$2 E; E=$($PY -c "import json; print(json.load(open('$C'))['log'])")
  bringup/lib/with_server.sh $L $C -- "$PY work/r5/warmup.py http://127.0.0.1:8081; $PY bringup/lib/ldrbench.py --config $L --engine-log $E --set holdout12 --file $WS/prompts/r12/ldr-holdout12.json --session $L"
}
SS=$(date -Iseconds | cut -c1-19)
for arm in "c131-a $P" "c14-a $CAND" "c14-b $CAND" "c131-b $P"; do
  set -- $arm
  bringup/lib/ldrscreen.sh r14-s8-L-$1 $2 > logs/r14/s8-L-$1.log 2>&1
  bringup/lib/decscreen.sh r14-s8-D-$1 $2 > logs/r14/s8-D-$1.log 2>&1
  bringup/lib/fullscreen.sh r14-s8-F-$1 $2 > logs/r14/s8-F-$1.log 2>&1
  hold r14-s8-H-$1 $2 > logs/r14/s8-H-$1.log 2>&1
  ldrhold r14-s8-LH-$1 $2 > logs/r14/s8-LH-$1.log 2>&1
done
SINCE=$SS $PY bringup/lib/ldr_table.py C131=r14-s8-L-c131-a,r14-s8-L-c131-b C14=r14-s8-L-c14-a,r14-s8-L-c14-b > results/r14/s8-ldr.md 2>&1
SINCE=$SS $PY bringup/lib/ab_table.py C131=r14-s8-D-c131-a,r14-s8-D-c131-b C14=r14-s8-D-c14-a,r14-s8-D-c14-b > results/r14/s8-dec.md 2>&1
SINCE=$SS $PY bringup/lib/ab_table.py C131=r14-s8-F-c131-a,r14-s8-F-c131-b C14=r14-s8-F-c14-a,r14-s8-F-c14-b > results/r14/s8-full.md 2>&1
SINCE=$SS $PY work/r14/hold12_table.py C131=r14-s8-H-c131-a,r14-s8-H-c131-b C14=r14-s8-H-c14-a,r14-s8-H-c14-b > results/r14/s8-hold.md 2>&1
SINCE=$SS $PY bringup/lib/ldr_table.py C131=r14-s8-LH-c131-a,r14-s8-LH-c131-b C14=r14-s8-LH-c14-a,r14-s8-LH-c14-b > results/r14/s8-ldrhold.md 2>&1
for t in ldr dec full hold ldrhold; do echo "s8 $t: $(grep -iE '^\| *decode' results/r14/s8-$t.md | head -1 | tr -s ' ' | cut -c1-200)"; done
