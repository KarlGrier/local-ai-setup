#!/bin/bash
# s4_gate.sh — round 14 step 4: the cost-aware draft gate (Round 12's r12-gate, rebased onto r14-port as r14-gate,
# engine-r14g): (1) its chi-square sampler test on the gate build's real kernels (work/r13/ess_test.cu: Round 9's
# exact-sampling cases + the negative control + two COST GATE cases deciding the length step by step from the table),
# (2) a served A B B A on LDR and on decode: A = the full candidate on the gate build with the gate off, B = the same +
# STRATA_COST_GATE=configs/r12-cost-gate.txt (Round 12's table, fitted to this drafter on v0.1.39's window costs).
# Keep at >= +1 % on both. Output: results/r14/s4-*.{txt,md}
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
S=$WS/strata-r14g; mkdir -p tmp/r14/ess-gate
/usr/local/cuda-13.3/bin/nvcc -O2 -std=c++17 -arch=sm_120 -I$S/include -o tmp/r14/ess-gate/ess_test work/r13/ess_test.cu \
  $S/build/libstrata_kernels.a $S/build/libstrata_core.a -lcuda > results/r14/s4-ess-build.txt 2>&1
if [ -x tmp/r14/ess-gate/ess_test ]; then
  STRATA_COST_GATE=$WS/configs/r12-cost-gate.txt CUDA_VISIBLE_DEVICES=GPU-UUID-RTX5080 \
    .venv/bin/python bringup/lib/guard.py r14-ess-gate -- tmp/r14/ess-gate/ess_test ${N:-200000} > results/r14/s4-ess-gate.txt 2>&1
  echo "s4 chi-square: $(grep -E 'ALL PASS|FAIL' results/r14/s4-ess-gate.txt | tail -1)" | tee -a results/r14/s4-summary.txt
else
  echo "s4 chi-square: ess_test did not build (results/r14/s4-ess-build.txt)" | tee -a results/r14/s4-summary.txt; exit 1
fi
R=$WS/bringup/out/r14; D=$WS/work/r14/cfg; mkdir -p $D
.venv/bin/python - $R/configs/cand.json $D <<'PY'
import json, sys, shutil
from pathlib import Path
src, d = Path(sys.argv[1]), Path(sys.argv[2])
for arm, gate in (("off", None), ("on", "/home/USER/ai-speed-testing/strata-compare/configs/r12-cost-gate.txt")):
    c = json.loads(src.read_text())
    c["exe"] = "/home/USER/ai-speed-testing/strata-compare/engine-r14g/strata"
    c["env"]["STRATA_ADAPT_LAND"] = "2"
    if gate: c["env"]["STRATA_COST_GATE"] = gate
    c["log"] = str(d / f"s4-gate-{arm}.log")
    (d / f"s4-gate-{arm}.json").write_text(json.dumps(c, indent=1) + "\n")
    sh = src.with_suffix("").as_posix() + ".shared-settings.json"
    if Path(sh).exists(): shutil.copy(sh, d / f"s4-gate-{arm}.shared-settings.json")
PY
export PROMPT_DIR=$R/prompts EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
for sc in L D; do
  SS=$(date -Iseconds | cut -c1-19); X=bringup/lib/decscreen.sh; [ $sc = L ] && X=bringup/lib/ldrscreen.sh
  for arm in "off-a off" "on-a on" "on-b on" "off-b off"; do set -- $arm; $X r14-s4-$sc-$1 $D/s4-gate-$2.json > logs/r14/s4-$sc-$1.log 2>&1; done
  T=bringup/lib/ab_table.py; [ $sc = L ] && T=bringup/lib/ldr_table.py
  SINCE=$SS .venv/bin/python $T gate_off=r14-s4-$sc-off-a,r14-s4-$sc-off-b gate_on=r14-s4-$sc-on-a,r14-s4-$sc-on-b > results/r14/s4-$sc.md 2>&1
  echo "$(date -Is) s4 $sc: $(grep -iE '^\| *decode' results/r14/s4-$sc.md | head -1 | tr -s ' ' | cut -c1-200)" | tee -a results/r14/s4-summary.txt
done
grep -h "cost-aware draft length" $D/s4-gate-on.log | tail -1 | tee -a results/r14/s4-summary.txt
