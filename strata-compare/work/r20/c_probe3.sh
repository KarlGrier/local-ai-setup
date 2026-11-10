#!/bin/bash
# c_probe3.sh - 2026-10-14 C: the 4 Q8_0 probe cases the guard cut (c_probe2's Q8_0 session reached the 6 GiB floor at
# 512 s, during case 4): two cases per fresh server so the session's memory does not drift to the floor.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
O=$WS/results/r20/q8loop; PY=$WS/suite/.venv/bin/python; TK=$(jq -r .tokenizer configs/Cstar171.json)
step() { echo "=== $(date -Is) $*"; }
SRV='^[^ ]*/llama-server( |$)|^[^ ]*/strata --serve'
mon_gone() { for i in $(seq 120); do pgrep -f 'monitor.py --pid-pattern' > /dev/null || return 0; sleep 1; done; }
srv_gone() { for i in $(seq 60); do pgrep -f "$SRV" > /dev/null || break; sleep 1; done; mon_gone; ! pgrep -fa "$SRV"; }
kc() { bringup/lib/kcheck.sh "$1" || { step "KERNEL CHECK FAILED ($1) - stopped"; exit 1; }; step "kernel check ok ($1)"; }
exec 9> tmp/suite/heavy.lock; flock 9
kc r20-c3-start; srv_gone || { step "a model server is running - stop"; exit 1; }
for CASES in "c171-iq3s-quick:c07_rpn:0,c171-iq3s-quick:c16_json_parser:0" "r16-q4-quick:c14_semver:0,r16-q4-quick:c16_json_parser:0"; do
  step "Q8_0 probe: $CASES"
  GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4 EVICT_GLOB="$WS/models/r15/Q8_0/*.gguf" \
  bringup/lib/with_server.sh 9>&- q8probe3 configs/r20-q8-probe.json -- \
    "$PY work/r20/loop_probe.py --logpos $O/logpos-q8b.tsv --model q8 --tokenizer $TK --cases $CASES --seq-from=-cont1024-q8" 2>&1 | grep -vE '^\[strata\]'
  tail -1 bringup/out/logs/guard/summary.txt | cut -c1-220
  srv_gone || step "server still running"; kc r20-c3
done
step "c_probe3 done"
