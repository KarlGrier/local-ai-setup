#!/bin/bash
# run-overnight.sh — the round-4 tests that did not run (NOT started automatically; run it yourself when the PC is free):
# stops C*4 on 8080 (one model server at a time), runs work/r4/overnight-queue.txt through the round-4 queue runner
# (browser test on the C*4 page and on the r4-web fix, 2-hour big-chat soak, llama.cpp needle, extra long-text accuracy
# runs; ~4.5 h in all; output in logs/r4/batch.log), then puts C*4 back on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
STRATA_PORT=8080 ./run-strata.sh stop || true
cp work/r4/overnight-queue.txt work/r4/queue.txt
work/r4/queue.sh                                    # returns at the STOP line
./switch-model.sh strata
