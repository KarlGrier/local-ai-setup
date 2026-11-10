#!/bin/bash
# promote-c16.sh — round 16 (run ONLY after C*16 passed its gates and the 2-hour soak): the launchers default to C*16
# (work/r16/*.c16; the old ones kept as work/r16/*.before-c16-promotion), then the real rollback test (stop 8080 ->
# C*15 -> stop -> the default C*16), leaving C*16 on 8080. Rollback any time: STRATA_CONFIG=configs/Cstar15.json.
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
cp -p run-strata.sh work/r16/run-strata.sh.before-c16-promotion
cp -p switch-model.sh work/r16/switch-model.sh.before-c16-promotion
cp work/r16/run-strata.sh.c16 run-strata.sh && chmod 775 run-strata.sh
cp work/r16/switch-model.sh.c16 switch-model.sh && chmod 775 switch-model.sh
bash -n run-strata.sh && bash -n switch-model.sh
grep -n 'CFG=\${STRATA_CONFIG' run-strata.sh switch-model.sh
echo "=== $(date -Is) launchers now default to configs/Cstar16.json"
bringup/lib/rollback_test.sh configs/Cstar15.json
