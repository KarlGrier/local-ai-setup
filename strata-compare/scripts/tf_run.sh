#!/bin/bash
# tf_run.sh LABEL CONFIG.json TEXT... — teacher-forced scoring (strata-v0111-tuned/engine/strata-tf, generate mode)
# of work/prof/tf-TEXT.{prompt,text} with the engine args of CONFIG.json (so the same cache/pcie/prefill settings).
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2; shift 2
ARGS=$($WS/.venv/bin/python -c "import json; print(' '.join(json.load(open('$CFG'))['args']))")
cd $WS/strata-v0111
for T in "$@"; do
  echo "=== $(date -Is) $L $T"
  $WS/strata-v0111-tuned/engine/strata-tf $ARGS --tokens-file $WS/work/prof/tf-$T.prompt \
     --teacher-force $WS/work/prof/tf-$T.text --max-new 4096 > $WS/logs/tf-$L-$T.out 2> $WS/logs/tf-$L-$T.err
  grep -h 'teacher-forced' $WS/logs/tf-$L-$T.out || tail -3 $WS/logs/tf-$L-$T.err
  cp $WS/work/prof/tf-$T.text.nll $WS/results/tf-$L-$T.nll 2>/dev/null
done
