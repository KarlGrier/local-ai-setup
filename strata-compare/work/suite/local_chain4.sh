#!/bin/bash
# local_chain4.sh - 2026-10-13, the r04 cause check. local_chain3.sh found: no filter or mask removed a likely
# </tool_call> (the model itself put ~97-99 % on <|im_end|> at the cut, or ~81-96 % on <|im_start|>), and stock v0.1.43
# cuts too (2 of 3). Every r04 prompt holds the fetched release notes' literal "</tool_call>", which C*17.1's server
# (and stock v0.1.43's) encodes as the real end-of-call token; upstream v0.1.43.1's a6830008 (#2026) encodes it as text.
# This runs r04 x6 on C*17.1's engine with a scratch server copy carrying only a6830008 (tmp/r19/r04fix/c171tree), from
# the frozen web cache, label c171-r04-fix2026 (separate; nothing scored is touched). Queued behind the API jobs' finish
# phase on tmp/suite/heavy.lock; one server at a time on 8081 under the guard; every server launch gets 9>&-.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
EV=logs/r19/uptime-c171/events.log
O=$WS/results/r19/r04diag
TK_C=$(.venv/bin/python -c "import json; print(json.load(open('configs/Cstar171.json'))['tokenizer'])")
step() { echo "=== $(date -Is) $*"; }
SRV='^[^ ]*/llama-server( |$)|^[^ ]*/strata --serve'
mon_gone() { for i in $(seq 120); do pgrep -f 'monitor.py --pid-pattern' > /dev/null || return 0; sleep 1; done; pgrep -fa 'monitor.py --pid-pattern'; }
srv_gone() { for i in $(seq 60); do pgrep -f "$SRV" > /dev/null || break; sleep 1; done; mon_gone; ! pgrep -fa "$SRV"; }
newest() { ls -t bringup/out/logs/server_$1_*.log 2>/dev/null | head -1; }
exec 9> tmp/suite/heavy.lock
step "r04 cause check: waiting for the heavy lock (the API jobs' finish phase)"
flock 9
step "lock held"
rm -f tmp/suite/LOCAL_CHAIN_DONE
finish() { touch tmp/suite/LOCAL_CHAIN_DONE; step "r04 cause check done; lock released"; }
bringup/lib/kcheck.sh suite-r04fix-start || { step "KERNEL CHECK FAILED - stopped, 8080 untouched"; finish; exit 1; }
rm -rf $O/req-c171fix
echo "$(date -Iseconds) PLANNED: 8080 stopped for the r04 cause check (one short guarded server on 8081, ~5 min); C*17.1 restarted on 8080 after" >> $EV
STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -2
srv_gone || { step "a model server is still running - stop"; ./switch-model.sh strata 9>&-; finish; exit 1; }

step "C*17.1 + upstream a6830008 (server only) + STRATA_DEBUG=1: r04 x6"
bringup/lib/with_server.sh 9>&- r04-c171fix configs/r19-r04-c171fix.json -- \
  "MSUITE_DUMP_REQUESTS=$O/req-c171fix suite/run.sh --label c171-r04-fix2026 --endpoint http://127.0.0.1:8081 --mode full --only research --items r04_strata_release --runs 6 2>&1 | tail -3" \
  2>&1 | grep -E 'start|ready|done|exited|graded|answers|scores'
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-160
.venv/bin/python work/suite/r04_probe_live.py contexts --label c171-r04-fix2026 --requests $O/req-c171fix --server-log "$(newest r04-c171fix)" --tokenizer $TK_C --out $O/ctx-c171fix.json
srv_gone || step "server still running after the check"

step "C*17.1 back on 8080"
bringup/lib/kcheck.sh suite-r04fix-end || step "KERNEL CHECK FAILED after the check (C*17.1 still restarted)"
./switch-model.sh strata 9>&- 2>&1 | tail -3
if ! curl -sf -m 10 http://127.0.0.1:8080/health > /dev/null; then step "8080 not healthy - one retry"; sleep 30; mon_gone; ./switch-model.sh strata 9>&- 2>&1 | tail -3; fi
curl -s -m 10 http://127.0.0.1:8080/health; echo
echo "$(date -Iseconds) END of the planned stop: C*17.1 back on 8080 after the r04 cause check" >> $EV
finish
