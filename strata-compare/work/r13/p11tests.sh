#!/bin/bash
# p11tests.sh — round 13 Part 1.1 (#838) and 1.5 (iq_multi_parity on this CUDA build): build the kernel parity tools
# with tests on (sm_89 + sm_120, CUDA 13.3) in TWO trees, then run them on both cards under the memory guard:
#   strata-r13t = r13-fix with the two CUDA-built q8_1 sites reverted (= C*13's kernels + the new fixture): must FAIL
#                 the overflow fixture (native_swiglu_quantize_q8_1 and PR245's native_gus) and pass everything else;
#   strata-r13  = r13-fix (#838 + our third site): must pass all.
# Tools: iq_multi_parity (incl. #606/#838's check and check_gus_finite), native_grouped_parity, native_expert_parity,
# shared_expert_parity, mmvq_il_parity (B.3's interleaving quantizer, the clamped q8_1 path it has).
# Needs the GPUs: run through the queue with no model server loaded.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source work/r13/env.sh
D=$WS/results/r13/p11; mkdir -p $D
TOOLS="iq_multi_parity native_grouped_parity native_expert_parity shared_expert_parity mmvq_il_parity"
for T in ${TREES:-strata-r13t strata-r13}; do
  S=$WS/$T; cd $S
  [ -d third_party/llama.cpp ] || cp -a $WS/strata-v0115/third_party/llama.cpp third_party/
  cmake -G Ninja -S . -B build-tests -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=ON \
    "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
    -DSTRATA_GGML_DIR="$S/third_party/llama.cpp" > build-tests-configure.log || { tail build-tests-configure.log; exit 1; }
  avail=""
  for t in $TOOLS; do grep -q "add_executable($t " CMakeLists.txt && avail="$avail $t"; done
  t0=$(date +%s)
  cmake --build build-tests --target $avail -j 16 > build-tests.log 2>&1 || { tail -30 build-tests.log; exit 1; }
  echo "$T: built$avail in $(( $(date +%s) - t0 )) s ($(git rev-parse --short HEAD), dirty $(git status --porcelain -uno | wc -l))"
  cd $WS
  for card in 5080:GPU-UUID-RTX5080 4060ti:GPU-UUID-RTX4060TI; do
    n=${card%%:*}; u=${card#*:}
    for t in $avail; do
      A=""; [ $t = native_expert_parity ] && A=$WS/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf
      CUDA_VISIBLE_DEVICES=$u .venv/bin/python work/r13/guard.py p11-$T-$t-$n${SUF:-} -- $S/build-tests/$t $A > $D/$T-$t-$n${SUF:-}.out 2>&1
      rc=$?
      echo "$T $t $n exit $rc: $(grep -E 'failures|FAIL|PASS|passed|ALL' $D/$T-$t-$n${SUF:-}.out | tail -1 | cut -c1-160)"
    done
    grep -E "q8_1 finite|q8_1 of h" $D/$T-iq_multi_parity-$n${SUF:-}.out | sed "s/^/  $T $n: /"
  done
done
