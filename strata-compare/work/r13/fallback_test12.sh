#!/bin/bash
# fallback_test.sh — round 10 copy: C*12's launcher fallback. Another process takes ~1 GiB of the RTX 4060 Ti (the desktop card),
# so it has less than the helper needs; ./run-strata.sh start (port 8081, configs/Cstar12.json) must then start
# configs/Cstar12-single.json (the RTX 5080 alone) and serve. Then the hog is released, and a normal start must use the helper.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
source $WS/work/r13/env.sh
T=GPU-UUID-RTX4060TI
echo "4060 Ti free before: $(nvidia-smi -i $T --query-gpu=memory.free --format=csv,noheader)"
CUDA_VISIBLE_DEVICES=$T work/r5/vramhog/vramhog 1024 > logs/r13/fallback-hog.out 2>&1 &
HOG=$!
sleep 8; cat logs/r13/fallback-hog.out
echo "4060 Ti free with the hog: $(nvidia-smi -i $T --query-gpu=memory.free --format=csv,noheader)"
STRATA_PORT=8081 STRATA_CONFIG=configs/Cstar12.json ./run-strata.sh start 2>&1 | grep -v "^$"
.venv/bin/python work/r13/guard.py FALLBACK-single --watch-pattern "engine-cstar12/strata --serve" > /dev/null 2>&1 &
G=$!
head -1 $(cat logs/run/strata-8081.logpath)
curl -s -m 60 http://127.0.0.1:8081/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"x","messages":[{"role":"user","content":"Say OK."}],"max_tokens":16,"reasoning_effort":"none"}' | head -c 300; echo
echo "strata processes on the 4060 Ti: $(nvidia-smi -i $T --query-compute-apps=pid,used_memory --format=csv,noheader | grep -v "^$HOG," | tr '\n' ' ')"
STRATA_PORT=8081 ./run-strata.sh stop
kill $HOG; wait $HOG 2>/dev/null; kill $G 2>/dev/null
sleep 3; echo "4060 Ti free after the hog: $(nvidia-smi -i $T --query-gpu=memory.free --format=csv,noheader)"
STRATA_PORT=8081 STRATA_CONFIG=configs/Cstar12.json ./run-strata.sh start 2>&1 | grep -v "^$"
head -1 $(cat logs/run/strata-8081.logpath)
echo "strata on the 4060 Ti now: $(nvidia-smi -i $T --query-compute-apps=pid,used_memory --format=csv,noheader | tr '\n' ' ')"
STRATA_PORT=8081 ./run-strata.sh stop
