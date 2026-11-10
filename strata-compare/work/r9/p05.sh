#!/bin/bash
# p05.sh — round 9 Phase 0.5: re-measure on C*10 what the backlog depends on (round 8 A.1 / A.4 methods):
#  1. window time by tokens per window W(T): CLI, C*10's flags, sampled at your settings (seed 21), --spec T
#     --spec-min-p 0 --suffix-draft 0 (every window full), T = 1..8, math + code, 768 tokens; ms per round incl. commit
#     + drafting (C*8: 16.0 + 3.9 ms per extra token);
#  2. served nsys traces (trace engine engine-r9t, capture = served windows 150-269): sampled (your settings) + greedy
#     -> flag wait per round (C*8: 3.54 of 19.86 ms) and the per-kernel GPU table (work/r9/nsys_analyze.py).
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
S='--seed 21 --temperature 1.0 --top-p 0.95 --top-k 20'
for T in 1 2 3 4 5 6 7 8; do for it in math code; do
  PROF_SAMPLING="$S" work/r9/run.sh W$T-$it configs/R9-C10.json $it 768 --spec $T --spec-min-p 0 --suffix-draft 0 | grep -E 'exit|speculation|decode ' | tr '\n' ' '; echo
done; done
.venv/bin/python work/r9/p0_table.py $(for T in 1 2 3 4 5 6 7 8; do echo W$T-math W$T-code; done)
work/r9/with_server.sh A1-nsys9-s configs/R9t-nsys-sampled.json -- ".venv/bin/python work/r5/warmup.py http://127.0.0.1:8081; .venv/bin/python work/r9/a1_client.py sampled"
work/r9/with_server.sh A1-nsys9-g configs/R9t-nsys-greedy.json -- ".venv/bin/python work/r5/warmup.py http://127.0.0.1:8081; .venv/bin/python work/r9/a1_client.py greedy"
for m in sampled greedy; do echo "=== nsys9-$m"; .venv/bin/python work/r9/nsys_analyze.py nsys9-$m > results/r9/nsys9-$m.txt 2>&1; head -60 results/r9/nsys9-$m.txt; done
