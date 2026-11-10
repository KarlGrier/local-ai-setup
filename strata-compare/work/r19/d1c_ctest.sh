#!/bin/bash
# d1c_ctest.sh - round 19 Part D 1: ctest on the v0.1.43 port and on stock v0.1.43 (the builds d1b made in build-tests; d1b's
# own ctest runs wrote to a relative path from inside the build directory and failed - my slip). GPUs free (8080 stopped).
# Kernel check after each. Ends with the promoted build (C*17) on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
R=$WS/results/r19
kc() { bringup/lib/kcheck.sh "$1" || { echo "=== $(date -Is) KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
kc d1c-start
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
for t in patched stock; do
  B=$WS/bringup/out/r19e/strata-$t/build-tests
  [ -f $B/CTestTestfile.cmake ] || { echo "ctest $t: no test build"; continue; }
  echo "=== $(date -Is) ctest $t ($(ctest --test-dir $B -N | tail -1))"
  (cd $B && timeout 3600 ctest --output-on-failure -j 1 > $R/d1-ctest-$t.txt 2>&1)
  echo "ctest $t: $(grep -E 'tests passed|tests failed' $R/d1-ctest-$t.txt | tail -1)"; grep -E '\*\*\*Failed|Not Run|Timeout' $R/d1-ctest-$t.txt | head -8
  kc d1c-$t
done
bringup/lib/phase_end.sh r19-d1c keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) d1c done"
