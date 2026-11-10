#!/bin/bash
# basecheck.sh — round 9: the newest tag the release watcher has seen vs the base being built on (v0.1.34 since 21:49). Loud if they differ.
WS=/home/USER/ai-speed-testing/strata-compare; BASE=${BASE:-v0.1.34}
newest=$(grep -o 'newest v[0-9.]*' $WS/logs/r9/tagwatch.log | tail -1 | cut -d' ' -f2)
if [ "$newest" != "$BASE" ]; then echo "!!! BASE $BASE BUT NEWEST RELEASE $newest"; else echo "base $BASE = newest release"; fi
