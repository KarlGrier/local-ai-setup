#!/bin/bash
# warmdiag.sh — round 13 B2 diagnostics (CLI, exact7's pins, warm page cache): which part of A8-1 costs or saves round
# time? The warm build with STRATA_WARM unset (off), =2 (fixed slices only), =3 (warming, dynamic split), =1 (both);
# greedy math, 1,024 tokens, order off 2 3 1 1 3 2 off; then the p2000 run that crashed, with =1, twice.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 3500"
i=0
for m in 0 2 3 1 1 3 2 0; do
  i=$((i + 1))
  if [ $m = 0 ]; then E=""; else E="STRATA_WARM=$m"; fi
  COLD=0 ENVX="$E" work/r13/run.sh wd-$m-$i configs/R12W-off.json math 1024 $X > /dev/null
done
for i in 1 2; do COLD=0 ENVX="STRATA_WARM=1" work/r13/run.sh wdp-$i configs/R12W-off.json p2000 64 $X > /dev/null; echo "p2000 run $i: exit $(grep -o 'exit=[-0-9]*' <(grep wdp-$i logs/r13/guard/summary.txt | tail -1))"; done
.venv/bin/python - <<'PY'
import sys, statistics as st
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/r13")
from p0_table import parse
by = {}
for i, m in enumerate([0, 2, 3, 1, 1, 3, 2, 0], 1):
    d = parse(f"wd-{m}-{i}"); by.setdefault(m, []).append(d)
names = {0: "off", 2: "fixed slices only", 3: "warming, dynamic split", 1: "fixed slices + warming"}
b = st.mean(x.get("ms_round", 0) for x in by[0])
for m in (0, 2, 3, 1):
    ms = [x.get("ms_round", 0) for x in by[m]]
    print(f"{names[m]:24s} ms per round {' / '.join(f'{v:.2f}' for v in ms)} -> {100 * (st.mean(ms) / b - 1):+.1f} % ; outputs {sorted({x['out'] for x in by[m]})}")
PY
grep -h "strata warm" logs/r13/prof/wd-1-*.err | tail -2
