#!/bin/bash
# research_wait.sh - run right after a test takes tmp/gpu-test.lock or tmp/suite/heavy.lock (2026-10-17).
# A deep research from Jan (~/ai/deep-research) holds its model calls while either lock is held (strata-proxy's gate
# on 127.0.0.1:8090); this waits until its call in progress has finished (up to 15 min), so the test has Strata and
# the GPUs to itself. Returns at once when no research proxy runs (or 8090 is something else).
r=$(curl -s -m 960 "http://127.0.0.1:8090/_research/wait-idle?timeout=900" 2>/dev/null)
case $r in
  *'"idle": true'*)  [[ $r == *'"waited_s": 0.0'* ]] || echo "research_wait: deep research paused for this test";;
  *'"idle": false'*) echo "research_wait: WARNING - a deep research call is still running after 15 min";;
esac
exit 0
