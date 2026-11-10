#!/bin/bash
# c_q8loop.sh - 2026-10-14 C (the user's loop test, quant vs engine): the 7 coding answers that kept looping at 1024
# (IQ3_S C*17.1 and Q4) continued from the same cut (the original reasoning + the withheld 256th digit) on the Unsloth
# Q8_0 file in C*17.1's engine (configs/r20-q8-cont.json: Round 15's budget placement B at 71 GiB, unbuffered load,
# tail skip 0, repeat_stop_tokens 768 = 1024 in total, the original sampling incl. min_p 0.05) -> labels
# <label>-cont1024-q8 built on the -cont1024 labels.  Then teacher-forced probes (STRATA_LOGPOS, top 5): p(top) inside
# each digit run on Q8_0 and on IQ3_S (C*17.1's own config + the hook) over the same token sequences.
# One server at a time on 8081 under the memory guard (6 GiB floor, swap +4 GiB); kernel check after each server.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
O=$WS/results/r20/q8loop; mkdir -p $O
PY=$WS/suite/.venv/bin/python
TK_C=$(jq -r .tokenizer configs/Cstar171.json); TK_Q=$(jq -r .tokenizer configs/r16-q4.json)
C171="c171-iq3s-full:c02_rle:2,c171-iq3s-full:c16_json_parser:0,c171-iq3s-full:c23_refactor_orderbook:2,c171-iq3s-quick:c07_rpn:0,c171-iq3s-quick:c16_json_parser:0"
Q4="r16-q4-quick:c14_semver:0,r16-q4-quick:c16_json_parser:0"
step() { echo "=== $(date -Is) $*"; }
SRV='^[^ ]*/llama-server( |$)|^[^ ]*/strata --serve'
mon_gone() { for i in $(seq 120); do pgrep -f 'monitor.py --pid-pattern' > /dev/null || return 0; sleep 1; done; pgrep -fa 'monitor.py --pid-pattern'; }
srv_gone() { for i in $(seq 60); do pgrep -f "$SRV" > /dev/null || break; sleep 1; done; mon_gone; ! pgrep -fa "$SRV"; }
kc() { bringup/lib/kcheck.sh "$1" || { step "KERNEL CHECK FAILED ($1) - stopped"; exit 1; }; step "kernel check ok ($1)"; }
exec 9> tmp/suite/heavy.lock
flock 9
step "lock held"
kc r20-c-start
srv_gone || { step "a model server is running - stop"; exit 1; }
export GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
Q8GLOB="$WS/models/r15/Q8_0/*.gguf"

step "1. Q8_0 continuation, 7 answers"
CONT="$PY work/suite/guard_continue.py --suffix=-cont1024-q8 --base-suffix=-cont1024"
EVICT_GLOB="$Q8GLOB" bringup/lib/with_server.sh 9>&- q8cont configs/r20-q8-cont.json -- \
  "$CONT --tokenizer $TK_C --cases $C171 && $CONT --tokenizer $TK_Q --cases $Q4" 2>&1 | grep -vE '^\[strata\]'
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-200
srv_gone || step "server still running after 1"
kc r20-c-q8cont
grep -E "TAIL_SKIP|tail skip|resident budget|budget" logs/r20/engine-q8cont.log | head -5 | cut -c1-200

step "2. teacher-forced probe on Q8_0 (its own continuations, then IQ3_S's)"
rm -f $O/logpos-q8.tsv
PROBE="$PY work/r20/loop_probe.py --logpos $O/logpos-q8.tsv --model q8"
EVICT_GLOB="$Q8GLOB" bringup/lib/with_server.sh 9>&- q8probe configs/r20-q8-probe.json -- \
  "$PROBE --tokenizer $TK_C --cases $C171 --seq-from=-cont1024-q8; $PROBE --tokenizer $TK_Q --cases $Q4 --seq-from=-cont1024-q8; \
   $PROBE --tokenizer $TK_C --cases $C171 --seq-from=-cont1024; $PROBE --tokenizer $TK_Q --cases $Q4 --seq-from=-cont1024" 2>&1 | grep -vE '^\[strata\]'
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-200
srv_gone || step "server still running after 2"
kc r20-c-q8probe

step "3. the same probe on IQ3_S (C*17.1 + the hook)"
rm -f $O/logpos-iq3.tsv
PROBE="$PY work/r20/loop_probe.py --logpos $O/logpos-iq3.tsv --model iq3"
( unset GUARD_MEM_GIB GUARD_SWAP_GROW_GIB
  bringup/lib/with_server.sh 9>&- iq3probe configs/r20-iq3-probe.json -- \
  "$PROBE --tokenizer $TK_C --cases $C171,$Q4 --seq-from=-cont1024-q8; $PROBE --tokenizer $TK_C --cases $C171,$Q4 --seq-from=-cont1024" 2>&1 | grep -vE '^\[strata\]' )
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-200
srv_gone || step "server still running after 3"
kc r20-c-iq3probe

step "4. grade the Q8_0 labels (coding)"
for L in c171-iq3s-full-cont1024-q8 c171-iq3s-quick-cont1024-q8 r16-q4-quick-cont1024-q8; do
  [ -d suite/results/$L ] || { echo "$L: missing"; continue; }
  suite/run.sh regrade $L --no-render 2>&1 | grep -E "^\| Coding|privacy" | cut -c1-200
done
step "C done"
