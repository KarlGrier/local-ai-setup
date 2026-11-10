#!/bin/bash
# tf.sh LABEL CONFIG.json TF_EXE TEXT... — round 9 (copy of round 7, copy of round 6, copy of work/r5/tf.sh, under the memory guard) teacher-forced scoring (round-1/3 method) with an explicit engine
# (a --teacher-force build) and the config's args + env + cwd; extra env via TF_ENV="K=V ...". Cold model page cache.
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$(realpath $2) EXE=$(realpath $3); shift 3
source $WS/bringup/lib/env.sh
ARGS=$($WS/.venv/bin/python -c "import json; print(' '.join(json.load(open('$CFG'))['args']))")
ENVS=$($WS/.venv/bin/python -c "import json; print(' '.join(f'{k}={v}' for k,v in json.load(open('$CFG')).get('env',{}).items()))")
CWD=$($WS/.venv/bin/python -c "import json; print(json.load(open('$CFG'))['cwd'])")
export LD_LIBRARY_PATH=/usr/local/cuda-13.3/lib64:${LD_LIBRARY_PATH:-}
cd $CWD
for T in "$@"; do
  $WS/.venv/bin/python $WS/scripts/evict.py ${EVICT_GLOB:-$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf} > /dev/null
  rm -f ${PROMPT_DIR:-$WS/work/prof}/tf-$T.text.nll $WS/bringup/out/results/tf-$L-$T.nll     # never keep a stale result from an earlier run
  echo "=== $(date -Is) tf $L $T exe=$EXE env=$ENVS ${TF_ENV:-}"
  env $ENVS ${TF_ENV:-} $WS/.venv/bin/python $WS/bringup/lib/guard.py tf-$L-$T -- $EXE $ARGS --tokens-file ${PROMPT_DIR:-$WS/work/prof}/tf-$T.prompt --teacher-force ${PROMPT_DIR:-$WS/work/prof}/tf-$T.text \
     --max-new 4096 > $WS/bringup/out/logs/tf-$L-$T.out 2> $WS/bringup/out/logs/tf-$L-$T.err
  grep -h 'teacher-forced' $WS/bringup/out/logs/tf-$L-$T.out || tail -3 $WS/bringup/out/logs/tf-$L-$T.err
  grep -h 'prompt chunk\|expert cache [0-9]' $WS/bringup/out/logs/tf-$L-$T.err | head -2
  if grep -q 'teacher-forced' $WS/bringup/out/logs/tf-$L-$T.out 2>/dev/null; then cp ${PROMPT_DIR:-$WS/work/prof}/tf-$T.text.nll $WS/bringup/out/results/tf-$L-$T.nll
  else echo "tf $L $T FAILED (no result written)"; fi
done
