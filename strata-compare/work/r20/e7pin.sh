#!/bin/bash
# e7pin.sh - Round 20 item 1: the cross-version exact7 checks with a cache size that does not depend on the free VRAM.
# Found 10-15: on a native pack exact7's "--expert-cache 3500" is a VRAM budget (3,500 x the largest blob, ~9.3 GB); the
# 5080 has less free than that, so the slot count follows the free VRAM (4,551 with the monitor on the iGPU, 4,510 with
# it on the 5080) and the GPU-vs-CPU rounding of the decode follows it. Hashes made on 10-11/12 (C*17.1's c171-e7,
# v0.1.43 stock rb-r19e-stock) therefore cannot be compared bit for bit with today's runs. Here every build runs in this
# session at PIN_CACHE=3000 (budget ~7.4 GiB, below the free VRAM either way), so the slot count is the same for all:
#   v0.1.43 stock (runbook r19e's engine and config) vs v0.1.44.1 stock (r20a): do the new defaults change our outputs?
#   C*17.1 (as served) vs r20a's all-on candidate: does the port compute what C*17.1 computes?
#   the candidate again (repeat), and with STRATA_COMMIT_BATCH=0: is the new default bitwise?
#   + C*17.1 at the default pin (free-VRAM bound now) vs v0.1.43 stock's default-pin run of today, for the record.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r20 PROMPT_DIR=$WS/bringup/out/r20a/prompts EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
O=$WS/results/r20/e7pin; mkdir -p $O
step() { echo "=== $(date -Is) $*"; }
G0=GPU-UUID-RTX5080
disp() { echo "$(date -Is) $1 display_active=$(nvidia-smi --id=$G0 --query-gpu=display_active --format=csv,noheader) 5080_used_MiB=$(nvidia-smi --id=$G0 --query-gpu=memory.used --format=csv,noheader,nounits) servers=$(pgrep -fc '/strata --serve')" | tee -a logs/r20/display.log; }
kc() { bringup/lib/kcheck.sh "e7pin-$1" || { step "KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; disp "e7pin-$1"; }
e7() {   # e7 LABEL CONFIG REF [ENVX]
  ENVX="${4:-}" REF=$3 bringup/lib/exact7.sh $1 $2 9>&- > $O/$1.txt 2>&1
  echo "$1 (ref $3): $(tail -1 $O/$1.txt | cut -c1-120) | $(grep -h 'expert cache [0-9]* slots' bringup/out/logs/prof/$1-x-math.err | head -1 | cut -c18-70)"
}
exec 9> tmp/suite/heavy.lock; flock 9
kc start
STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
R19=bringup/out/r19e/configs R20=bringup/out/r20a/configs
export PIN_CACHE=3000
e7 e7p-v043stock $R19/stock.json rb-r19e-stock
e7 e7p-v0441stock $R20/stock.json e7p-v043stock
kc stocks
e7 e7p-c171 configs/Cstar171.json c171-e7
e7 e7p-cand $R20/cand.json e7p-c171
e7 e7p-cand2 $R20/cand.json e7p-cand
e7 e7p-cb0 $R20/cand-cb0.json e7p-cand
kc cands
export PIN_CACHE=3500
e7 e7d-c171 configs/Cstar171.json rb-r20a-cand
kc default-pin
bringup/lib/phase_end.sh r20-e7pin keep 9>&- 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
kc end
step "e7pin done"
