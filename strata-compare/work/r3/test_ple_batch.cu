// test_ple_batch.cu - round 3 unit test: the batched PLE post-ops (ple_postops_batch) against the per-token path the
// prompt path ran before (native_ple_postops + ple_history_advance per token, as ple_block does with native post-ops
// on), from the same projected keys and values.  Random inputs; bitwise comparison of every token's result and of
// the history after the chunk.  Build: see work/r3/build_test_ple.sh.
#include "strata/kernels/native_ple_postops.hpp"
#include "strata/kernels/ple.hpp"
#include "strata/kernels/ple_batch.hpp"
#include "strata/kernels/ngram.hpp"

#include <cuda_fp16.h>
#include <cuda_runtime.h>

#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>

using namespace strata::kernels;

int main(int argc, char** argv) {
    const int T = argc > 1 ? std::atoi(argv[1]) : 37;
    constexpr int N = NG_N_EMBD, D = NG_HC_DIM, HIST = NG_HIST;
    std::mt19937 rng(1234);
    std::normal_distribution<float> nd(0.0f, 1.0f);
    auto fill = [&](std::vector<float>& v, float s) { for (auto& x : v) x = nd(rng) * s; };
    std::vector<float> K((size_t) T * D), V((size_t) T * N), R((size_t) T * D), hist((size_t) D * HIST);
    std::vector<float> nk(D), nq(D), nc(D);
    std::vector<uint16_t> cw((size_t) 4 * D);
    fill(K, 0.5f); fill(V, 0.3f); fill(R, 1.0f); fill(hist, 0.7f); fill(nk, 1.0f); fill(nq, 1.0f); fill(nc, 1.0f);
    for (auto& w : cw) { __half h = __float2half(nd(rng) * 0.2f); std::memcpy(&w, &h, 2); }

    auto up = [](const void* h, size_t bytes) { void* d = nullptr; cudaMalloc(&d, bytes); cudaMemcpy(d, h, bytes, cudaMemcpyHostToDevice); return d; };
    float *dK = (float*) up(K.data(), K.size() * 4), *dK2 = (float*) up(K.data(), K.size() * 4);
    float *dV = (float*) up(V.data(), V.size() * 4);
    float *dRa = (float*) up(R.data(), R.size() * 4), *dRb = (float*) up(R.data(), R.size() * 4);
    float *dHa = (float*) up(hist.data(), hist.size() * 4), *dHb = (float*) up(hist.data(), hist.size() * 4);
    PleWeights w;
    w.norm_key = (const float*) up(nk.data(), D * 4);
    w.norm_query = (const float*) up(nq.data(), D * 4);
    w.norm_conv = (const float*) up(nc.data(), D * 4);
    w.conv1d_f16 = (const uint16_t*) up(cw.data(), cw.size() * 2);
    cudaStream_t st;
    cudaStreamCreate(&st);

    // A: per token, the buffers ple_block gives native_ple_postops (key->d_query, query/normalized->d_norm)
    float *d_query, *d_norm, *d_gate, *d_gated, *d_conv;
    cudaMalloc(&d_query, D * 4); cudaMalloc(&d_norm, D * 4); cudaMalloc(&d_gate, 64); cudaMalloc(&d_gated, D * 4);
    cudaMalloc(&d_conv, D * 4);
    for (int t = 0; t < T; ++t) {
        NativePlePostopsBuffers b{d_query, d_norm, d_gate, d_gated, d_norm, d_conv, dRa + (size_t) t * D};
        native_ple_postops(dK + (size_t) t * D, dRa + (size_t) t * D, dV + (size_t) t * N, dHa, w, b, st);
        ple_history_advance(dHa, d_norm, st);
    }
    // B: the chunk at once
    float *Q, *G, *g;
    cudaMalloc(&Q, (size_t) T * D * 4); cudaMalloc(&G, (size_t) T * D * 4); cudaMalloc(&g, (size_t) T * 4 * 4);
    ple_postops_batch(dK2, dRb, dV, dHb, w, Q, G, g, dRb, T, st);
    if (cudaStreamSynchronize(st) != cudaSuccess) { std::printf("CUDA error %s\n", cudaGetErrorString(cudaGetLastError())); return 2; }

    std::vector<float> ra(R.size()), rb(R.size()), ha(hist.size()), hb(hist.size());
    cudaMemcpy(ra.data(), dRa, ra.size() * 4, cudaMemcpyDeviceToHost);
    cudaMemcpy(rb.data(), dRb, rb.size() * 4, cudaMemcpyDeviceToHost);
    cudaMemcpy(ha.data(), dHa, ha.size() * 4, cudaMemcpyDeviceToHost);
    cudaMemcpy(hb.data(), dHb, hb.size() * 4, cudaMemcpyDeviceToHost);
    size_t diff_r = 0, diff_h = 0;
    double maxd = 0;
    for (size_t i = 0; i < ra.size(); ++i) if (std::memcmp(&ra[i], &rb[i], 4)) { ++diff_r; maxd = std::fmax(maxd, std::fabs(ra[i] - rb[i])); }
    for (size_t i = 0; i < ha.size(); ++i) if (std::memcmp(&ha[i], &hb[i], 4)) ++diff_h;
    std::printf("T=%d: result %zu of %zu floats differ (max |diff| %.3g), history %zu of %zu differ -> %s\n", T, diff_r,
                ra.size(), maxd, diff_h, ha.size(), (diff_r == 0 && diff_h == 0) ? "BIT-IDENTICAL" : "MISMATCH");
    return (diff_r == 0 && diff_h == 0) ? 0 : 1;
}
