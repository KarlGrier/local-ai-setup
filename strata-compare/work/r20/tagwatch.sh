#!/bin/bash
# tagwatch.sh - 2026-10-14: hourly check for a Strata tag newer than v0.1.44.1 (read-only ls-remote); exits when one
# appears (prints it) or at 09:00 on 2026-10-15 (Round 20 starts then on the newest tag anyway).
LOG=/home/USER/ai-speed-testing/strata-compare/logs/r20/tagwatch.log
END=$(date -d '2026-10-15 09:00' +%s)
while :; do
  T=$(git -C /home/USER/ai-speed-testing/strata-compare/strata ls-remote --tags origin 2>/dev/null | grep -v '\^{}' | awk '{print $2}' | sed 's#refs/tags/##' | sort -V | tail -1)
  echo "$(date -Is) newest tag: ${T:-?}" >> $LOG
  if [ -n "$T" ] && [ "$(printf '%s\n%s\n' v0.1.44.1 "$T" | sort -V | tail -1)" != v0.1.44.1 ]; then echo "NEW TAG $T at $(date -Is)"; exit 0; fi
  [ $(date +%s) -ge $END ] && { echo "09:00 reached, newest $T"; exit 0; }
  sleep 3600
done
