#!/bin/bash
# w1c.sh — round 9 (v0.1.32 base, R10): one-token windows W(1) for v5 (default) and v3 (STRATA_GR_V3=1): --spec 2 --spec-min-p 1.01 keeps every
# window at one token (the drafter still runs once a round); sampled seed 21, math + code, 768 tokens; alternating.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
S='--seed 21 --temperature 1.0 --top-p 0.95 --top-k 20'
for it in math code; do
  PROF_SAMPLING="$S" work/r10/run.sh W1c-$it configs/R10.json $it 768 --spec 2 --spec-min-p 1.01 --suffix-draft 0 | grep -E 'exit' | tr '\n' ' '; echo
  ENVX=STRATA_GR_V3=1 PROF_SAMPLING="$S" work/r10/run.sh Wv3c-1-$it configs/R10.json $it 768 --spec 2 --spec-min-p 1.01 --suffix-draft 0 | grep -E 'exit' | tr '\n' ' '; echo
done
.venv/bin/python work/r10/p0_table.py W1c-math Wv3c-1-math W1c-code Wv3c-1-code
