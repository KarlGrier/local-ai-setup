#!/bin/bash
# build_kq.sh TREE OUTDIR LABEL - round 19: Release CUDA build (sm_89 + sm_120) of TREE with the K-quant prompt kernels
# (-DSTRATA_MMQ_KQUANTS=ON, the UD-Q4_K_XL file needs them), tests off, at low CPU priority; the binary goes to OUTDIR.
# BUILD_DIR (default build): the build directory inside TREE (b7: build-kq, beside the runbook's IQ3_S build).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; T=$WS/$1; O=$WS/$2; L=$3
cd $T || exit 1
[ -e third_party/llama.cpp ] || ln -sfn $(readlink -f $WS/strata-v0115/third_party/llama.cpp) third_party/llama.cpp
t0=$(date +%s)
B=${BUILD_DIR:-build}
nice -n 10 cmake -G Ninja -S . -B $B -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF -DSTRATA_MMQ_KQUANTS=ON \
  "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc -DSTRATA_GGML_DIR="$PWD/third_party/llama.cpp" > $B-configure.log 2>&1 \
  && nice -n 10 cmake --build $B --target strata -j 16 > $B.log 2>&1
rc=$?
echo "$(date -Is) $1 rc $rc in $(( $(date +%s) - t0 )) s"
[ $rc = 0 ] || exit $rc
mkdir -p $O && cp $B/strata $O/strata && sha256sum $O/strata > $O/SHA256
echo "$L, -DSTRATA_MMQ_KQUANTS=ON, $(git log --oneline -1 | cut -c1-70), tree $(git rev-parse HEAD^{tree})" > $O/SOURCE
cat $O/SOURCE $O/SHA256
