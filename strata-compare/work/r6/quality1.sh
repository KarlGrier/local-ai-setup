#!/bin/bash
# quality1.sh LABEL — round 6: the 5 quality prompts once (32,768-token cap) against the server on 127.0.0.1:8081,
# your chat settings sent explicitly (temperature 1.0, top_p 0.95, top_k 20, min_p 0.05; reasoning = server default)
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
.venv/bin/python scripts/bench.py quality --config $1 --base http://127.0.0.1:8081 --model x --rep 0 --session $1-quality \
  ${ELOG:+--engine-log $ELOG} --extra '{"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}'
