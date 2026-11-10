#!/bin/bash
# post_daily.sh - 10-26 14:30: waits for ds41-after's launcher smoke test (the line "launcher smoke test on 8086") and then
# runs post_daily.py (the daily config -> its own learning profile, seeded once from the pinned seed); if the block ends
# without writing the daily config, it says so and changes nothing. Log: results/ds41/after/post_daily.log.
SC=/home/USER/ai-speed-testing/strata-compare
L=$SC/results/ds41/after/after.log
OUT=$SC/results/ds41/after/post_daily.log
until grep -q "launcher smoke test on 8086" $L; do
  if ! systemctl --user is-active -q ds41-after; then
    echo "$(date '+%F %T') ds41-after ended without the smoke test - nothing changed" >> $OUT
    exit 0
  fi
  sleep 30
done
sleep 10   # (its stop and the engine's exit write the profile first)
if [ -f $SC/configs/DS41-daily.json ]; then
  python3 $SC/work/ds41/after/post_daily.py >> $OUT 2>&1
  echo "$(date '+%F %T') post_daily.py rc $?" >> $OUT
else
  echo "$(date '+%F %T') no configs/DS41-daily.json - nothing changed" >> $OUT
fi
