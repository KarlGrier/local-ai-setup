#!/bin/bash
# nsys.sh LABEL CONFIG.json TOKENS(1k|32k|math) NEW FROM ROUNDS [GRAPHTRACE=node|graph] [extra engine args...]
# One `strata generate --stats` run of the TRACE build (strata-r3/build-trace/strata unless EXE= is set: NVTX ranges
# + cudaProfilerStart/Stop at decode rounds FROM .. FROM+ROUNDS) under nsys, with the engine args of CONFIG.json,
# sampled like the user's settings (temperature 0.6, top-p 0.95, top-k 20, seed 1; generate has no min-p flag).
# Output: logs/r3/nsys/LABEL.{nsys-rep,sqlite}, logs/r3/nsys/LABEL.{out,err}. Temp files stay in the workspace.
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2 T=$3 N=$4 FROM=$5 ROUNDS=$6 GT=${7:-node}; shift 7
EXE=${EXE:-$WS/strata-r3/build-trace/strata}
ARGS=$($WS/.venv/bin/python -c "import json; print(' '.join(json.load(open('$CFG'))['args']))")
ENVS=$($WS/.venv/bin/python -c "import json; print(' '.join(f'{k}={v}' for k,v in json.load(open('$CFG')).get('env',{}).items()))")
mkdir -p $WS/logs/r3/nsys $WS/tmp
$WS/.venv/bin/python $WS/scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
cd $WS/strata-v0111
export LD_LIBRARY_PATH=/usr/local/cuda-13.3/lib64:${LD_LIBRARY_PATH:-}
echo "=== $(date -Is) nsys $L $T $N from=$FROM rounds=$ROUNDS graph-trace=$GT exe=$EXE $* env=$ENVS"
env TMPDIR=$WS/tmp $ENVS STRATA_PROFILE_FROM=$FROM STRATA_PROFILE_ROUNDS=$ROUNDS \
  /usr/local/cuda-13.3/bin/nsys profile -o $WS/logs/r3/nsys/$L --force-overwrite=true \
    --trace=cuda,nvtx --cuda-graph-trace=$GT --sample=none --cpuctxsw=none \
    --capture-range=cudaProfilerApi --capture-range-end=stop --export=sqlite \
  $EXE $ARGS --tokens-file $WS/work/prof/$T.tokens --max-new $N --stats --seed 1 --temperature 0.6 --top-p 0.95 --top-k 20 "$@" \
  > $WS/logs/r3/nsys/$L.out 2> $WS/logs/r3/nsys/$L.err
echo "exit $?"
grep -vE '^(prompt|output) +:' $WS/logs/r3/nsys/$L.out | grep -E 'verify window|pool multi|dispatch|decode|speculation|mtp' | head -12
