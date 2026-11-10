#!/bin/bash
# build-variant.sh fix|test|p343|A+B - 10-26 (the user, items 2, 3, 6; Karl's ports): a local test variant of Strata v0.2.6's DeepSeek engine,
# built like build-v026.sh (same toolchain, sm_89 + sm_120, the same llama.cpp checkout, memguard) in its own worktree
# strata-v026<name> at the v0.2.6 tag + apply_variant.py <name>; binary + SOURCE + SHA256 in engine-v026<name>-ds41/
# ("+" in a name becomes "-" in the folders). Configure and build offline (unshare -rn, Karl 10-26). Never posted.
set -euo pipefail
N=$1; ND=${N//+/-}; WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
NVCC=/usr/local/cuda-13.3/bin/nvcc; LL=$(readlink -f strata/third_party/llama.cpp); W=strata-v026$ND; T=v0.2.6
[ -d $W ] || git -C strata worktree add --detach $WS/$W $T > /dev/null
[ "$(git -C $W rev-parse HEAD)" = "$(git -C strata rev-parse $T^{commit})" ] || { echo "$W is not at $T"; exit 1; }
git -C $W checkout -- src/dsv41   # (start from the tag's text every time)
[ -z "$(git -C $W status --porcelain --untracked-files=no)" ] || { echo "$W is dirty"; exit 1; }
PIN=$(cut -d' ' -f1 $W/third_party/ggml/VERSION.txt)
[ "$(git -C $LL rev-parse HEAD)" = "$PIN" ] || { echo "llama.cpp checkout is not $T's pinned ggml $PIN"; exit 1; }
python3 $WS/work/ds41/after/apply_variant.py $N $WS/$W
pgrep -f "work/r22/[b]uild_memguard.sh" > /dev/null || { setsid nohup work/r22/build_memguard.sh 14400 > /dev/null 2>&1 < /dev/null & }
rm -rf $W/build
(cd $W && unshare -rn nice -n 5 cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
   -DSTRATA_BUILD_DSV41=ON "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=$NVCC -DSTRATA_GGML_DIR="$LL" > build-configure.log 2>&1 \
 && unshare -rn nice -n 5 cmake --build build --target strata-dsv41 -j ${BUILD_JOBS:-16} > build.log 2>&1)
E=engine-v026$ND-ds41
mkdir -p $E && cp $W/build/strata-dsv41 $E/strata-dsv41
git -C $W diff > $E/variant.diff
echo "v0.2.6 ($(git -C $W rev-parse HEAD)) + local variant '$N' (variant.diff), target strata-dsv41, built offline" > $E/SOURCE
sha256sum $E/strata-dsv41 > $E/SHA256; cat $E/SOURCE $E/SHA256
