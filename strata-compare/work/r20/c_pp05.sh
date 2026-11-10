#!/bin/bash
# c_pp05.sh - 2026-10-14 (the user, after D): the same 7 stuck coding answers continued on IQ3_S from the same cut with
# presence_penalty 0.5 (the model card's remedy for endless repetition; the user's other sampling as in the original
# runs: T 1.0, top_p 0.95, top_k 20, min_p 0.05; Strata applies it over the last 64 tokens, the server's default
# penalty_last_n), repeat limit 1024 in total, on C*17.1's engine + the hook server on 8081 (configs/r19-guard-c171cont.json;
# the served config is not changed) -> labels <label>-cont1024-pp05 built on -cont1024; graded (coding).
# Then the 2 Q8_0 probe cases c_probe3 did not reach (c16 of the quick and Q4 labels), into the engine's own logpos file.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
PY=$WS/suite/.venv/bin/python; TK_C=$(jq -r .tokenizer configs/Cstar171.json); TK_Q=$(jq -r .tokenizer configs/r16-q4.json)
C171="c171-iq3s-full:c02_rle:2,c171-iq3s-full:c16_json_parser:0,c171-iq3s-full:c23_refactor_orderbook:2,c171-iq3s-quick:c07_rpn:0,c171-iq3s-quick:c16_json_parser:0"
Q4="r16-q4-quick:c14_semver:0,r16-q4-quick:c16_json_parser:0"
step() { echo "=== $(date -Is) $*"; }
SRV='^[^ ]*/llama-server( |$)|^[^ ]*/strata --serve'
mon_gone() { for i in $(seq 120); do pgrep -f 'monitor.py --pid-pattern' > /dev/null || return 0; sleep 1; done; }
srv_gone() { for i in $(seq 60); do pgrep -f "$SRV" > /dev/null || break; sleep 1; done; mon_gone; ! pgrep -fa "$SRV"; }
kc() { bringup/lib/kcheck.sh "$1" || { step "KERNEL CHECK FAILED ($1) - stopped"; exit 1; }; step "kernel check ok ($1)"; }
exec 9> tmp/suite/heavy.lock; flock 9
kc r20-pp-start
STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -1
srv_gone || { step "a model server is running - stop"; exit 1; }
step "IQ3_S continuation with presence_penalty 0.5"
CONT="$PY work/suite/guard_continue.py --suffix=-cont1024-pp05 --base-suffix=-cont1024 --sampling '{\"presence_penalty\":0.5}'"
bringup/lib/with_server.sh 9>&- pp05 configs/r19-guard-c171cont.json -- \
  "$CONT --tokenizer $TK_C --cases $C171 && $CONT --tokenizer $TK_Q --cases $Q4; grep -c 'penalty_present=0.5' \$ELOG | sed 's/^/engine lines with penalty_present=0.5: /'" 2>&1 | grep -vE '^\[strata\]'
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-200
srv_gone || step "server still running"; kc r20-pp
for L in c171-iq3s-full-cont1024-pp05 c171-iq3s-quick-cont1024-pp05 r16-q4-quick-cont1024-pp05; do
  [ -d suite/results/$L ] && suite/run.sh regrade $L --no-render 2>&1 | grep -E "^\| Coding|privacy" | cut -c1-200
done
step "Q8_0 probe: the 2 cases not reached"
GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4 EVICT_GLOB="$WS/models/r15/Q8_0/*.gguf" \
bringup/lib/with_server.sh 9>&- q8probe4 configs/r20-q8-probe.json -- \
  "$PY work/r20/loop_probe.py --logpos $WS/results/r20/q8loop/logpos-q8.tsv --model q8 --tokenizer $TK_C --cases c171-iq3s-quick:c16_json_parser:0 --seq-from=-cont1024-q8; \
   $PY work/r20/loop_probe.py --logpos $WS/results/r20/q8loop/logpos-q8.tsv --model q8 --tokenizer $TK_C --cases r16-q4-quick:c16_json_parser:0 --seq-from=-cont1024-q8" 2>&1 | grep -vE '^\[strata\]'
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-200
srv_gone || step "server still running"; kc r20-q8p4
step "C*17.1 back on 8080"; ./switch-model.sh strata 9>&- 2>&1 | tail -3; curl -s -m 10 http://127.0.0.1:8080/health; echo
step "c_pp05 done"
