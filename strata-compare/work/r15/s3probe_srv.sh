#!/bin/bash
# s3probe_srv.sh LABEL CONFIG.json — round 15 step 3: s3probe_srv.py on a fresh guarded server (127.0.0.1:8081, cold model
# page cache) for a placement the engine runs only with --serve (the layer split); the guard's floors from the environment.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
L=$1 CFG=$2
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
mkdir -p results/r15/s3; : > results/r15/s3/$L-probe.txt
echo "=== $(date -Is) probe $L ($CFG, served)" | tee -a results/r15/s3/$L-probe.txt
.venv/bin/python scripts/evict.py ${EVICT_GLOB:-} > /dev/null
touch "$ELOG"; EL0=$(wc -l < "$ELOG")
if ! bringup/lib/srv.sh start $L "$CFG" > results/r15/s3/$L-srvstart.txt 2>&1; then
  echo "did NOT start (served): $(tail -n +$((EL0 + 1)) "$ELOG" | grep -iE 'error|refus|cannot|does not|not support|needs|out of memory' | head -3 | tr '\n' ' ' | cut -c1-400)" | tee -a results/r15/s3/$L-probe.txt
  tail -5 results/r15/s3/$L-srvstart.txt >> results/r15/s3/$L-probe.txt; exit 1
fi
tail -n +$((EL0 + 1)) "$ELOG" | grep -E 'expert cache [0-9]|VRAM free|resident RAM mode|page-lock|file tier reads|layer split|stage [0-9]|split|CUDA1|WARNING' | head -16 | cut -c1-240 | tee -a results/r15/s3/$L-probe.txt
.venv/bin/python work/r15/s3probe_srv.py $L "$ELOG"
bringup/lib/srv.sh stop | tail -1 | cut -c1-260 | tee -a results/r15/s3/$L-probe.txt
echo "ssd: $(tail -1 logs/r15/ssd.csv)" | tee -a results/r15/s3/$L-probe.txt
