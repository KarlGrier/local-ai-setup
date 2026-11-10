#!/bin/bash
# p1_cand.sh - round 18 part 1: the clean candidate (engine-r18c, configs/r18-cand.json): exact7 vs C*16's hashes, a CLI
# A B B A against C*16 (GPU wait per round), then the #567 check (work/r18/p1_567.sh).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
export RB_CACHE=$WS/tmp/r18; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
export PROMPT_DIR=$WS/bringup/out/r16/prompts
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 3500"
REF=c16 bringup/lib/exact7.sh r18-e7-cand configs/r18-cand.json 2>&1 | tail -8
for arm in c16:a cand:a cand:b c16:b; do
  IFS=: read -r st s <<< "$arm"; C=configs/Cstar16.json; [ $st = cand ] && C=configs/r18-cand.json
  for it in math code; do bringup/lib/run.sh r18-cnd-$st-$s-$it $C $it 1024 $X > /dev/null; done
done
.venv/bin/python work/r18/cli_table.py r18-cnd "c16=C*16" "cand=candidate C*16.1" > results/r18/p1-cand-cli.md; cat results/r18/p1-cand-cli.md
work/r18/p1_567.sh r18-cand
