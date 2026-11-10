#!/bin/bash
# b7b_share0.sh - round 19 B7, the lossless check's follow-up: budget 66 vs --resident-experts gave the same outputs on the
# three long items (2K / 32K / 112K: chunks above STRATA_PREFILL_CPU_SHARE_MAX=1792, no CPU share) and different outputs
# on the four short ones (the share applies: the CPU takes a share of the experts the GPU would stream, and which ones
# depends on where the experts live). The four short items again with the share off (STRATA_PREFILL_CPU_SHARE=0) in both
# placements: identical -> the placement is lossless and the difference is the share's split. Kernel log after each run.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r19 GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
export EVICT_GLOB="/home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL/*.gguf"
export PROMPT_DIR=$WS/bringup/out/r16q4/prompts
P=.venv/bin/python; R=results/r19
kc() { bringup/lib/kcheck.sh "$1" || { echo "=== $(date -Is) KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
kc b7b-start
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 2400"; S='--seed 11 --temperature 1.0 --top-p 0.95 --top-k 20'
for arm in b66 res; do
  for it in "x-math math" "s-math math" "x-code code" "s-code code"; do
    set -- $it; L=r19-b7b-s0-$arm-$1
    if [ "${1:0:1}" = s ]; then ENVX="STRATA_PREFILL_CPU_SHARE=0" PROF_SAMPLING="$S" COLD=1 bringup/lib/run.sh $L configs/r19-q4-$arm.json $2 1024 $X > /dev/null
    else ENVX="STRATA_PREFILL_CPU_SHARE=0" COLD=1 bringup/lib/run.sh $L configs/r19-q4-$arm.json $2 1024 $X > /dev/null; fi
    tail -1 bringup/out/logs/guard/summary.txt | cut -c1-150; kc $L
  done
done
$P - <<'PY' | tee $R/b7-q4-exact-share0.md
import sys
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/bringup/lib")
from p0_table import parse
print("| item (share off) | budget 66 | --resident-experts | equal |\n|---|---|---|---|")
n = 0
for it in ("x-math", "s-math", "x-code", "s-code"):
    a, b = parse(f"r19-b7b-s0-b66-{it}") or {}, parse(f"r19-b7b-s0-res-{it}") or {}
    eq = a.get("out") is not None and a.get("out") == b.get("out"); n += eq
    print(f"| {it} | {a.get('out')} | {b.get('out')} | {'yes' if eq else 'NO'} |")
print(f"\nshare off: {n}/4 identical (with the share: 0/4; the 3 long items, no share either way: 3/3)")
PY
bringup/lib/phase_end.sh r19-b7b keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
kc b7b-end
echo "=== $(date -Is) b7b done"
