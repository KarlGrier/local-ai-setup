#!/bin/bash
# with_llama.sh LABEL -- CMD...   start llama.cpp's llama-server (work/r4/server-L.sh: signal-3.8-opus build as-is, or
# LLAMA_BIN) on 127.0.0.1:8081 with a cold model page cache and a resource monitor, run CMD, stop both.
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1; shift 2
cd $WS; source work/r4/env.sh
.venv/bin/python scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
(setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern 'llama-server' --out logs/r4/monitor-$L > /dev/null 2>&1 &)
echo "=== $(date -Is) $L start (llama-server ${LLAMA_BIN:-signal 6fcaa16})"
work/r4/server-L.sh start || { scripts/stopmon.sh $L; exit 1; }
echo "vram after load: $(nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader)"
bash -c "$*"
echo "vram at end: $(nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader)"
work/r4/server-L.sh stop
scripts/stopmon.sh $L
echo "=== $(date -Is) $L done"
