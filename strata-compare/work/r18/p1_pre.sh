#!/bin/bash
# p1_pre.sh - round 18 part 1, pre-screen (CLI, precise): where does C*16 lose ~3 % per verify round against C*14?
# C*14 (v0.1.40.1 + 34, B.3) and C*16 (v0.1.41 + 27, F4 instead of B.3, re-ported side mixer) with their served flags,
# exact7's fixed computation (--expert-cache 3500 --adapt-swaps 0 --suffix-draft 0), greedy math + code, 1,024 tokens:
# identical outputs on both builds -> identical windows -> ms per round compares like for like.
# States: on (as served) / il0 (STRATA_MMVQ_IL=0: B.3 off on C*14, F4 off on C*16) / sm0 (STRATA_SIDE_MIXER=0).
# A B B A (c14 c16 c16 c14) per state; cold page cache per run; guard 20 GiB / 300 MiB. 8080 must be stopped first.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
export RB_CACHE=$WS/tmp/r18; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
export PROMPT_DIR=$WS/bringup/out/r16/prompts
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 3500"
pgrep -af '/strata --serve' > /dev/null && { echo "a model server is running: refusing"; exit 1; }
for st in on il0 sm0; do
  case $st in on) E="";; il0) E="STRATA_MMVQ_IL=0";; sm0) E="STRATA_SIDE_MIXER=0";; esac
  for arm in c14:a c16:a c16:b c14:b; do
    IFS=: read -r b s <<< "$arm"; C=configs/Cstar${b#c}.json
    for it in math code; do ENVX="$E" bringup/lib/run.sh r18-pre-$st-$b-$s-$it $C $it 1024 $X > /dev/null; done
    echo "$(date -Is) $st $b-$s done; $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-160)"
  done
done
.venv/bin/python work/r18/p1_pre_table.py > results/r18/p1-pre.md 2>&1; cat results/r18/p1-pre.md
