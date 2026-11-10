#!/bin/bash
# hold.sh NAME — round 18 (copy of round 16): the queue waits here until tmp/r18/go-NAME exists (a decision of mine); the waiter returns
# when it sees the hold line.
WS=/home/USER/ai-speed-testing/strata-compare
echo "=== $(date -Is) hold $1: waiting for tmp/r18/go-$1"
until [ -f $WS/tmp/r18/go-$1 ]; do sleep 10; done
echo "=== $(date -Is) hold $1: released"
