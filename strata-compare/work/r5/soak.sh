#!/bin/bash
# soak.sh [MINUTES] — round 5, phase 6: the big-chat soak on the FINAL build, on 127.0.0.1:8080 as you use it
# (./switch-model.sh strata = configs/Cstar5.json: warm-up, SearXNG, 5080 pin). Traffic = work/r5/chatsoak5.py bigsoak
# (10-12 big chats pasted from 32K/64K/120K documents so the 6-chat / 16 GiB chat cache overflows, going back to old
# chats, Stop, regenerate, long reasoning, short chats, web-search chats and their follow-ups, a 32K probe every
# 10 min; your settings: temperature 1.0 / 0.95 / 20 / 0.05). 1 s resource monitor; summary at the end.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
source $WS/work/r5/env.sh
M=${1:-120}
L=SOAK5-$(date +%m%dT%H%M)
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('configs/Cstar5.json'))['log'])")
./switch-model.sh strata || { echo "soak: switch-model.sh strata failed - no soak"; exit 1; }
curl -sf http://127.0.0.1:8080/health > /dev/null || { echo "soak: nothing answers on 8080 - no soak"; exit 1; }
(setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern 'strata --serve' --out logs/r5/monitor-$L > /dev/null 2>&1 &)
echo "=== $(date -Is) soak $L start ($M min)"
.venv/bin/python work/r5/chatsoak5.py bigsoak --base http://127.0.0.1:8080 --label $L --engine-log $ELOG --minutes $M
echo "=== $(date -Is) soak $L traffic done"
scripts/stopmon.sh $L
.venv/bin/python work/r5/soak_summary5.py $L $ELOG
grep -ciE 'error|stall|no progress|watchdog' $ELOG | sed 's/^/engine log error-ish lines (incl. start-up "no error" lines): /'
echo "=== $(date -Is) soak $L done"
