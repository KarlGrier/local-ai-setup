#!/bin/bash
# s1_bisect.sh — round 14 step 1: which v0.1.40 default makes stock v0.1.40.1's sampled-math exact7 run (6c9b2d10)
# differ from v0.1.39's (a10f2135) at token 958? The release's own off-switches for its new default-on paths, all off
# first; then halves. Same config / pinned cache / flags as exact7's s-math. Output: results/r14/s1-bisect.txt
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
CFG=bringup/out/r14/configs/stock.json; export PROMPT_DIR=$WS/bringup/out/r14/prompts EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 3500"; S='--seed 11 --temperature 1.0 --top-p 0.95 --top-k 20'
OUT=results/r14/s1-bisect.txt
ALL=(STRATA_NO_MULTI_GR=1 STRATA_NO_BATCH_KV_STEP=1 STRATA_NO_NORM_ROPE=1 STRATA_NO_SUB16_GU=1 STRATA_NO_MMVQ_ROWS2=1
     STRATA_HEAD_MIX_MULTI=0 STRATA_ONE_TOKEN_COMMIT=0 STRATA_MULTI_BLOCK_ARGMAX=0 STRATA_MTP_SHARED_BRANCH=0
     STRATA_QSA_EARLY_EXIT=0 STRATA_SH_FORK_LATE=0 STRATA_NO_AVXVNNI=1 STRATA_MTP_CATCHUP_ALL=1 STRATA_MTP_PRIORITY=0)
h() { .venv/bin/python -c "
import sys; sys.path.insert(0, 'bringup/lib')
from p0_table import parse
d = parse('$1'); print(d['out'], d.get('rounds'), d.get('acc'))"; }
first() { .venv/bin/python - "$1" <<'PY'
import re, sys
def ids(f):
    m = re.search(r"^output\s*:\s*(.*)$", open(f, errors="replace").read(), re.M); return m[1].split()
a = ids("bringup/out/logs/prof/rb-rehA-stock-s-math.out"); b = ids(f"bringup/out/logs/prof/{sys.argv[1]}.out")
d = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), None); print("same as v0.1.39" if d is None else f"first diff at {d}")
PY
}
run() {   # run LABEL ENV...
  local L=$1; shift
  ENVX="$*" PROF_SAMPLING="$S" bringup/lib/run.sh $L $CFG math 1024 $X > /dev/null 2>&1
  echo "$L [$*]: $(h $L) - $(first $L)" | tee -a $OUT
}
echo "=== $(date -Is) s1 bisect (v0.1.39 stock s-math a10f2135; v0.1.40.1 stock 6c9b2d10)" | tee -a $OUT
run rb-r14-bis-all "${ALL[@]}"
run rb-r14-bis-none
if grep -q "rb-r14-bis-all.*same as v0.1.39" $OUT; then
  lo=0; hi=${#ALL[@]}   # find the smallest prefix of ALL that restores v0.1.39 (assumes one cause)
  while [ $((hi - lo)) -gt 1 ]; do
    mid=$(( (lo + hi) / 2 ))
    run rb-r14-bis-p$mid "${ALL[@]:0:$mid}"
    if tail -1 $OUT | grep -q "same as v0.1.39"; then hi=$mid; else lo=$mid; fi
  done
  echo "cause: ${ALL[$lo]} (prefix of $hi restores v0.1.39)" | tee -a $OUT
  run rb-r14-bis-one "${ALL[$lo]}"
fi
echo "=== $(date -Is) s1 bisect done" | tee -a $OUT
