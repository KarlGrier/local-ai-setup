#!/bin/bash
# b443tests.sh — round 10 B.3: #443's own roofline tests from the transplant branch (strata-v36b443), built with tests on
# (sm_89 + sm_120), on BOTH cards (RTX 5080 = CUDA device 0 by UUID, RTX 4060 Ti), under the memory guard:
#   gr_roofline: upstream's read with and without STRATA_GR_DOWN_MAX4 (bitwise parity + µs), STRATA_HC_SPLIT 0/1/2;
#   mmvq_roofline MODEL.gguf: the dense GEMVs of blk.0 / blk.3 + the output head, multi-column kernel vs the single-column
#   oracle, default and STRATA_MMVQ_WARP1=1 (bit diffs + relative L1, µs per call), alternated default / warp1 / warp1 / default.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source work/r10/env.sh
S=$WS/strata-v36b443; D=$WS/results/r10/b443; mkdir -p $D
cd $S
[ -d third_party/llama.cpp ] || cp -a $WS/strata-v0115/third_party/llama.cpp third_party/
cmake -G Ninja -S . -B build-tests -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=ON \
  "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
  -DSTRATA_GGML_DIR="$S/third_party/llama.cpp" > build-tests-configure.log || { tail build-tests-configure.log; exit 1; }
cmake --build build-tests --target gr_roofline mmvq_roofline -j 16 > build-tests.log 2>&1 || { tail -30 build-tests.log; exit 1; }
cd $WS
G=$WS/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf
for card in 5080:GPU-UUID-RTX5080 4060ti:GPU-UUID-RTX4060TI; do
  n=${card%%:*}; u=${card#*:}
  CUDA_VISIBLE_DEVICES=$u .venv/bin/python work/r10/guard.py b443-gr-$n -- $S/build-tests/gr_roofline > $D/gr-$n.out 2>&1; echo "gr_roofline $n exit $? $(tail -1 $D/gr-$n.out)"
  for arm in def w1 w1 def; do
    k=$([ -f $D/mmvq-$n-$arm-1.out ] && echo 2 || echo 1)
    if [ $arm = w1 ]; then E="STRATA_MMVQ_WARP1=1 STRATA_BENCH_ALLOW_ROUNDING=1"; else E=""; fi
    env CUDA_VISIBLE_DEVICES=$u $E .venv/bin/python work/r10/guard.py b443-mmvq-$n-$arm-$k -- $S/build-tests/mmvq_roofline $G > $D/mmvq-$n-$arm-$k.out 2>&1
    echo "mmvq_roofline $n $arm run $k exit $? $(tail -1 $D/mmvq-$n-$arm-$k.out)"
  done
done
