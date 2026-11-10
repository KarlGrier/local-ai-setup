#!/bin/bash
# s5_b3swap.sh — round 14 step 5 (the B.3 table): the runbook re-derived B.3's rows-a-warp table on v0.1.40.1 (17 of 80
# cells differ) -> patches/r14c36 = r14c35 + that table. Keep r14c35's engine (engine-r14f35) for the A/B, re-clone and
# build r14f with r14c36 (clean clone), then: all-on exact7 vs r14c35's candidate (rb-r14f-cand) must be 7/7 (the table
# only moves work between kernels; every choice is bitwise native_mmvq's output), B.3's own pair gate, and a decode
# A B B A old table vs new; finally C*14's assets are re-made from the new build.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
R=$WS/bringup/out/r14f; D=$WS/work/r14/cfg
mkdir -p engine-r14f35 && cp $R/engine-patched/strata engine-r14f35/strata && sha256sum engine-r14f35/strata
.venv/bin/python - <<'PY'
import json, shutil
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); R = WS / "bringup/out/r14f"; D = WS / "work/r14/cfg"
c = json.loads((R / "configs/cand.json").read_text())
c["exe"] = str(WS / "engine-r14f35/strata"); c["log"] = str(D / "c14-35.log")
(D / "c14-35.json").write_text(json.dumps(c, indent=1) + "\n")
shutil.copy(R / "configs/cand.shared-settings.json", D / "c14-35.shared-settings.json")
PY
sed -i 's#^RB_PATCHES=.*#RB_PATCHES=/home/USER/ai-speed-testing/strata-compare/patches/r14c36#; s#^RB_MEAS=.*#RB_MEAS=/home/USER/ai-speed-testing/strata-compare/patches/r14-meas36#' $R/run.env
bringup/runbook.sh r14f clone build
export PROMPT_DIR=$R/prompts EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
REF=rb-r14f-cand bringup/lib/exact7.sh rb-r14f-cand36 $R/configs/cand.json 2>&1 | tail -1 | tee results/r14/s5-b3swap.txt
PT_TF_ONLY=0 CFG=$R/configs/cand.json TREE=bringup/out/r14f/strata-patched TFEXE=$R/engine-twin/strata bringup/patchtest.sh mmvq_il 2>&1 | tail -1 | tee -a results/r14/s5-b3swap.txt
SS=$(date -Iseconds | cut -c1-19)
for arm in "old-a $D/c14-35.json" "new-a $R/configs/cand.json" "new-b $R/configs/cand.json" "old-b $D/c14-35.json"; do
  set -- $arm; bringup/lib/decscreen.sh r14-s5-b3-$1 $2 > logs/r14/s5-b3-$1.log 2>&1; done
SINCE=$SS .venv/bin/python bringup/lib/ab_table.py table_r11=r14-s5-b3-old-a,r14-s5-b3-old-b table_r14=r14-s5-b3-new-a,r14-s5-b3-new-b > results/r14/s5-b3table-ab.md 2>&1
grep -E "^\| (decode|ms per)" results/r14/s5-b3table-ab.md | tee -a results/r14/s5-b3swap.txt
work/r14/build-cstar14.sh 2>&1 | tail -4 | tee -a results/r14/s5-b3swap.txt
