#!/bin/bash
# tf.sh LABEL CONFIG.json TF_EXE TEXT... — round 7 (copy of round 6, copy of work/r5/tf.sh, under the memory guard) teacher-forced scoring (round-1/3 method) with an explicit engine
# (a --teacher-force build) and the config's args + env + cwd; extra env via TF_ENV="K=V ...". Cold model page cache.
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$(realpath $2) EXE=$(realpath $3); shift 3
source $WS/work/r7/env.sh
ARGS=$($WS/.venv/bin/python -c "import json; print(' '.join(json.load(open('$CFG'))['args']))")
ENVS=$($WS/.venv/bin/python -c "import json; print(' '.join(f'{k}={v}' for k,v in json.load(open('$CFG')).get('env',{}).items()))")
CWD=$($WS/.venv/bin/python -c "import json; print(json.load(open('$CFG'))['cwd'])")
export LD_LIBRARY_PATH=/usr/local/cuda-13.3/lib64:${LD_LIBRARY_PATH:-}
cd $CWD
for T in "$@"; do
  $WS/.venv/bin/python $WS/scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
  rm -f $WS/work/prof/tf-$T.text.nll $WS/results/tf-$L-$T.nll     # never keep a stale result from an earlier run
  echo "=== $(date -Is) tf $L $T exe=$EXE env=$ENVS ${TF_ENV:-}"
  env $ENVS ${TF_ENV:-} $WS/.venv/bin/python $WS/work/r7/guard.py tf-$L-$T -- $EXE $ARGS --tokens-file $WS/work/prof/tf-$T.prompt --teacher-force $WS/work/prof/tf-$T.text \
     --max-new 4096 > $WS/logs/r7/tf-$L-$T.out 2> $WS/logs/r7/tf-$L-$T.err
  grep -h 'teacher-forced' $WS/logs/r7/tf-$L-$T.out || tail -3 $WS/logs/r7/tf-$L-$T.err
  grep -h 'prompt chunk\|expert cache [0-9]' $WS/logs/r7/tf-$L-$T.err | head -2
  if grep -q 'teacher-forced' $WS/logs/r7/tf-$L-$T.out 2>/dev/null; then cp $WS/work/prof/tf-$T.text.nll $WS/results/tf-$L-$T.nll
  else echo "tf $L $T FAILED (no result written)"; fi
done
