#!/bin/bash
# soak.sh [MINUTES] — round 9 (copy of round 7, copy of round 6): the round-5 big-chat soak (work/r5/chatsoak5.py bigsoak) on the FINAL build, on
# 127.0.0.1:8080 as you use it (STRATA_CONFIG, default configs/Cstar7.json, through ./switch-model.sh strata: warm-up,
# SearXNG, both GPUs). Traffic: 10-12 big chats pasted from 32K/64K/120K documents so the 6-chat / 16 GiB chat cache
# overflows, going back to old chats, Stop, regenerate, long reasoning, short chats, web-search chats, a 32K probe every
# 10 min; your settings (temperature 1.0 / 0.95 / 20 / 0.05). 1 s resource monitor + the memory guard watching the
# engine through the whole soak (MemAvailable >= 20 GiB, 5080 >= 300 MiB free; it stops the engine if crossed).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
source $WS/work/r11/env.sh
M=${1:-120}
CFG=${STRATA_CONFIG:-configs/Cstar7.json}
L=SOAK8-$(date +%m%dT%H%M)
ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
EXE=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['exe'])")
STRATA_CONFIG=$CFG ./switch-model.sh strata || { echo "soak: switch-model.sh strata failed - no soak"; exit 1; }
curl -sf http://127.0.0.1:8080/health > /dev/null || { echo "soak: nothing answers on 8080 - no soak"; exit 1; }
(setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern '/strata --serve' --out logs/r11/monitor-$L > /dev/null 2>&1 &)
(setsid nohup .venv/bin/python work/r11/guard.py $L --watch-pattern "$EXE --serve" > logs/r11/guard-$L.out 2>&1 &)
echo "=== $(date -Is) soak $L start ($M min, $CFG)"
.venv/bin/python work/r5/chatsoak5.py bigsoak --base http://127.0.0.1:8080 --label $L --engine-log $ELOG --minutes $M
echo "=== $(date -Is) soak $L traffic done"
scripts/stopmon.sh $L
.venv/bin/python work/r5/soak_summary5.py $L $ELOG $WS/logs/r11/monitor-$L
grep -ciE 'error|stall|no progress|watchdog' $ELOG | sed 's/^/engine log error-ish lines (incl. start-up "no error" lines): /'
echo "guard (still watching the engine until it stops): $(tail -2 logs/r11/guard/$L.csv | tail -1)"
echo "=== $(date -Is) soak $L done"
