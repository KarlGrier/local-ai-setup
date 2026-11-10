#!/bin/bash
# e7_rebuilt.sh - round 19 after the RAM fault: the rebuilt engines' behaviour against their recorded exact7 hashes (CUDA
# builds are not byte-reproducible here: two clean builds of one tree differ, so the binaries cannot be compared; the
# seven fixed-computation outputs can). No model server runs (8080 is down after the reboot). The kernel log is checked
# after each. Ends with C*16.1 on 8080 if its rebuild repeats its recorded hashes 7/7.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r19 PROMPT_DIR=$WS/bringup/out/r16/prompts
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
OUT=results/r19/integrity/e7-rebuilt.txt; : > $OUT
.venv/bin/python bringup/lib/mkcfg.py r19i-v42kq r18v42-prc-main exe=tmp/r19/engine-v42-kq/strata > /dev/null
e7() {   # e7 LABEL CONFIG REF WHAT
  bringup/lib/kcheck.sh "e7-$1-before" || exit 1
  echo "=== $(date -Is) $4: $2 vs REF $3" | tee -a $OUT
  REF=$3 bringup/lib/exact7.sh $1 $2 2>&1 | tail -8 | tee -a $OUT
  bringup/lib/kcheck.sh "e7-$1" || exit 1
}
e7 r19i-e7-c161    configs/Cstar161.json         c161           "C*16.1 rebuilt (engine-cstar161)"
e7 r19i-e7-twin161 configs/twin161.json          c161           "C*16.1's twin rebuilt (engine-twin161; its 4 commits only measure)"
e7 r19i-e7-c16     configs/Cstar16.json          c16            "C*16 rebuilt (engine-cstar16, the rollback)"
e7 r19i-e7-v42main configs/r18v42-prc-main.json  r18v42-e7-main "stock v0.1.42 rebuilt (tmp/r18/v42-main)"
e7 r19i-e7-v42kq   configs/r19i-v42kq.json       r18v42-e7-main "stock v0.1.42 K-quant build rebuilt (tmp/r19/engine-v42-kq; reference = the plain build's)"
echo "=== $(date -Is) done" | tee -a $OUT
