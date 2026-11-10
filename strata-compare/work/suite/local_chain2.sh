#!/bin/bash
# local_chain2.sh — 2026-10-12 21:2x: the second pass of the local chain's Q4 step. The first pass (local_chain.sh) ran
# the research capture, the #2027 configure and the #2028 hook check, then stopped before the Q4 run: its "server still
# running" check matched with_server.sh's monitor (fixed in q4_quick.sh). The API jobs' finish phase took the free lock
# at 21:21:50 (Opus 4.5, Sonnet 4.6: agentic items + grading); this waits for it, then holds tmp/suite/heavy.lock for
# work/suite/q4_quick.sh (step 0 and the two checks skip themselves: cache frozen, results present), so the Q4 run and
# the API jobs' heavy work never overlap. 8080 stays stopped until q4_quick.sh's step 3.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
step() { echo "=== $(date -Is) $*"; }
rm -f tmp/suite/LOCAL_CHAIN_DONE
exec 9> tmp/suite/heavy.lock
step "waiting for the heavy lock (the API jobs' finish phase)"
flock 9
step "lock held"
bash work/suite/q4_quick.sh
step "Q4 script ended with $?"
touch tmp/suite/LOCAL_CHAIN_DONE
step "local chain done; lock released"
