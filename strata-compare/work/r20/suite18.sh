#!/bin/bash
# suite18.sh - Round 20 item 3: the suite's quick runs on C*18 IQ3_S (configs/Cstar18.json) and C*18 NVFP4 (the config the
# NVFP4 trial chose, results/r20/nvfp4/chosen-config.txt), labels c18-iq3s-quick / c18-nvfp4-quick, research from the
# frozen web cache (r04 scorable on v0.1.44.1: #2026 + its follow-up). One server at a time on 8081 under the guard (the
# standing 20 GiB floor: a GUARD-STOP is reported with the lowest value, not retried lower); answers collected with
# --no-grade, graded after the servers are gone (CPU only); the promoted build back on 8080 in between and at the end.
# Re-running resumes each label where it stopped. LABELS="iq3s nvfp4" limits it.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r20
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
step() { echo "=== $(date -Is) $*"; }
G0=GPU-UUID-RTX5080
disp() { echo "$(date -Is) $1 display_active=$(nvidia-smi --id=$G0 --query-gpu=display_active --format=csv,noheader) 5080_used_MiB=$(nvidia-smi --id=$G0 --query-gpu=memory.used --format=csv,noheader,nounits) servers=$(pgrep -fc '/strata --serve')" | tee -a logs/r20/display.log; }
SRV='^[^ ]*/llama-server( |$)|^[^ ]*/strata --serve'
mon_gone() { for i in $(seq 120); do pgrep -f 'monitor.py --pid-pattern' > /dev/null || return 0; sleep 1; done; }
srv_gone() { for i in $(seq 60); do pgrep -f "$SRV" > /dev/null || break; sleep 1; done; mon_gone; ! pgrep -fa "$SRV"; }
kc() { bringup/lib/kcheck.sh "suite18-$1" || { step "KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; disp "suite18-$1"; }
exec 9> tmp/suite/heavy.lock; flock 9
kc start
M=$WS/models/Maximilian228--Qwen3.8-Flash-Next-NVFP4-GPTQ-Strata
NVCFG=$(cat results/r20/nvfp4/chosen-config.txt 2>/dev/null || echo configs/r20-nv18.json)
for which in ${LABELS:-iq3s nvfp4}; do
  case $which in
    iq3s)  L=c18-iq3s-quick;  CFG=configs/Cstar18.json; export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf" ;;
    nvfp4) L=c18-nvfp4-quick; CFG=$NVCFG;               export EVICT_GLOB="$M/*.gguf $M/pack/experts.bin" ;;
  esac
  step "$L on $CFG (8081, guarded)"
  STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -1
  srv_gone || { step "a model server is still running - stop"; exit 1; }
  bringup/lib/with_server.sh 9>&- suite-$L $CFG -- \
    "suite/run.sh --label $L --endpoint http://127.0.0.1:8081 --mode quick --no-grade; echo suite exit \$?" 2>&1 | grep -vE '^\[strata\]' | tail -8
  g=$(grep " srv-suite-$L " bringup/out/logs/guard/summary.txt | tail -1); echo "guard: $(echo "$g" | cut -c1-230)"
  echo "$g" | grep -q GUARD-STOP && step "GUARD-STOP in $L: lowest MemAvailable $(echo "$g" | grep -oE 'min_MemAvailable=[^ ]+') - not retried (floor 20 GiB)"
  srv_gone || step "server still running after $L"
  kc $which
  bringup/lib/phase_end.sh r20-suite18-$which keep 9>&- 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
done
step "grade (CPU only; the promoted build serves 8080)"
for which in ${LABELS:-iq3s nvfp4}; do L=c18-$which-quick; suite/run.sh regrade $L 9>&- 2>&1 | tail -30; done
kc end
step "suite18 done"
