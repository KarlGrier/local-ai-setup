#!/bin/bash
# p5-start.sh [--check] - the Phase 5 holdout in one command, once the build is final (staged 10-29; not run yet).
#   --check   run every check below and stop: changes nothing outside staging/phase5 and the logs, starts nothing
#             (safe while other runs are live)
# Checks (any failure = not started, with a desktop notice and a line in logs/p5-start.log):
#   - no HOLD file staging/phase5/HOLD-p5, no tmp/bench2.stop (the queue would stop at once);
#   - p5.json has no PLACEHOLDER left and the plan builds (p5.py plan: arms, items the queue can switch, p4s7's time
#     limits, 25 + 4 + 3 questions, the frozen files present);
#   - the engine: 8080 (if up) and the promoted config strata-ensure.sh starts on demand are p5.json's engine
#     (p5.py check-engine: config + sha256(exe)[:12]);
#   - the frozen question / answer files still match their FROZEN-*.txt hashes (p5.py check-frozen);
#   - deep-research-bench.service is not running, no ldr-* chain unit is active, no run holds run/bench.lock;
#   - strata-compare's kernel check (bringup/lib/kcheck.sh) passes;
#   - tools/bench2.py is the staged copy or the file it was staged from (bench2.py.orig).
# Then, holding run/bench.lock (no bench2 run or Jan job starts meanwhile):
#   1 tools/bench2.py <- staging/phase5/bench2.py (backup tools/bench2.py.before-p5): sets p5-harder / p5-o01, the p5
#     answers for the cross-check, `next` with a step's own budgets;
#   2 results/bench2/queue-plan-p5.json <- the plan;
#   3 the swap counters are remembered (p5.py swap-mark; p5.py status prints the change);
# then deep-research-bench.service's BENCH2_PLAN -> queue-plan-p5.json (backup .before-p5; the convention since p4s6)
# and the service starts. From there the queue's own rules hold: tmp/bench2.hold waits, tmp/bench2.stop stops at a
# clean point, a Strata release on our Qwen path pauses it (start the service again after the review), Jan jobs go
# first, three search-failed runs in a row stop it. It logs to logs/bench2-queue.log and ends with
# "queue finished (queue-plan-p5.json)".
set -u
WS=/home/USER/ai/deep-research
S=$WS/staging/phase5
B=$WS/results/bench2
LOG=${P5_LOG:-$WS/logs/p5-start.log}      # P5_LOG / P5_CONFIG / P5_PLAN_OUT: for the offline tests only
CFG=${P5_CONFIG:-$S/p5.json}
PLAN_OUT=${P5_PLAN_OUT:-$S/queue-plan-p5.json}
UNIT=$HOME/.config/systemd/user/deep-research-bench.service
KC=/home/USER/ai-speed-testing/strata-compare/bringup/lib/kcheck.sh
PYI="$WS/.venv/bin/python -I"
CHECK=0; [ "${1:-}" = --check ] && CHECK=1
[ "${P5_TEST:-0}" = 1 ] && CHECK=1     # the offline tests: never past the checks, no desktop notices
say() { echo "$(date '+%F %T') p5-start: $*" | tee -a "$LOG"; }
nostart() {
  say "$* - Phase 5 NOT started"
  [ $CHECK = 1 ] || notify-send -a "Deep research" -u critical "Phase 5 not started" "$*" 2> /dev/null || true
  exit 1
}

say "checks$([ $CHECK = 1 ] && echo ' only (--check: nothing is changed)')"
[ -e "$S/HOLD-p5" ] && nostart "HOLD file staging/phase5/HOLD-p5 present ($(head -c 200 "$S/HOLD-p5"))"
[ -e "$WS/tmp/bench2.stop" ] && nostart "tmp/bench2.stop present (the queue would stop at once): remove it first"
$PYI "$S/p5.py" --config "$CFG" plan --out "$PLAN_OUT" >> "$LOG" 2>&1 \
  || nostart "the plan was not built (PLACEHOLDER or unknown items in p5.json, or a set not frozen; see logs/p5-start.log)"
