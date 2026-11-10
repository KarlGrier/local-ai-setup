#!/bin/bash
# build-cstar121.sh BRANCH — round 10 (C*12.1 = C*12 on v0.1.38): clean-checkout build of the C*12.1 candidate: export the patch series
# v0.1.38..BRANCH into patches/r10c38/ (+ SHA256SUMS), clone Strata v0.1.38 (99f3dbd) from the local repository into
# strata-cstar121/, `git am` the series, check that the tree equals BRANCH's, build like setup.py (Release, ggml + MMQ
# from the pinned llama.cpp 3cf03257) for sm_89 + sm_120, copy to engine-cstar121/strata (+ SHA256, SOURCE). Through the
# queue (no benchmark beside it). Never touches engine-cstar11/ or strata-cstar11/ (C*11 = rollback target).
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare
source $WS/work/r10/env.sh
BR=$1
DEST=$WS/strata-cstar121
PD=$WS/patches/r10c38
case "$DEST" in *cstar11|*cstar12) echo "refusing to touch C*11 / C*12"; exit 1;; esac
rm -rf "$DEST" "$PD"; mkdir -p "$PD"
git -C $WS/strata format-patch -q -o "$PD" v0.1.38..$BR
(cd "$PD" && sha256sum 0*.patch > SHA256SUMS)
WANT=$(git -C $WS/strata rev-parse "$BR^{tree}")
git clone -q "$WS/strata" "$DEST"
cd "$DEST"
git checkout -q 99f3dbd0b21d1401b3769e0c0d963913607f380b          # v0.1.38
test "$(git rev-parse HEAD)" = "$(git -C $WS/strata rev-parse v0.1.38)"
(cd $PD && sha256sum -c --quiet SHA256SUMS)
git -c user.name=strata-compare -c user.email=339962272+KarlGrier@users.noreply.github.com am -q "$PD"/0*.patch
git log --oneline v0.1.38..HEAD | cat
test "$(git rev-parse HEAD^{tree})" = "$WANT" || { echo "tree differs from $BR"; exit 1; }
cp -a "$WS/strata-v0115/third_party/llama.cpp" third_party/
cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
  "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
  -DSTRATA_GGML_DIR="$DEST/third_party/llama.cpp" > build-configure.log
cmake --build build --target strata -j 16 > build.log 2>&1 || { tail -30 build.log; exit 1; }
mkdir -p $WS/engine-cstar121
cp build/strata $WS/engine-cstar121/strata
sha256sum $WS/engine-cstar121/strata | tee $WS/engine-cstar121/SHA256
echo "Strata v0.1.38 (99f3dbd) + patches/r10c38 ($(ls $PD/0*.patch | wc -l) patches, = $BR) (sm_89+sm_120), clean clone $(date -Is); tree $(git rev-parse HEAD^{tree})" > $WS/engine-cstar121/SOURCE
cat $WS/engine-cstar121/SOURCE
