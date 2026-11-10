#!/bin/bash
# local_chain.sh — the local part of the model-suite order, holding tmp/suite/heavy.lock the whole time so the API
# jobs' heavy work (agentic loops, sandboxed tests, Chromium renders) never overlaps a local run:
#   1. wait for c171-iq3s-full (started 11:44 before this lock existed); if it stopped early (endpoint error), resume
#      it (the suite resumes where it stopped), at most twice
#   2. the Q4 quick run (work/suite/q4_quick.sh: C*17.1 stopped, Q4 guarded on 8081 with its own 6 GiB floor,
#      C*17.1 back on 8080, then grading) — only if the full run completed
#   3. touch tmp/suite/LOCAL_CHAIN_DONE and release the lock
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
step() { echo "=== $(date -Is) $*"; }
exec 9> tmp/suite/heavy.lock
flock 9
step "lock held"
CON=tmp/suite/c171-iq3s-full.console
for attempt in 1 2 3; do
  until grep -q "^exit [0-9]" $CON; do sleep 30; done
  rc=$(grep "^exit [0-9]" $CON | tail -1 | cut -d' ' -f2)
  st=$(.venv/bin/python -c "import json; print(json.load(open('suite/results/c171-iq3s-full/meta.json')).get('status'))")
  step "c171-iq3s-full: exit $rc, status $st"
  [ "$rc" = 0 ] && [ "$st" = complete ] && break
  [ $attempt = 3 ] && { step "full run did not complete after 2 resumes - Q4 not started"; touch tmp/suite/LOCAL_CHAIN_DONE; exit 1; }
  step "resuming c171-iq3s-full (attempt $attempt)"
  suite/run.sh --label c171-iq3s-full --endpoint http://127.0.0.1:8080 --mode full >> $CON 2>&1; echo "exit $?" >> $CON
done
step "Q4 quick run"
work/suite/q4_quick.sh
step "Q4 script ended with $?"
touch tmp/suite/LOCAL_CHAIN_DONE
step "local chain done; lock released"
