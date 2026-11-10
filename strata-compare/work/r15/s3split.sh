#!/bin/bash
# s3split.sh LABEL CONFIG.json — round 15 step 3: where a round's time goes, from the engine's own --stats (CLI, the
# config's flags as served, the adaptive tier live, greedy, 1,024 tokens of the math prompt; cold model page cache, then
# the same run again warm) with STRATA_IO_STATS=1 (the file tier's page-cache split and the decode's wait in its fetches):
# ms per round = GPU work + the GPU's wait for the CPU pool; the pool's time = its reads of RAM + the file tier's
# reading (SSD + page cache). Output: bringup/out/logs/prof/LABEL-split-{cold,warm}.out
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
L=$1 CFG=$2
export PROMPT_DIR=${PROMPT_DIR:-$WS/bringup/out/r15/prompts}
ENVX="STRATA_IO_STATS=1 ${ENVX:-}" COLD=1 bringup/lib/run.sh $L-split-cold "$CFG" math 1024 > /dev/null
ENVX="STRATA_IO_STATS=1 ${ENVX:-}" COLD=0 bringup/lib/run.sh $L-split-warm "$CFG" math 1024 > /dev/null
for k in cold warm; do
  f=bringup/out/logs/prof/$L-split-$k.out
  echo "--- $L split ($k)"
  grep -E '^(speculation|verify window|pool multi|expert tiers|io path|resident RAM|adaptive tier|decode  )|R4 expert-cache hits|^  the CPU expert pool|ple io|CUDA1 experts' $f | cut -c1-260
  tail -1 $f | cut -c1-260
done
