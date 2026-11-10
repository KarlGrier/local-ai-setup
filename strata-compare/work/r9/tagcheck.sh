#!/bin/bash
# tagcheck.sh STEP — round 9: read the watcher log at every step; flags NEW TAG / branch moves; records the read.
WS=/home/USER/ai-speed-testing/strata-compare; LOG=$WS/logs/r9/tagwatch.log; POS=$WS/tmp/r9/tagwatch.pos
touch $LOG; last=$(cat $POS 2>/dev/null || echo 0); n=$(wc -l < $LOG)
new=$(tail -n +$((last+1)) $LOG); echo $n > $POS
pid=$(cat $WS/tmp/r9/tagwatch.pid 2>/dev/null); alive=NOT-RUNNING
[ -n "$pid" ] && grep -q tagwatch.sh /proc/$pid/cmdline 2>/dev/null && alive=alive
nt=$(echo "$new" | grep -c 'NEW TAG'); nb=$(echo "$new" | grep -c 'BRANCH')
echo "tagcheck [$*] $(date -Is): watcher $alive; $(echo "$new" | grep -c . ) new line(s); last: $(tail -1 $LOG | cut -c1-220)"
[ "$nt" -gt 0 ] && { echo "!!! NEW TAG(S):"; echo "$new" | grep 'NEW TAG'; }
[ "$nb" -gt 0 ] && { echo "branch changes:"; echo "$new" | grep 'BRANCH'; }
echo "$(date -Is) step=[$*] watcher=$alive new_lines=$(echo "$new" | grep -c .) new_tags=$nt branch_changes=$nb" >> $WS/logs/r9/tagwatch-reads.log
