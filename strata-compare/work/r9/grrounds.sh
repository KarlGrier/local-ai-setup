#!/bin/bash
# grrounds.sh — round 9 Phase 0.3: ms per round of C*10 with each hyper-connection read (v5 default / STRATA_GR_V3=1 /
# STRATA_GR_OLD=1), fixed computation (--adapt-swaps 0 --suffix-draft 0 --expert-cache 3500), sampled at your settings
# (seed 11) on math + code (1,024 tokens), greedy math once; two rounds in mirrored order. Through the queue.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 3500"
S='--seed 11 --temperature 1.0 --top-p 0.95 --top-k 20'   # the CLI has no min-p flag (as in round 8)
env_of() { case $1 in v5) echo "";; v3) echo "STRATA_GR_V3=1";; old) echo "STRATA_GR_OLD=1";; esac; }
for rep in 1 2; do
  order="v5 v3 old"; [ $rep = 2 ] && order="old v3 v5"
  for m in $order; do
    for it in math code; do
      ENVX="$(env_of $m)" PROF_SAMPLING="$S" work/r9/run.sh gr-$m-s-$it-$rep configs/R9-C10.json $it 1024 $X | tail -3
    done
    [ $rep = 1 ] && ENVX="$(env_of $m)" work/r9/run.sh gr-$m-g-math-1 configs/R9-C10.json math 1024 $X | tail -2
  done
done
.venv/bin/python work/r9/p0_table.py $(for m in v5 v3 old; do for it in math code; do echo gr-$m-s-$it-1 gr-$m-s-$it-2; done; echo gr-$m-g-math-1; done)
