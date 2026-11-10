#!/bin/bash
# effort_suite2.sh WAITPID - 2026-10-17, your change (replaces the "high" run, which Strata renders as xhigh): after the
# IQ3_S medium run (c18t-quick-medium, started 10:13 by effort_suite.sh; WAITPID = its with_server.sh):
#   1  the GPTQ NVFP4 pack at effort medium (c18-nvfp4-quick-medium; configs/r20-nv18.json as Friday's c18-nvfp4-quick,
#      memory floor 6 GiB); 8080 down while it runs, C*18t back after
#   2  both medium runs graded; every scored category where they differ by more than one item (sums of item scores on
#      the shared items differ by > 1.0, work/r21/rerun_pick.py) run once more on both (labels *-medium-rr, --only)
#   3  C*18t at effort low (c18t-quick-low), only if it can end before 23:00 with dsh's ~50 min still after it
#   4  dsh Minimal r5 on the bug-fix task (harness_batch5b.sh, ARMS=dsh-minimal)
# Then results/r21/effort-suite.md (work/r21/effort_suite_report.py): per category score, wall time, median reasoning
# tokens, cut-offs (token limit / loop stop), paired against Friday's xhigh runs (IQ3_S 90.7, GPTQ 86.8).
# Every suite run is cut at 23:00 (your rule; a rerun resumes the label). One guarded server on 8081 at a time.
set -u
WAITPID=${1:?WAITPID}
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT EVICT_GLOB
CI=configs/Cstar18t.json; CN=configs/r20-nv18.json; O=results/r21; P=.venv/bin/python
G=$WS/models/Maximilian228--Qwen3.8-Flash-Next-NVFP4-GPTQ-Strata
EI="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"; EN="$G/*.gguf $G/pack/experts.bin"
END=$(date -d '23:00' +%s)
step() { echo "=== $(date -Is) $*"; }
kc() { bringup/lib/kcheck.sh "effsuite2-$1" || { step "KERNEL CHECK FAILED after $1 - stopped"; back; exit 1; }; }
SRV='^[^ ]*/llama-server( |$)|^[^ ]*/strata --serve'
srv_gone() { for i in $(seq 60); do pgrep -f "$SRV" > /dev/null || break; sleep 1; done; ! pgrep -fa "$SRV"; }
fits() { [ $(( $(date +%s) + $1 * 60 )) -lt $END ]; }   # minutes
back() { bringup/lib/phase_end.sh r21-effsuite2 keep 9>&- 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"; }
gline() { grep " srv-suite-$1 " bringup/out/logs/guard/summary.txt | tail -1 | cut -c1-230; }
suiterun() {   # LABEL CONFIG FLOOR_GIB EVICT EFFORT [suite args]; returns 3 on a GUARD-STOP
  local L=$1 C=$2 GM=$3 EV=$4 LV=$5; shift 5
  step "$L on $C (8081, guarded, floor $GM GiB), effort $LV $*"
  STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -1
  srv_gone || { step "a model server is still running - stop"; exit 1; }
  EVICT_GLOB="$EV" GUARD_MEM_GIB=$GM bringup/lib/with_server.sh 9>&- suite-$L $C -- \
    "timeout $(( END - $(date +%s) )) suite/run.sh --label $L --endpoint http://127.0.0.1:8081 --mode quick --no-grade $* --extra-body '{\"reasoning_effort\": \"$LV\"}'; echo suite exit \$?" \
    2>&1 | grep -vE '^\[strata\]' | tail -6
  local g; g=$(gline $L); echo "guard: $g"
  grep -oE '\[strata\] (sampling defaults|other apps use).*' $(ls -t bringup/out/logs/server_suite-${L}_*.log | head -1)
  srv_gone || step "server still running after $L"
  kc $L
  if echo "$g" | grep -q GUARD-STOP; then
    step "GUARD-STOP in $L: lowest MemAvailable $(echo "$g" | grep -oE 'min_MemAvailable=[^ ]+') - not retried"; return 3
  fi
}
grade() { for L in "$@"; do [ -d suite/results/$L ] && suite/run.sh regrade $L 9>&- 2>&1 | tail -2; done; }

step "waiting for the IQ3_S medium run (with_server pid $WAITPID)"
while kill -0 $WAITPID 2>/dev/null; do sleep 30; done
exec 9> tmp/suite/heavy.lock; flock 9
step "IQ3_S medium ended; guard: $(gline c18t-quick-medium)"
srv_gone || { step "a model server is still running - stop"; exit 1; }
kc medium-iq3s

# 1 NVFP4 medium
NV_OK=1
suiterun c18-nvfp4-quick-medium $CN 6 "$EN" medium || NV_OK=0
back

# 2 grade both medium runs; rerun the categories that differ by more than one item, on both
grade c18t-quick-medium c18-nvfp4-quick-medium
suite/run.sh compare c18-iq3s-quick c18t-quick-medium 9>&- > /dev/null 2>&1
suite/run.sh compare c18-nvfp4-quick c18-nvfp4-quick-medium 9>&- > /dev/null 2>&1
suite/run.sh compare c18t-quick-medium c18-nvfp4-quick-medium 9>&- > /dev/null 2>&1
RR=""
if [ $NV_OK = 1 ] && [ -f suite/results/c18-nvfp4-quick-medium/grades.json ]; then
  RR=$($P work/r21/rerun_pick.py c18t-quick-medium c18-nvfp4-quick-medium 2> $O/rerun-pick.txt); cat $O/rerun-pick.txt
fi
if [ -n "$RR" ]; then
  step "2 category reruns at medium on both: $RR"
  suiterun c18t-quick-medium-rr $CI 20 "$EI" medium --only $RR
  suiterun c18-nvfp4-quick-medium-rr $CN 6 "$EN" medium --only $RR
  back
  grade c18t-quick-medium-rr c18-nvfp4-quick-medium-rr
else
  step "2 no category differs by more than one item (or the NVFP4 run is incomplete) - no reruns"
fi

# 3 IQ3_S low, if it ends before 23:00 with dsh still after it
MED_MIN=$($P -c "import json; print(int(json.load(open('suite/results/c18t-quick-medium/scores.json'))['totals']['wall_s'] / 60) + 10)")
if fits $(( MED_MIN + 60 )); then
  suiterun c18t-quick-low $CI 20 "$EI" low
  back
  grade c18t-quick-low
  suite/run.sh compare c18-iq3s-quick c18t-quick-low 9>&- > /dev/null 2>&1
else
  step "3 IQ3_S low not started: ~$MED_MIN min + dsh's ~60 min would run past 23:00"
fi

$P work/r21/effort_suite_report.py > $O/effort-suite.md 2>&1; cat $O/effort-suite.md

# 4 dsh Minimal r5 (it takes the heavy lock itself and leaves C*18t on 8080)
if fits 50; then
  step "4 dsh Minimal r5 (bug-fix task)"
  flock -u 9
  ARMS=dsh-minimal work/usability/harness_batch5b.sh 9>&- > logs/usability/batch5c.log 2>&1
  tail -4 logs/usability/batch5c.log
  flock 9
  back
else
  step "4 dsh r5 not started: it would run past 23:00"
fi
kc end
step "effort_suite2 done"
