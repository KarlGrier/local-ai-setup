#!/bin/bash
# tagcheck.sh STEP — round 7: read the tag watcher's log at every step (your rule). Prints the lines added since the
# last check, flags any NEW TAG loudly, confirms the watcher process is alive, and records the read in
# logs/r7/tagwatch-reads.log (so every step's read is auditable).
WS=/home/USER/ai-speed-testing/strata-compare; LOG=$WS/logs/r7/tagwatch.log; POS=$WS/tmp/r7/tagwatch.pos
touch $LOG; last=$(cat $POS 2>/dev/null || echo 0); n=$(wc -l < $LOG)
new=$(tail -n +$((last+1)) $LOG); echo $n > $POS
alive=$(pgrep -f 'work/r7/tagwatch.sh' >/dev/null && echo alive || echo NOT-RUNNING)
nt=$(echo "$new" | grep -c 'NEW TAG')
echo "tagcheck [$*] $(date -Is): watcher $alive; $(echo "$new" | grep -c . ) new line(s); last: $(tail -1 $LOG)"
[ "$nt" -gt 0 ] && { echo "!!! NEW TAG(S):"; echo "$new" | grep 'NEW TAG'; }
echo "$(date -Is) step=[$*] watcher=$alive new_lines=$(echo "$new" | grep -c .) new_tags=$nt last=[$(tail -1 $LOG)]" >> $WS/logs/r7/tagwatch-reads.log
