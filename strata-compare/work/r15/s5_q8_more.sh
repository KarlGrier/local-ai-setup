#!/bin/bash
# s5_q8_more.sh — round 15 step 5, Q8_0 D, inside its 2 hours (51 min used): the two keeps whose gain sat inside the base
# arms' spread, again, and the two together against the base (A B B A each, same method as s5_settings.sh)
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
export GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
EVICT_GLOB="$WS/models/r15/Q8_0/*.gguf" PROMPT_DIR=$WS/bringup/out/r15q8/prompts work/r15/s5_settings.sh q8-D71r configs/r15-q8-Dx71.json \
  "combo:-:--adapt-swaps=48+--max-context=65536" "swaps48r:-:--adapt-swaps=48" "ctx64kr:-:--max-context=65536"
