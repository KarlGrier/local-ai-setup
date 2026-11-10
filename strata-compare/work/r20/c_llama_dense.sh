#!/bin/bash
# c_llama_dense.sh - 2026-10-14 C: llama.cpp on the same Q8_0 file and the same ids (dumped by c_llama.sh), every digit
# j = 480..540 of the run (the region where Strata's IQ3_S and Q8_0 both dip and hosted Flash stopped), 3 cases.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
PY=$WS/suite/.venv/bin/python; TK=$(jq -r .tokenizer configs/Cstar171.json)
CASES="c171-iq3s-quick:c07_rpn:0,c171-iq3s-full:c23_refactor_orderbook:2,c171-iq3s-full:c02_rle:2"
step() { echo "=== $(date -Is) $*"; }
SRV='^[^ ]*/llama-server( |$)|^[^ ]*/strata --serve'
kc() { bringup/lib/kcheck.sh "$1" || { step "KERNEL CHECK FAILED ($1) - stopped"; exit 1; }; step "kernel check ok ($1)"; }
exec 9> tmp/suite/heavy.lock; flock 9
kc r20-cld-start; pgrep -fa "$SRV" && { step "a model server is running - stop"; exit 1; }
LB=/home/USER/ai-speed-testing/signal-3.8-opus/build/llama.cpp-6fcaa16/build/bin/llama-server
CUDA_VISIBLE_DEVICES=GPU-UUID-RTX5080 setsid $LB \
  --model $WS/models/r15/Q8_0/Qwen3.8-Flash-Next-Q8_0-00001-of-00006.gguf --host 127.0.0.1 --port 8091 \
  --ctx-size 12288 --parallel 1 --gpu-layers all --override-tensor 'blk\.[0-9]+\.ffn_(up|gate|down)_exps\.weight=CPU' \
  --ubatch-size 4096 --batch-size 4096 --flash-attn on --no-context-shift --cache-reuse 0 9>&- > logs/r20/llama-q8-dense.log 2>&1 < /dev/null &
LP=$!
for i in $(seq 600); do curl -sf -m 2 http://127.0.0.1:8091/health > /dev/null && break; kill -0 $LP 2>/dev/null || break; sleep 1; done
P=$(seq -s, 480 540)
$PY work/r20/c_llama.py probe --endpoint http://127.0.0.1:8091 --tokenizer $TK --cases $CASES --positions "$P" --tag -dense 2>&1 | \
  awk '{print; fflush()}' | grep --line-buffered -E '"p_top": 0\.[0-8]|"p_top": 0\.9[0-4]|Error|Traceback' || true
kill $LP; for i in $(seq 60); do kill -0 $LP 2>/dev/null || break; sleep 1; done; kill -9 $LP 2>/dev/null
kc r20-cld-end
step "c_llama_dense done"
