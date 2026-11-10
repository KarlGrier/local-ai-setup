#!/bin/bash
# s2_abba.sh [STEP...] — round 14 step 2: a served A B B A for every patch that was worth >= 1 % (patches/LEDGER.md),
# added back in the ledger's order of value on the patched build (bringup/out/r14/engine-patched): A = the switches of
# the steps before it, B = + this one. Screen = where the ledger measured its gain (LDR = research-shaped, D = decode).
# The always-on rows (PR245, the n-gram prefetch) are A/B'd on top of the full set by their off switch.
# Configs from the runbook's cand.json (my flags, chat cache, web search) with the switch env replaced.
# Output: results/r14/s2-<step>.md, one line per step in results/r14/s2-summary.txt
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
R=$WS/bringup/out/r14; C=$R/configs/cand.json; D=$WS/work/r14/cfg; mkdir -p $D
export PROMPT_DIR=$R/prompts EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
SW="STRATA_ADAPT_HELPER STRATA_QSA_SPLIT_ATTN STRATA_GR_FORK STRATA_SPEC_EXACT STRATA_ROUTER_Q8K STRATA_MMVQ_IL STRATA_SIDE_MIXER STRATA_ADAPT_LAND STRATA_EXPERTS_OLD STRATA_PLE_PREFETCH"
mk() {   # mk NAME "K=V ..." -> $D/NAME.json : cand.json with every switch of $SW removed, then these set
  .venv/bin/python - "$C" "$D/$1.json" "$SW" "$2" <<'PY'
import json, sys, shutil
from pathlib import Path
src, dst, sw, kv = sys.argv[1:5]
c = json.loads(Path(src).read_text())
for k in sw.split():
    c["env"].pop(k, None)
for p in kv.split():
    k, v = p.split("=", 1); c["env"][k] = v
c["log"] = str(Path(dst).with_suffix(".log"))
Path(dst).write_text(json.dumps(c, indent=1) + "\n")
sh = Path(src).with_suffix("").as_posix() + ".shared-settings.json"
if Path(sh).exists():
    shutil.copy(sh, Path(dst).with_suffix("").as_posix() + ".shared-settings.json")
PY
}
# the cumulative steps: name | screen | the switches before it | + this one
K1="STRATA_ADAPT_HELPER=1"; K2="$K1 STRATA_QSA_SPLIT_ATTN=1"; K3="$K2 STRATA_GR_FORK=1"; K4="$K3 STRATA_SPEC_EXACT=1"
K5="$K4 STRATA_ROUTER_Q8K=1"; K6="$K5 STRATA_MMVQ_IL=1"; K7="$K6 STRATA_SIDE_MIXER=2"
STEPS=(
  "adapt_helper|L||$K1"
  "qsa_split_attn|L|$K1|$K2"
  "gr_fork|L|$K2|$K3"
  "spec_exact|D|$K3|$K4"
  "router_q8k|L|$K4|$K5"
  "mmvq_il|L|$K5|$K6"
  "side_mixer|D|$K6|$K7"
  "pr245|D|$K7 STRATA_EXPERTS_OLD=1|$K7"
  "ple_prefetch|D|$K7 STRATA_PLE_PREFETCH=0|$K7"
)
want=" ${*:-all} "
for st in "${STEPS[@]}"; do
  IFS='|' read -r n sc a b <<< "$st"
  [[ "$want" == " all " || "$want" == *" $n "* ]] || continue
  mk s2-$n-A "$a"; mk s2-$n-B "$b"
  SS=$(date -Iseconds | cut -c1-19)
  if [ $sc = L ]; then S=bringup/lib/ldrscreen.sh; else S=bringup/lib/decscreen.sh; fi
  for arm in "A-a A" "B-a B" "B-b B" "A-b A"; do
    set -- $arm
    $S r14-s2-$n-$1 $D/s2-$n-$2.json > logs/r14/s2-$n-$1.log 2>&1
  done
  if [ $sc = L ]; then
    SINCE=$SS .venv/bin/python bringup/lib/ldr_table.py without=r14-s2-$n-A-a,r14-s2-$n-A-b with=r14-s2-$n-B-a,r14-s2-$n-B-b > results/r14/s2-$n.md 2>&1
  else
    SINCE=$SS .venv/bin/python bringup/lib/ab_table.py without=r14-s2-$n-A-a,r14-s2-$n-A-b with=r14-s2-$n-B-a,r14-s2-$n-B-b > results/r14/s2-$n.md 2>&1
  fi
  echo "$(date -Is) $n ($sc): $(grep -iE '^\| *decode' results/r14/s2-$n.md | head -1 | tr -s ' ' | cut -c1-200)" | tee -a results/r14/s2-summary.txt
  # the guard line of the B arm's engine (this patch's guard must not have turned it off)
  echo "    guards: $(grep -h 'patch guards' $D/s2-$n-B.log 2>/dev/null | tail -1 | cut -c1-160)" | tee -a results/r14/s2-summary.txt
done
