#!/bin/bash
# ess_probe.sh N — round 9 A.1: round 5's sampling probe (near-ties at j0 = a lone first token and j3 = inside a verify
# window) on the exact-sampling measurement twin with a fixed expert placement: Strata's own forced log-probabilities
# (3 reps) as the reference, N sampled requests per case at your settings (T 1.0), chi-square.  Through the queue.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
export SP_LABEL=ess
rm -f work/r9/sp-strata-ess.jsonl
work/r9/with_server.sh SP-ess configs/R9em-probe.json -- ".venv/bin/python work/r9/sampling_probe.py strata_logp http://127.0.0.1:8081; .venv/bin/python work/r9/sampling_probe.py strata http://127.0.0.1:8081 ${1:-1500} 1.0"
.venv/bin/python work/r9/sampling_probe.py analyze own | tee results/r9/ess-probe.md
grep -c 'EXACT speculative sampling on' logs/engine-R9em-probe.log
