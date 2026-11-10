#!/bin/bash
# promote-c161.sh — round 18 (copy of work/r16/promote-c16.sh; run ONLY after C*16.1 passed its gates and the 2-hour soak): the launchers default to C*16.1
# (work/r18/*.c161; the old ones kept as work/r18/*.before-c161-promotion), then the real rollback test (stop 8080 ->
# C*16 -> stop -> the default C*16.1), leaving C*16.1 on 8080. Rollback any time: STRATA_CONFIG=configs/Cstar16.json.
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
cp -p run-strata.sh work/r18/run-strata.sh.before-c161-promotion
cp -p switch-model.sh work/r18/switch-model.sh.before-c161-promotion
cp work/r18/run-strata.sh.c161 run-strata.sh && chmod 775 run-strata.sh
cp work/r18/switch-model.sh.c161 switch-model.sh && chmod 775 switch-model.sh
bash -n run-strata.sh && bash -n switch-model.sh
grep -n 'CFG=\${STRATA_CONFIG' run-strata.sh switch-model.sh
echo "=== $(date -Is) launchers now default to configs/Cstar161.json"
bringup/lib/rollback_test.sh configs/Cstar16.json
