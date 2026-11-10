#!/bin/bash
# e1_cmake0431.sh - #2027 follow-up (2026-10-12): the owner's fix (17d8a171) ships in v0.1.43.1; they could not run a CUDA
# configure and ask us to say if a FIRST configure does not show "Total Tests: 113". Configure only - nothing from
# v0.1.43.1 is built or run (ctest -N only lists): a fresh export of the tag, a fresh build directory, CUDA on + tests
# on with the flags of the issue's steps, then a second configure as the cross-check. Run between suite runs: called
# from work/suite/q4_quick.sh after c171-iq3s-full, before the research capture.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
O=$WS/results/r19/cmake-native-v0431; T=$WS/tmp/r19/cmake-v0431
rm -rf $T $O; mkdir -p $T/src $O
git -C strata archive v0.1.43.1 | tar -x -C $T/src
{ echo "started $(date -Is)"
  echo "v0.1.43.1 = $(git -C strata rev-parse v0.1.43.1^{commit}); 17d8a171 in it: $(git -C strata merge-base --is-ancestor 17d8a171 v0.1.43.1 && echo yes || echo no)"
  grep -n 'option(STRATA_NATIVE_EXPERTS\|if(STRATA_BUILD_TESTS AND STRATA_NATIVE_EXPERTS)' $T/src/CMakeLists.txt
  cmake --version | head -1; /usr/local/cuda-13.3/bin/nvcc --version | tail -2 | head -1; } > $O/source.txt
cd $T/src
nice -n 5 cmake -S . -B build -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=ON -DCMAKE_CUDA_ARCHITECTURES=120 \
  -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc -DSTRATA_GGML_DIR="$(readlink -f $WS/strata/third_party/llama.cpp)" \
  > $O/configure-1.log 2>&1
echo "configure 1: rc $?" >> $O/source.txt
ctest --test-dir build -N > $O/cuda-tests-1.txt 2>&1
nice -n 5 cmake -S . -B build > $O/configure-2.log 2>&1
echo "configure 2: rc $?" >> $O/source.txt
ctest --test-dir build -N > $O/cuda-tests-2.txt 2>&1
{ echo "first configure:  $(tail -1 $O/cuda-tests-1.txt)"
  echo "second configure: $(tail -1 $O/cuda-tests-2.txt)"
  for t in expert_layout_test native_dense_ple_key_test expert_cache_per_layer_test expert_cache_segmented_test; do
    echo "$t in the first configure: $(grep -qw $t $O/cuda-tests-1.txt && echo yes || echo NO)"; done
  echo "finished $(date -Is)"; } >> $O/source.txt
cat $O/source.txt
touch $O/DONE
