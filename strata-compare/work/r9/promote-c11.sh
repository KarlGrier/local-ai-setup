#!/bin/bash
# promote-c11.sh — round 9 Phase C (run ONLY after C*11's 2-hour soak and every gate passed): the launchers default to
# C*11 (work/r9/*.c11; old copies kept as work/r9/*.before-c11-promotion), then the real rollback test (stop 8080 ->
# C*10 -> stop -> the default C*11), leaving C*11 on 8080.
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
cp -p run-strata.sh work/r9/run-strata.sh.before-c11-promotion
cp -p switch-model.sh work/r9/switch-model.sh.before-c11-promotion
cp work/r9/run-strata.sh.c11 run-strata.sh && chmod 775 run-strata.sh
cp work/r9/switch-model.sh.c11 switch-model.sh && chmod 775 switch-model.sh
bash -n run-strata.sh && bash -n switch-model.sh
grep -n 'CFG=\${STRATA_CONFIG' run-strata.sh switch-model.sh
echo "=== $(date -Is) launchers now default to configs/Cstar11.json"
work/r9/rollback_test.sh configs/Cstar10.json
