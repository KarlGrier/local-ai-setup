#!/bin/bash
# strata-ensure.sh - make sure Strata answers on 127.0.0.1:8080 before an app opens (2026-10-17). Used by jan-strata,
# opencode-strata, codex-strata and dsh-strata; exits 0 when 8080 is ready, 1 when it is not (the launcher then does not
# open the app; the reason is shown as a desktop notification and on stderr).
#   * 8080 answers               -> ready at once
#   * a test run holds the GPUs  -> "Strata is busy with a test" (the measurement lock tmp/gpu-test.lock or the queue's
#                                   tmp/suite/heavy.lock is held, or another model server runs) - nothing is started
#   * otherwise                  -> "Starting Strata..." and the promoted config (configs/Cstar18t.json, through
#                                   bringup/lib/phase_end.sh: memory floors checked first, the standing guard after);
#                                   ready when /health answers and the model is loaded; gives up after 3 minutes
#   * 8080 taken but never ready -> (2026-10-18) after the wait, a stale server (e.g. the kernel watcher ended its engine
#                                   and the wrapper stayed) is stopped with run-strata.sh stop and Strata is started once
#                                   more; not while a test holds the GPU locks
# STRATA_NO_AUTOSTART=1 skips all of this (the measurement harness sets it). Log: logs/run/strata-ensure.log.
WS=/home/USER/ai-speed-testing/strata-compare
[ "${STRATA_NO_AUTOSTART:-0}" = 1 ] && exit 0
URL=http://127.0.0.1:8080
LOG=$WS/logs/run/strata-ensure.log
APP=${1:-an app}
WAIT_S=${STRATA_START_WAIT_S:-180}
# the server must not inherit the launchers' offline proxy (its web search and page fetches go to the internet)
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy NO_PROXY no_proxy NODE_USE_ENV_PROXY

say() { echo "$(date -Is) [$APP] $*" >> "$LOG"; }
note() {   # a desktop notification (and stderr for the terminal apps)
  echo "strata: $2" >&2
  notify-send -a Strata -i jan-strata -u "${3:-normal}" "$1" "$2" 2>/dev/null || true
}
ready() { curl -s -m 3 "$URL/health" 2>/dev/null | grep -q '"loaded": *true'; }
held() {   # a lock some measurement holds: try to take it without waiting, release at once
  [ -e "$1" ] || return 1
  ! flock -n "$2" "$1" true 2>/dev/null
}
test_busy() {
  held "$WS/tmp/gpu-test.lock" -x && { echo "a measurement holds tmp/gpu-test.lock"; return 0; }
  held "$WS/tmp/suite/heavy.lock" -s && { echo "the test queue holds tmp/suite/heavy.lock"; return 0; }
  return 1
}
busy() {
  test_busy && return 0
  local p; p=$(pgrep -f '(^|/)llama-server( |$)|strata --serve' | head -1)
  [ -n "$p" ] && { echo "a model server is running (pid $p) but 8080 does not answer"; return 0; }
  return 1
}

ready && exit 0
# 11-09 (Karl, Stop model): while the model is stopped (deepseek-session.sh stop-model) nothing starts it by itself;
# opening Jan or DS Harness runs the full Back to Qwen path there (P028x started and checked, the test lock and the
# research hold released). Asked before this script's own start lock: the Back to Qwen path runs this script again
# for its own start. Only an explicit refusal (1) blocks; any other answer (a missing or failing gate) goes on as before.
DSS=${STRATA_ENSURE_DSS:-$WS/configs/usability/bin/deepseek-session.sh}
if [ -x "$DSS" ]; then
  G=$("$DSS" ensure-gate "$APP" 2> /dev/null < /dev/null 7>&-); GRC=$?
  case $GRC in
    10) if ready; then say "ready: the model was stopped; $APP brought Qwen back (the Back to Qwen path)"; exit 0; fi
        say "the Back to Qwen path for $APP finished but 8080 is not ready"
        note "Strata did not start" "Qwen did not come back for $APP; click Back to Qwen." critical; exit 1;;
    1) say "not started: $G"
       case $APP in OpenCode|Codex|Jan|"DS Harness"|"DeepSeek Harness") note "The model is stopped" "$G";; esac   # (an app icon: say why; the queue's callers only log)
       exit 1;;
  esac
fi
exec 7> "$WS/tmp/strata-ensure.lock"
flock 7                                   # one start at a time: a second launcher waits for the first one's start
ready && exit 0
listening() { [ -n "$(ss -H -ltn '( sport = :8080 )')" ]; }
start_strata() {
  if why=$(busy); then
    say "busy: $why"
    note "Strata is busy with a test" "Not started: $why. $APP was not opened." critical
    exit 1
  fi
  say "starting the promoted config for $APP"
  note "Starting Strata…" "Loading the model for $APP (usually under a minute)."
  # its own scope, so the server does not belong to the app that started it
  systemd-run --user --scope --quiet --collect --unit="strata-8080-$(date +%s)" \
    "$WS/bringup/lib/phase_end.sh" ondemand keep >> "$LOG" 2>&1 < /dev/null 7>&- &
  STARTER=$!
}
wait_ready() {   # 0 = ready; 1 = not ready after WAIT_S; exits when our own start gave up
  local i why
  for i in $(seq "$WAIT_S"); do
    ready && { say "ready after $(awk "BEGIN {printf \"%.1f\", $(date +%s.%N) - $T0}") s"; return 0; }
    if [ -n "${STARTER:-}" ] && ! kill -0 "$STARTER" 2>/dev/null && ! ready; then   # the start gave up (e.g. a floor)
      why=$(grep -E "GUARD|FAILED|switch-model:|die|not starting" "$LOG" | tail -1)
      say "start failed: $why"
      note "Strata did not start" "${why:-see logs/run/strata-ensure.log}. $APP was not opened." critical
      exit 1
    fi
    sleep 1
  done
  return 1
}
T0=$(date +%s.%N)
STARTER=""
if listening; then
  say "8080 is listening but not ready yet (starting or loading): waiting"
else
  start_strata
fi
wait_ready && exit 0
if [ -z "$STARTER" ]; then
  # 8080 was taken when we came and never got ready: a stale server (its engine gone, the wrapper still listening).
  if why=$(test_busy); then
    say "not ready after $WAIT_S s and $why: not touching 8080"
    note "Strata is busy with a test" "8080 is not ready and $why. $APP was not opened." critical
    exit 1
  fi
  say "not ready after $WAIT_S s: stopping the stale server on 8080 (run-strata.sh stop), then starting Strata once more"
  STRATA_PORT=8080 "$WS/run-strata.sh" stop >> "$LOG" 2>&1 7>&-
  if listening; then
    say "8080 is still taken after run-strata.sh stop: $(ss -H -ltnp '( sport = :8080 )' | grep -o 'pid=[0-9]*' | head -1)"
    note "Strata did not start" "Port 8080 is taken by a process run-strata.sh does not own; see logs/run/strata-ensure.log. $APP was not opened." critical
    exit 1
  fi
  T0=$(date +%s.%N)
  start_strata
  wait_ready && exit 0
fi
say "not ready after $WAIT_S s"
note "Strata did not start" "Not ready after $((WAIT_S / 60)) minutes; see logs/run/strata-ensure.log. $APP was not opened." critical
exit 1
