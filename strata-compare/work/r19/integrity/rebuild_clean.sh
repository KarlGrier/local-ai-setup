#!/bin/bash
# rebuild_clean.sh - Round 19 after the RAM fault: every engine build this round can run, rebuilt from a fresh build
# directory (the old one is kept as build.pre-r19) with its original CMake flags, in its original source tree (git fsck and
# the worktree check passed; the tree must be the recorded one and clean). The new binary is compared with the installed
# one: identical -> the installed binary is proven intact (left as is); different -> the old one is kept as strata.pre-r19,
# the new one installed and SHA256 rewritten (a behaviour check follows: exact7 against the recorded references).
# Output: results/r19/integrity/rebuild.txt.   The r19 runbook builds are redone by b1 (clone = fresh trees).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
OUT=results/r19/integrity/rebuild.txt; : > $OUT
NVCC=/usr/local/cuda-13.3/bin/nvcc
one() {   # one NAME TREE EXPECTED_TREE INSTALLED_BINARY KQUANTS TESTS
  local name=$1 T=$WS/$2 want=$3 inst=$WS/$4 kq=$5 tests=$6 t0 rc old new
  t0=$(date +%s)
  [ "$(git -C $T rev-parse HEAD^{tree})" = "$want" ] || { echo "$name: TREE MISMATCH $(git -C $T rev-parse HEAD^{tree}) != $want" | tee -a $OUT; return 1; }
  [ -z "$(git -C $T status --porcelain --untracked-files=no)" ] || { echo "$name: TREE DIRTY" | tee -a $OUT; return 1; }
  [ -e $T/third_party/llama.cpp ] || { echo "$name: no third_party/llama.cpp" | tee -a $OUT; return 1; }
  if [ -d $T/build ]; then rm -rf $T/build.pre-r19; mv $T/build $T/build.pre-r19; fi
  (cd $T && nice -n 5 cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=$tests \
     -DSTRATA_MMQ_KQUANTS=$kq "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=$NVCC \
     -DSTRATA_GGML_DIR="$T/third_party/llama.cpp" > build-configure.r19.log 2>&1 \
   && nice -n 5 cmake --build build --target strata -j 24 > build.r19.log 2>&1)
  rc=$?
  [ $rc = 0 ] || { echo "$name: BUILD FAILED rc $rc (see $T/build.r19.log)" | tee -a $OUT; return 1; }
  old=$(sha256sum < $inst | cut -d' ' -f1); new=$(sha256sum < $T/build/strata | cut -d' ' -f1)
  if [ "$old" = "$new" ]; then
    echo "$name: IDENTICAL $new ($(( $(date +%s) - t0 )) s) - installed binary intact" | tee -a $OUT
  elif [ "${7:-}" = inplace ]; then   # the config runs TREE/build/strata itself: the new build is now the one in use
    echo "$name: DIFFERENT old $old new $new ($(( $(date +%s) - t0 )) s) - the config's build/strata is the new one; old in build.pre-r19" | tee -a $OUT
  else
    cp -p $inst $inst.pre-r19 && cp $T/build/strata $inst && (cd $(dirname $inst) && sha256sum $(basename $inst) > SHA256.new) \
      && echo "$name: DIFFERENT old $old new $new ($(( $(date +%s) - t0 )) s) - new installed, old kept as $(basename $inst).pre-r19" | tee -a $OUT
  fi
}
one c161     strata-r18                      27146e444082ab37aa093684c54ec6d6f1c13e1c engine-cstar161/strata     OFF OFF
TW=$(grep -o 'r18-meas [0-9a-f]*' engine-twin161/SOURCE | cut -d' ' -f2)   # the recorded commit -> its tree
one twin161  tmp/r18/wt-meas                 $(git -C strata rev-parse $TW^{tree}) engine-twin161/strata OFF OFF
one c16      bringup/out/r16z/strata-patched 83801065abf8447824424c7b0ed705545a1e556c engine-cstar16/strata      OFF OFF
one v42kq    tmp/r19/v42-kq                  7417abeee74c20912310306a2b1dc16f9ea7515b tmp/r19/engine-v42-kq/strata ON OFF
one v42main  tmp/r18/v42-main                7417abeee74c20912310306a2b1dc16f9ea7515b tmp/r18/v42-main/build.pre-r19/strata OFF ON inplace
echo "rebuild done $(date -Is)" | tee -a $OUT
