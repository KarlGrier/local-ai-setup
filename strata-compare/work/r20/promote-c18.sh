#!/bin/bash
# promote-c18.sh - round 20 (copy of work/r19/promote-c171.sh; run ONLY after C*18 passed its gates, the acceptance suite and
# the 2-hour soak): the launchers default to C*18 (work/r20/*.c18; the old ones kept as work/r20/*.before-c18-promotion),
# then the real rollback test (stop 8080 -> C*17.1 -> stop -> the default C*18), leaving C*18 on 8080.
# Rollback any time: STRATA_CONFIG=configs/Cstar171.json ./switch-model.sh strata
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
cp -p run-strata.sh work/r20/run-strata.sh.before-c18-promotion
cp -p switch-model.sh work/r20/switch-model.sh.before-c18-promotion
cp work/r20/run-strata.sh.c18 run-strata.sh && chmod 775 run-strata.sh
cp work/r20/switch-model.sh.c18 switch-model.sh && chmod 775 switch-model.sh
bash -n run-strata.sh && bash -n switch-model.sh
grep -n 'CFG=\${STRATA_CONFIG' run-strata.sh switch-model.sh
echo "=== $(date -Is) launchers now default to configs/Cstar18.json"
bringup/lib/rollback_test.sh configs/Cstar171.json
