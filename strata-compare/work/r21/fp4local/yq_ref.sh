#!/bin/bash
# yq_ref.sh - r21 item 7: the quant yardstick's Q8_0 reference run (tools/quant_quality.py run, configs/r21-q8ref.json),
# made before the Q8_0 files are deleted.  8080 is stopped for it (RAM); afterwards phase_end.sh starts the default
# (C*18t) again with the standing guard.
# Guard: the standing 20 GiB MemAvailable floor (this is not an NVFP4 run), 5080 VRAM floor 300 MiB.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT
O=results/r21/yq; mkdir -p $O logs/r21
step() { echo "=== $(date -Is) $*"; }
kc() { bringup/lib/kcheck.sh "yq-$1" || { step "KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
exec 9> tmp/suite/heavy.lock; flock 9
kc start
step "stop 8080"
STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
step "Q8_0 reference: MemAvailable $(awk '/MemAvailable/{printf "%.1f", $2/1048576}' /proc/meminfo) GiB"
t0=$(date +%s)
.venv/bin/python bringup/lib/guard.py yq-q8ref -- .venv/bin/python strata-cstar18/tools/quant_quality.py run \
  --config configs/r21-q8ref.json --out $O/q8ref.tsv --min-free-gb 30 9>&- 2>&1 | grep -vE '^\[strata\]' | tail -12
step "done in $(( $(date +%s) - t0 )) s"
grep " yq-q8ref " bringup/out/logs/guard/summary.txt | tail -1 | cut -c1-260
kc q8ref
ls -la $O/
bringup/lib/phase_end.sh r21-yq-ref keep 9>&- 2>&1 | grep -E "phase end|answered|8080:|FAILED|GUARD"
