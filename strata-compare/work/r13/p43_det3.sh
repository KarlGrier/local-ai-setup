#!/bin/bash
# p43_det3.sh — round 13 Part 4.3: which part of the Q4 both-GPU --mmap-experts setup makes stock v0.1.39 not repeat?
# Greedy x-math (1,024 tokens, exact7's pins) 3x each on one GPU + --mmap-experts and one GPU + --resident-budget-gib.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
R=$WS/bringup/out/rehB; source $R/run.env
export EVICT_GLOB="$(dirname $RB_GGUF)/*.gguf" PROMPT_DIR=$R/prompts
PIN=$(.venv/bin/python -c "import json; print(min(3500, int(json.load(open('$R/fitplan.json'))['slots_5080'] * 0.9)))")
BUDGET=$(.venv/bin/python -c "import json; print(int(json.load(open('$R/fitplan.json'))['resident_budget_suggest_gib']))")
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache $PIN"
for n in 1 2 3; do for c in det-1budget; do bringup/lib/run.sh rb-rehB-$c-$n $R/configs/$c.json math 1024 $X > /dev/null; done; done
.venv/bin/python - <<'PY'
import sys
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/bringup/lib")
from p0_table import parse
for c in ("det-1budget",):
    r = [parse(f"rb-rehB-{c}-{n}") for n in (1, 2, 3)]
    print(c, [x["out"] for x in r], "tok/s", [x.get("decode_tps") or x.get("tps") for x in r])
PY
grep -E "rb-rehB-det" bringup/out/logs/guard/summary.txt | tail -6 | cut -c1-200
