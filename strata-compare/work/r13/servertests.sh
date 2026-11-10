#!/bin/bash
# servertests.sh DIR — round 10: upstream's server unit tests (the 7 serve/test_*.py modules) in a Strata checkout, as
# after every port (your rule). CPU only; no model, no GPU, no network (localhost only).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; D=$1
cd "$D" && $WS/.venv/bin/python -m unittest serve.test_server serve.test_detok serve.test_lifecycle serve.test_mcp \
  serve.test_monitor serve.test_structured serve.test_winjob 2>&1 | tail -4
