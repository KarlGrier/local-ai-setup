#!/bin/bash
# hold.sh NAME — round 16 (copy of round 15): the queue waits here until tmp/r16/go-NAME exists (a decision of mine); the waiter returns
# when it sees the hold line.
WS=/home/USER/ai-speed-testing/strata-compare
echo "=== $(date -Is) hold $1: waiting for tmp/r16/go-$1"
until [ -f $WS/tmp/r16/go-$1 ]; do sleep 10; done
echo "=== $(date -Is) hold $1: released"
