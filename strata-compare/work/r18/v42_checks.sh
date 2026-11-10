#!/bin/bash
# v42_checks.sh NAME TREE "SWITCH_ENV" - round 18 part 2 on v0.1.42 (your 12:00 message): pr_checks.sh against stock v0.1.42
# (tmp/r18/v42-main = 61b3fb5d): exact7 (both cards, the community report's stock flags, STRATA_PREFILL_CPU_SHARE=0) on
# TREE's build with the switch OFF -> must equal stock v0.1.42 7/7; with the switch ON; upstream's ctest on TREE's build.
# The CLI is not affected by v0.1.42's tail skip (its default is set only at serve start-up). No model server beside it.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
export RB_CACHE=$WS/tmp/r18; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
export PROMPT_DIR=$WS/bringup/out/r16/prompts
NAME=${1:?} TREE=${2:?} SW=${3:?}; PY=.venv/bin/python
for i in $(seq 60); do pgrep -f '/strata --serve' > /dev/null || break; sleep 1; done
pgrep -af '/strata --serve' > /dev/null && { echo "a model server is running: refusing"; exit 1; }
$PY bringup/lib/mkcfg.py r18v42-prc-$NAME-off r18v42-prc-main exe=$TREE/build/strata > /dev/null
args=""; for kv in $SW; do args="$args env.$kv"; done
$PY bringup/lib/mkcfg.py r18v42-prc-$NAME-on r18v42-prc-main exe=$TREE/build/strata $args > /dev/null
O=results/r18/v42-prc-$NAME.txt; : > $O
echo "stock v0.1.42 exact7 = run r18v42-e7-main" | tee -a $O
REF=r18v42-e7-main bringup/lib/exact7.sh r18v42-e7-$NAME-off configs/r18v42-prc-$NAME-off.json 2>&1 | tail -8 | sed 's/^/switch off: /' | tee -a $O
REF=r18v42-e7-main bringup/lib/exact7.sh r18v42-e7-$NAME-on configs/r18v42-prc-$NAME-on.json 2>&1 | tail -8 | sed 's/^/switch on: /' | tee -a $O
(cd $TREE && ctest --test-dir build -j1 --timeout 600 > $WS/results/r18/ctest-v42-$NAME.txt 2>&1); tail -5 results/r18/ctest-v42-$NAME.txt | sed 's/^/ctest PR: /' | tee -a $O
grep -E "\*\*\*Failed|Not Run|Timeout" results/r18/ctest-v42-$NAME.txt | sed 's/^/ctest PR failed: /' | tee -a $O
