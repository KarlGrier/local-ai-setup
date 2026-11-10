#!/bin/bash
# c_probe2.sh - 2026-10-14 C, second try at the teacher-forced probes (the first logged nothing: a prompt longer than
# --short-read goes through the batched path, which does not write STRATA_LOGPOS).  Now: prime + tail, --short-read 2048.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
O=$WS/results/r20/q8loop; mkdir -p $O
PY=$WS/suite/.venv/bin/python
TK=$(jq -r .tokenizer configs/Cstar171.json)
CASES="c171-iq3s-full:c02_rle:2,c171-iq3s-full:c16_json_parser:0,c171-iq3s-full:c23_refactor_orderbook:2,c171-iq3s-quick:c07_rpn:0,c171-iq3s-quick:c16_json_parser:0,r16-q4-quick:c14_semver:0,r16-q4-quick:c16_json_parser:0"
step() { echo "=== $(date -Is) $*"; }
SRV='^[^ ]*/llama-server( |$)|^[^ ]*/strata --serve'
mon_gone() { for i in $(seq 120); do pgrep -f 'monitor.py --pid-pattern' > /dev/null || return 0; sleep 1; done; }
srv_gone() { for i in $(seq 60); do pgrep -f "$SRV" > /dev/null || break; sleep 1; done; mon_gone; ! pgrep -fa "$SRV"; }
kc() { bringup/lib/kcheck.sh "$1" || { step "KERNEL CHECK FAILED ($1) - stopped"; exit 1; }; step "kernel check ok ($1)"; }
exec 9> tmp/suite/heavy.lock; flock 9
kc r20-c2-start; srv_gone || { step "a model server is running - stop"; exit 1; }
step "IQ3_S probe"
rm -f $O/logpos-iq3.tsv
bringup/lib/with_server.sh 9>&- iq3probe configs/r20-iq3-probe.json -- \
  "$PY work/r20/loop_probe.py --logpos $O/logpos-iq3.tsv --model iq3 --tokenizer $TK --cases $CASES --seq-from=-cont1024-q8" 2>&1 | grep -vE '^\[strata\]'
srv_gone || step "server still running"; kc r20-c2-iq3
step "Q8_0 probe"
rm -f $O/logpos-q8.tsv
GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4 EVICT_GLOB="$WS/models/r15/Q8_0/*.gguf" \
bringup/lib/with_server.sh 9>&- q8probe configs/r20-q8-probe.json -- \
  "$PY work/r20/loop_probe.py --logpos $O/logpos-q8.tsv --model q8 --tokenizer $TK --cases $CASES --seq-from=-cont1024-q8" 2>&1 | grep -vE '^\[strata\]'
srv_gone || step "server still running"; kc r20-c2-q8
step "probes done"
