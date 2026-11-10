#!/bin/bash
# effort_suite.sh - 2026-10-17, your morning plan items 3 and 4:
#   3  the suite's quick run on C*18t (IQ3_S, configs/Cstar18t.json) at reasoning effort medium, then at high, your
#      sampling (the suite sends T 1.0 / 0.95 / 20 / min-p 0.05; the effort through --extra-body, merged last into every
#      request). Labels c18t-quick-medium / c18t-quick-high; each compared per category against the 10-15 xhigh run
#      c18-iq3s-quick (90.7), with wall time and median reasoning tokens per category (results/r21/effort-suite.md).
#      Note: Strata renders "high" as xhigh (serve/frontend.py EFFORT), so the high run is the xhigh prompt again.
#   4  dsh Minimal r5 on the bug-fix task (harness_batch5b.sh, ARMS=dsh-minimal), then the harness table (r5 + r6).
# Daytime only (your rule: no run over ~30 min between 23:00 and 09:00): a level starts only if its estimate ends
# before 23:00, and every suite run is cut at 23:00 (a rerun resumes the label). One guarded server on 8081 at a time
# (floor 20 GiB); graded after the servers are gone; C*18t back on 8080 at the end.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT
export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
CFG=configs/Cstar18t.json; BASE=c18-iq3s-quick; O=results/r21
END=$(date -d '23:00' +%s)
step() { echo "=== $(date -Is) $*"; }
kc() { bringup/lib/kcheck.sh "effsuite-$1" || { step "KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
SRV='^[^ ]*/llama-server( |$)|^[^ ]*/strata --serve'
srv_gone() { for i in $(seq 60); do pgrep -f "$SRV" > /dev/null || break; sleep 1; done; ! pgrep -fa "$SRV"; }
fits() { [ $(( $(date +%s) + $1 * 60 )) -lt $END ]; }   # minutes
exec 9> tmp/suite/heavy.lock; flock 9
kc start
STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -1
srv_gone || { step "a model server is still running - stop"; bringup/lib/phase_end.sh effsuite-abort keep 9>&- 2>&1 | grep -E "phase end|8080:"; exit 1; }
for lv in ${LEVELS:-medium high}; do
  L=c18t-quick-$lv; EST=$([ $lv = medium ] && echo 90 || echo 200)
  if ! fits $EST; then step "$L not started: ~$EST min would run past 23:00"; continue; fi
  step "$L on $CFG (8081, guarded), effort $lv"
  bringup/lib/with_server.sh 9>&- suite-$L $CFG -- \
    "timeout $(( END - $(date +%s) )) suite/run.sh --label $L --endpoint http://127.0.0.1:8081 --mode quick --no-grade --extra-body '{\"reasoning_effort\": \"$lv\"}'; echo suite exit \$?" \
    2>&1 | grep -vE '^\[strata\]' | tail -6
  g=$(grep " srv-suite-$L " bringup/out/logs/guard/summary.txt | tail -1); echo "guard: $(echo "$g" | cut -c1-230)"
  echo "$g" | grep -q GUARD-STOP && step "GUARD-STOP in $L: lowest MemAvailable $(echo "$g" | grep -oE 'min_MemAvailable=[^ ]+') - not retried (floor 20 GiB)"
  f=$(ls -t bringup/out/logs/server_suite-${L}_*.log | head -1); grep -oE '\[strata\] (sampling defaults|other apps use).*' $f
  srv_gone || step "server still running after $L"
  kc $lv
done
bringup/lib/phase_end.sh r21-effsuite keep 9>&- 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
step "grade (CPU only; C*18t serves 8080)"
for lv in ${LEVELS:-medium high}; do
  [ -d suite/results/c18t-quick-$lv ] || continue
  suite/run.sh regrade c18t-quick-$lv 9>&- 2>&1 | tail -3
  suite/run.sh compare $BASE c18t-quick-$lv 9>&- > $O/compare-$BASE-vs-c18t-quick-$lv.txt 2>&1
done
.venv/bin/python work/r21/effort_suite_table.py $BASE c18t-quick-medium c18t-quick-high > $O/effort-suite.md 2>&1
cat $O/effort-suite.md
step "4 dsh Minimal r5 (bug-fix task)"
if fits 50; then
  flock -u 9
  ARMS=dsh-minimal work/usability/harness_batch5b.sh 9>&- > logs/usability/batch5c.log 2>&1
  tail -4 logs/usability/batch5c.log
  flock 9
  bringup/lib/phase_end.sh r21-batch5c keep 9>&- 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
else
  step "dsh r5 not started: it would run past 23:00"
fi
kc end
step "effort_suite done"
