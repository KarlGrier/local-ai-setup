#!/bin/bash
# s5_after_full.sh — round 15: step 5 on each file's best placement at the budget its full set PASSED at (the full-run
# check against your floor, work/r15/s3full.sh), then step 7. Q8_0: placement D (CLI, your sampling, s5_settings.sh);
# the splice: placement C (served, s5_srv.sh: the engine runs the layer split only under --serve).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
OPTS="spec3:-:--spec=3 floor07:STRATA_COST_GATE=:--spec-min-p=0.7 pcie02:-:--pcie-frac=0.2 pool12:-:--pool-workers=12 reserve713:-:--vram-reserve-mib=713 kv16k:-:--kv-resident=16384 ctx64k:-:--max-context=65536 swaps48:-:--adapt-swaps=48 swaps192:-:--adapt-swaps=192"
passed() {   # passed LABEL BASECFG -> the config its full set passed with (empty: none passed)
  local L=$1 B=$2 line b
  line=$(awk '/2026-10-07T19:13:/{f=1} f' bringup/out/logs/batch.log | grep -E "$L(-try[0-9])?: full set ran without a guard stop at [0-9]+ GiB" | tail -1)
  [ -z "$line" ] && return
  b=$(echo "$line" | grep -oE 'at [0-9]+ GiB' | grep -oE '[0-9]+')
  if [ -f work/r15/cfg/$L-b$b.json ]; then echo work/r15/cfg/$L-b$b.json; else echo $B; fi
}
export GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
C8=$(passed r15-q8-Dx71-full configs/r15-q8-Dx71.json)
C5=$(passed r15-q5s-Cx72-full configs/r15-q5s-Cx72.json)
echo "=== $(date -Is) step 5 configs: Q8_0 D = ${C8:-none passed}; the splice C = ${C5:-none passed}"
if [ -n "$C8" ]; then
  B8=$(.venv/bin/python -c "import json; a=json.load(open('$C8'))['args']; print(a[a.index('--resident-budget-gib')+1])")
  EVICT_GLOB="$WS/models/r15/Q8_0/*.gguf" PROMPT_DIR=$WS/bringup/out/r15q8/prompts work/r15/s5_settings.sh q8-D$B8 $C8 $OPTS
fi
if [ -n "$C5" ]; then
  B5=$(.venv/bin/python -c "import json; a=json.load(open('$C5'))['args']; print(a[a.index('--resident-budget-gib')+1])")
  for i in $(seq 120); do ss -H -ltn "( sport = :8081 )" | grep -q . || break; sleep 1; done
  # round 15 (your additions for C): the split point (auto = 47 against 46 and 44: CUDA1 starts there) and the prompt chunk
  # (auto = 1,024 here, capped by the 4060 Ti's 431 slots, against explicit 2,048 and 512; the engine may shrink 2,048 back) first,
  # judged by the prompt read at no more than -3 % decode; then the step-5 list in order of likely value; 2-hour limit
  OPTSC="split46:-:--layer-split=46 split44:-:--layer-split=44 chunk2048:-:--prefill=2048 chunk512:-:--prefill=512 spec3:-:--spec=3 floor07:STRATA_COST_GATE=:--spec-min-p=0.7 reserve713:-:--vram-reserve-mib=713 kv16k:-:--kv-resident=16384 ctx64k:-:--max-context=65536 swaps48:-:--adapt-swaps=48 pcie02:-:--pcie-frac=0.2 pool12:-:--pool-workers=12 swaps192:-:--adapt-swaps=192"
  EVICT_GLOB="$WS/models/r15/splice-q5/*.gguf" S5_MIN=120 work/r15/s5_srv.sh q5s-C$B5 $C5 $OPTSC
fi
