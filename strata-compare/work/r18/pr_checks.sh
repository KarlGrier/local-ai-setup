#!/bin/bash
# pr_checks.sh NAME TREE "SWITCH_ENV" - round 18 part 2, per pull request (no model server runs beside it):
#   1. the default path: exact7 (seven fixed-computation outputs: greedy / seeded math and code at 1,024 tokens, 2K /
#      32K / 112K-token prompts) on stock main (bringup/out/r16/engine-stock = fb58e0db) and on TREE's build with the
#      switch OFF - the community report's stock flags, two cards, STRATA_PREFILL_CPU_SHARE=0 on both (v0.1.41's CPU
#      share makes short-prompt outputs timing-dependent; with it off stock repeats itself) -> the hashes must match 7/7
#   2. exact7 with the switch ON (an exact patch must match too; a rounding-level one is gated separately)
#   3. upstream's ctest suite on TREE's build and on stock main's (tmp/r18/wt-try/build), same machine, one at a time
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
export RB_CACHE=$WS/tmp/r18; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
export PROMPT_DIR=$WS/bringup/out/r16/prompts
NAME=${1:?} TREE=${2:?} SW=${3:?}; PY=.venv/bin/python
for i in $(seq 60); do pgrep -f '/strata --serve' > /dev/null || break; sleep 1; done   # a server (or its guard) still exiting
pgrep -af '/strata --serve' > /dev/null && { echo "a model server is running: refusing"; exit 1; }
cp work/r17/cfg/cb-stock.json configs/r18-prc-main.json; cp work/r17/cfg/cb-stock.shared-settings.json configs/r18-prc-main.shared-settings.json
$PY bringup/lib/mkcfg.py r18-prc-main r18-prc-main env.STRATA_PREFILL_CPU_SHARE=0 > /dev/null
$PY bringup/lib/mkcfg.py r18-prc-$NAME-off r18-prc-main exe=$TREE/build/strata > /dev/null
args=""; for kv in $SW; do args="$args env.$kv"; done
$PY bringup/lib/mkcfg.py r18-prc-$NAME-on r18-prc-main exe=$TREE/build/strata $args > /dev/null
O=results/r18/prc-$NAME.txt; : > $O
if [ ! -f bringup/out/logs/prof/r18-e7-main-x-112k.out ]; then
  REF=c16 bringup/lib/exact7.sh r18-e7-main configs/r18-prc-main.json 2>&1 | tail -8 | sed 's/^/stock main: /' | tee -a $O
fi
echo "stock main exact7 = run r18-e7-main" | tee -a $O
REF=r18-e7-main bringup/lib/exact7.sh r18-e7-$NAME-off configs/r18-prc-$NAME-off.json 2>&1 | tail -8 | sed 's/^/switch off: /' | tee -a $O
REF=r18-e7-main bringup/lib/exact7.sh r18-e7-$NAME-on configs/r18-prc-$NAME-on.json 2>&1 | tail -8 | sed 's/^/switch on: /' | tee -a $O
if [ ! -f results/r18/ctest-main.txt ]; then
  (cd tmp/r18/wt-try && ctest --test-dir build -j1 --timeout 600 > $WS/results/r18/ctest-main.txt 2>&1); tail -5 results/r18/ctest-main.txt | sed 's/^/ctest main: /' | tee -a $O
fi
(cd $TREE && ctest --test-dir build -j1 --timeout 600 > $WS/results/r18/ctest-$NAME.txt 2>&1); tail -5 results/r18/ctest-$NAME.txt | sed 's/^/ctest PR: /' | tee -a $O
grep -E "\*\*\*Failed|Not Run|Timeout" results/r18/ctest-main.txt | sed 's/^/ctest main failed: /' | tee -a $O
grep -E "\*\*\*Failed|Not Run|Timeout" results/r18/ctest-$NAME.txt | sed 's/^/ctest PR failed: /' | tee -a $O
