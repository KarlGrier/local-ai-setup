#!/bin/bash
# after_speed.sh - r21: runs once reserve2.sh has finished (it waits for "reserve done" in logs/r21/reserve2.log).
#  1. item 2: the candidate (reserve 512) at PIN_CACHE=3000 (a slot count that does not follow the free VRAM) against
#     C*18's own PIN 3000 run c18-e7p -> must be 7/7 if the reserve changes nothing but the cache size
#  2. item 4: the token gate - the same 10 recorded requests, greedy, on C*18 (TK18A) and C*18 + think-fence (TK18B),
#     raw outputs and token counts compared; then the full serve suite on the patched tree
# Ends with C*18 back on 8080 (phase_end, the standing guard).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
until grep -q "reserve done" logs/r21/reserve2.log; do sleep 20; done
unset GUARD_MEM_GIB GUARD_SWAP_GROW_GIB LR_MAX
kc() { bringup/lib/kcheck.sh "r21-after-$1" || { echo "KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
echo "=== $(date -Is) exact7 candidate at PIN_CACHE=3000 vs c18-e7p"
GUARD_VRAM_MIB=128 PIN_CACHE=3000 REF=c18-e7p bringup/lib/exact7.sh c18rp3-e7 configs/Cstar18r.json 2>&1 | tail -9 | tee results/r21/res-exact7-pin3000.txt
for l in c18-e7p c18rp3-e7; do echo "$l: $(grep -h 'expert cache [0-9]* slots' bringup/out/logs/prof/$l-x-math.err | head -1 | cut -c17-70)"; done | tee -a results/r21/res-exact7-pin3000.txt
kc pin3000
echo "=== $(date -Is) token gate"
rm -rf results/r21/tk-A results/r21/tk-B
bringup/lib/with_server.sh TKA configs/TK18A.json -- ".venv/bin/python work/r21/think_tokens.py send results/r21/tk-A" 2>&1 | grep -vE "^vram|engine pid" | tail -14
kc tka
bringup/lib/with_server.sh TKB configs/TK18B.json -- ".venv/bin/python work/r21/think_tokens.py send results/r21/tk-B" 2>&1 | grep -vE "^vram|engine pid" | tail -14
kc tkb
LA=$(ls -t bringup/out/logs/server_TKA_*.log | head -1); LB=$(ls -t bringup/out/logs/server_TKB_*.log | head -1)
.venv/bin/python work/r21/think_tokens.py compare results/r21/tk-A results/r21/tk-B $LA $LB 2>&1 | tee results/r21/think-token-gate.txt
echo "=== $(date -Is) full serve suite on strata-r21think"
(cd strata-r21think && $WS/tmp/usability/venv-rt/bin/python -m unittest discover -s serve -t . -p 'test_*.py' > $WS/logs/r21/serve-suite-r21think.log 2>&1; echo "serve suite rc=$?") | tee results/r21/serve-suite-r21think.txt
tail -4 logs/r21/serve-suite-r21think.log | tee -a results/r21/serve-suite-r21think.txt
kc suite
bringup/lib/phase_end.sh r21-after keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) after_speed done"
