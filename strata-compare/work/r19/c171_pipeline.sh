#!/bin/bash
# c171_pipeline.sh [CAND] - round 19 Part D: C*17.1 from assets to the hold before the soak (from c17x_pipeline.sh /
# c17_pipeline.sh). CAND = the candidate config build-cstar171.sh starts from (default configs/r19e-cand.json; the
# overlap config if D2 keeps it). Your rule: promote if it passes every gate and is within 1 % of C*17 or faster.
#   1 build-cstar171.sh (engine-cstar171 / engine-twin171, configs Cstar171*, twin171, R171RT, BR171)
#   2 exact7 twice: vs C*17's hashes (c17x-e7: runbook r19e's all-on run matched them 7/7), then vs itself
#   3 the gates (gates17.sh, REF = step 2's first run)
#   4 the acceptance suite (acc-c171: our exact-sampling chi-square on this tree, the near-tie frequencies, TF, needles, ...)
#   5 speed: C*17 (A, as served) vs C*17.1, A B B A, a fresh guarded server per screen: LDR, decode, full screens
# A phase end (C*17, still promoted) after each step, a kernel check after each. The soak, rollback test and promotion
# follow after reading these.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r19 CAND=${1:-configs/r19e-cand.json}
P=.venv/bin/python; R=results/r19
step() { echo "=== $(date -Is) $*"; }
pe() { bringup/lib/phase_end.sh r19-$1 keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED" ; }
kc() { bringup/lib/kcheck.sh "c171-$1" || { step "KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
kc start
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
step "1 build (CAND $CAND)"; work/r19/build-cstar171.sh > logs/r19/build-cstar171.log 2>&1 || { tail -5 logs/r19/build-cstar171.log; step "BUILD FAILED"; exit 1; }
head -4 logs/r19/build-cstar171.log; grep -E '^Cstar171' logs/r19/build-cstar171.log | cut -c1-260; kc build
step "2 exact7 twice"; export PROMPT_DIR=$WS/bringup/out/r19/prompts   # as C*17's c17x-e7
REF=c17x-e7 bringup/lib/exact7.sh c171-e7 configs/Cstar171.json 2>&1 | tail -8 | tee $R/c171-e7.txt; kc e7
REF=c171-e7 bringup/lib/exact7.sh c171-e7b configs/Cstar171.json 2>&1 | tail -1 | tee -a $R/c171-e7.txt; kc e7b
pe e7
step "3 gates"; STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
work/r19/gates17.sh c171 configs/Cstar171.json configs/R171RT.json configs/BR171.json c171-e7 > logs/r19/gates171.log 2>&1
grep -v '^PASS stream' $R/g-gates-c171.txt | cut -c1-200
pe gates; kc gates
step "4 acceptance suite"; STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
bringup/acceptance.sh acc-c171 configs/Cstar171.json configs/twin171.json > $R/accept-c171.txt 2>&1
cp bringup/out/accept/acc-c171/table.md $R/accept-c171-table.md 2>/dev/null; tail -22 bringup/out/accept/acc-c171/table.md
pe accept; kc accept
step "5 speed vs C*17 (A B B A)"
A_CFG=configs/Cstar17.json A_TAG=c17 work/r19/d7_speed.sh configs/Cstar171.json c171 > logs/r19/d7-speed.log 2>&1; grep -E 'results/|done' logs/r19/d7-speed.log | cut -c1-300
kc speed
step "C*17.1 pipeline (first half) done"
