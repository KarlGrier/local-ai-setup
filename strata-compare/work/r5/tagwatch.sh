#!/bin/bash
# tagwatch.sh — round 5: every 45 min, `git ls-remote --tags` of the Strata repo (no fetch, no polling beyond that);
# logs the tag list when it changes to logs/r5/tagwatch.log (a line "NEW TAG ..." for each new one).
WS=/home/USER/ai-speed-testing/strata-compare; LOG=$WS/logs/r5/tagwatch.log; LAST=$WS/tmp/r5/tags.last
URL=https://github.com/Niko1221/Strata
while true; do
  now=$(timeout 60 git ls-remote --tags --refs "$URL" 2>&1 | sort)
  if [ $? -ne 0 ] || [ -z "$now" ]; then echo "$(date -Is) ls-remote failed: $(echo "$now" | head -1)" >> $LOG
  else
    if [ -f $LAST ]; then
      comm -13 <(cut -f2 $LAST | sort) <(echo "$now" | cut -f2 | sort) | sed "s#^#$(date -Is) NEW TAG #" >> $LOG
    fi
    echo "$now" > $LAST
    echo "$(date -Is) checked: $(echo "$now" | wc -l) tags, newest $(echo "$now" | cut -f2 | sed 's#refs/tags/##' | sort -V | tail -1)" >> $LOG
  fi
  sleep 2700
done
