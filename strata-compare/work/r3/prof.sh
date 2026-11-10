#!/bin/bash
# prof.sh (round 3) LABEL CONFIG.json TOKENS(1k|32k|math|...) NEW [extra engine args...]
# One `strata generate --stats` run with the engine args of CONFIG.json (cold model page cache), sampled like the
# user's settings (generate has no min-p flag: temperature 0.6, top-p 0.95, top-k 20, seed 1).
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2 T=$3 N=$4; shift 4
EXE=$($WS/.venv/bin/python -c "import json; print(json.load(open('$CFG'))['exe'])")
ARGS=$($WS/.venv/bin/python -c "import json; print(' '.join(json.load(open('$CFG'))['args']))")
ENVS=$($WS/.venv/bin/python -c "import json; print(' '.join(f'{k}={v}' for k,v in json.load(open('$CFG')).get('env',{}).items()))")
PFX=$($WS/.venv/bin/python -c "import json; print(' '.join(json.load(open('$CFG')).get('prefix',[])))")
$WS/.venv/bin/python $WS/scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
cd $WS/strata-v0111
export LD_LIBRARY_PATH=/usr/local/cuda-13.3/lib64:${LD_LIBRARY_PATH:-}
echo "=== $(date -Is) prof $L $T $N $* env=$ENVS prefix=$PFX"
env $ENVS $PFX $EXE $ARGS --tokens-file $WS/work/prof/$T.tokens --max-new $N --stats --seed 1 --temperature 0.6 --top-p 0.95 --top-k 20 "$@" \
  > $WS/logs/r3/prof-$L-$T.out 2> $WS/logs/r3/prof-$L-$T.err
echo "exit $?"
grep -vE '^(prompt|output) +:' $WS/logs/r3/prof-$L-$T.out | head -40