$PYI "$S/p5.py" --config "$CFG" check-engine >> "$LOG" 2>&1 || nostart "the engine is not the final one (p5.py check-engine; see the log)"
$PYI "$S/p5.py" --config "$CFG" check-frozen >> "$LOG" 2>&1 || nostart "a frozen question / answer file changed or is missing (p5.py check-frozen)"
systemctl --user is-active -q deep-research-bench.service \
  && nostart "deep-research-bench.service is running ($(grep -o 'BENCH2_PLAN=.*' "$UNIT"))"
CH=$(systemctl --user list-units --state=active --plain --no-legend 'ldr-*' 2> /dev/null | awk '{print $1}' | tr '\n' ' ')
[ -n "$CH" ] && nostart "a chain unit is active: $CH"
flock -n "$WS/run/bench.lock" true || nostart "run/bench.lock is held (a bench2 run, replay or rerun is going)"
if [ "${P5_TEST:-0}" = 1 ]; then say "kernel check skipped (P5_TEST, offline tests)"
else bash "$KC" p5-start >> "$LOG" 2>&1 || nostart "kernel check failed (strata-compare bringup/lib/kcheck.sh)"; fi
grep -q '^Environment=BENCH2_PLAN=' "$UNIT" || nostart "$UNIT has no Environment=BENCH2_PLAN= line"
if [ -e "$B/queue-plan-p5.json" ] && ! cmp -s "$PLAN_OUT" "$B/queue-plan-p5.json"; then
  nostart "results/bench2/queue-plan-p5.json exists and differs from the new plan (an earlier start?) - compare them first"
fi
if ! cmp -s "$S/bench2.py" "$WS/tools/bench2.py"; then
  cmp -s "$S/bench2.py.orig" "$WS/tools/bench2.py" \
    || nostart "tools/bench2.py changed since it was staged (it is not staging/phase5/bench2.py.orig): port the p5 hunks (diff bench2.py.orig bench2.py) by hand"
  [ -e "$WS/tools/bench2.py.before-p5" ] && nostart "tools/bench2.py.before-p5 exists - not overwriting it"
fi
if [ $CHECK = 1 ]; then
  say "check only: every check passed (a real start installs bench2.py, writes the plan, switches the bench unit and starts it)"
  exit 0
fi

# 1-3 under the bench lock
exec 7> "$WS/run/bench.lock"
flock -n 7 || nostart "run/bench.lock was taken meanwhile"
if cmp -s "$S/bench2.py" "$WS/tools/bench2.py"; then
  say "1 tools/bench2.py is the staged copy already"
else
  cp -p "$WS/tools/bench2.py" "$WS/tools/bench2.py.before-p5" || nostart "backup of tools/bench2.py failed"
  if cp "$S/bench2.py" "$WS/tools/bench2.py" && $PYI -m py_compile "$WS/tools/bench2.py"; then
    say "1 tools/bench2.py installed (backup tools/bench2.py.before-p5)"
  else
    cp -p "$WS/tools/bench2.py.before-p5" "$WS/tools/bench2.py"
    nostart "installing tools/bench2.py failed (the old one is back)"
  fi
fi
cp "$PLAN_OUT" "$B/queue-plan-p5.json" || nostart "writing results/bench2/queue-plan-p5.json failed"
say "2 plan -> results/bench2/queue-plan-p5.json ($(grep -c '"set"' "$B/queue-plan-p5.json") steps)"
$PYI "$S/p5.py" --config "$CFG" swap-mark >> "$LOG" 2>&1
say "3 swap counters remembered"
exec 7>&-

[ -e "$UNIT.before-p5" ] || cp -p "$UNIT" "$UNIT.before-p5"
sed -i 's|^Environment=BENCH2_PLAN=.*|Environment=BENCH2_PLAN=queue-plan-p5.json|' "$UNIT"
systemctl --user daemon-reload
systemctl --user start deep-research-bench.service
sleep 5
say "bench service: $(systemctl --user is-active deep-research-bench.service), plan $(grep -o 'BENCH2_PLAN=.*' "$UNIT")"
notify-send -a "Deep research" "Phase 5 holdout started" "deep-research-bench.service on queue-plan-p5.json; progress: staging/phase5/p5.py status" 2> /dev/null || true
