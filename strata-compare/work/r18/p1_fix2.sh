#!/bin/bash
# p1_fix.sh - round 18 part 1: the two fixes on the r18 build (engine-r18p1 = C*16's tree + STRATA_SIDE_IL / STRATA_QUANT_IL,
# both opt-in), CLI fixed computation as p1_pre.sh (greedy math + code, 1,024 tokens, cold page cache), C*16's flags.
#   1. exactness: exact7 with both switches off and with both on, against C*16's hashes (REF=c16 labels from Round 16)
#   2. ms per round, A B B A per arm pair: off / side / quant / both on the r18 build, C*14 alongside (same session)
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
export RB_CACHE=$WS/tmp/r18; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
export PROMPT_DIR=$WS/bringup/out/r16/prompts
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 3500"
C18=configs/r18-p1.json
pgrep -af '/strata --serve' > /dev/null && { echo "a model server is running: refusing"; exit 1; }
if [ "${SKIP_EXACT:-0}" != 1 ]; then
  echo "=== $(date -Is) exact7: switches off, then both on"
  PROMPT_DIR=$WS/bringup/out/r16/prompts REF=${REF:-c16} bringup/lib/exact7.sh r18-e7-off $C18 2>&1 | tail -10
  ENVX="STRATA_SIDE_IL=1 STRATA_QUANT_IL=1" PROMPT_DIR=$WS/bringup/out/r16/prompts REF=${REF:-c16} bringup/lib/exact7.sh r18-e7-both $C18 2>&1 | tail -10
fi
for arm in side:a sq:a off:a c14:a c14:b off:b sq:b side:b; do
  IFS=: read -r st s <<< "$arm"
  case $st in off) E=""; C=$C18;; side) E="STRATA_SIDE_IL=1"; C=$C18;; quant) E="STRATA_QUANT_IL=1"; C=$C18;;
              both) E="STRATA_SIDE_IL=1 STRATA_QUANT_IL=1"; C=$C18;; sq) E="STRATA_SIDE_IL=1 STRATA_SIDE_QKV_FIRST=1"; C=$C18;; c14) E=""; C=configs/Cstar14.json;; esac
  for it in math code; do ENVX="$E" bringup/lib/run.sh r18-fix2-$st-$s-$it $C $it 1024 $X > /dev/null; done
  echo "$(date -Is) $st-$s done; $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-140)"
done
.venv/bin/python work/r18/p1_fix_table.py r18-fix2 > results/r18/p1-fix2.md 2>&1; cat results/r18/p1-fix2.md
