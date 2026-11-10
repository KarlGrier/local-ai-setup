cd /home/USER/ai-speed-testing/strata-compare
for run in plain side; do
  L=V-det-$run
  .venv/bin/python scripts/evict.py models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
  scripts/server-C.sh start configs/V-det.json /home/USER/ai-speed-testing/strata-compare/strata-v0111/serve/server.py | tail -1
  B=".venv/bin/python scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log /home/USER/ai-speed-testing/strata-compare/logs/engine-V-det.log --session $L"
  $B warmup
  if [ $run = plain ]; then $B multiturn --mt-tag mt-fixed1; else $B multiturn --side --mt-tag mt-fixed1; fi
  scripts/server-C.sh stop
done
