// test_mmvf_multi.cu - round 3: bf16_gemv_fp32_mmvf_multi against bf16_gemv_fp32_mmvf per token (bitwise), and timing.
#include "strata/kernels/bf16_gemv.hpp"
#include <cuda_runtime.h>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
using namespace strata::kernels;
int main() {
    std::mt19937 rng(11);
    std::normal_distribution<float> nd(0.0f, 1.0f);
    const int n_in = 2560, MT = 8;
    int bad = 0;
    cudaStream_t st; cudaStreamCreate(&st);
    cudaEvent_t e0, e1; cudaEventCreate(&e0); cudaEventCreate(&e1);
    for (int n_out : {512, 128, 1}) {
        std::vector<uint16_t> w((size_t) n_out * n_in);
        for (auto& v : w) { float f = nd(rng) * 0.05f; uint32_t i; std::memcpy(&i, &f, 4); v = (uint16_t) (i >> 16); }
        std::vector<float> x((size_t) MT * n_in);
        for (auto& v : x) v = nd(rng);
        uint16_t* dw; float *dx, *ya, *yb;
        cudaMalloc(&dw, w.size() * 2); cudaMalloc(&dx, x.size() * 4); cudaMalloc(&ya, MT * n_out * 4); cudaMalloc(&yb, MT * n_out * 4);
        cudaMemcpy(dw, w.data(), w.size() * 2, cudaMemcpyHostToDevice); cudaMemcpy(dx, x.data(), x.size() * 4, cudaMemcpyHostToDevice);
        for (int T = 1; T <= MT; ++T) {
            for (int t = 0; t < T; ++t) bf16_gemv_fp32_mmvf(dx + t * n_in, dw, ya + t * n_out, n_in, n_out, st);
            bf16_gemv_fp32_mmvf_multi(dx, n_in, dw, yb, n_out, n_in, n_out, T, st);
            cudaStreamSynchronize(st);
            std::vector<float> a(T * n_out), b(T * n_out);
            cudaMemcpy(a.data(), ya, a.size() * 4, cudaMemcpyDeviceToHost); cudaMemcpy(b.data(), yb, b.size() * 4, cudaMemcpyDeviceToHost);
            int d = 0; for (size_t i = 0; i < a.size(); ++i) d += std::memcmp(&a[i], &b[i], 4) != 0;
            if (d) { ++bad; std::printf("n_out=%d T=%d: %d of %zu differ\n", n_out, T, d, a.size()); }
            if (T == 4 && n_out == 512) {
                float ms[2];
                for (int which = 0; which < 2; ++which) {
                    cudaEventRecord(e0, st);
                    for (int r = 0; r < 200; ++r) {
                        if (which == 0) for (int t = 0; t < T; ++t) bf16_gemv_fp32_mmvf(dx + t * n_in, dw, ya + t * n_out, n_in, n_out, st);
                        else bf16_gemv_fp32_mmvf_multi(dx, n_in, dw, yb, n_out, n_in, n_out, T, st);
                    }
                    cudaEventRecord(e1, st); cudaEventSynchronize(e1); cudaEventElapsedTime(&ms[which], e0, e1);
                }
                std::printf("router shape, T=4: %.1f us per token-loop -> %.1f us multi\n", ms[0] * 5.0f, ms[1] * 5.0f);
            }
        }
    }
    std::printf("%s\n", bad ? "MISMATCH" : "bf16_gemv_fp32_mmvf_multi: BIT-IDENTICAL to per-token (n_out 512/128/1, T=1..8)");
    return bad;
}
