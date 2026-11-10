#!/bin/bash
# basecheck.sh — round 12 (copy of round 11, copy of round 10): the newest release tag in the watcher's latest full ref snapshot (tmp/r12/refs.last, all tags,
# sorted by version) vs the base being built on. Loud if they differ. Also prints the snapshot's age.
WS=/home/USER/ai-speed-testing/strata-compare; BASE=${BASE:-$(cat $WS/tmp/r12/base.tag 2>/dev/null || echo unset)}
SNAP=$WS/tmp/r12/refs.last
newest=$(grep refs/tags $SNAP | cut -f2 | sed 's#refs/tags/##' | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1)
age=$(( ($(date +%s) - $(stat -c %Y $SNAP)) / 60 ))
if [ "$newest" != "$BASE" ]; then echo "!!! BASE $BASE BUT NEWEST RELEASE $newest (snapshot ${age} min old)"; else echo "base $BASE = newest release $newest (snapshot ${age} min old)"; fi
echo "$(date -Is) basecheck base=$BASE newest=$newest snapshot_age_min=$age" >> $WS/logs/r12/tagwatch-reads.log
