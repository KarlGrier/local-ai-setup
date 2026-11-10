#!/bin/bash
# s7_refuse.sh — round 14 step 7: does v0.1.40.1 (stock) still refuse a RAM budget beside a helper-GPU cache, and does
# it take one with a layer split? Option checks only: each start must refuse or be stopped right after its first
# log lines (no model server stays up; through the queue, under the memory guard).
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
E=$WS/bringup/out/r14/engine-stock/strata; G=$WS/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf
P=$WS/bringup/out/r14/pack; PROF=$WS/bringup/out/r14/strata-stock/data/expert-profile.bin
COMMON="--pack $P --native $G --expert-profile $PROF --mmap-experts --max-context 8192 --kv int8"
for t in "helper|--resident-budget-gib 8 --expert-cache-device1 3300" "split|--resident-budget-gib 8 --layer-split auto"; do
  n=${t%%|*}; a=${t#*|}
  .venv/bin/python bringup/lib/guard.py r14-s7-$n -- timeout 40 $E $COMMON $a --tokens-file $WS/bringup/out/r14/prompts/p2000.tokens --max-new 1 > results/r14/s7-refuse-$n.txt 2>&1
  echo "s7 $n (rc $?): $(grep -m2 -iE 'does not support|refus|resident|split' results/r14/s7-refuse-$n.txt | tr '\n' ' ' | cut -c1-260)"
done | tee results/r14/s7-refuse.txt
