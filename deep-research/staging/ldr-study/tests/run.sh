#!/bin/bash
# run.sh - build a patched COPY of the installed LDR package (scratch/testsite = the venv's local_deep_research + the
# staged patches 0007-0009) and run the offline tests against it. Touches nothing outside staging/ldr-study/.
set -euo pipefail
ST=/home/USER/ai/deep-research/staging/ldr-study
SP=/home/USER/ai/deep-research/.venv/lib/python3.12/site-packages
TS=$ST/scratch/testsite
rm -rf "$TS"; mkdir -p "$TS"
nice -n 19 rsync -a --exclude=__pycache__ --exclude='*.before*' "$SP/local_deep_research" "$TS/"
for p in 0007-memwatch 0008-subagent-steps 0009-paper-quotes; do
  patch -d "$TS" -p1 -s -f --no-backup-if-mismatch < "$ST/patches/$p.patch"
done
echo "testsite: installed package + 0007 0008 0009 applied"
LDR_STUDY_TESTSITE="$TS" nice -n 19 taskset -c 31 timeout 300 prlimit --as=4294967296 \
  /home/USER/ai/deep-research/.venv/bin/python -I -B -W ignore "$ST/tests/test_ldr_study.py" "$@"
