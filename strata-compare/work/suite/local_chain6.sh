#!/bin/bash
# local_chain6.sh - 2026-10-13 ~12:4x, the user's three follow-ups to the guard continuation, on the heavy lock:
#  A/C  the 7 answers that did not recover at 1024 (min_p 0.05) continued again from the same cut (the original
#       reasoning + the withheld 256th digit), same guard (1024 in total), only min_p 0 (the engine's min_p off: the
#       server sends no min_p key for 0, the engine default is 0.0) -> labels <label>-cont1024-minp0, built on the
#       -cont1024 labels (so c171 full c07 r0, recovered at min_p 0.05, stays in). 8080 down ~10 min.
#  E    grade them (coding)
#  G    Sonnet 5.5's 3 agentic items again at the new per-step limit (65,536; the 32,768-limit answers kept in
#       tmp/suite/sonnet55-agentic-32k/): the label's own command, so only the missing answers are asked
#  F    if most of the 7 recover (>= 4): the coding category once on the served C*17.1 (8080, as is) with min_p 0
#       (quick, coding only) -> label c171-iq3s-quick-minp0
# One server at a time on 8081 under the memory guard (Q4 with its 6 GiB floor); every server launch gets 9>&-; the
# served config is not changed.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
EV=logs/r19/uptime-c171/events.log
O=$WS/results/r19/guardcont; mkdir -p $O
PY=$WS/suite/.venv/bin/python
TK_C=$(jq -r .tokenizer configs/Cstar171.json); TK_Q=$(jq -r .tokenizer configs/r16-q4.json)
CONT="$PY work/suite/guard_continue.py --suffix=-cont1024-minp0 --base-suffix=-cont1024 --sampling '{\"min_p\":0}'"
step() { echo "=== $(date -Is) $*"; }
SRV='^[^ ]*/llama-server( |$)|^[^ ]*/strata --serve'
mon_gone() { for i in $(seq 120); do pgrep -f 'monitor.py --pid-pattern' > /dev/null || return 0; sleep 1; done; pgrep -fa 'monitor.py --pid-pattern'; }
srv_gone() { for i in $(seq 60); do pgrep -f "$SRV" > /dev/null || break; sleep 1; done; mon_gone; ! pgrep -fa "$SRV"; }
exec 9> tmp/suite/heavy.lock
step "min_p 0 continuation: waiting for the heavy lock"
flock 9
step "lock held"
rm -f tmp/suite/LOCAL_CHAIN_DONE
finish() { touch tmp/suite/LOCAL_CHAIN_DONE; step "chain6 done; lock released"; }
bringup/lib/kcheck.sh suite-minp0-start || { step "KERNEL CHECK FAILED - stopped, 8080 untouched"; finish; exit 1; }
T0=$(date +%s)
echo "$(date -Iseconds) PLANNED: 8080 stopped for the min_p 0 continuation (two short guarded servers on 8081, ~10 min); C*17.1 restarted on 8080 after" >> $EV
STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -2
srv_gone || { step "a model server is still running - stop"; ./switch-model.sh strata 9>&-; finish; exit 1; }

step "A. C*17.1 + the prefix hook, 1024 in total, min_p 0: its 5 answers"
bringup/lib/with_server.sh 9>&- guard-c171cont configs/r19-guard-c171cont.json -- \
  "$CONT --tokenizer $TK_C --cases c171-iq3s-full:c02_rle:2,c171-iq3s-full:c16_json_parser:0,c171-iq3s-full:c23_refactor_orderbook:2,c171-iq3s-quick:c07_rpn:0,c171-iq3s-quick:c16_json_parser:0" \
  2>&1 | grep -vE '^\[strata\]'
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-200
srv_gone || step "server still running after A"

step "C. the Q4 config + the prefix hook, 1024 in total, min_p 0: its 2 answers"
( export GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
  export EVICT_GLOB="/home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL/*.gguf"
  bringup/lib/with_server.sh 9>&- guard-q4cont configs/r19-guard-q4cont.json -- \
    "$CONT --tokenizer $TK_Q --cases r16-q4-quick:c14_semver:0,r16-q4-quick:c16_json_parser:0" \
    2>&1 | grep -vE '^\[strata\]' )
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-200
srv_gone || step "server still running after C"

step "C*17.1 back on 8080"
bringup/lib/kcheck.sh suite-minp0-end || step "KERNEL CHECK FAILED after the continuation (C*17.1 still restarted)"
./switch-model.sh strata 9>&- 2>&1 | tail -3
if ! curl -sf -m 10 http://127.0.0.1:8080/health > /dev/null; then step "8080 not healthy - one retry"; sleep 30; mon_gone; ./switch-model.sh strata 9>&- 2>&1 | tail -3; fi
curl -s -m 10 http://127.0.0.1:8080/health; echo
echo "$(date -Iseconds) END of the planned stop: C*17.1 back on 8080 after the min_p 0 continuation" >> $EV

step "E. grade the min_p 0 labels (coding)"
for L in c171-iq3s-full-cont1024-minp0 c171-iq3s-quick-cont1024-minp0 r16-q4-quick-cont1024-minp0; do
  [ -d suite/results/$L ] || { echo "$L: missing"; continue; }
  suite/run.sh regrade $L --no-render 2>&1 | grep -E "^\| Coding|privacy" | cut -c1-200
done
REC=$($PY - <<'EOF'
import json, glob
n = tot = 0
for f in glob.glob("/home/USER/ai-speed-testing/strata-compare/suite/results/*-cont1024-minp0/answers/coding/*.json"):
    c = json.load(open(f)).get("continuation") or {}
    if (c.get("sampling") or {}).get("min_p") == 0:
        tot += 1
        n += (c.get("digit_run_total") or 0) < 1023
print(n, tot)
EOF
)
step "recovered at min_p 0: $REC (recovered / continued)"

step "G. Sonnet 5.5's agentic items at the 65,536 per-step limit"
mkdir -p tmp/suite/sonnet55-agentic-32k
if ls suite/results/sonnet-5-5-quick/answers/agentic/*.json > /dev/null 2>&1; then
  mv suite/results/sonnet-5-5-quick/answers/agentic/*.json tmp/suite/sonnet55-agentic-32k/
fi
suite/run.sh --label sonnet-5-5-quick --endpoint claude:claude-sonnet-5-5 --mode quick --estimate-from c171-iq3s-quick --budget 25 \
  2>&1 | grep -vE 'batch .*in_progress' | tail -25 | cut -c1-220

set -- $REC
if [ "${1:-0}" -ge 4 ]; then
  step "F. most recovered: coding once on the served C*17.1 (8080) with min_p 0"
  suite/run.sh --label c171-iq3s-quick-minp0 --endpoint http://127.0.0.1:8080 --mode quick --only coding --sampling '{"min_p": 0}' \
    2>&1 | grep -E 'sampling|=== |graded|scores|privacy|\| Coding' | cut -c1-220
  grep -E '^\| Coding' suite/results/c171-iq3s-quick-minp0/scores.md | cut -c1-200
else
  step "F. skipped: fewer than 4 of 7 recovered at min_p 0"
fi
echo "elapsed $(( ($(date +%s) - T0) / 60 )) min"
finish
