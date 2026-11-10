#!/bin/bash
# s3_overlaps.sh [NAME...] — round 14 step 3: where v0.1.40 brings its own version of something we carry, ours vs
# upstream's on the same build (bringup/out/r14/engine-patched), everything else = the full candidate (all our switches).
#   land    ours STRATA_ADAPT_LAND=2 vs upstream's STRATA_ADAPT_LAG=2 (#764): identity first (CLI, adaptive swaps live,
#           seed 11 sampled math, exact sampling off as repeat3 does), then a decode A B B A
#   helper  ours STRATA_ADAPT_HELPER=1 vs upstream's STRATA_DISJOINT_ADAPT=1 (#731): identity, then an LDR A B B A
#   hcread  ours STRATA_GR_FORK=1 (B.1) vs upstream's read (v0.1.40's default multi-token read: GR_FORK and GR_V3 unset): LDR
#   f7      the fork's drafter / head kernels upstream took (F7: HEAD_MIX_MULTI, ONE_TOKEN_COMMIT, MULTI_BLOCK_ARGMAX,
#           MTP_SHARED_BRANCH) on vs off: decode (we carry no version of them: Round 10 deferred them)
# (PR245 vs #783 PR-h and the side mixer vs upstream's window are step 2's pr245 / side_mixer A B B As.)
# Output: results/r14/s3-<name>.md, results/r14/s3-summary.txt
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
R=$WS/bringup/out/r14; C=$R/configs/cand.json; D=$WS/work/r14/cfg; mkdir -p $D
export PROMPT_DIR=$R/prompts EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
SW="STRATA_ADAPT_HELPER STRATA_QSA_SPLIT_ATTN STRATA_GR_FORK STRATA_GR_V3 STRATA_SPEC_EXACT STRATA_ROUTER_Q8K STRATA_MMVQ_IL STRATA_SIDE_MIXER STRATA_ADAPT_LAND STRATA_ADAPT_LAG STRATA_DISJOINT_ADAPT"
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
FULL="STRATA_ADAPT_HELPER=1 STRATA_QSA_SPLIT_ATTN=1 STRATA_GR_FORK=1 STRATA_GR_V3=1 STRATA_SPEC_EXACT=1 STRATA_ROUTER_Q8K=1 STRATA_MMVQ_IL=1 STRATA_SIDE_MIXER=2"
NOH=${FULL/STRATA_ADAPT_HELPER=1 /}
NOGR=${FULL/STRATA_GR_FORK=1 STRATA_GR_V3=1 /}
F7OFF="STRATA_HEAD_MIX_MULTI=0 STRATA_ONE_TOKEN_COMMIT=0 STRATA_MULTI_BLOCK_ARGMAX=0 STRATA_MTP_SHARED_BRANCH=0"
OUT=results/r14/s3-summary.txt
ident() {   # ident NAME CFG_A CFG_B: two CLI runs each with the adaptive tier live; the four output hashes
  local n=$1 a=$2 b=$3 S='--seed 11 --temperature 1.0 --top-p 0.95 --top-k 20'
  for arm in A B; do local cfg; [ $arm = A ] && cfg=$a || cfg=$b
    for i in 1 2; do ENVX=STRATA_SPEC_EXACT=0 PROF_SAMPLING="$S" bringup/lib/run.sh r14-s3-$n-$arm$i $cfg math 1024 --suffix-draft 0 > /dev/null 2>&1; done
  done
  .venv/bin/python - $n <<'PY' | tee -a results/r14/s3-summary.txt
import sys
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/bringup/lib")
from p0_table import parse
n = sys.argv[1]
h = {k: parse(f"r14-s3-{n}-{k}") for k in ("A1", "A2", "B1", "B2")}
hs = {k: v["out"] for k, v in h.items()}
print(f"s3 {n} identity (CLI, swaps live): A {hs['A1']} {hs['A2']} | B {hs['B1']} {hs['B2']} -> "
      + ("ALL 4 IDENTICAL" if len(set(hs.values())) == 1 else f"{len(set(hs.values()))} different")
      + f" | tok/s A {h['A1'].get('tps')} {h['A2'].get('tps')} B {h['B1'].get('tps')} {h['B2'].get('tps')}")
PY
}
abba() {   # abba NAME L|D CFG_A CFG_B
  local n=$1 sc=$2 a=$3 b=$4 SS; SS=$(date -Iseconds | cut -c1-19)
  local S=bringup/lib/decscreen.sh; [ $sc = L ] && S=bringup/lib/ldrscreen.sh
  $S r14-s3-$n-A-a $a > logs/r14/s3-$n-A-a.log 2>&1; $S r14-s3-$n-B-a $b > logs/r14/s3-$n-B-a.log 2>&1
  $S r14-s3-$n-B-b $b > logs/r14/s3-$n-B-b.log 2>&1; $S r14-s3-$n-A-b $a > logs/r14/s3-$n-A-b.log 2>&1
  local T=bringup/lib/ab_table.py; [ $sc = L ] && T=bringup/lib/ldr_table.py
  SINCE=$SS .venv/bin/python $T ours=r14-s3-$n-A-a,r14-s3-$n-A-b upstream=r14-s3-$n-B-a,r14-s3-$n-B-b > results/r14/s3-$n.md 2>&1
  echo "$(date -Is) s3 $n ($sc, A = ours / without, B = upstream's / with): $(grep -iE '^\| *decode' results/r14/s3-$n.md | head -1 | tr -s ' ' | cut -c1-200)" | tee -a $OUT
}
want=" ${*:-land helper hcread f7} "
if [[ "$want" == *" land "* ]]; then
  mk s3-land-ours "$FULL STRATA_ADAPT_LAND=2"; mk s3-land-up "$FULL STRATA_ADAPT_LAG=2"
  ident land $D/s3-land-ours.json $D/s3-land-up.json
  abba land D $D/s3-land-ours.json $D/s3-land-up.json
fi
if [[ "$want" == *" helper "* ]]; then
  mk s3-helper-ours "$FULL STRATA_ADAPT_LAND=2"; mk s3-helper-up "$NOH STRATA_DISJOINT_ADAPT=1 STRATA_ADAPT_LAND=2"
  ident helper $D/s3-helper-ours.json $D/s3-helper-up.json
  abba helper L $D/s3-helper-ours.json $D/s3-helper-up.json
fi
if [[ "$want" == *" hcread "* ]]; then
  mk s3-hcread-ours "$FULL STRATA_ADAPT_LAND=2"; mk s3-hcread-up "$NOGR STRATA_ADAPT_LAND=2"
  abba hcread L $D/s3-hcread-ours.json $D/s3-hcread-up.json
fi
if [[ "$want" == *" f7 "* ]]; then
  mk s3-f7-off "$FULL STRATA_ADAPT_LAND=2 $F7OFF"; mk s3-f7-on "$FULL STRATA_ADAPT_LAND=2"
  abba f7 D $D/s3-f7-off.json $D/s3-f7-on.json
fi
