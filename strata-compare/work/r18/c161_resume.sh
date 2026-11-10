#!/bin/bash
# c161_resume.sh - round 18: the pipeline after my twin-config slip (the twin configs pointed at C*16.1's own server, which
# has no force=N hooks, so the round trips returned nothing): the round trips again on the fixed R161RT.json, then the
# acceptance suite (fixed twin161.json), a phase end, and the rest of c161_pipeline.sh from the soak hold on.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r18 PROMPT_DIR=$WS/bringup/out/r16z/prompts EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
P=.venv/bin/python; L=c161
step() { echo "=== $(date -Is) $*"; }
pe() { bringup/lib/phase_end.sh r18-$1 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED" ; }
step "2b round trips (fixed twin)"
for m in "direct small $L-direct1" "direct small $L-direct2" "park small $L-park" "editref small $L-editref"; do
  bringup/lib/with_server.sh RT-$L configs/R161RT.json -- "$P bringup/lib/roundtrip.py $m" > /dev/null 2>&1
done
$P bringup/lib/rt_compare.py $L > results/r18/g-roundtrip-$L.md 2>&1; tail -8 results/r18/g-roundtrip-$L.md | tee -a results/r18/g-gates-$L.txt
step "3 acceptance suite"; bringup/acceptance.sh acc-c161 configs/Cstar161.json configs/twin161.json > results/r18/accept-c161.txt 2>&1; tail -22 bringup/out/accept/acc-c161/table.md
pe accept
work/r18/hold.sh c161-soak
step "4 soak (2 h, C*16.1 on 8080)"; STRATA_CONFIG=configs/Cstar161.json bringup/lib/soak13.sh 120 > logs/r18/soak161.log 2>&1; tail -30 logs/r18/soak161.log
bringup/lib/soakdec.sh SDEC161 configs/Cstar161.json > logs/r18/soakdec161.log 2>&1; tail -3 logs/r18/soakdec161.log
step "5 tags"; git ls-remote --tags https://github.com/Niko1221/Strata.git 2>/dev/null | grep -o 'refs/tags/v[0-9.]*$' | sort -V | tail -3
work/r18/hold.sh c161-promote
step "6 promote"; work/r18/promote-c161.sh > logs/r18/promote-c161.log 2>&1; tail -20 logs/r18/promote-c161.log
step "pipeline done"
