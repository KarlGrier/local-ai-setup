#!/bin/bash
# s1_v3check.sh — round 14 step 1 follow-up: is STRATA_HEAD_MIX_MULTI's rounding change (sampled math splits at token
# 958 vs v0.1.39) its own, or the final mixer now going through the opt-in STRATA_GR_V3=1 read that my settings
# enable? Stock v0.1.40.1, exact7's sampled-math pin, GR_V3 unset: HEAD_MIX_MULTI default vs =0.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
CFG=bringup/out/r14/configs/stock.json; export PROMPT_DIR=$WS/bringup/out/r14/prompts EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 3500"; S='--seed 11 --temperature 1.0 --top-p 0.95 --top-k 20'
.venv/bin/python - $CFG <<'PY'
import json, sys
c = json.load(open(sys.argv[1])); c["env"].pop("STRATA_GR_V3", None)
json.dump(c, open("/home/USER/ai-speed-testing/strata-compare/work/r14/cfg/stock-nov3.json", "w"), indent=1)
PY
for arm in "on " "off STRATA_HEAD_MIX_MULTI=0"; do set -- $arm
  ENVX="${2:-}" PROF_SAMPLING="$S" bringup/lib/run.sh rb-r14-v3-$1 work/r14/cfg/stock-nov3.json math 1024 $X > /dev/null 2>&1; done
.venv/bin/python - <<'PY' | tee results/r14/s1-v3check.txt
import sys
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/bringup/lib")
from p0_table import parse
a, b = parse("rb-r14-v3-on")["out"], parse("rb-r14-v3-off")["out"]
print(f"GR_V3 unset, sampled math: HEAD_MIX_MULTI on {a} / off {b} -> {'identical: the change needs GR_V3=1' if a == b else 'DIFFERENT: HEAD_MIX_MULTI changes rounding by itself'}")
PY
