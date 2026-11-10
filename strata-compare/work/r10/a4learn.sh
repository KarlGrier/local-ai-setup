#!/bin/bash
# a4learn.sh — round 10 A.4 (#477), inside work/r10/with_server.sh (configs/A4-learn.json: v36-a2, STRATA_ADAPT_HELPER=1,
# --expert-profile-save tmp/r10/prof-learned.bin every 5 min + at QUIT): the same personal traffic the routing traces
# used, both halves (all 60 aging-pool requests + all 24 chat prompts) at your settings. Never the screens or holdouts.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
.venv/bin/python work/r5/warmup.py http://127.0.0.1:8081
.venv/bin/python work/r10/ldrbench.py --config A4L-pool --engine-log $ELOG --set pool --ids $(cat tmp/r10/pool-A.ids tmp/r10/pool-B.ids)
.venv/bin/python work/r10/ldrbench.py --config A4L-chat --engine-log $ELOG --set chat --file prompts/r10/personal-chat.json --ids $(cat tmp/r10/chat-A.ids tmp/r10/chat-B.ids)
