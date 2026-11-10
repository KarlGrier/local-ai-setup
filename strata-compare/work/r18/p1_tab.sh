#!/bin/bash
# p1_tab.sh - round 18 part 1: F4's rows table on top of the side-mixer fixes (STRATA_SIDE_IL=1 STRATA_SIDE_QKV_FIRST=1):
# F4's shared table (sm_86 + sm_120) vs the table measured on this RTX 5080 by mmvq_il_parity --emit-table vs B.3's
# (C*14's) table, each via STRATA_MMVQ_IL_ROWS; C*14 alongside. CLI fixed computation, A B C D D C B A.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
export RB_CACHE=$WS/tmp/r18; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
export PROMPT_DIR=$WS/bringup/out/r16/prompts
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 3500"; F="STRATA_SIDE_IL=1 STRATA_SIDE_QKV_FIRST=1"
pgrep -af '/strata --serve' > /dev/null && { echo "a model server is running: refusing"; exit 1; }
for arm in sq:a t5080:a b3t:a c14:a c14:b b3t:b t5080:b sq:b; do
  IFS=: read -r st s <<< "$arm"
  case $st in sq) E="$F"; C=configs/r18-p1.json;; t5080) E="$F STRATA_MMVQ_IL_ROWS=$(cat work/r18/t5080-table.env)"; C=configs/r18-p1.json;;
              b3t) E="$F STRATA_MMVQ_IL_ROWS=$(cat work/r18/b3-table.env)"; C=configs/r18-p1.json;; c14) E=""; C=configs/Cstar14.json;; esac
  for it in math code; do ENVX="$E" bringup/lib/run.sh r18-tab-$st-$s-$it $C $it 1024 $X > /dev/null; done
  echo "$(date -Is) $st-$s done"
done
