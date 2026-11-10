#!/bin/bash
# post18.sh - Round 20 item 1, after the pipeline (run by hand once C*18 passed every gate and is within 1 % of C*17.1):
#   1 the stop-string test 3 more times on C*18 (8081, guarded): its one "failure" in gates18 was the stop-early heuristic
#     (145 tokens against 0.75 x a 190-token control whose thinking is sampled; text, no leak, finish reason all right)
#   2 the 2-hour soak of C*18 on 8080 (bringup/lib/soak13.sh with STRATA_CONFIG=configs/Cstar18.json), then SDEC18
#   3 promote-c18.sh (launchers -> C*18, the rollback test to C*17.1) only if the soak logged "errors: 0"
# Kernel check after each step; the standing 20 GiB MemAvailable floor (guard default).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
step() { echo "=== $(date -Is) $*"; }
G0=GPU-UUID-RTX5080
disp() { echo "$(date -Is) $1 display_active=$(nvidia-smi --id=$G0 --query-gpu=display_active --format=csv,noheader) 5080_used_MiB=$(nvidia-smi --id=$G0 --query-gpu=memory.used --format=csv,noheader,nounits) servers=$(pgrep -fc '/strata --serve')" | tee -a logs/r20/display.log; }
kc() { bringup/lib/kcheck.sh "post18-$1" || { step "KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; disp "post18-$1"; }
# 13:00 fix: with_server.sh's monitor ("--pid-pattern /strata --serve") can still be exiting after its server; the
# launcher counts it as another model server and refused the soak's start (first run: "no soak") - wait for it
mon_gone() { for i in $(seq 120); do pgrep -f 'monitor.py --pid-pattern' > /dev/null || return 0; sleep 1; done; pgrep -fa 'monitor.py --pid-pattern'; }
exec 9> tmp/suite/heavy.lock; flock 9
kc start
if [ "${SKIP_STOP:-0}" != 1 ]; then
step "1 stop-string test x3 on C*18"
STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
bringup/lib/with_server.sh 9>&- stop-c18 configs/Cstar18.json -- \
  "for k in 1 2 3; do .venv/bin/python bringup/lib/stoptest.py http://127.0.0.1:8081 c18-re\$k | grep -E '^stoptest|FAIL'; done" 2>&1 | grep -vE '^\[strata\]' | tail -12
kc stoptest
else step "1 skipped (SKIP_STOP=1: done 12:58-12:59, 3/3 ALL PASS)"; fi
mon_gone
step "2 soak of C*18 (2 h, on 8080)"
echo "=== $(date -Is) soak C*18 (2 h, on 8080)" >> logs/r20/soak18.log
STRATA_CONFIG=configs/Cstar18.json bringup/lib/soak13.sh 120 9>&- >> logs/r20/soak18.log 2>&1
tail -25 logs/r20/soak18.log | cut -c1-220
if grep -q "no soak" <(tail -5 logs/r20/soak18.log); then step "the soak did not start - stopped (no verdict); the launchers' default back on 8080"
  mon_gone; ./switch-model.sh strata 9>&- 2>&1 | tail -2; kc nosoak; exit 2; fi
kc soak
bringup/lib/soakdec.sh SDEC18 configs/Cstar18.json 9>&- > logs/r20/soakdec18.log 2>&1; tail -6 logs/r20/soakdec18.log | cut -c1-200
kc soakdec
if grep -q 'errors: 0 ' logs/r20/soak18.log; then
  step "3 promote C*18"; work/r20/promote-c18.sh 9>&- > logs/r20/promote-c18.log 2>&1; tail -12 logs/r20/promote-c18.log | cut -c1-220
else
  step "3 NOT promoted: the soak did not log 'errors: 0' (see logs/r20/soak18.log); C*17.1 back on 8080"
  STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -1   # switch-model.sh keeps any running Strata: stop first
  for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done; sleep 5
  STRATA_CONFIG=configs/Cstar171.json ./switch-model.sh strata 9>&- 2>&1 | tail -2
fi
kc end
step "post18 done"
