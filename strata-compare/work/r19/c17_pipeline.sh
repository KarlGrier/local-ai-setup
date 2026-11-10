#!/bin/bash
# c17_pipeline.sh - round 19 B6: C*17 from assets to the hold before the soak (copy of work/r18/c161_pipeline.sh's first
# half), with a phase end (C*16.1, still the promoted build, on 8080) after each measuring step and a kernel check after each:
#   1 build-cstar17.sh   2 gates17.sh   3 the acceptance suite (STRATA_SPEC_PROB mode: upstream's sampler tests)
#   4 the LDR screen, C*16.1 vs C*17 as promoted (A B B A): B6's one regression (1-4K prompts) after STRATA_PREFILL_CPU_SHARE_MAX
# The soak, promotion and the 48-hour monitor follow after reading these.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r19
step() { echo "=== $(date -Is) $*"; }
pe() { bringup/lib/phase_end.sh r19-$1 keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED" ; }
kc() { bringup/lib/kcheck.sh "c17-$1" || { step "KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
kc start
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
step "1 build"; work/r19/build-cstar17.sh > logs/r19/build-cstar17.log 2>&1 || { tail -5 logs/r19/build-cstar17.log; step "BUILD FAILED"; exit 1; }
tail -14 logs/r19/build-cstar17.log; kc build
step "2 gates"; work/r19/gates17.sh c17 configs/Cstar17.json configs/R17RT.json configs/BR17.json > logs/r19/gates17.log 2>&1; cat results/r19/g-gates-c17.txt
pe gates; kc gates
step "3 acceptance suite"; STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
bringup/acceptance.sh acc-c17 configs/Cstar17.json configs/twin17.json > results/r19/accept-c17.txt 2>&1; tail -22 bringup/out/accept/acc-c17/table.md
pe accept; kc accept
step "4 LDR screen, C*16.1 vs C*17 (A B B A)"; STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"; SS=$(date -Iseconds | cut -c1-19)
for arm in "c161-a configs/Cstar161.json" "c17-a configs/Cstar17.json" "c17-b configs/Cstar17.json" "c161-b configs/Cstar161.json"; do
  set -- $arm; bringup/lib/ldrscreen.sh r19-c17-L-$1 $2 > logs/r19/c17-L-$1.log 2>&1
  echo "  $1: $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-120)"; kc ldr-$1
done
SINCE=$SS .venv/bin/python bringup/lib/ldr_table.py C161=r19-c17-L-c161-a,r19-c17-L-c161-b C17=r19-c17-L-c17-a,r19-c17-L-c17-b > results/r19/c17-ldr.md 2>&1; head -22 results/r19/c17-ldr.md
pe ldr; kc end
step "pipeline (first half) done"
