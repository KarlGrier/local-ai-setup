#!/bin/bash
# p52kv.sh LABEL KVTYPE MODEL_FIRST_SHARD — round 13 Part 5.2 (copy of round 12 A7 a7score.sh with the KV type as a parameter): Round 4's llama.cpp teacher-forced scorer
# (work/r4/llama_tf-6fcaa16, the build Round 4's reference numbers came from; its libraries are only executed) on Phase E's
# nine texts (work/prof/tf-{math,corpus,long16k,long24k,long28k,long40k,long64k,long96k,long112k}), all in one process.
# Round 4's flags: experts on the CPU through the page cache (--load-mode mmap), n-gram table lazy, q8_0 KV, FA, ubatch /
# batch 4096, 131072 context, --parallel 1. Under work/r13/guard.py (MemAvailable >= 20 GiB, 5080 >= 300 MiB free; the
# llama.cpp process is its child). NLL per token: results/r13/p52/tf-LABEL-TEXT.nll (one value per line).
set -u
WS=/home/USER/ai-speed-testing/strata-compare
L=$1 KV=$2 MODEL=$3; shift 3
source $WS/work/r13/env.sh
mkdir -p $WS/results/r13/p52 $WS/logs/r13/p52
J=()
for T in ${TEXTS:-math corpus long16k long24k long28k long40k long64k long96k long112k}; do
  rm -f $WS/results/r13/p52/tf-$L-$T.nll
  J+=(--tf $WS/work/prof/tf-$T.prompt $WS/work/prof/tf-$T.text $WS/results/r13/p52/tf-$L-$T.nll)
done
echo "=== $(date -Is) p52kv $L $KV model $MODEL $*; before: MemAvailable $(awk '/MemAvailable/ {printf "%.1f GiB", $2/1048576}' /proc/meminfo)"
$WS/.venv/bin/python $WS/scripts/evict.py $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
env -u LLAMA_ARG_HOST CUDA_VISIBLE_DEVICES=GPU-UUID-RTX5080 $WS/.venv/bin/python $WS/work/r13/guard.py p52-$L -- \
  $WS/work/r4/llama_tf-6fcaa16 "${J[@]}" --model $MODEL --ctx-size 131072 --kv-unified \
  --cache-type-k $KV --cache-type-v $KV --flash-attn on --fit off --gpu-layers all \
  --override-tensor 'blk\.[0-9]+\.ffn_(up|gate|down)_exps\.weight=CPU' --ubatch-size 4096 --batch-size 4096 \
  --load-mode mmap --lazy-mode on --parallel 1 "$@" > $WS/logs/r13/p52/$L.out 2> $WS/logs/r13/p52/$L.err
echo "exit $?"
tail -1 $WS/logs/r13/guard/summary.txt
cat $WS/logs/r13/p52/$L.out | tail -12
grep -E 'llama_tf:|error|ERROR|failed' $WS/logs/r13/p52/$L.err | head -8
for T in ${TEXTS:-math corpus long16k long24k long28k long40k long64k long96k long112k}; do echo "$T $(wc -l < $WS/results/r13/p52/tf-$L-$T.nll 2>/dev/null)"; done | tr '\n' ' '; echo
echo "=== $(date -Is) p52kv $L $KV done"
