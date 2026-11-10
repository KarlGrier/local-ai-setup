#!/bin/bash
# Stuck-run watchdog checks (staged 11-03). READ-ONLY: installs nothing, starts or stops nothing, sends no search.
#   check.sh tests     the staged test suites only
#   check.sh live      is it a moment to install / restart the bench unit? (see nothing_live)
#   check.sh pre       live + the live files are still the ones the watchdog was staged against + the staged tests
#   check.sh post      after the install: installed == staged (sha256), backups, syntax, --watchdog-min present,
#                      the staged tests (staged == installed), bench2.py next still answers
# Exit 0 = all good; the first failing check is printed and exits 1.
set -u
W=/home/USER/ai/deep-research
S=$W/staging/watchdog
PY=$W/.venv/bin/python
FILES="ldr-client.py bench2.py bench2-queue.sh"
UNIT=deep-research-bench.service
fail() { echo "FAIL: $*"; exit 1; }
ok() { echo "ok: $*"; }

nothing_live() {
  # no bench run (bench2.py holds run/bench.lock for a whole question), no paid run, no Jan job running (the runner
  # names it in run/research-control.json), no model call running or held at the proxy, no replay / grading unit,
  # and the bench queue either stopped or waiting on its hold file (between questions, e.g. in a gap)
  flock -n $W/run/bench.lock true || fail "run/bench.lock is held (a bench run is live)"
  [ -e $W/run/paid-run.json ] && fail "run/paid-run.json exists (a paid test or research run is live)"
  /usr/bin/python3 -I - "$W/run/research-control.json" "$W/run/research-clock.json" <<'EOF' || fail "a Jan job or a model call is live (above)"
import json, sys, time
try:
    ctl = json.load(open(sys.argv[1]))
except (OSError, ValueError):
    ctl = {}
if ctl.get("job"):
    sys.exit(print(f"a Jan research job is active ({ctl['job']})") or 1)
try:
    g = json.load(open(sys.argv[2]))
except (OSError, ValueError):
    g = {}
if time.time() - float(g.get("updated") or 0) < 30 and (g.get("inflight") or g.get("held")):
    sys.exit(print(f"the proxy has a call running or held (inflight {g.get('inflight')}, held {g.get('held')})") or 1)
EOF
  local busy
  busy=$(systemctl --user list-units --type=service --state=active --no-legend 2>/dev/null \
         | awk '{print $1}' | grep -i -E 'replay|grade|grading|item7|freshldr|fixes-chain|p4s|p5-|readpass' || true)
  [ -n "$busy" ] && fail "a replay / grading / install unit is active: $busy"
  if systemctl --user is-active --quiet $UNIT; then
    [ -e $W/tmp/bench2.hold ] || fail "the bench queue is active and not held (no tmp/bench2.hold): wait for a gap"
    tail -n 1 $W/logs/bench2-queue.log | grep -q "hold file: waiting" \
      || fail "the bench queue is active but its last log line is not 'hold file: waiting': $(tail -n 1 $W/logs/bench2-queue.log)"
    ok "bench queue active, waiting on its hold file (between questions)"
  else
    ok "bench queue not running"
  fi
  ok "no bench run, paid run, active Jan job, live model call, replay or grading"
}

case "${1:-}" in
tests)
  bash $S/tests/run_all.sh || fail "staged tests"
  ok "staged tests pass"
  ;;
live)
  nothing_live
  ;;
pre)
  nothing_live
  for f in $FILES; do
    want=$(grep " $W/tools/$f\$" $S/LIVE-SHA256-AT-STAGING.txt | awk '{print $1}')
    [ "$(sha256sum $W/tools/$f | awk '{print $1}')" = "$want" ] \
      || fail "tools/$f changed since the watchdog was staged (11-03): re-port the change onto it"
  done
  ok "live tools/{$FILES} unchanged since staging"
  bash $S/tests/run_all.sh || fail "staged tests"
  ok "staged tests pass (pre-install)"
  ;;
post)
  for f in $FILES; do
    [ "$(sha256sum $W/tools/$f | awk '{print $1}')" = "$(sha256sum $S/tools/$f | awk '{print $1}')" ] \
      || fail "tools/$f differs from the staged copy"
    [ -e "$W/tools/$f.before-watchdog" ] || fail "no backup tools/$f.before-watchdog"
  done
  ok "installed tools == staged, backups *.before-watchdog present"
  bash -n $W/tools/bench2-queue.sh || fail "bash -n tools/bench2-queue.sh"
  $PY -I -B -c "import ast, sys; [ast.parse(open(f).read(), f) for f in sys.argv[1:]]" \
    $W/tools/ldr-client.py $W/tools/bench2.py || fail "python syntax"
  $PY -I -B -W ignore $W/tools/ldr-client.py research --help 2>&1 | grep -q -- "--watchdog-min" \
    || fail "tools/ldr-client.py research has no --watchdog-min"
  ok "syntax fine; ldr-client.py research --watchdog-min present"
  bash $S/tests/run_all.sh || fail "staged tests"
  ok "staged suites pass (staged == installed)"
  plan=$(systemctl --user show -p Environment --value $UNIT 2>/dev/null | tr ' ' '\n' | sed -n 's/^BENCH2_PLAN=//p')
  nxt=$(BENCH2_PLAN=${plan:-queue-plan.json} $PY -I -B $W/tools/bench2.py next --wide 2>&1 | tail -n 1)
  echo "bench2.py next --wide (${plan:-queue-plan.json}): $nxt"
  case "$nxt" in Traceback*|*Error*) fail "bench2.py next failed";; esac
  ok "bench2.py next answers"
  ;;
*) echo "usage: check.sh tests|live|pre|post"; exit 2;;
esac
