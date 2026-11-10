#!/bin/bash
# frontier-now.sh - Karl 10-29: finish the frontier comparison set on the expiring promotional credits ($30.14 until
# 11-01 UTC): Sonnet 4.6, then Opus 4.6, both effort high, on the same hard set and rules as Opus 4.5 (30,000-token room,
# 3 runs per item, Batch API for single-turn items, API only); estimates with today's prices (checked 10-29 on
# platform.claude.com pricing: Sonnet 4.6 $3/$15, Opus 4.6 and 4.5 $5/$25, batch -50 %) before sending; the total of this
# week's runs stays under $30; everything before Sat 10-31 18:00 Chicago; then the full passes (agentic item + grading)
# for all three once the measurement locks are free. A model the API does not have is skipped and logged.
# Cap math: the batch path checks the hard stop only between batches, so each budget leaves one batch's worst case
# (every request writing the full 30,000 tokens) below the cap: Sonnet chunks of 20 ($4.50), Opus 4.6 chunks of 5 ($1.90).
# Opus 4.5 (collected $8.39) is capped at $9.70 in its full pass; Sonnet's and Opus 4.6's full passes at their collected
# cost + $0.80 / + $1.20 (the agentic item: its 2x-output estimates $0.70 / $1.16). Target: total <= $29.50. Log: logs/suite/frontier-now.log.
set -u
WS=/home/USER/ai-speed-testing/strata-compare
LOG=$WS/logs/suite/frontier-now.log
R=$WS/suite/results
ITEMS=$(grep '^ITEMS=' $WS/work/suite/opus45-hard.sh | cut -d= -f2)
COMMON=(--mode quick --only agentic,coding,honesty,instruct,math,research,tools --items "$ITEMS" --runs 3 --max-tokens 30000
        --estimate-from opus-4-5-hard-r3)
TARGET=29.50; O45_CAP=9.70; S_AG=0.80; O46_AG=1.20; S_CHUNK=20; S_WORST=4.50; O_CHUNK=5; O_WORST=1.90
mkdir -p "${LOG%/*}"
say() { echo "$(date '+%m-%d %H:%M:%S') $*" >> "$LOG"; }
note() { notify-send -a "Frontier set" "$1" "$2" 2> /dev/null || true; }
late() { [ "$(date +%Y%m%d%H)" -gt 2026103117 ]; }
cost_of() { python3 -c "import json; print(round(float(json.load(open('$R/$1/meta.json')).get('cost_usd') or 0), 2))" 2> /dev/null || echo 0; }
calc() { python3 -c "print(round($1, 2))"; }
busy() {
  local f
  for f in "$WS/tmp/gpu-test.lock" "$WS/tmp/suite/heavy.lock" /home/USER/ai/deep-research/run/bench.lock; do
    [ -e "$f" ] || continue
    flock -n -x "$f" true 2> /dev/null || { echo "${f##*/}"; return 0; }
  done
  return 1
}
collect() {   # collect LABEL MODEL BUDGET CHUNK -> rc (answers only; the agentic item and grading come later)
  say "$1 ($2): collect-only, estimate limit and hard stop \$$3, batches of $4"
  bash "$WS/suite/run.sh" --label "$1" --endpoint "claude:$2" --claude-effort high "${COMMON[@]}" --max-estimate "$3" \
    --budget "$3" --batch-chunk "$4" --collect-only >> "$LOG" 2>&1
  local rc=$?
  say "$1: collect-only ended rc $rc, cost \$$(cost_of $1)"
  return $rc
}
O45=$(cost_of opus-4-5-hard-r3)
say "start: Opus 4.5 collected \$$O45 (capped at \$$O45_CAP with its agentic item); target total <= \$$TARGET"

# 1 Sonnet 4.6
SB=$(calc "min(25.0, $TARGET - $O45_CAP - $S_AG - $S_WORST)")
S_OK=0
if collect sonnet-4-6-hard-r3 claude-sonnet-4-6 "$SB" $S_CHUNK; then S_OK=1
elif grep -q -i -E 'not_found|not found|404' "$R/sonnet-4-6-hard-r3/run.log" 2> /dev/null; then say "Sonnet 4.6 is not available on the API - skipped"; fi
S=$(cost_of sonnet-4-6-hard-r3)

# 2 Opus 4.6, if its estimate still fits
OB=$(calc "min(25.0, $TARGET - $O45_CAP - ($S + $S_AG) - $O46_AG - $O_WORST)")
O_OK=0
if late; then say "Sat 18:00 reached - Opus 4.6 not started"
elif python3 -c "import sys; sys.exit(0 if $OB >= 3 else 1)"; then
  if collect opus-4-6-hard-r3 claude-opus-4-6 "$OB" $O_CHUNK; then O_OK=1
  elif grep -q -i -E 'not_found|not found|404' "$R/opus-4-6-hard-r3/run.log" 2> /dev/null; then say "Opus 4.6 is not available on the API - skipped"
  else say "Opus 4.6 not run or stopped (estimate over \$$OB, or rc != 0) - see above"; fi
else say "Opus 4.6: only \$$OB left under the cap - not run"; fi
O46=$(cost_of opus-4-6-hard-r3)
say "collected: Opus 4.5 \$$O45, Sonnet 4.6 \$$S, Opus 4.6 \$$O46 (total \$$(calc "$O45 + $S + $O46"))"

# 3 the full passes (agentic item + grading) once no measurement holds a lock
while b=$(busy); do
  late && { say "locks still held at Sat 10-31 18:00 ($b) - full passes left for later"; note "Frontier set: grading left" "Locks held at Sat 18:00"; exit 0; }
  sleep 600
done
full() {   # full LABEL MODEL CAP [EFFORT-ARG...]
  local l=$1 m=$2 cap=$3; shift 3
  say "$l: full pass, hard stop \$$cap (label total)"
  bash "$WS/suite/run.sh" --label "$l" --endpoint "claude:$m" "$@" "${COMMON[@]}" --max-estimate 25 --budget "$cap" >> "$LOG" 2>&1
  say "$l: full pass ended rc $?, cost \$$(cost_of $l)"
}
late || full opus-4-5-hard-r3 claude-opus-4-5-20251101 $O45_CAP
[ $S_OK = 1 ] && ! late && full sonnet-4-6-hard-r3 claude-sonnet-4-6 "$(calc "$S + $S_AG")" --claude-effort high
[ $O_OK = 1 ] && ! late && full opus-4-6-hard-r3 claude-opus-4-6 "$(calc "$O46 + $O46_AG")" --claude-effort high
T=$(calc "$(cost_of opus-4-5-hard-r3) + $(cost_of sonnet-4-6-hard-r3) + $(cost_of opus-4-6-hard-r3)")
say "done: Opus 4.5 \$$(cost_of opus-4-5-hard-r3), Sonnet 4.6 \$$(cost_of sonnet-4-6-hard-r3), Opus 4.6 \$$(cost_of opus-4-6-hard-r3) = \$$T"
note "Frontier set done" "Total \$$T - research items need the blind grade"
