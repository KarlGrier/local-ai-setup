#!/bin/bash
# tagwatch.sh — round 15 (copy of round 14) (copy of round 13, round 11, copy of round 10): every 40 min, `git ls-remote` of the Strata repo (tags AND branch heads; no
# fetch). Logs changes to logs/r15/tagwatch.log: "NEW TAG x", "NEW/MOVED BRANCH x sha". Round 11 addition: a new
# release tag (vX.Y.Z) also creates bringup/out/tmp/NEW-RELEASE (round 14: four-part tags like v0.1.40.1 count too)-<tag> so the waiters and phase-boundary checks cannot miss it.
WS=/home/USER/ai-speed-testing/strata-compare; LOG=$WS/logs/r15/tagwatch.log; LAST=$WS/tmp/r15/refs.last
URL=https://github.com/Niko1221/Strata
echo $$ > $WS/tmp/r15/tagwatch.pid
while true; do
  now=$(timeout 60 git ls-remote --tags --heads --refs "$URL" 2>&1 | sort -k2)
  if [ $? -ne 0 ] || [ -z "$now" ] || ! echo "$now" | grep -q refs/tags; then echo "$(date -Is) ls-remote failed: $(echo "$now" | head -1)" >> $LOG
  else
    if [ -f $LAST ]; then
      newtags=$(comm -13 <(grep refs/tags $LAST | cut -f2 | sort) <(echo "$now" | grep refs/tags | cut -f2 | sort) | sed 's#^refs/tags/##')
      [ -n "$newtags" ] && echo "$newtags" | sed "s#^#$(date -Is) NEW TAG #" >> $LOG
      for t in $newtags; do echo "$t" | grep -qE '^v[0-9]+(\.[0-9]+){2,3}$' && echo "$(date -Is) $t" > $WS/bringup/out/tmp/NEW-RELEASE-$t; done
      comm -13 <(grep refs/heads $LAST | sort) <(echo "$now" | grep refs/heads | sort) | awk -v d="$(date -Is)" '{sub("refs/heads/","",$2); print d" NEW/MOVED BRANCH "$2" "substr($1,1,10)}' >> $LOG
    fi
    echo "$now" > $LAST
    echo "$(date -Is) checked: $(echo "$now" | grep -c refs/tags) tags, newest $(echo "$now" | grep refs/tags | cut -f2 | sed 's#refs/tags/##' | sort -V | tail -1); branches: $(echo "$now" | grep refs/heads | awk '{sub("refs/heads/","",$2); printf "%s@%s ", $2, substr($1,1,8)}')" >> $LOG
  fi
  sleep 2400
done
