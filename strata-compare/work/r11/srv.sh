#!/bin/bash
# srv.sh — round 9 (copy of round 7, copy of round 6): a test server on 127.0.0.1:${PORT:-8081} from a config JSON, run UNDER THE MEMORY GUARD
# (work/r11/guard.py is its parent: samples MemAvailable / 5080 / 4060 Ti free from before the load, stops the server
# on MemAvailable < 20 GiB or 5080 free < 300 MiB, writes logs/r11/guard/summary.txt when it exits).
#   srv.sh start LABEL CONFIG.json    |   srv.sh stop   |   srv.sh status
# (13:2x fix: `stop` used to take the guard's first child, which can be one of its nvidia-smi streams, so the server
#  kept running; `stop` now stops whatever server listens on the port, and `start` refuses a port that is in use)
WS=/home/USER/ai-speed-testing/strata-compare
PORT=${PORT:-8081}
PIDF=$WS/logs/r11/srv.pid   # the guard's pid

listener() {   # pid of the process listening on 127.0.0.1:$PORT
  ss -H -ltnp "( sport = :$PORT )" 2>/dev/null | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2
}

case ${1:-} in
start)
  L=$2 CFG=$3
  if [ -n "$(listener)" ]; then echo "port $PORT is in use (pid $(listener)): refusing to start"; exit 1; fi
  SRV=$($WS/.venv/bin/python -c "import json; print(json.load(open('$CFG'))['server'])")
  LOG=$WS/logs/r11/server_${L}_$(date +%Y%m%dT%H%M%S).log
  ENVS=$($WS/.venv/bin/python -c "import json; print(' '.join(f'{k}={v}' for k,v in json.load(open('$CFG')).get('env',{}).items()))")
  echo "# $(date -Is) label=$L cfg=$CFG server=$SRV env=$ENVS exe=$($WS/.venv/bin/python -c "import json; print(json.load(open('$CFG'))['exe'])")" > "$LOG"; cat "$CFG" >> "$LOG"
  t0=$(date +%s.%N)
  setsid nohup env $ENVS $WS/.venv/bin/python $WS/work/r11/guard.py srv-$L -- $WS/.venv/bin/python "$SRV" --engine strata --config "$CFG" \
      --host 127.0.0.1 --port $PORT >> "$LOG" 2>&1 < /dev/null &
  echo $! > "$PIDF"
  for i in $(seq 1 900); do
    kill -0 $(cat "$PIDF") 2>/dev/null || { tail -30 "$LOG"; echo "server exited"; exit 1; }
    P=$(listener)
    if [ -n "$P" ] && tr '\0' ' ' < /proc/$P/cmdline | grep -q -- "--config $CFG" && curl -sf -m 2 http://127.0.0.1:$PORT/health >/dev/null 2>&1; then break; fi
    sleep 1
  done
  echo "server ready (guard pid $(cat $PIDF), server pid $(listener)) load_time_s $(echo "$(date +%s.%N) - $t0" | bc) log $LOG";;
stop)
  P=$(listener)
  if [ -n "$P" ]; then
    E=$(pgrep -P $P -f 'strata --serve')
    kill -INT $P 2>/dev/null
    for i in $(seq 1 60); do kill -0 $P 2>/dev/null || break; sleep 0.5; done
    kill -0 $P 2>/dev/null && kill -TERM $P
    [ -n "$E" ] && { for i in $(seq 1 30); do kill -0 $E 2>/dev/null || break; sleep 0.5; done; kill -0 $E 2>/dev/null && kill -TERM $E; }
  fi
  if [ -f "$PIDF" ]; then G=$(cat "$PIDF"); for i in $(seq 1 20); do kill -0 $G 2>/dev/null || break; sleep 0.5; done; rm -f "$PIDF"; fi
  sleep 1
  tail -1 $WS/logs/r11/guard/summary.txt
  [ -n "$(listener)" ] && echo "WARNING: port $PORT still in use by pid $(listener)";;
status) P=$(listener); [ -n "$P" ] && ps -o pid,etime,rss,args -p $P | cut -c1-200;;
esac
