#!/bin/bash
# a4trace.sh HALF — round 10 A.4, inside work/r11/with_server.sh (the routing-trace build's server on 8081, $ELOG): the
# personal prompts of half HALF (A / B: every other aging-pool topic, both requests of each, and every other chat
# prompt) at your settings; the engine writes tmp/r11/route/R4t-HALF.{dump,r6}. Never the screens or holdouts.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; H=$1
.venv/bin/python work/r5/warmup.py http://127.0.0.1:8081
.venv/bin/python work/r11/ldrbench.py --config R4t-$H-pool --engine-log $ELOG --set pool --ids $(cat tmp/r11/pool-$H.ids)
.venv/bin/python work/r11/ldrbench.py --config R4t-$H-chat --engine-log $ELOG --set chat --file prompts/r10/personal-chat.json --ids $(cat tmp/r11/chat-$H.ids)
