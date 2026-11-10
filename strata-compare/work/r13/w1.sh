#!/bin/bash
# w1.sh — round 9: one-token windows W(1) for v5 (default) and v3 (STRATA_GR_V3=1): --spec 2 --spec-min-p 1.01 keeps every
# window at one token (the drafter still runs once a round); sampled seed 21, math + code, 768 tokens; alternating.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
S='--seed 21 --temperature 1.0 --top-p 0.95 --top-k 20'
for it in math code; do
  PROF_SAMPLING="$S" work/r13/run.sh W1b-$it configs/R9-C10.json $it 768 --spec 2 --spec-min-p 1.01 --suffix-draft 0 | grep -E 'exit' | tr '\n' ' '; echo
  ENVX=STRATA_GR_V3=1 PROF_SAMPLING="$S" work/r13/run.sh Wv3b-1-$it configs/R9-C10.json $it 768 --spec 2 --spec-min-p 1.01 --suffix-draft 0 | grep -E 'exit' | tr '\n' ' '; echo
done
.venv/bin/python work/r13/p0_table.py W1b-math Wv3b-1-math W1b-code Wv3b-1-code
