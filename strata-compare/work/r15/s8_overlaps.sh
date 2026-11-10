#!/bin/bash
# s8_overlaps.sh [PART...] — round 15 step 8: where v0.1.40.2's new code overlaps ours, served A/B on IQ3_S with your
# config (C*14's flags; the 20 GB floor), each arm on a fresh guarded server (the runbook's candidate = v0.1.40.2 + r15p27):
#   draft  our exact sampling (STRATA_SPEC_EXACT=1) vs upstream's probabilistic acceptance (STRATA_SPEC_PROB=1, its own
#          --spec-min-p gating on the drawn draft) vs STRATA_SPEC_PROB=1 under our cost gate; decode screen A B C C B A,
#          then the two best on the LDR screen A B B A
#   mixer  our side mixer (STRATA_SIDE_MIXER=2) vs upstream's STRATA_DF_BRANCH=1 vs neither; decode screen A B C C B A
#   q8k    our A.2 (STRATA_ROUTER_Q8K=1) on vs off - v0.1.40.2 quantizes the CPU experts' Q8_K rows with AVX2 by default
#          (#851); LDR screen A B B A
#   f4     upstream's F4 (STRATA_MMVQ_IL, on by default) on vs off - what it carries of our dropped B.3; LDR A B B A
# Tables -> results/r15/s8-<part>.md
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
R=$WS/bringup/out/r15; C=$R/configs/cand.json; D=$WS/work/r15/cfg; mkdir -p $D results/r15
export PROMPT_DIR=$R/prompts EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
PY=.venv/bin/python
mk() {   # mk NAME "K=V ..." ["-K ..."] -> $D/NAME.json : cand.json with these env set (K=) / removed (-K)
  $PY - "$C" "$D/$1.json" "$2" <<'PY'
import json, sys, shutil
from pathlib import Path
src, dst, kv = sys.argv[1:4]
c = json.loads(Path(src).read_text())
for p in kv.split():
    if p.startswith("-"):
        c["env"].pop(p[1:], None)
    else:
        k, v = p.split("=", 1); c["env"][k] = v
c["log"] = str(Path(dst).with_suffix(".log"))
Path(dst).write_text(json.dumps(c, indent=1) + "\n")
sh = Path(src).with_suffix("").as_posix() + ".shared-settings.json"
if Path(sh).exists():
    shutil.copy(sh, Path(dst).with_suffix("").as_posix() + ".shared-settings.json")
PY
}
dec() { bringup/lib/decscreen.sh r15-s8-$1 $D/$2.json > logs/r15/s8-$1.log 2>&1; }
ldr() { bringup/lib/ldrscreen.sh r15-s8-$1 $D/$2.json > logs/r15/s8-$1.log 2>&1; }
mkdir -p logs/r15
for part in ${@:-draft mixer q8k f4}; do
  SS=$(date -Iseconds | cut -c1-19)
  case $part in
  draft)
    mk ess ""
    mk prob "-STRATA_SPEC_EXACT STRATA_SPEC_PROB=1 -STRATA_COST_GATE"
    mk probgate "-STRATA_SPEC_EXACT STRATA_SPEC_PROB=1"
    for a in ess-a:ess prob-a:prob probgate-a:probgate probgate-b:probgate prob-b:prob ess-b:ess; do dec D-${a%%:*} ${a#*:}; done
    SINCE=$SS $PY bringup/lib/ab_table.py ours_ESS=r15-s8-D-ess-a,r15-s8-D-ess-b upstream_PROB=r15-s8-D-prob-a,r15-s8-D-prob-b PROB_costgate=r15-s8-D-probgate-a,r15-s8-D-probgate-b > results/r15/s8-draft-dec.md 2>&1
    # the LDR screen: ours vs the faster of upstream's two arms on the decode screen
    best=$($PY - <<'PY'
import re
t = open("/home/USER/ai-speed-testing/strata-compare/results/r15/s8-draft-dec.md").read()
row = [l for l in t.splitlines() if l.startswith("| decode (tok/s)")][0]
m = [float(x) for x in re.findall(r"\*\*([\d.]+)\*\*", row)]
print("prob" if m[1] >= m[2] else "probgate")
PY
)
    SS2=$(date -Iseconds | cut -c1-19)
    for a in ess-a:ess $best-a:$best $best-b:$best ess-b:ess; do ldr L-${a%%:*} ${a#*:}; done
    SINCE=$SS2 $PY bringup/lib/ldr_table.py ours_ESS=r15-s8-L-ess-a,r15-s8-L-ess-b upstream_$best=r15-s8-L-$best-a,r15-s8-L-$best-b > results/r15/s8-draft-ldr.md 2>&1 ;;
  mixer)
    mk side ""
    mk dfbr "-STRATA_SIDE_MIXER STRATA_DF_BRANCH=1"
    mk nomix "-STRATA_SIDE_MIXER"
    for a in side-a:side dfbr-a:dfbr nomix-a:nomix nomix-b:nomix dfbr-b:dfbr side-b:side; do dec M-${a%%:*} ${a#*:}; done
    SINCE=$SS $PY bringup/lib/ab_table.py ours_side2=r15-s8-M-side-a,r15-s8-M-side-b upstream_DF_BRANCH=r15-s8-M-dfbr-a,r15-s8-M-dfbr-b neither=r15-s8-M-nomix-a,r15-s8-M-nomix-b > results/r15/s8-mixer.md 2>&1 ;;
  q8k)
    mk q8k ""
    mk noq8k "-STRATA_ROUTER_Q8K"
    for a in q8k-a:q8k noq8k-a:noq8k noq8k-b:noq8k q8k-b:q8k; do ldr Q-${a%%:*} ${a#*:}; done
    SINCE=$SS $PY bringup/lib/ldr_table.py A2_on=r15-s8-Q-q8k-a,r15-s8-Q-q8k-b A2_off=r15-s8-Q-noq8k-a,r15-s8-Q-noq8k-b > results/r15/s8-q8k.md 2>&1 ;;
  f4)
    mk f4 "STRATA_MMVQ_IL=1"
    mk nof4 "STRATA_MMVQ_IL=0"
    for a in f4-a:f4 nof4-a:nof4 nof4-b:nof4 f4-b:f4; do ldr F-${a%%:*} ${a#*:}; done
    SINCE=$SS $PY bringup/lib/ldr_table.py F4_on=r15-s8-F-f4-a,r15-s8-F-f4-b F4_off=r15-s8-F-nof4-a,r15-s8-F-nof4-b > results/r15/s8-f4.md 2>&1 ;;
  esac
  echo "s8 $part: $(grep -hiE '^\| *decode' results/r15/s8-$part*.md 2>/dev/null | head -2 | tr -s ' ' | cut -c1-220 | tr '\n' ' ')"
done
