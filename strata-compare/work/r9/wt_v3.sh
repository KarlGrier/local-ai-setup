#!/bin/bash
# wt_v3.sh — round 9 Phase 0.3: window time by tokens per window W(T) with upstream's v3 hyper-connection read
# (STRATA_GR_V3=1), same method as p05.sh's v5 runs (sampled seed 21, --spec T --spec-min-p 0 --suffix-draft 0, math +
# code, 768 tokens): per-size in-engine comparison of v3 vs v5 (each mode writes its own text, so only fixed-size windows
# compare). Through the queue, right after p05.sh.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
S='--seed 21 --temperature 1.0 --top-p 0.95 --top-k 20'
# W(1): --spec 1 is refused (T >= 2), so a floor above 1 keeps every window at one token (the drafter still runs once a
# round, as in a real one-token window): v5 and v3, alternating
for it in math code; do
  PROF_SAMPLING="$S" work/r9/run.sh W1-$it configs/R9-C10.json $it 768 --spec 2 --spec-min-p 1.01 --suffix-draft 0 | grep -E 'exit' | tr '\n' ' '; echo
  ENVX=STRATA_GR_V3=1 PROF_SAMPLING="$S" work/r9/run.sh Wv3-1-$it configs/R9-C10.json $it 768 --spec 2 --spec-min-p 1.01 --suffix-draft 0 | grep -E 'exit' | tr '\n' ' '; echo
done
for T in 2 3 4 5; do for it in math code; do
  ENVX=STRATA_GR_V3=1 PROF_SAMPLING="$S" work/r9/run.sh Wv3-$T-$it configs/R9-C10.json $it 768 --spec $T --spec-min-p 0 --suffix-draft 0 | grep -E 'exit' | tr '\n' ' '; echo
done; done
.venv/bin/python work/r9/p0_table.py $(for T in 1 2 3 4 5; do echo W$T-math Wv3-$T-math W$T-code Wv3-$T-code; done)
