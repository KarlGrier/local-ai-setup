#!/bin/bash
# hold.sh NAME — round 9: the queue waits here (the promoted build stays on 8080) until tmp/r10/go-NAME exists, so a phase
# starts only after I have read the previous phase's results.
WS=/home/USER/ai-speed-testing/strata-compare
echo "=== $(date -Is) hold $1: waiting for tmp/r10/go-$1"
until [ -f $WS/tmp/r10/go-$1 ]; do sleep 30; done
echo "=== $(date -Is) hold $1: released"
