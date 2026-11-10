#!/bin/bash
# c18_pipeline.sh - Round 20 item 1, part 2: C*18 from assets to the hold before the soak (from work/r19/c171_pipeline.sh).
# Your rule: promote as C*18 only if it passes every gate and is within 1 % of C*17.1 or faster.
#   1 build-cstar18.sh (engine-cstar18 = v0.1.44.1 + the 29 commits; engine-twin18 for measurements; configs Cstar18*, twin18,
#     R18RT, BR18). CB0=1 sets STRATA_COMMIT_BATCH=0 (only if runbook r20a found the new default not bitwise).
#   2 exact7: at PIN_CACHE=3000 vs C*17.1's e7p-c171 (e7pin.sh, this session: the binding check), at the default pin
#     vs C*17.1's e7d-c171 of today, then vs itself (the default pin's slot count follows the free VRAM: see e7pin.sh)
#   3 the gates (gates18.sh, REF = step 2's first run)
#   4 the acceptance suite (acc-c18)
#   5 r04 x6 from the frozen web cache on C*18 (#2026 + its v0.1.44 follow-up), label c18-r04-check, with the request dumps
#   6 speed: C*17.1 (A, as served) vs C*18, A B B A, a fresh guarded server per screen: LDR, decode, full screens
# The 20 GiB MemAvailable floor (GUARD_* unset); a kernel check and the display state after each step; C*17.1 on 8080
# between and after the steps (phase end, keep). The soak, rollback test and promotion follow after reading these.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r20
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB LR_MAX SPEED_FILE
P=.venv/bin/python; R=results/r20; mkdir -p $R logs/r20
step() { echo "=== $(date -Is) $*"; }
G0=GPU-UUID-RTX5080
disp() { echo "$(date -Is) $1 display_active=$(nvidia-smi --id=$G0 --query-gpu=display_active --format=csv,noheader) 5080_used_MiB=$(nvidia-smi --id=$G0 --query-gpu=memory.used --format=csv,noheader,nounits) servers=$(pgrep -fc '/strata --serve')" | tee -a logs/r20/display.log; }
pe() { bringup/lib/phase_end.sh r20-c18-$1 keep 9>&- 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED" ; }
kc() { bringup/lib/kcheck.sh "c18-$1" || { step "KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
stop8080() { STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -1; for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done; disp "$1"; }
exec 9> tmp/suite/heavy.lock; flock 9
kc start
stop8080 c18-start
step "1 build (CB0=${CB0:-0})"; CB0=${CB0:-0} work/r20/build-cstar18.sh > logs/r20/build-cstar18.log 2>&1 || { tail -5 logs/r20/build-cstar18.log; step "BUILD FAILED"; pe buildfail; exit 1; }
head -6 logs/r20/build-cstar18.log; grep -E '^(Cstar18|args|configs)' logs/r20/build-cstar18.log | cut -c1-300; kc build
step "2 exact7 twice"; export PROMPT_DIR=$WS/bringup/out/r20a/prompts EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
# the binding check at PIN_CACHE=3000 (a slot count that does not follow the free VRAM; e7pin.sh made C*17.1's e7p-c171 in
# this session), then the default pin vs C*17.1's default-pin run of today (e7d-c171) and C*18 vs itself
PIN_CACHE=3000 REF=e7p-c171 bringup/lib/exact7.sh c18-e7p configs/Cstar18.json 9>&- 2>&1 | tail -8 | tee $R/c18-e7.txt; kc e7p
REF=e7d-c171 bringup/lib/exact7.sh c18-e7 configs/Cstar18.json 9>&- 2>&1 | tail -1 | tee -a $R/c18-e7.txt; kc e7
REF=c18-e7 bringup/lib/exact7.sh c18-e7b configs/Cstar18.json 9>&- 2>&1 | tail -1 | tee -a $R/c18-e7.txt; kc e7b
for l in e7p-c171 c18-e7p e7d-c171 c18-e7 c18-e7b; do echo "$l: $(grep -h 'expert cache [0-9]* slots' bringup/out/logs/prof/$l-x-math.err | head -1 | cut -c18-70)"; done | tee -a $R/c18-e7.txt
disp c18-e7
step "3 gates"
work/r20/gates18.sh c18 configs/Cstar18.json configs/R18RT.json configs/BR18.json c18-e7 9>&- > logs/r20/gates18.log 2>&1
grep -v '^PASS stream' $R/g-gates-c18.txt | cut -c1-200
kc gates; disp c18-gates
step "4 acceptance suite"
bringup/acceptance.sh acc-c18 configs/Cstar18.json configs/twin18.json 9>&- > $R/accept-c18.txt 2>&1
cp bringup/out/accept/acc-c18/table.md $R/accept-c18-table.md 2>/dev/null; tail -22 bringup/out/accept/acc-c18/table.md
kc accept; disp c18-accept
step "5 r04 x6 from the frozen web cache (label c18-r04-check)"
O=$WS/results/r20/r04; mkdir -p $O; rm -rf $O/req-c18
TK=$($P -c "import json; print(json.load(open('configs/Cstar18.json'))['tokenizer'])")
bringup/lib/with_server.sh 9>&- r04-c18 configs/Cstar18.json -- \
  "MSUITE_DUMP_REQUESTS=$O/req-c18 suite/run.sh --label c18-r04-check --endpoint http://127.0.0.1:8081 --mode full --only research --items r04_strata_release --runs 6 2>&1 | tail -3" \
  2>&1 | grep -E 'start|ready|done|exited|graded|answers|scores'
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-160
$P work/suite/r04_probe_live.py contexts --label c18-r04-check --requests $O/req-c18 --server-log "$(ls -t bringup/out/logs/server_r04-c18_*.log 2>/dev/null | head -1)" --tokenizer $TK --out $O/ctx-c18.json 2>&1 | tail -8
kc r04; disp c18-r04
step "6 speed vs C*17.1 (A B B A)"
work/r20/speed18.sh configs/Cstar18.json c18 9>&- > logs/r20/speed18.log 2>&1; grep -E 'results/|done' logs/r20/speed18.log | cut -c1-300
kc speed
step "C*18 pipeline (first half) done"
