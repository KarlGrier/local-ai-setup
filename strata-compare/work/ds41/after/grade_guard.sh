#!/bin/bash
# grade_guard.sh UNIT - 10-26 18:20 (Karl: "Keep CPU-heavy grading (unit tests) out of the context-cost speed runs: finish it
# before they start, or pause it while they run"): while UNIT (the grading) runs, pauses it (SIGSTOP to every process in
# the unit) as soon as ds41-after starts a context-cost arm ("ctx-32k:" ...), and resumes it (SIGCONT) once the last one
# is done ("context 131072:") or the block has stopped / ended. Log: results/ds41/after/grade_guard.log.
UNIT=${1:?unit}
SC=/home/USER/ai-speed-testing/strata-compare
L=$SC/results/ds41/after/after.log
OUT=$SC/results/ds41/after/grade_guard.log
say() { echo "$(date '+%F %T') $*" >> $OUT; }
paused=0
say "watching $UNIT"
while systemctl --user is-active -q $UNIT; do
  started=$(grep -cE "^=== [0-9-]+ [0-9:]+ ctx-[0-9]+k: " $L)
  done_all=$(grep -cE "^=== [0-9-]+ [0-9:]+ context 131072: |STOPPED" $L)
  if [ "$started" -gt 0 ] && [ "$done_all" -eq 0 ] && systemctl --user is-active -q ds41-after; then
    if [ $paused -eq 0 ]; then systemctl --user kill -s SIGSTOP $UNIT; paused=1; say "context-cost runs started - $UNIT paused"; fi
  elif [ $paused -eq 1 ]; then
    systemctl --user kill -s SIGCONT $UNIT; paused=0; say "context-cost runs done (or the block ended) - $UNIT resumed"
  fi
  sleep 5
done
[ $paused -eq 1 ] && systemctl --user kill -s SIGCONT $UNIT 2>/dev/null
say "$UNIT ended"
