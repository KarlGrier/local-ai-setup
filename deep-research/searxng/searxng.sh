#!/bin/bash
# searxng.sh start|stop|restart|status — Local Deep Research's own SearXNG instances (127.0.0.1 only). The chat
# page's SearXNG on 8888 belongs to strata-compare and is not touched.
#
#   main      127.0.0.1:8889  settings.yml           engines measured to work from here + academic (the default)
#   baseline  127.0.0.1:8890  settings.baseline.yml  8888's engine choices, for baseline measurements only
#   choose with SEARXNG_INSTANCE=baseline ./searxng.sh start
#
# Server: granian 2.8.3 (SearXNG's production server) on CPython 3.12.13 (uv's standalone build in python/, venv
# venv-3.12.13/). Not on Ubuntu's python3.12 (3.12.3): it lacks the gh-119585 fix, and granian's worker threads can
# crash it when they exit (NOTES.md 2026-09-30; reproductions in tests/). A keeper loop restarts granian if it ever
# exits unexpectedly and logs that to logs/searxng-<instance>-events.log; faulthandler is on, so a crash would
# leave a Python traceback in logs/searxng-<instance>.log.
#
# 2026-10-21 (the user: "run 8889, 8890 and 8888 as their own user services, independent of the queue service, so
# restarting the queue can't kill them"): each instance is a systemd user service - searxng-ldr.service (main, 8889)
# and searxng-ldr-baseline.service (8890), both `searxng.sh run` (granian in the foreground; systemd restarts it, in
# place of the keeper loop). While the unit file exists: start = systemctl --user start; stop leaves it running (the
# runner's idle stop, run-ldr.sh, the queue's end can no longer take it down; SEARXNG_FORCE_STOP=1 or systemctl
# --user stop UNIT stops it); status = the unit's state + /healthz. Without the unit file the old keeper path runs.
set -u
SX=/home/USER/ai/deep-research/searxng
source $SX/env.sh
INST=${SEARXNG_INSTANCE:-main}
case $INST in
  main)     PORT=8889; SETTINGS=$SX/settings.yml;;
  baseline) PORT=8890; SETTINGS=$SX/settings.baseline.yml;;
  *) echo "unknown instance $INST (main|baseline)"; exit 2;;
esac
PIDF=$SX/run/searxng-$INST.pid; LOG=$SX/logs/searxng-$INST.log; EV=$SX/logs/searxng-$INST-events.log
UNIT=$([ $INST = main ] && echo searxng-ldr.service || echo searxng-ldr-baseline.service)
unit_mode() { [ -f "$HOME/.config/systemd/user/$UNIT" ]; }
VENV=${SEARXNG_VENV:-$SX/venv-3.12.13}
mkdir -p $SX/run $SX/logs
running() { [ -f $PIDF ] && kill -0 $(cat $PIDF) 2>/dev/null; }
healthy() { curl -sf -m 3 http://127.0.0.1:$PORT/healthz >/dev/null 2>&1; }
keeper() {
  cd $SX/searxng-git
  local n=0
  while :; do
    SEARXNG_SETTINGS_PATH=$SETTINGS PYTHONFAULTHANDLER=1 $VENV/bin/granian --interface wsgi --host 127.0.0.1 \
      --port $PORT --workers 1 --blocking-threads 8 searx.webapp:app >> $LOG 2>&1 < /dev/null
    local rc=$?
    [ -f $SX/run/stopping-$INST ] && break
    n=$((n+1)); echo "$(date -Is) granian exited rc=$rc; restart #$n in 2 s" >> $EV
    sleep 2
  done
}
case ${1:-} in
run)   # the unit's ExecStart: granian in the foreground (systemd's Restart= replaces the keeper loop)
  cd $SX/searxng-git
  echo "$(date -Is) run under systemd ($UNIT; $($VENV/bin/python -V), $SETTINGS)" >> $EV
  export SEARXNG_SETTINGS_PATH=$SETTINGS PYTHONFAULTHANDLER=1
  exec $VENV/bin/granian --interface wsgi --host 127.0.0.1 --port $PORT --workers 1 --blocking-threads 8 \
    searx.webapp:app >> $LOG 2>&1 < /dev/null;;
start)
  if unit_mode; then
    systemctl --user start $UNIT || { echo "systemctl --user start $UNIT failed"; exit 1; }
    for i in $(seq 1 60); do healthy && { echo "searxng $INST up on http://127.0.0.1:$PORT ($UNIT)"; exit 0; }; sleep 1; done
    echo "searxng $INST ($UNIT) did not answer on $PORT; see $LOG"; tail -20 $LOG; exit 1
  fi
  running && { echo "searxng $INST already running (keeper pid $(cat $PIDF))"; exit 0; }
  ss -H -ltn "( sport = :$PORT )" | grep -q . && { echo "port $PORT is taken"; exit 1; }
  rm -f $SX/run/stopping-$INST
  echo "$(date -Is) start ($($VENV/bin/python -V), granian $($VENV/bin/granian --version 2>/dev/null | awk '{print $NF}'), $SETTINGS)" >> $EV
  export -f keeper; export SX PORT LOG EV VENV SETTINGS INST
  setsid nohup bash -c keeper > /dev/null 2>&1 < /dev/null &
  echo $! > $PIDF
  for i in $(seq 1 60); do healthy && { echo "searxng $INST up on http://127.0.0.1:$PORT (keeper pid $(cat $PIDF))"; exit 0; }; sleep 1; done
  echo "searxng $INST did not come up; see $LOG"; tail -20 $LOG; exit 1;;
stop)
  if unit_mode; then
    if [ "${SEARXNG_FORCE_STOP:-0}" = 1 ]; then systemctl --user stop $UNIT; echo "searxng $INST stopped ($UNIT)"
    else echo "searxng $INST left running: it is the user service $UNIT (systemctl --user stop $UNIT to stop it)"; fi
    exit 0
  fi
  if running; then
    touch $SX/run/stopping-$INST; kill -TERM -- -$(cat $PIDF) 2>/dev/null
    for i in $(seq 1 30); do running || break; sleep 0.5; done
    running && kill -KILL -- -$(cat $PIDF) 2>/dev/null
    echo "$(date -Is) stop" >> $EV
  fi
  rm -f $PIDF; echo "searxng $INST stopped";;
restart) if unit_mode; then systemctl --user restart $UNIT && exec $0 start; fi; $0 stop; $0 start;;
status)
  if unit_mode; then
    st=$(systemctl --user is-active $UNIT)
    echo "searxng $INST: $UNIT $st on 127.0.0.1:$PORT, health $(healthy && echo ok || echo FAIL), restarts by systemd: $(systemctl --user show -p NRestarts --value $UNIT)"
    [ "$st" = active ] && healthy && exit 0; exit 3
  fi
  if running; then
    echo "searxng $INST: running on 127.0.0.1:$PORT (keeper pid $(cat $PIDF)), health $(healthy && echo ok || echo FAIL), unexpected restarts: $(grep -c "granian exited" $EV 2>/dev/null; true)"
  else echo "searxng $INST: not running"; exit 3; fi;;
*) sed -n 2,14p $0; exit 2;;
esac
