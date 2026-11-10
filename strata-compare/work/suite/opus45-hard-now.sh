#!/bin/bash
# opus45-hard-now.sh - copy of opus45-hard.sh, run 10-29 on the expiring credits (Karl 10-29). Original: Karl 10-27: Opus 4.5 on the hard set, 11-02 (results/OPUS45-PLAN-1027.md). The same 30,000-token room
# as the local runs (thinking budget 28,976), 3 runs per item, effort high (the suite's highest for Opus 4.5), estimate
# under $25 or nothing is sent, hard stop $25. The key is read by the suite from its own file only (never here).
# Started by suite-opus45-hard.timer (user unit, Persistent: a missed start runs at the next boot). Only inside
# 11-01 .. 11-24 (Opus 4.5 is guaranteed until 11-24; no Claude spending before November).
# Beside a measurement (strata-compare's GPU test lock, the suite's heavy lock or LDR's bench lock held): --collect-only
# first (API calls only - no agentic item, no local grading), then the same command again once the locks are free (adds
# the agentic item and grades). Log: logs/suite/opus45-hard.log; a desktop notice at the end.
# 10-27 (Karl): his monthly API credits are low until they reset - nothing is sent before Karl confirms the reset: the
# run waits for the file tmp/suite/opus45-credits-ok (written when Karl says so; `touch` it to confirm). The timer fires
# daily at 09:00 from 11-02 to 11-24; each day without the file it logs, sends one desktop notice and exits.
set -u
WS=/home/USER/ai-speed-testing/strata-compare
LOG=$WS/logs/suite/opus45-hard.log
LABEL=opus-4-5-hard-r3
ITEMS=coding/c01_parse_duration,coding/c14_semver,coding/c16_json_parser,coding/c19_mini_regex,coding/c24_exact_calc,coding/c23_refactor_orderbook,coding/c02_rle,coding/c07_rpn,coding/c05_wrap,math/m03,math/m08,math/m05,math/m09,math/m15,tools/t03_currency,tools/t06_nested_ticket,agentic/a2_textstats,honesty/h01_cartographer,honesty/h03_viirmets,honesty/h05_strondalsvik,honesty/h06_ostrava_linden,honesty/h07_glasbienen,honesty/h11_borovanadic,honesty/h12_pan_baltic_1923,honesty/h14_einstein_dentist,instruct/i14_quadsept,instruct/i15_title_rule,research/r02_best_model,research/r05_gpu_price
ARGS=(--label $LABEL --endpoint claude:claude-opus-4-5-20251101 --mode quick --only agentic,coding,honesty,instruct,math,research,tools
      --items $ITEMS --runs 3 --max-tokens 30000 --estimate-from h1026-qwen-xhigh --max-estimate 25 --budget 25)
mkdir -p "${LOG%/*}"
say() { echo "$(date '+%m-%d %H:%M:%S') $*" >> "$LOG"; }
today=$(date +%Y%m%d)
# 10-29 (Karl): run NOW on the promotional credits that expire 11-01 UTC (same settings); must finish before
# Sat 10-31 18:00 Chicago. The 11-02 timer then finds the run complete and does nothing.
if [ "$today" -lt 20261029 ] || [ "$today" -gt 20261031 ]; then say "outside 10-29..10-31 (the expiring credits) - not run"; exit 0; fi
if grep -q '"status": "complete"' "$WS/suite/results/$LABEL/meta.json" 2>/dev/null; then say "$LABEL is complete already"; exit 0; fi
OK_FILE=$WS/tmp/suite/opus45-credits-ok
if [ ! -f "$OK_FILE" ]; then
  say "waiting for Karl's OK that the monthly API credits have reset ($OK_FILE missing) - not run today"
  notify-send -a "Opus 4.5 hard set" "Opus 4.5 run is waiting for your OK" "It starts once you confirm your API credits have reset (tell Claude, or: touch ~/ai-speed-testing/strata-compare/tmp/suite/opus45-credits-ok). Window ends 11-24." 2> /dev/null || true
  exit 0
fi
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
  [ $rc -eq 0 ] || { notify-send -a "Opus 4.5 hard set" "Opus 4.5 hard-set run stopped (rc $rc)" "See logs/suite/opus45-hard.log" 2> /dev/null; exit $rc; }
  while b=$(busy); do
    [ "$(date +%Y%m%d%H)" -gt 2026103117 ] && { say "locks still held at Sat 10-31 18:00 - grading left for later"; exit 0; }
    sleep 600
  done
fi
say "full pass (agentic item + grading)"
bash "$WS/suite/run.sh" "${ARGS[@]}" >> "$LOG" 2>&1; rc=$?
cost=$(python3 -c "import json; print(json.load(open('$WS/suite/results/$LABEL/meta.json')).get('cost_usd'))" 2> /dev/null)
say "done (rc $rc, cost \$${cost:-?})"
notify-send -a "Opus 4.5 hard set" "Opus 4.5 hard set: $([ $rc -eq 0 ] && echo done || echo "stopped (rc $rc)")" "Cost \$${cost:-?}. Research items still need the blind grade. suite/results/$LABEL" 2> /dev/null || true
exit $rc
