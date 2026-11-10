#!/bin/bash
# promote-c17.sh - round 19 (copy of work/r18/promote-c161.sh; run ONLY after C*17 passed its gates, the acceptance suite and
# the 2-hour soak): the launchers default to C*17 (work/r19/*.c17; the old ones kept as work/r19/*.before-c17-promotion),
# then the real rollback test (stop 8080 -> C*16.1 -> stop -> the default C*17), leaving C*17 on 8080.
# Rollback any time: STRATA_CONFIG=configs/Cstar161.json ./switch-model.sh strata
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
cp -p run-strata.sh work/r19/run-strata.sh.before-c17-promotion
cp -p switch-model.sh work/r19/switch-model.sh.before-c17-promotion
cp work/r19/run-strata.sh.c17 run-strata.sh && chmod 775 run-strata.sh
cp work/r19/switch-model.sh.c17 switch-model.sh && chmod 775 switch-model.sh
bash -n run-strata.sh && bash -n switch-model.sh
grep -n 'CFG=\${STRATA_CONFIG' run-strata.sh switch-model.sh
echo "=== $(date -Is) launchers now default to configs/Cstar17.json"
bringup/lib/rollback_test.sh configs/Cstar161.json
