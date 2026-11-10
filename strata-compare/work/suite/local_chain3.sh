#!/bin/bash
# local_chain3.sh — 2026-10-12 23:0x, the user's r04 diagnostic (with their two additions). Queued behind local_chain2.sh
# (the Q4 run), ahead of the API jobs' finish phase: it holds tmp/suite/heavy.lock the whole time. One model server at
# a time, each on 127.0.0.1:8081 under the memory guard (bringup/lib/with_server.sh); 8080 stays stopped until the end.
# Known before it runs (NOTES.md 2026-10-12 22:3x): no limit cut r04; the C*17.1 server passes both tool-call tags
# through as text; the engine stops only on <|endoftext|> / <|im_end|>; nothing masks tokens (logit_bias only from the
# request; the draft vocabulary has both tags). The scored c171-iq3s-* answers are not touched (separate labels).
#  A  C*17.1 as configured + STRATA_DEBUG=1 (raw replies, the ending token included): r04 x6 from the frozen web cache,
#     every request body saved (MSUITE_DUMP_REQUESTS) -> label c171-r04-diag, contexts of the replies
#  B  C*17.1's engine binary + a scratch server copy with strata_prefix_ids, STRATA_LOGPOS + TOPK=20: at each cut
#     reply's ending position the top 20 before the sampler's filters, and after them (the engine's chain replayed)
#  C  stock v0.1.43 (its own engine and server, the same model GGUF, the same spec flags) + STRATA_DEBUG=1: r04 x3
#     -> label v043-r04-stock, contexts
#  D  the measurement build (stock + inert hooks) with STRATA_LOGPOS + TOPK=20: the same probes at C*17.1's and
#     stock's cut positions
#  then C*17.1 back on 8080 (switch-model.sh strata).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
EV=logs/r19/uptime-c171/events.log
O=$WS/results/r19/r04diag
P="$WS/.venv/bin/python $WS/work/suite/r04_probe_live.py"
TK_C=$(.venv/bin/python -c "import json; print(json.load(open('configs/Cstar171.json'))['tokenizer'])")
TK_S=$(.venv/bin/python -c "import json; print(json.load(open('configs/r19-st43-em.json'))['tokenizer'])")
step() { echo "=== $(date -Is) $*"; }
SRV='^[^ ]*/llama-server( |$)|^[^ ]*/strata --serve'
mon_gone() { for i in $(seq 120); do pgrep -f 'monitor.py --pid-pattern' > /dev/null || return 0; sleep 1; done; pgrep -fa 'monitor.py --pid-pattern'; }
srv_gone() { for i in $(seq 60); do pgrep -f "$SRV" > /dev/null || break; sleep 1; done; mon_gone; ! pgrep -fa "$SRV"; }
newest() { ls -t bringup/out/logs/server_$1_*.log 2>/dev/null | head -1; }
exec 9> tmp/suite/heavy.lock
step "r04 diagnostic: waiting for the heavy lock (the Q4 chain)"
flock 9
step "lock held"
rm -f tmp/suite/LOCAL_CHAIN_DONE
finish() { touch tmp/suite/LOCAL_CHAIN_DONE; step "r04 diagnostic done; lock released"; }
bringup/lib/kcheck.sh suite-r04diag-start || { step "KERNEL CHECK FAILED - stopped, 8080 untouched"; finish; exit 1; }
# 2026-10-13 07:5x: the Q4 chain's 8080 server and SearXNG inherited this lock's fd 9 and held it; they were stopped by hand
# to release it, so 8080 being down here is expected. Every server started below gets 9>&- (no inherited lock).
curl -sf -m 10 http://127.0.0.1:8080/health > /dev/null && step "8080 healthy" || step "8080 already stopped (released the leaked lock)"
mkdir -p $O; rm -rf $O/req-c171 $O/req-v43; rm -f $O/logpos-c171.tsv $O/logpos-meas43.tsv
echo "$(date -Iseconds) PLANNED: 8080 stopped for the r04 diagnostic (four short guarded servers on 8081, ~45 min); C*17.1 restarted on 8080 after" >> $EV
STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -2
srv_gone || { step "a model server is still running - stop"; ./switch-model.sh strata 9>&-; finish; exit 1; }

