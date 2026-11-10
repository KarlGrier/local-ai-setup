#!/bin/bash
# c17x_pipeline.sh - round 19, the FALLBACK C*17 (the user's plan: upstream's STRATA_SPEC_PROB biases the near-tie case,
# the ground truth with speculation off matches the reference): C*17 = our exact sampling + our cost gate (C*16.1's
# combination, which passed this check) on v0.1.42 (r19-port), STRATA_PREFILL_CPU_SHARE=0.4 below 1,792 tokens.
#   1 build-cstar17x.sh (engine-cstar17 / engine-twin17 / configs Cstar17*, twin17, R17RT, BR17 from r19-port / r19-meas)
#   2 exact7 twice (must repeat 7/7; the short items vs B3's share-0.4 hashes, the long ones vs C*16.1's)
#   3 the sampler check: our exact-sampling chi-square on the build's kernels (ess_test), the near-tie probe on the twin:
#     the suite's 6 cases x 200 and arith-j3 x 2,000 at T 0.6, against the build's own probabilities
#   4 the gates (gates17.sh, REF = step 2's first run)
# A phase end (C*16.1, still promoted) after each step, a kernel check after each. The soak and promotion follow after
# reading these.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r19
P=.venv/bin/python; R=results/r19; O=$R/sp-c17x; mkdir -p $O
step() { echo "=== $(date -Is) $*"; }
pe() { bringup/lib/phase_end.sh r19-$1 keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED" ; }
kc() { bringup/lib/kcheck.sh "c17x-$1" || { step "KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
kc start
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
step "1 build (fallback)"; work/r19/build-cstar17x.sh > logs/r19/build-cstar17x.log 2>&1 || { tail -5 logs/r19/build-cstar17x.log; step "BUILD FAILED"; exit 1; }
head -4 logs/r19/build-cstar17x.log; grep -E '^Cstar17' logs/r19/build-cstar17x.log | cut -c1-250; kc build
step "2 exact7 twice"; export PROMPT_DIR=$WS/bringup/out/r19/prompts
REF=c161 bringup/lib/exact7.sh c17x-e7 configs/Cstar17.json 2>&1 | tail -8 | tee $R/c17x-e7.txt; kc e7
REF=c17x-e7 bringup/lib/exact7.sh c17x-e7b configs/Cstar17.json 2>&1 | tail -1 | tee -a $R/c17x-e7.txt; kc e7b
echo "B3's share-0.4 hashes (C*16.1's series): x-math 2ad1b419 s-math 6148c14a x-code 2c21861d s-code 854d0149" | tee -a $R/c17x-e7.txt
step "3 sampler check"
T17=$($P -c "import json,pathlib; print(pathlib.Path(json.load(open('configs/Cstar17.json'))['server']).parent.parent.name)")
TREE=$T17 bash bringup/lib/ess_test.sh > $O/ess.txt 2>&1; grep -E "ALL PASS|FAIL" $O/ess.txt | tail -1 | tee $O/ess-result.txt
cp bringup/out/accept/acc-c17/sp/sp-cases.json bringup/out/accept/acc-c17/sp/sp-llama.json $O/; rm -f $O/sp-strata-c17x-*.jsonl
TW=$($P -c "import json,pathlib; print(pathlib.Path(json.load(open('configs/twin17.json'))['server']).parent.parent)")
bringup/lib/with_server.sh r19-c17x-sp configs/twin17.json -- "SP_DIR=$O SP_LABEL=c17x-all STRATA_SERVE_TREE=$TW $P bringup/lib/sampling_probe.py strata http://127.0.0.1:8081 200 0.6 > $O/strata-all.txt 2>&1; \
  SP_DIR=$O SP_LABEL=c17x-j3 STRATA_SERVE_TREE=$TW $P bringup/lib/sampling_probe.py strata http://127.0.0.1:8081 2000 0.6 arith-j3 > $O/strata-j3.txt 2>&1; \
  SP_DIR=$O SP_LABEL=c17x-all STRATA_SERVE_TREE=$TW $P bringup/lib/sampling_probe.py strata_logp http://127.0.0.1:8081 > $O/logp.txt 2>&1; \
  grep -m1 -E 'EXACT speculative sampling|probabilistic draft' \$ELOG | cut -c1-100; grep -c 'cost-aware draft length ON' \$ELOG | sed 's/^/gate ON lines: /'" 2>&1 | grep -E 'start|done|EXACT|probabilistic|gate ON'
cp $O/sp-strata-logp-c17x-all.json $O/sp-strata-logp-c17x-j3.json
for l in all j3; do SP_DIR=$O SP_LABEL=c17x-$l STRATA_SERVE_TREE=$TW $P bringup/lib/sampling_probe.py analyze own > $O/analyze-own-$l.txt 2>&1; done
cat $O/analyze-own-all.txt; grep arith-j3 $O/analyze-own-j3.txt
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-150; kc sampler
pe sampler
step "4 gates"; STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
PROMPT_DIR=$WS/bringup/out/r19/prompts work/r19/gates17.sh c17x configs/Cstar17.json configs/R17RT.json configs/BR17.json c17x-e7 > logs/r19/gates17x.log 2>&1
cat $R/g-gates-c17x.txt | grep -v '^PASS stream' | cut -c1-200
pe gates; kc end
step "fallback pipeline (first half) done"
