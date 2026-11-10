#!/bin/bash
# build-cstar131.sh BRANCH — round 13 (C*13.1 = Round 13 Parts 1-2 on v0.1.39; copy of round 11 build-cstar13.sh): clean-checkout build of the C*13.1 candidate: export the patch series
# v0.1.39..BRANCH into patches/r13c39/ (+ SHA256SUMS), clone Strata v0.1.39 (6f32ec0) from the local repository into
# strata-cstar131/, `git am` the series, check that the tree equals BRANCH's, build like setup.py (Release, ggml + MMQ
# from the pinned llama.cpp 3cf03257) for sm_89 + sm_120, copy to engine-cstar131/strata (+ SHA256, SOURCE). Through the
# queue (no benchmark beside it). Never touches C*11 / C*12 / C*12.1 (C*12.1 = the rollback target).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/work/r13/env.sh
BR=$1
DEST=$WS/strata-cstar131
PD=$WS/patches/r13c39
case "$DEST" in *cstar13|*cstar121) echo "refusing to touch C*13 / C*12.1 (the rollback targets)"; exit 1;; esac
rm -rf "$DEST" "$PD"; mkdir -p "$PD"
git -C $WS/strata format-patch -q -o "$PD" v0.1.39..$BR
(cd "$PD" && sha256sum 0*.patch > SHA256SUMS)
WANT=$(git -C $WS/strata rev-parse "$BR^{tree}")
git clone -q "$WS/strata" "$DEST"
cd "$DEST"
git checkout -q 6f32ec070f23ced9f50e704d854d775da52591ab          # v0.1.39
test "$(git rev-parse HEAD)" = "$(git -C $WS/strata rev-parse v0.1.39)"
(cd $PD && sha256sum -c --quiet SHA256SUMS)
git -c user.name=strata-compare -c user.email=339962272+KarlGrier@users.noreply.github.com am -q "$PD"/0*.patch
git log --oneline v0.1.39..HEAD | cat
test "$(git rev-parse HEAD^{tree})" = "$WANT" || { echo "tree differs from $BR"; exit 1; }
cp -a "$WS/strata-v0115/third_party/llama.cpp" third_party/
cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
  "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
  -DSTRATA_GGML_DIR="$DEST/third_party/llama.cpp" > build-configure.log
cmake --build build --target strata -j 16 > build.log 2>&1 || { tail -30 build.log; exit 1; }
mkdir -p $WS/engine-cstar131
cp build/strata $WS/engine-cstar131/strata
sha256sum $WS/engine-cstar131/strata | tee $WS/engine-cstar131/SHA256
echo "Strata v0.1.39 (6f32ec0) + patches/r13c39 ($(ls $PD/0*.patch | wc -l) patches, = $BR) (sm_89+sm_120), clean clone $(date -Is); tree $(git rev-parse HEAD^{tree})" > $WS/engine-cstar131/SOURCE
cat $WS/engine-cstar131/SOURCE
