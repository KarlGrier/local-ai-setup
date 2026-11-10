#!/bin/bash
# c_llama.sh - 2026-10-14 C, engine cross-check: the same token sequences on the same Q8_0 file in llama.cpp
# (signal-3.8-opus build 6fcaa16, which serves this architecture): experts memory-mapped on the CPU, the rest on the
# 5080, f16 KV, port 8091; p(top) at digits 256 / 300 / 600 / 900 (work/r20/c_llama.py).  Ids dumped first by the
# scratch hook server on C*17.1 (configs/r19-guard-c171cont.json; only the dump field is new).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
PY=$WS/suite/.venv/bin/python
TK=$(jq -r .tokenizer configs/Cstar171.json)
CASES="c171-iq3s-quick:c07_rpn:0,c171-iq3s-full:c23_refactor_orderbook:2,c171-iq3s-full:c02_rle:2"
step() { echo "=== $(date -Is) $*"; }
SRV='^[^ ]*/llama-server( |$)|^[^ ]*/strata --serve'
mon_gone() { for i in $(seq 120); do pgrep -f 'monitor.py --pid-pattern' > /dev/null || return 0; sleep 1; done; }
srv_gone() { for i in $(seq 60); do pgrep -f "$SRV" > /dev/null || break; sleep 1; done; mon_gone; ! pgrep -fa "$SRV"; }
kc() { bringup/lib/kcheck.sh "$1" || { step "KERNEL CHECK FAILED ($1) - stopped"; exit 1; }; step "kernel check ok ($1)"; }
exec 9> tmp/suite/heavy.lock; flock 9
kc r20-cl-start; srv_gone || { step "a model server is running - stop"; exit 1; }
step "dump the ids (C*17.1 + hook)"
bringup/lib/with_server.sh 9>&- cl-dump configs/r19-guard-c171cont.json -- \
  "$PY work/r20/c_llama.py dump --endpoint http://127.0.0.1:8081 --tokenizer $TK --cases $CASES" 2>&1 | grep -vE '^\[strata\]'
srv_gone || { step "server still running"; exit 1; }
kc r20-cl-dump
step "llama.cpp on Q8_0"
LB=/home/USER/ai-speed-testing/signal-3.8-opus/build/llama.cpp-6fcaa16/build/bin/llama-server
LOG=logs/r20/llama-q8.log
CUDA_VISIBLE_DEVICES=GPU-UUID-RTX5080 setsid $LB \
  --model $WS/models/r15/Q8_0/Qwen3.8-Flash-Next-Q8_0-00001-of-00006.gguf --host 127.0.0.1 --port 8091 \
  --ctx-size 12288 --parallel 1 --gpu-layers all --override-tensor 'blk\.[0-9]+\.ffn_(up|gate|down)_exps\.weight=CPU' \
  --ubatch-size 4096 --batch-size 4096 --flash-attn on --no-context-shift --cache-reuse 0 9>&- > $LOG 2>&1 < /dev/null &
LP=$!
for i in $(seq 600); do curl -sf -m 2 http://127.0.0.1:8091/health > /dev/null && break; kill -0 $LP 2>/dev/null || break; sleep 1; done
if curl -sf -m 2 http://127.0.0.1:8091/health > /dev/null; then
  step "llama-server up (pid $LP) after ${i} s; min MemAvailable is logged by the probe's caller"
  $PY work/r20/c_llama.py probe --endpoint http://127.0.0.1:8091 --tokenizer $TK --cases $CASES 2>&1
else
  step "llama-server did not come up"; tail -30 $LOG
fi
kill $LP 2>/dev/null; for i in $(seq 60); do kill -0 $LP 2>/dev/null || break; sleep 1; done; kill -9 $LP 2>/dev/null
grep -E "model type|n_expert|ggml_cuda|CUDA0|KV self size|error|failed" $LOG | head -12 | cut -c1-200
srv_gone || step "a server is still running"
kc r20-cl-end
step "c_llama done"
