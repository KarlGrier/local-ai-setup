#!/bin/bash
# restart_after.sh - 10-26 16:05 (Karl: the final config's rounding check + the daily end tests in this block, "wherever it's
# least disruptive"): the running ds41-after (started 14:14) holds its 14:14 code. At the boundary after the Qwen graded run
# (its "graded set Qwen:" line, then the next arm's start line "g-ds50:") the unit is stopped - the effort-50 arm has only
# just begun its server - and started again from the same state.json with the new code: done steps are skipped, the gap
# stays held (ds41-after-gaplock), the new steps (final_gate, daily_tests) run, then the effort-50 run starts over.
# Anything else (STOPPED, the unit ending on its own): nothing restarts. Log: results/ds41/after/restart.log.
SC=/home/USER/ai-speed-testing/strata-compare
L=$SC/results/ds41/after/after.log
OUT=$SC/results/ds41/after/restart.log
say() { echo "$(date '+%F %T') $*" >> $OUT; }
since() { sed -n '/15:56:33 launcher smoke test/,$p' $L; }
until since | grep -qE "^=== [0-9-]+ [0-9:]+ g-ds50: |STOPPED"; do
  systemctl --user is-active -q ds41-after || { say "ds41-after ended on its own - no restart"; exit 0; }
  sleep 3
done
if since | grep -q "STOPPED"; then say "the block STOPPED - no restart"; exit 0; fi
say "boundary reached (g-ds50 starting) - stopping ds41-after"
systemctl --user stop ds41-after
for i in $(seq 1 60); do [ -z "$(pgrep -x strata-dsv41)" ] && break; sleep 1; done
for p in $(pgrep -x strata-dsv41); do kill -9 $p; say "killed a leftover engine pid $p"; done
systemctl --user is-active -q ds41-after-gaplock.scope && say "gap still held (ds41-after-gaplock)" || say "WARNING: the gap lock scope is not active"
sleep 5
systemd-run --user --unit ds41-after --collect -p WorkingDirectory=$SC /usr/bin/python3 -u $SC/work/ds41/after/after.py >> $OUT 2>&1
say "ds41-after restarted with the new code (rc $?)"
