#!/bin/bash
# bench2-retry-run.sh KEY - (Karl 11-06: "Make sure a manual restart can't get stuck refusing a run that's already at
# 3.") Give one bench run that bench2-queue.sh stopped on (or dropped) after 3 failures a fresh count of 3, then start
# the queue. KEY = the run key the alert / NOTES.md line names, SET/PROFILE/LABEL/ID (e.g. screen/deep/pc3c/o02).
# Appends a "reset" line for the unit's plan (BENCH2_PLAN in the unit file) to results/bench2/queue-failures.tsv: the
# queue counts this run's failures (and `bench2.py next` its drop) only after it. A run that also hung twice
# (results/bench2/watchdog-faults.tsv) stays refused by the watchdog rule - the script says so and does not start.
# Starts deep-research-bench.service unless it is already active (then the reset applies when the queue next picks
# the run). One NOTES.md line. Nothing else is changed.
set -u
WS=/home/USER/ai/deep-research
UNIT_NAME=deep-research-bench.service
UNIT=$HOME/.config/systemd/user/$UNIT_NAME
ST=$WS/results/bench2/queue-failures.tsv
[ $# -eq 1 ] && [ -n "$1" ] || { echo "usage: bench2-retry-run.sh SET/PROFILE/LABEL/ID   (the key in the queue's alert)"; exit 2; }
KEY=$1
case $KEY in */*/*/*) ;; *) echo "not a run key (SET/PROFILE/LABEL/ID): $KEY"; exit 2 ;; esac
PLAN=$(sed -n 's/^Environment=BENCH2_PLAN=//p' "$UNIT" 2> /dev/null | tail -1); PLAN=${PLAN:-queue-plan.json}
N=$(awk -F'\t' -v p="$PLAN" -v k="$KEY" '$2 == p && $3 == k { if ($4 == "reset") n = 0; else if ($4 == "fail") n++ } END { print n + 0 }' "$ST" 2> /dev/null || echo 0)
[ "${N:-0}" -gt 0 ] || { echo "no failures of $KEY recorded for $PLAN (the unit's plan) in results/bench2/queue-failures.tsv - nothing to reset"; exit 1; }
printf '%s\t%s\t%s\t%s\t%s\n' "$(date '+%F %T')" "$PLAN" "$KEY" reset "by hand (bench2-retry-run.sh; $N failures before)" >> "$ST"
echo "$KEY on $PLAN: reset (it had $N failures) - a fresh count of 3"
WD=$(awk -F'\t' -v k="$KEY" '$1 == k' "$WS/results/bench2/watchdog-faults.tsv" 2> /dev/null | wc -l)
if [ "$WD" -ge 2 ]; then
  echo "NOTE: $KEY also hung twice (results/bench2/watchdog-faults.tsv) - the watchdog rule still refuses it: remove its lines there first, then run this again (unit not started)"
  echo "* $(date '+%F %H:%M') BENCH QUEUE: $KEY reset by hand (tools/bench2-retry-run.sh; $N failures before, plan $PLAN) - unit NOT started: it also hung twice (watchdog-faults.tsv)." >> "$WS/NOTES.md"
  exit 1
fi
if systemctl --user is-active -q $UNIT_NAME; then
  echo "$UNIT_NAME is running: the reset applies when it next picks $KEY"; S="the queue was running"
else
  systemctl --user start $UNIT_NAME && echo "$UNIT_NAME started" || { echo "systemctl --user start $UNIT_NAME failed"; exit 1; }
  S="$UNIT_NAME started"
fi
echo "* $(date '+%F %H:%M') BENCH QUEUE: $KEY reset by hand (tools/bench2-retry-run.sh; $N failures before, plan $PLAN): a fresh count of 3; $S." >> "$WS/NOTES.md"
exit 0
