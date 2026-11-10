#!/bin/bash
# bringup/accept_llama_rerun.sh LABEL CONFIG.json TWIN.json [LLAMA_GGUF] — re-run only the acceptance suite's llama.cpp
# session (ids, needles, sampler probabilities, probes) into bringup/out/accept/LABEL/, then the sampler analysis and the
# table (round 13: the first C*13.1 run's llama-server was not pinned to the 5080 and did not start).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
L=$1 CFG=$(realpath $2) TWIN=$(realpath $3)
O=$WS/bringup/out/accept/$L; P=$WS/.venv/bin/python
# 10-27: the config's own --native file by default, and only for an arch our llama.cpp builds were checked on
LM=${4:-$($P -c "import json; a=json.load(open('$CFG'))['args']; print(a[a.index('--native')+1] if '--native' in a else '')")}
LM=${LM:-$WS/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf}
LARCH=$($P -c "import sys; sys.path.insert(0, '$WS/bringup'); from gguf_head import read_model; print(read_model('$LM').arch())" 2>/dev/null)
case " ${ACCEPT_LLAMA_ARCHS:-qwen4exp} " in *" $LARCH "*) ;; *) echo "llama.cpp rows: $LM is '$LARCH', not in ACCEPT_LLAMA_ARCHS - nothing to re-run"; exit 0;; esac
TREE=$($P -c "import json,pathlib; print(pathlib.Path(json.load(open('$CFG'))['server']).parent.parent)")
TWTREE=$($P -c "import json,pathlib; print(pathlib.Path(json.load(open('$TWIN'))['server']).parent.parent)")
TP=$($P -c "import json; print(json.load(open('$CFG'))['tokenizer'])")
export NEEDLE_DIR=${NEEDLE_DIR:-$WS/work/r5/needle2} STRATA_TOKENIZER_DIR=$TP STRATA_SERVE_TREE=$TREE
NR=${NEEDLE_RUNS:-0,1}; t0=$(date +%s)
echo "=== $(date -Is) accept $L: llama.cpp session re-run" | tee -a $O/steps.log
LLAMA_MODEL=$LM bringup/lib/with_llama.sh $L-llama -- "$P bringup/lib/accept_ids.py http://127.0.0.1:8081 $TREE $TP $O/ids.json > $O/ids.txt 2>&1; \
  $P bringup/lib/needle2.py ask --base http://127.0.0.1:8081 --label $L-llama --temperature 1.0 --runs $NR > $O/needle-llama.txt 2>&1; \
  SP_DIR=$O/sp $P bringup/lib/sampling_probe.py llama http://127.0.0.1:8081 > $O/sp-llama.txt 2>&1; \
  $P bringup/lib/stoptest.py http://127.0.0.1:8081 $L-llama > $O/stop-llama.txt 2>&1; \
  $P bringup/lib/tooltag_test.py http://127.0.0.1:8081 $L-llama 3 > $O/tool-llama.txt 2>&1; \
  $P bringup/lib/p12_probe.py http://127.0.0.1:8081 $L-llama > $O/ctl-llama.txt 2>&1" > $O/llama-session.txt 2>&1
tail -1 $O/ids.txt
SP_DIR=$O/sp SP_LABEL=$L STRATA_SERVE_TREE=$TWTREE $P bringup/lib/sampling_probe.py analyze > $O/sp-analyze.txt 2>&1
$P bringup/lib/accept_table.py $O | tee $O/table.md
echo "llama.cpp re-run time: $(( $(date +%s) - t0 )) s" | tee -a $O/table.md
