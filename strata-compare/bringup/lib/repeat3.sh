#!/bin/bash
# repeat3.sh LABEL CONFIG.json — round 10 Phase A (b) gate: the three-run repeatability check with the adaptive tier
# live (CLI, the config's flags, sampled at seed 11 / T 1.0 / top-p 0.95 / top-k 20, math 1,024 tokens, cold page cache
# each): the three outputs must be identical (STRATA_ADAPT_LAND=2 makes the landing deterministic).
# 15:10 fix: runs with exact sampling OFF by default (ENVX=STRATA_SPEC_EXACT=0; set ENVX to override): with it on, the
# realized draws depend on which drafts were proposed, and upstream's DraftPolicy picks lookup vs MTP windows from
# measured round times (wall clock), so sampled outputs differ run to run on every build, C*11 included - that says
# nothing about the tier. Without it the output is a function of the seed and the computation (Round 9's form).
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
export ENVX=${ENVX-STRATA_SPEC_EXACT=0}
L=$1 CFG=$2; S='--seed 11 --temperature 1.0 --top-p 0.95 --top-k 20'
# round 11 (10:00): the lookup (suffix) drafter picks windows from measured round times and the sampled text depends
# at rounding level on how tokens are grouped into windows (C*12.1 too: rep-c121r) -> pin the windows; the adaptive
# tier stays live. RX overrides (RX="" = the served flags as before).
RX=${RX---suffix-draft 0}
for i in 1 2 3; do PROF_SAMPLING="$S" bringup/lib/run.sh $L-r$i $CFG math 1024 $RX > /dev/null; done
.venv/bin/python - $L <<'PY'
import sys
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/bringup/lib")
from p0_table import parse
L = sys.argv[1]
h = [parse(f"{L}-r{i}")["out"] for i in (1, 2, 3)]
print(f"repeat3 {L}: outputs {h} -> {'3/3 identical' if len(set(h)) == 1 else str(len(set(h))) + ' different'}")
PY
