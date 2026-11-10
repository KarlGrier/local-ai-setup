#!/bin/bash
# (round 5 copy: pinned to the RTX 5080, logs in logs/r5) ltf.sh LABEL BUILD_TAG [extra llama flags...] — teacher-forced scoring on an as-is llama.cpp build (work/r4/llama_tf-TAG,
# linked against that build's own libraries) with llama-server's flags for this model (server-B/L: experts in RAM,
# n-gram table lazy, q8_0 KV, FA, ubatch/batch 4096, 131072 ctx). Round 4: --load-mode mmap (experts through the page
# cache: 'none' pinned 48 GB + ~41 GB anon during load on this build and the kernel OOM-killed it), memguard at 10 GB. All five texts in one process (model loads once).
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 TAG=$2; shift 2
source $WS/work/r5/env.sh
MODEL=$WS/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf
$WS/.venv/bin/python $WS/scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
J=()
for T in ${TEXTS:-math corpus long16k long24k long64k}; do rm -f $WS/results/tf-$L-$T.nll; J+=(--tf $WS/work/prof/tf-$T.prompt $WS/work/prof/tf-$T.text $WS/results/tf-$L-$T.nll); done
echo "=== $(date -Is) ltf $L build $TAG $*"
env -u LLAMA_ARG_HOST CUDA_VISIBLE_DEVICES=GPU-UUID-RTX5080 $WS/work/r4/llama_tf-$TAG "${J[@]}" --model $MODEL --ctx-size 131072 --kv-unified \
  --cache-type-k q8_0 --cache-type-v q8_0 --flash-attn on --fit off --gpu-layers all \
  --override-tensor 'blk\.[0-9]+\.ffn_(up|gate|down)_exps\.weight=CPU' --ubatch-size 4096 --batch-size 4096 \
  --load-mode mmap --lazy-mode on --parallel 1 "$@" > $WS/logs/r5/ltf-$L.out 2> $WS/logs/r5/ltf-$L.err &
LP=$!; $WS/work/r4/memguard.sh $LP 20480 1024 2>> $WS/logs/r5/ltf-$L.err & wait $LP; echo "exit $?"; cat $WS/logs/r5/ltf-$L.out; grep -E 'llama_tf:|sparse|flash|n_ubatch|error|ERROR' $WS/logs/r5/ltf-$L.err | head -8
