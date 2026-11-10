#!/bin/bash
# build-r5de.sh — round 5: build the v0.1.23 / v0.1.24 ports and the v0.1.24 measurement build (sm_120), one after
# the other, after the running screen has ended (so the builds do not disturb its decode numbers); then GO-R5DE.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
until grep -q "END (.*R5c-grb" logs/r5/batch.log; do sleep 10; done
for t in strata-r5d strata-r5e strata-r5e-meas; do
  echo "=== $(date -Is) build $t"
  work/r5/build-dev.sh $t || { echo "BUILD FAILED $t"; exit 1; }
done
touch work/r5/GO-R5DE
echo "=== $(date -Is) builds done, GO-R5DE"
