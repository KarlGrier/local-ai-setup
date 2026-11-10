#!/bin/bash
# run.sh LABEL CONFIG.json TOKENS NEW [extra engine args...] — round 9 (copy of round 7, copy of work/r6/run.sh): one `strata generate --stats` run under the
# memory guard (bringup/lib/guard.py), engine args + env of CONFIG.json (the served config's flags), greedy windows unless
# PROF_SAMPLING is set.  Env knobs:
#   EXE=path        engine (default: the config's exe; with NSYS the trace build strata-r8/build-trace/strata)
#   ENVX="K=V ..."  extra environment (e.g. STRATA_R6_ROUTE=..., STRATA_PREFILL_TIMING=1)
#   NSYS=node       run under nsys (--cuda-graph-trace=node, capture range = cudaProfilerApi; default EXE = build-trace)
#   COLD=0          keep the page cache (default: evict both GGUF shards first = cold filesystem cache)
# Output: bringup/out/logs/prof/LABEL.{out,err} (+ .nsys-rep/.sqlite with NSYS), guard line in bringup/out/logs/guard/summary.txt.
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/bringup/lib/env.sh
L=$1 CFG=$2 T=$3 N=$4; shift 4
PY=$WS/.venv/bin/python
CFGEXE=$($PY -c "import json; print(json.load(open('$CFG'))['exe'])")
if [ -n "${NSYS:-}" ]; then EXE=${EXE:-$WS/strata-r8/build-trace/strata}; else EXE=${EXE:-$CFGEXE}; fi
ARGS=$($PY -c "import json; print(' '.join(json.load(open('$CFG'))['args']))")
ENVS=$($PY -c "import json; print(' '.join(f'{k}={v}' for k,v in json.load(open('$CFG')).get('env',{}).items()))")
PD=${PROMPT_DIR:-$WS/work/prof}; TOKF=$PD/$T.tokens; [ -f "$TOKF" ] || TOKF=$PD/$T
mkdir -p $WS/bringup/out/logs/prof $TMPDIR
[ "${COLD:-1}" = 1 ] && $PY $WS/scripts/evict.py ${EVICT_GLOB:-$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf} > /dev/null
cd $($PY -c "import json; print(json.load(open('$CFG'))['cwd'])")
export LD_LIBRARY_PATH=/usr/local/cuda-13.3/lib64:${LD_LIBRARY_PATH:-}
echo "=== $(date -Is) run $L cfg=$CFG tokens=$T new=$N exe=$EXE sha=$(sha256sum $EXE | cut -c1-12) nsys=${NSYS:-} cold=${COLD:-1} env=$ENVS $ENVX args+=$* sampling=${PROF_SAMPLING:-greedy}"
PRE=()
if [ -n "${NSYS:-}" ]; then
  PRE=(/usr/local/cuda-13.3/bin/nsys profile -o $WS/bringup/out/logs/prof/$L --force-overwrite=true --trace=cuda,nvtx
       --cuda-graph-trace=$NSYS --sample=none --cpuctxsw=none --capture-range=cudaProfilerApi --capture-range-end=stop
       --export=sqlite)
  # bring-up: NSYS_ALL=1 traces the whole run (the base has no cudaProfilerStart; keep such runs short)
  [ "${NSYS_ALL:-0}" = 1 ] && PRE=(/usr/local/cuda-13.3/bin/nsys profile -o $WS/bringup/out/logs/prof/$L --force-overwrite=true --trace=cuda
       --cuda-graph-trace=$NSYS --sample=none --cpuctxsw=none --export=sqlite)
fi
env $ENVS ${ENVX:-} $PY $WS/bringup/lib/guard.py $L -- "${PRE[@]}" $EXE $ARGS --tokens-file $TOKF --max-new $N --stats ${PROF_SAMPLING:-} "$@" \
  > $WS/bringup/out/logs/prof/$L.out 2> $WS/bringup/out/logs/prof/$L.err
rc=$?
echo "exit $rc"
tail -1 $WS/bringup/out/logs/prof/$L.out
grep -E '^(verify window|pool multi|dispatch|decode|prefill|speculation|  R4 expert-cache hits)' $WS/bringup/out/logs/prof/$L.out | head -12
