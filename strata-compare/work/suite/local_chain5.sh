#!/bin/bash
# local_chain5.sh - 2026-10-13, the user's guard continuation (queued behind the Sonnet 5.5 quick run on the heavy
# lock): the 8 coding answers Strata's repeat guard ended at a 256-digit run, continued from their exact cut (not
# re-sampled) with the guard at 1024 in total (work/suite/guard_continue.py, measurement hook strata_prefix_ids), under
# labels <label>-cont1024; a live check that a guard of 1024 still stops a forced single-token loop (and lets a real
# 600-digit answer through), and the same check on the served 8080 (default 256) after; then grading. One server at a
# time on 8081 under the memory guard (Q4 with its 6 GiB floor); every server launch gets 9>&-; the served config is
# not changed.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
EV=logs/r19/uptime-c171/events.log
O=$WS/results/r19/guardcont; mkdir -p $O
PY=$WS/suite/.venv/bin/python
TK_C=$(jq -r .tokenizer configs/Cstar171.json); TK_Q=$(jq -r .tokenizer configs/r16-q4.json)
step() { echo "=== $(date -Is) $*"; }
SRV='^[^ ]*/llama-server( |$)|^[^ ]*/strata --serve'
mon_gone() { for i in $(seq 120); do pgrep -f 'monitor.py --pid-pattern' > /dev/null || return 0; sleep 1; done; pgrep -fa 'monitor.py --pid-pattern'; }
srv_gone() { for i in $(seq 60); do pgrep -f "$SRV" > /dev/null || break; sleep 1; done; mon_gone; ! pgrep -fa "$SRV"; }
exec 9> tmp/suite/heavy.lock
step "guard continuation: waiting for the heavy lock (the Sonnet 5.5 run)"
flock 9
step "lock held"
rm -f tmp/suite/LOCAL_CHAIN_DONE
finish() { touch tmp/suite/LOCAL_CHAIN_DONE; step "guard continuation done; lock released"; }
bringup/lib/kcheck.sh suite-guard-start || { step "KERNEL CHECK FAILED - stopped, 8080 untouched"; finish; exit 1; }
echo "$(date -Iseconds) PLANNED: 8080 stopped for the guard continuation (three short guarded servers on 8081, ~30-60 min); C*17.1 restarted on 8080 after" >> $EV
STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -2
srv_gone || { step "a model server is still running - stop"; ./switch-model.sh strata 9>&-; finish; exit 1; }

step "A. C*17.1 + the prefix hook, repeat_stop_tokens 768 (1024 in total): continue its 6 guard-stopped coding answers"
bringup/lib/with_server.sh 9>&- guard-c171cont configs/r19-guard-c171cont.json -- \
  "$PY work/suite/guard_continue.py --tokenizer $TK_C --cases c171-iq3s-full:c02_rle:2,c171-iq3s-full:c07_rpn:0,c171-iq3s-full:c16_json_parser:0,c171-iq3s-full:c23_refactor_orderbook:2,c171-iq3s-quick:c07_rpn:0,c171-iq3s-quick:c16_json_parser:0" \
  2>&1 | grep -vE '^\[strata\]'
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-200
srv_gone || { step "server still running after A - stop"; finish; exit 1; }

step "B. C*17.1 (served server code) with repeat_stop_tokens 1024: forced single-token loops + a real 600-digit answer"
bringup/lib/with_server.sh 9>&- guard-c171check configs/r19-guard-c171check.json -- \
  "$PY work/suite/guard_loopcheck.py --tokenizer $TK_C --expect 1024 --out $O/loopcheck-1024.json" 2>&1 | grep -vE '^\[strata\]'
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-200
srv_gone || { step "server still running after B - stop"; finish; exit 1; }
bringup/lib/kcheck.sh suite-guard-mid || { step "KERNEL CHECK FAILED - stopped"; finish; exit 1; }

step "C. the Q4 config + the prefix hook, repeat_stop_tokens 768 (1024 in total): continue its 2 guard-stopped coding answers"
( export GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
  export EVICT_GLOB="/home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL/*.gguf"
  bringup/lib/with_server.sh 9>&- guard-q4cont configs/r19-guard-q4cont.json -- \
    "$PY work/suite/guard_continue.py --tokenizer $TK_Q --cases r16-q4-quick:c14_semver:0,r16-q4-quick:c16_json_parser:0" \
    2>&1 | grep -vE '^\[strata\]' )
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-200
srv_gone || step "server still running after C"

step "C*17.1 back on 8080"
bringup/lib/kcheck.sh suite-guard-end || step "KERNEL CHECK FAILED after the continuation (C*17.1 still restarted)"
./switch-model.sh strata 9>&- 2>&1 | tail -3
if ! curl -sf -m 10 http://127.0.0.1:8080/health > /dev/null; then step "8080 not healthy - one retry"; sleep 30; mon_gone; ./switch-model.sh strata 9>&- 2>&1 | tail -3; fi
curl -s -m 10 http://127.0.0.1:8080/health; echo
echo "$(date -Iseconds) END of the planned stop: C*17.1 back on 8080 after the guard continuation" >> $EV

step "D. the same check on the served 8080 (its config as is: repeat_stop_tokens default 256)"
$PY work/suite/guard_loopcheck.py --endpoint http://127.0.0.1:8080 --tokenizer $TK_C --expect 256 --out $O/loopcheck-256-served.json

step "E. grade the continued labels (coding)"
for L in c171-iq3s-full-cont1024 c171-iq3s-quick-cont1024 r16-q4-quick-cont1024; do
  [ -d suite/results/$L ] || { echo "$L: missing"; continue; }
  suite/run.sh regrade $L --no-render 2>&1 | grep -E "^\| Coding|privacy" | cut -c1-200
done
finish
