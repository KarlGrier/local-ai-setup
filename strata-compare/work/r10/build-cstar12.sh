#!/bin/bash
# build-cstar12.sh BRANCH — round 10 Phase E (on v0.1.36 since the 12:00 port): clean-checkout build of the C*12 candidate: export the patch series
# v0.1.36..BRANCH into patches/r10c/ (+ SHA256SUMS), clone Strata v0.1.36 (36fa455) from the local repository into
# strata-cstar12/, `git am` the series, check that the tree equals BRANCH's, build like setup.py (Release, ggml + MMQ
# from the pinned llama.cpp 3cf03257) for sm_89 + sm_120, copy to engine-cstar12/strata (+ SHA256, SOURCE). Through the
# queue (no benchmark beside it). Never touches engine-cstar11/ or strata-cstar11/ (C*11 = rollback target).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/work/r10/env.sh
BR=$1
DEST=$WS/strata-cstar12
PD=$WS/patches/r10c
case "$DEST" in *cstar11*) echo "refusing to touch C*11"; exit 1;; esac
rm -rf "$DEST" "$PD"; mkdir -p "$PD"
git -C $WS/strata format-patch -q -o "$PD" v0.1.36..$BR
(cd "$PD" && sha256sum 0*.patch > SHA256SUMS)
WANT=$(git -C $WS/strata rev-parse "$BR^{tree}")
git clone -q "$WS/strata" "$DEST"
cd "$DEST"
git checkout -q 36fa455e579b23a9c909c2c6fe1bddd9e51cb8ca          # v0.1.36
test "$(git rev-parse HEAD)" = "$(git -C $WS/strata rev-parse v0.1.36)"
(cd $PD && sha256sum -c --quiet SHA256SUMS)
git -c user.name=strata-compare -c user.email=339962272+KarlGrier@users.noreply.github.com am -q "$PD"/0*.patch
git log --oneline v0.1.36..HEAD | cat
test "$(git rev-parse HEAD^{tree})" = "$WANT" || { echo "tree differs from $BR"; exit 1; }
cp -a "$WS/strata-v0115/third_party/llama.cpp" third_party/
cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
  "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
  -DSTRATA_GGML_DIR="$DEST/third_party/llama.cpp" > build-configure.log
cmake --build build --target strata -j 16 > build.log 2>&1 || { tail -30 build.log; exit 1; }
mkdir -p $WS/engine-cstar12
cp build/strata $WS/engine-cstar12/strata
sha256sum $WS/engine-cstar12/strata | tee $WS/engine-cstar12/SHA256
echo "Strata v0.1.36 (36fa455) + patches/r10c ($(ls $PD/0*.patch | wc -l) patches, = $BR) (sm_89+sm_120), clean clone $(date -Is); tree $(git rev-parse HEAD^{tree})" > $WS/engine-cstar12/SOURCE
cat $WS/engine-cstar12/SOURCE
