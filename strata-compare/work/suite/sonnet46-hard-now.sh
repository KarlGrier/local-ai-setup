#!/bin/bash
# sonnet46-hard-now.sh - Karl 10-29: after the Opus 4.5 hard-set run (opus45-hard-now.sh), Sonnet 4.6 on the same hard set
# with the same rules (30,000-token room, 3 runs per item, effort pinned to high with --claude-effort, Batch API for the
# single-turn items, API only) - only if Opus came in clearly under $25 and enough of the expiring $30.14 of promotional
# credits (until 11-01 UTC) is left. Total spend on the expiring credits must stay under $30: Sonnet's estimate limit and
# hard stop = min($25, $30.14 - Opus's cost - $1.00 margin). Must finish before Sat 10-31 18:00 Chicago.
# The key is read by the suite from its own file only (never here). Log: logs/suite/sonnet46-hard.log.
set -u
WS=/home/USER/ai-speed-testing/strata-compare
LOG=$WS/logs/suite/sonnet46-hard.log
OPUS=$WS/suite/results/opus-4-5-hard-r3/meta.json
LABEL=sonnet-4-6-hard-r3
ITEMS=$(grep '^ITEMS=' $WS/work/suite/opus45-hard.sh | cut -d= -f2)
CREDIT=30.14; MARGIN=1.00; CLEAR=20.00          # "clearly under $25": Opus at most $20
mkdir -p "${LOG%/*}"
say() { echo "$(date '+%m-%d %H:%M:%S') $*" >> "$LOG"; }
note() { notify-send -a "Sonnet 4.6 hard set" "$1" "$2" 2> /dev/null || true; }
late() { [ "$(date +%Y%m%d%H)" -gt 2026103117 ]; }
say "waiting for the Opus 4.5 hard-set run to complete"
until grep -q '"status": "complete"' "$OPUS" 2> /dev/null; do
  if ! systemctl --user is-active --quiet suite-opus45-now.service; then
    grep -q '"status": "complete"' "$OPUS" 2> /dev/null && break
    say "the Opus run ended without completing ($(python3 -c "import json; print(json.load(open('$OPUS')).get('status'))" 2> /dev/null)) - Sonnet not run"
    note "Sonnet 4.6 not run" "The Opus 4.5 run did not complete - see logs/suite/opus45-hard.log"; exit 1
  fi
  late && { say "Sat 10-31 18:00 reached before Opus completed - Sonnet not run"; exit 0; }
  sleep 300
done
opus=$(python3 -c "import json; print(round(float(json.load(open('$OPUS')).get('cost_usd') or 0), 2))")
budget=$(python3 -c "print(round(min(25.0, $CREDIT - $opus - $MARGIN), 2))")
say "Opus 4.5 cost \$$opus; Sonnet budget = min(25, $CREDIT - $opus - $MARGIN) = \$$budget"
if python3 -c "import sys; sys.exit(0 if $opus <= $CLEAR and $budget >= 3 else 1)"; then :; else
  say "Opus not clearly under \$25 or too little of the expiring credits left - Sonnet not run"
  note "Sonnet 4.6 not run" "Opus cost \$$opus; budget left \$$budget"; exit 0
fi
ARGS=(--label $LABEL --endpoint claude:claude-sonnet-4-6 --claude-effort high --mode quick
      --only agentic,coding,honesty,instruct,math,research,tools --items "$ITEMS" --runs 3 --max-tokens 30000
      --estimate-from h1026-qwen-xhigh --max-estimate "$budget" --budget "$budget")
busy() {   # a measurement holds one of the locks (tried without waiting, released at once)
  local f
  for f in "$WS/tmp/gpu-test.lock" "$WS/tmp/suite/heavy.lock" /home/USER/ai/deep-research/run/bench.lock; do
    [ -e "$f" ] || continue
    flock -n -x "$f" true 2> /dev/null || { echo "${f##*/}"; return 0; }
  done
  return 1
}
if b=$(busy); then
  say "a measurement holds $b: collecting answers only first"
  bash "$WS/suite/run.sh" "${ARGS[@]}" --collect-only >> "$LOG" 2>&1; rc=$?
  say "collect-only pass ended (rc $rc)"
  [ $rc -eq 0 ] || { note "Sonnet 4.6 run stopped (rc $rc)" "See logs/suite/sonnet46-hard.log"; exit $rc; }
  while b=$(busy); do
    late && { say "locks still held at Sat 10-31 18:00 - grading left for later"; exit 0; }
    sleep 600
  done
fi
say "full pass (agentic item + grading)"
bash "$WS/suite/run.sh" "${ARGS[@]}" >> "$LOG" 2>&1; rc=$?
cost=$(python3 -c "import json; print(json.load(open('$WS/suite/results/$LABEL/meta.json')).get('cost_usd'))" 2> /dev/null)
say "done (rc $rc, cost \$${cost:-?}; with Opus \$$opus)"
note "Sonnet 4.6 hard set: $([ $rc -eq 0 ] && echo done || echo "stopped (rc $rc)")" "Cost \$${cost:-?} (+ Opus \$$opus). suite/results/$LABEL"
exit $rc
