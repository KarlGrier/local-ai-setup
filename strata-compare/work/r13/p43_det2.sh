#!/bin/bash
# p43_det2.sh — round 13 Part 4.3: which part of the Q4 both-GPU --mmap-experts setup makes stock v0.1.39 not repeat?
# Greedy x-math (1,024 tokens, exact7's pins) 3x each on one GPU + --mmap-experts and one GPU + --resident-budget-gib.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
R=$WS/bringup/out/rehB; source $R/run.env
export EVICT_GLOB="$(dirname $RB_GGUF)/*.gguf" PROMPT_DIR=$R/prompts
PIN=$(.venv/bin/python -c "import json; print(min(3500, int(json.load(open('$R/fitplan.json'))['slots_5080'] * 0.9)))")
BUDGET=$(.venv/bin/python -c "import json; print(int(json.load(open('$R/fitplan.json'))['resident_budget_suggest_gib']))")
.venv/bin/python - "$BUDGET" <<'PY'
import json, sys
from pathlib import Path
R = Path("/home/USER/ai-speed-testing/strata-compare/bringup/out/rehB")
c = json.loads((R / "configs/stock.json").read_text())
def one(args):
    a = list(args)
    if "--expert-cache-device1" in a:
        i = a.index("--expert-cache-device1"); del a[i:i + 2]
    return a
for name, extra, drop in (("det-1mmap", [], []), ("det-1budget", ["--resident-budget-gib", sys.argv[1]], ["--mmap-experts"])):
    a = [x for x in one(c["args"]) if x not in drop] + extra
    d = dict(c); d["args"] = a; d["log"] = str(R / f"engine-{name}.log")
    d["env"] = dict(c["env"]); d["env"]["CUDA_VISIBLE_DEVICES"] = c["env"]["CUDA_VISIBLE_DEVICES"].split(",")[0]
    (R / f"configs/{name}.json").write_text(json.dumps(d, indent=1) + "\n")
PY
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache $PIN"
for n in 1 2 3; do for c in det-1mmap det-1budget; do bringup/lib/run.sh rb-rehB-$c-$n $R/configs/$c.json math 1024 $X > /dev/null; done; done
.venv/bin/python - <<'PY'
import sys
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/bringup/lib")
from p0_table import parse
for c in ("det-1mmap", "det-1budget"):
    r = [parse(f"rb-rehB-{c}-{n}") for n in (1, 2, 3)]
    print(c, [x["out"] for x in r], "tok/s", [x.get("decode_tps") or x.get("tps") for x in r])
PY
grep -E "rb-rehB-det" bringup/out/logs/guard/summary.txt | tail -6 | cut -c1-200
