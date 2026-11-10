#!/bin/bash
# s7_quality.sh [LABEL...] — round 15 step 7 (1 hour): teacher-forced NLL on the acceptance suite's 9 texts (math, corpus:
# 1,536 tokens each; long16k ... long112k: 1,536 forced tokens after a 16K-112K document) for each stand-in next to IQ3_S
# and UD-Q4_K_XL, all on v0.1.40.2 + r15p27's measurement twin (bringup/lib/tf.sh; the twin config = the runbook's: every
# switch on, --adapt-swaps 0, STRATA_STATE_HASH=1; the experts' placement as in step 2). Stand-ins under your 6 GB floor,
# IQ3_S and Q4 under the 20 GB floor. Table -> results/r15/s7-quality.md (work/r15/s7_table.py).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
TEXTS="math corpus long16k long24k long28k long40k long64k long96k long112k"
one() {   # one LABEL RUN TWIN_CONFIG EVICT_GLOB [6gb]
  local L=$1 RUN=$2 C=$3
  export EVICT_GLOB="$4" PROMPT_DIR=$WS/bringup/out/$RUN/prompts
  if [ "${5:-}" = 6gb ]; then export GUARD_MEM_GIB=6 GUARD_SWAP_GROW_GIB=4; else unset GUARD_MEM_GIB GUARD_SWAP_GROW_GIB; fi
  local X; X=$(.venv/bin/python -c "import json; print(json.load(open('$C'))['exe'])")
  echo "=== $(date -Is) s7 $L ($C, exe $X)"
  bringup/lib/tf.sh s7-$L $C $X $TEXTS 2>&1 | grep -E 'teacher-forced|FAILED|GUARD' | sed "s/^/$L: /"
}
for l in ${@:-q8 q5s iq3 q4}; do
  case $l in
    q8)  one q8 r15q8 bringup/out/r15q8/configs/twin.json "$WS/models/r15/Q8_0/*.gguf" 6gb ;;
    q5s) one q5s r15q5s bringup/out/r15q5s/configs/twin.json "$WS/models/r15/splice-q5/*.gguf" 6gb ;;
    iq3) one iq3 r15 bringup/out/r15/configs/twin.json "$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf" ;;
    q4)  one q4 r15 work/r15/cfg/s7-q4-twin.json "/home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL/*.gguf" ;;
  esac
done
.venv/bin/python work/r15/s7_table.py > results/r15/s7-quality.md 2>&1
cat results/r15/s7-quality.md
