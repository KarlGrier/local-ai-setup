#!/bin/bash
# s5_settings.sh NAME CONFIG.json OPTION... — round 15 step 5 (copy of s4_filetier.sh): settings on the best placement, each
# ALONE against the config as it is, A B B A (A = the config), engine level: `strata generate --stats`, YOUR SAMPLING
# with the config's flags as served (adaptive tier live), greedy, 1,024 tokens of the math prompt (S4_N), cold model page cache
# per run, STRATA_IO_STATS=1 on both arms (the page-cache split; it only counts). Keep at >= +3 % decode.
# OPTION is NAME:ENV or NAME:ENV:ARG=VAL (ENV "K=V,K=V" or "-", ARG an engine flag), e.g.
#   ub0:STRATA_UNBUFFERED_LOAD=0   ub1:STRATA_UNBUFFERED_LOAD=1   pf:STRATA_IO_PREFETCH=1   fetch16:STRATA_FETCH_THREADS=16
#   budget56:-:--resident-budget-gib=56
# Table -> results/r15/s5-NAME.md
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
N=$1 CFG=$2; shift 2
D=$WS/work/r15/cfg; mkdir -p $D results/r15
export PROMPT_DIR=${PROMPT_DIR:-$WS/bringup/out/r15/prompts}
PY=.venv/bin/python
run() {   # run LABEL CFG ENV
  ENVX="$3" PROF_SAMPLING="--seed 11 --temperature 1.0 --top-p 0.95 --top-k 20" COLD=1 bringup/lib/run.sh $1 $2 math ${S4_N:-1024} > /dev/null
}
for opt in "$@"; do
  IFS=: read -r on env arg <<< "$opt"
  env=$([ "$env" = "-" ] && echo "" || echo "$env" | tr ',' ' ')
  C2=$CFG
  if [ -n "${arg:-}" ]; then   # an engine flag: a config copy with it set
    C2=$D/s5-$N-$on.json
    $PY - "$CFG" "$C2" "$arg" <<'PY'
import json, sys
from pathlib import Path
c = json.loads(Path(sys.argv[1]).read_text()); a = c["args"]
for fv in sys.argv[3].split("+"):   # round 15: several flags at once, joined by "+" (a combination)
    f, v = fv.split("=", 1)
    if f in a: a[a.index(f) + 1] = v
    else: a.extend([f, v])
Path(sys.argv[2]).write_text(json.dumps(c, indent=1) + "\n")
PY
  fi
  run s5-$N-$on-base-a $CFG ""
  run s5-$N-$on-opt-a $C2 "$env"
  run s5-$N-$on-opt-b $C2 "$env"
  run s5-$N-$on-base-b $CFG ""
done
$PY work/r15/s5_table.py $N "$@" > results/r15/s5-$N.md 2>&1
cat results/r15/s5-$N.md
