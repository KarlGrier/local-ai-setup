#!/bin/bash
# tagwatch.sh — round 10: every 40 min, `git ls-remote` of the Strata repo (tags AND branch heads, so release candidates
# show up too; no fetch). Logs changes to logs/r10/tagwatch.log: "NEW TAG x", "NEW/MOVED BRANCH x sha".
WS=/home/USER/ai-speed-testing/strata-compare; LOG=$WS/logs/r10/tagwatch.log; LAST=$WS/tmp/r10/refs.last
URL=https://github.com/Niko1221/Strata
echo $$ > $WS/tmp/r10/tagwatch.pid
while true; do
  now=$(timeout 60 git ls-remote --tags --heads --refs "$URL" 2>&1 | sort -k2)
  if [ $? -ne 0 ] || [ -z "$now" ] || ! echo "$now" | grep -q refs/tags; then echo "$(date -Is) ls-remote failed: $(echo "$now" | head -1)" >> $LOG
  else
    if [ -f $LAST ]; then
      comm -13 <(grep refs/tags $LAST | cut -f2 | sort) <(echo "$now" | grep refs/tags | cut -f2 | sort) | sed "s#^refs/tags/#$(date -Is) NEW TAG #" >> $LOG
      comm -13 <(grep refs/heads $LAST | sort) <(echo "$now" | grep refs/heads | sort) | awk -v d="$(date -Is)" '{sub("refs/heads/","",$2); print d" NEW/MOVED BRANCH "$2" "substr($1,1,10)}' >> $LOG
    fi
    echo "$now" > $LAST
    echo "$(date -Is) checked: $(echo "$now" | grep -c refs/tags) tags, newest $(echo "$now" | grep refs/tags | cut -f2 | sed 's#refs/tags/##' | sort -V | tail -1); branches: $(echo "$now" | grep refs/heads | awk '{sub("refs/heads/","",$2); printf "%s@%s ", $2, substr($1,1,8)}')" >> $LOG
  fi
  sleep 2400
done