step "A. C*17.1 + STRATA_DEBUG=1: r04 x6"
bringup/lib/with_server.sh 9>&- r04-c171dbg configs/r19-r04-c171dbg.json -- \
  "MSUITE_DUMP_REQUESTS=$O/req-c171 suite/run.sh --label c171-r04-diag --endpoint http://127.0.0.1:8081 --mode full --only research --items r04_strata_release --runs 6 2>&1 | tail -3" \
  2>&1 | grep -E 'start|ready|done|exited|graded|answers|scores'
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-160
$P contexts --label c171-r04-diag --requests $O/req-c171 --server-log "$(newest r04-c171dbg)" --tokenizer $TK_C --out $O/ctx-c171.json
srv_gone || { step "server still running after A - stop"; finish; exit 1; }

step "B. C*17.1's engine + the prefix hook, STRATA_LOGPOS top 20: probes at the cut positions"
bringup/lib/with_server.sh 9>&- r04-c171probe configs/r19-r04-c171probe.json -- \
  "$P probe --endpoint http://127.0.0.1:8081 --contexts $O/ctx-c171.json --logpos $O/logpos-c171.tsv --tokenizer $TK_C --out $O/probe-c171.json" \
  2>&1 | grep -vE '^\[strata\]'
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-160
srv_gone || { step "server still running after B - stop"; finish; exit 1; }
bringup/lib/kcheck.sh suite-r04diag-mid || { step "KERNEL CHECK FAILED - stopped"; finish; exit 1; }

step "C. stock v0.1.43, the same model file + STRATA_DEBUG=1: r04 x3"
bringup/lib/with_server.sh 9>&- r04-v43 configs/r19-r04-v43.json -- \
  "MSUITE_DUMP_REQUESTS=$O/req-v43 suite/run.sh --label v043-r04-stock --endpoint http://127.0.0.1:8081 --mode full --only research --items r04_strata_release --runs 3 2>&1 | tail -3" \
  2>&1 | grep -E 'start|ready|done|exited|graded|answers|scores'
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-160
$P contexts --label v043-r04-stock --requests $O/req-v43 --server-log "$(newest r04-v43)" --tokenizer $TK_S --out $O/ctx-v43.json
srv_gone || { step "server still running after C - stop"; finish; exit 1; }

step "D. the measurement build (stock + hooks), STRATA_LOGPOS top 20: probes at C*17.1's and stock's cut positions"
bringup/lib/with_server.sh 9>&- r04-meas43probe configs/r19-r04-meas43probe.json -- \
  "$P probe --endpoint http://127.0.0.1:8081 --contexts $O/ctx-c171.json,$O/ctx-v43.json --logpos $O/logpos-meas43.tsv --tokenizer $TK_S --out $O/probe-meas43.json" \
  2>&1 | grep -vE '^\[strata\]'
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-160
srv_gone || step "server still running after D"

step "C*17.1 back on 8080"
bringup/lib/kcheck.sh suite-r04diag-end || step "KERNEL CHECK FAILED after the diagnostic (C*17.1 still restarted)"
./switch-model.sh strata 9>&- 2>&1 | tail -3
if ! curl -sf -m 10 http://127.0.0.1:8080/health > /dev/null; then step "8080 not healthy - one retry"; sleep 30; mon_gone; ./switch-model.sh strata 9>&- 2>&1 | tail -3; fi
curl -s -m 10 http://127.0.0.1:8080/health; echo
echo "$(date -Iseconds) END of the planned stop: C*17.1 back on 8080 after the r04 diagnostic" >> $EV
finish
