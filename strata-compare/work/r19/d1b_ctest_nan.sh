#!/bin/bash
# d1b_ctest_nan.sh - round 19 Part D 1, after the runbook: (1) ctest on the v0.1.43 port and on stock v0.1.43 (the runbook's
# clean trees, tests on, configured twice for the STRATA_NATIVE_EXPERTS ordering bug, GPUs free); (2) the non-finite guard
# with our chat cache: the candidate (runbook r19e's cand.json) with STRATA_NAN_INJECT=1,60, work/r19/nan_chat_test.py.
# Kernel check after each. Ends with the promoted build (C*17) on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
P=.venv/bin/python; R=results/r19; NVCC=/usr/local/cuda-13.3/bin/nvcc
kc() { bringup/lib/kcheck.sh "$1" || { echo "=== $(date -Is) KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
kc d1b-start
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
for t in patched stock; do
  T=$WS/bringup/out/r19e/strata-$t; B=$T/build-tests
  echo "=== $(date -Is) ctest $t: configure x2, build"
  for n in 1 2; do (cd $T && nice -n 5 cmake -G Ninja -S . -B $B -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=ON \
      "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=$NVCC -DSTRATA_GGML_DIR="$T/third_party/llama.cpp" > $B.configure$n.log 2>&1); done
  nice -n 5 cmake --build $B -j 24 > $B.build.log 2>&1 || { echo "ctest $t: BUILD FAILED"; tail -5 $B.build.log; }
  (cd $B && timeout 3600 ctest --output-on-failure -j 1 > $R/d1-ctest-$t.txt 2>&1)
  echo "ctest $t: $(grep -E 'tests passed|tests failed' $R/d1-ctest-$t.txt | tail -1)"; grep -E '\*\*\*Failed|Not Run|Timeout' $R/d1-ctest-$t.txt | head -8
  kc d1b-ctest-$t
done
echo "=== $(date -Is) the non-finite guard with our chat cache"
cp bringup/out/r19e/configs/cand.json configs/r19e-cand.json; [ -f configs/r19e-base.shared-settings.json ] && cp configs/r19e-base.shared-settings.json configs/r19e-cand.shared-settings.json
$P bringup/lib/mkcfg.py r19e-nan r19e-cand env.STRATA_NAN_INJECT=1,60 "_comment=Round 19 Part D: the v0.1.43 port's candidate with STRATA_NAN_INJECT=1,60 (the guard's debug switch)" | cut -c1-60
bringup/lib/with_server.sh r19-d1-nan configs/r19e-nan.json -- "$P work/r19/nan_chat_test.py http://127.0.0.1:8081 \$ELOG $R/d1-nan-chat.json" 2>&1 | grep -E '^A|^B|VERDICT|start|done'
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-150; kc d1b-nan
bringup/lib/phase_end.sh r19-d1b keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) d1b done"
