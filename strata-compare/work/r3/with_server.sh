#!/bin/bash
# with_server.sh LABEL CONFIG.json -- CMD...   start a test server on 127.0.0.1:8081 from CONFIG (cold model page cache,
# resource monitor), run CMD (it gets $ELOG = the engine log), stop the server and the monitor.
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 CFG=$2; shift 3
cd $WS
SRV=$($WS/.venv/bin/python -c "import json; print(json.load(open('$CFG')).get('server', '$WS/strata-r3-run/serve/server.py'))")
export ELOG=$($WS/.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
.venv/bin/python scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
(setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern 'strata --serve' --out logs/r3/monitor-$L > /dev/null 2>&1 &)
echo "=== $(date -Is) $L start ($CFG)"
scripts/server-C.sh start "$CFG" "$SRV" || { scripts/stopmon.sh $L; exit 1; }
echo "vram after load: $(nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader)"
bash -c "$*"
echo "vram at end: $(nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader)"
scripts/server-C.sh stop
scripts/stopmon.sh $L
echo "=== $(date -Is) $L done"
