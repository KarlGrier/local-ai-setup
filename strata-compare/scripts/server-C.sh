#!/bin/bash
# Strata test server on 127.0.0.1:8081 from a config JSON (C0 = setup.py's, variants from mkcfg.py).
#   server-C.sh start CONFIG.json [SERVER_PY]   |   server-C.sh stop   |   server-C.sh status
WS=/home/USER/ai-speed-testing/strata-compare
PORT=${PORT:-8081}
PIDF=$WS/logs/server-C.pid
case ${1:-} in
start)
  CFG=$2; SRV=${3:-$WS/strata/serve/server.py}
  LOG=$WS/logs/server-C_$(date +%Y%m%dT%H%M%S).log
  ENVS=$($WS/.venv/bin/python -c "import json; print(' '.join(f'{k}={v}' for k,v in json.load(open('$CFG')).get('env',{}).items()))")
  echo "# $(date -Is) cfg=$CFG server=$SRV env=$ENVS" > "$LOG"; cat "$CFG" >> "$LOG"
  t0=$(date +%s.%N)
  setsid nohup env $ENVS $WS/.venv/bin/python "$SRV" --engine strata --config "$CFG" --host 127.0.0.1 --port $PORT >> "$LOG" 2>&1 < /dev/null &
  echo $! > "$PIDF"
  for i in $(seq 1 900); do
    kill -0 $(cat "$PIDF") 2>/dev/null || { tail -30 "$LOG"; echo "C exited"; exit 1; }
    curl -sf -m 2 http://127.0.0.1:$PORT/health >/dev/null 2>&1 && break; sleep 1
  done
  echo "C ready pid $(cat $PIDF) load_time_s $(echo "$(date +%s.%N) - $t0" | bc) log $LOG";;
stop)
  if [ -f "$PIDF" ]; then P=$(cat "$PIDF"); E=$(pgrep -P $P -f 'strata --serve'); kill -INT $P 2>/dev/null
    for i in $(seq 1 60); do kill -0 $P 2>/dev/null || break; sleep 0.5; done
    kill -0 $P 2>/dev/null && kill -TERM $P; [ -n "$E" ] && { for i in $(seq 1 30); do kill -0 $E 2>/dev/null || break; sleep 0.5; done; kill -0 $E 2>/dev/null && kill -TERM $E; }
    rm -f "$PIDF"; sleep 2; echo stopped; fi;;
status) [ -f "$PIDF" ] && ps -o pid,etime,rss,args -p $(cat "$PIDF") | cut -c1-200; pgrep -af 'strata --serve' | cut -c1-200;;
esac
