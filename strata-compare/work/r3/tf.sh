#!/bin/bash
# tf.sh LABEL CONFIG.json TF_EXE TEXT... — round 3 teacher-forced scoring (round-1 method, scripts/tf_run.sh) with an
# explicit engine (a --teacher-force build) and the config's args + env; extra env via TF_ENV="K=V ...".
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$(realpath $2) EXE=$(realpath $3); shift 3
ARGS=$($WS/.venv/bin/python -c "import json; print(' '.join(json.load(open('$CFG'))['args']))")
ENVS=$($WS/.venv/bin/python -c "import json; print(' '.join(f'{k}={v}' for k,v in json.load(open('$CFG')).get('env',{}).items()))")
export LD_LIBRARY_PATH=/usr/local/cuda-13.3/lib64:${LD_LIBRARY_PATH:-}
cd $WS/strata-v0111
for T in "$@"; do
  $WS/.venv/bin/python $WS/scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
  rm -f $WS/work/prof/tf-$T.text.nll $WS/results/tf-$L-$T.nll     # never keep a stale result from an earlier run
  echo "=== $(date -Is) tf $L $T exe=$EXE env=$ENVS ${TF_ENV:-}"
  env $ENVS ${TF_ENV:-} $EXE $ARGS --tokens-file $WS/work/prof/tf-$T.prompt --teacher-force $WS/work/prof/tf-$T.text \
     --max-new 4096 > $WS/logs/r3/tf-$L-$T.out 2> $WS/logs/r3/tf-$L-$T.err
  grep -h 'teacher-forced' $WS/logs/r3/tf-$L-$T.out || tail -3 $WS/logs/r3/tf-$L-$T.err
  if grep -q 'teacher-forced' $WS/logs/r3/tf-$L-$T.out 2>/dev/null; then cp $WS/work/prof/tf-$T.text.nll $WS/results/tf-$L-$T.nll
  else echo "tf $L $T FAILED (no result written)"; fi
done
