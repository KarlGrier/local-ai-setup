#!/bin/bash
# rollback_test.sh — round 6: after the launchers point at C*6, prove the rollback: 8080 -> C*5 (the round-5 build,
# STRATA_CONFIG=configs/Cstar5.json), check it answers and runs engine-cstar5, then back to the default (C*6), check again.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
eng() { local p; p=$(ss -H -ltnp "( sport = :8080 )" | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2); \
        local e; e=$(pgrep -P "$p" -f 'strata --serve' | head -1); \
        echo "server $p engine $e exe $(readlink /proc/$e/exe) sha $(sha256sum $(readlink /proc/$e/exe) | cut -c1-12) config $(tr '\0' ' ' < /proc/$p/cmdline | grep -o -- '--config [^ ]*')"; }
echo "=== $(date -Is) rollback: STRATA_CONFIG=configs/Cstar5.json ./switch-model.sh strata"
t0=$(date +%s); STRATA_CONFIG=configs/Cstar5.json ./switch-model.sh strata 2>&1 | tail -4; echo "switch took $(( $(date +%s) - t0 )) s"
eng
curl -s -m 60 http://127.0.0.1:8080/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"x","messages":[{"role":"user","content":"What is 17*3? Answer with the number only."}],"max_tokens":400}' | .venv/bin/python -c "import json,sys; d=json.load(sys.stdin); print('answer:', d['choices'][0]['message']['content'][:60].strip(), '| finish', d['choices'][0]['finish_reason'])"
nvidia-smi --query-compute-apps=pid,gpu_uuid,used_memory --format=csv,noheader
echo "=== $(date -Is) back to the default: ./switch-model.sh strata"
t0=$(date +%s); ./switch-model.sh strata 2>&1 | tail -4; echo "switch took $(( $(date +%s) - t0 )) s"
eng
curl -s -m 60 http://127.0.0.1:8080/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"x","messages":[{"role":"user","content":"What is 17*3? Answer with the number only."}],"max_tokens":400}' | .venv/bin/python -c "import json,sys; d=json.load(sys.stdin); print('answer:', d['choices'][0]['message']['content'][:60].strip(), '| finish', d['choices'][0]['finish_reason'])"
nvidia-smi --query-compute-apps=pid,gpu_uuid,used_memory --format=csv,noheader
./switch-model.sh status 2>&1 | head -8
echo "=== $(date -Is) rollback test done"
