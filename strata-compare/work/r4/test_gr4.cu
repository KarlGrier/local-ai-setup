// test_gr4.cu - round 4 unit test: fused_gr_read_multi with the round-4 kernels against the previous kernels
// (fused_gr_multi_set_old(true)) on random inputs, T = 1..8, apply on/off, inject on/off.
// Every output (lo, rs, inject_out, mixed, R updated in place) must be bit-identical.  Also times both.
#include "strata/kernels/fused_gr.hpp"

#include <cuda_runtime.h>

#include <cstdio>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <random>
#include <vector>

using namespace strata::kernels;
constexpr int N = 2560, HC = 4, D = N * HC, LR = 320, MT = kFusedGrMaxT;

static uint16_t bf(float f) { uint32_t i; std::memcpy(&i, &f, 4); return (uint16_t) ((i + 0x7fff + ((i >> 16) & 1)) >> 16); }

struct Bufs {
    float *R, *bo, *inj_prev, *lo, *rs, *inj_out, *mixed, *xn;
};

int main() {
    std::mt19937 rng(7);
    std::normal_distribution<float> nd(0.0f, 1.0f);
    auto rnd = [&](size_t n, float s) { std::vector<float> v(n); for (auto& x : v) x = nd(rng) * s; return v; };
    auto dev = [](const void* h, size_t bytes) { void* d; cudaMalloc(&d, bytes); cudaMemcpy(d, h, bytes, cudaMemcpyHostToDevice); return d; };
    auto bfv = [&](size_t n, float s) { std::vector<uint16_t> v(n); for (auto& x : v) x = bf(nd(rng) * s); return v; };
    const auto wn = rnd(D, 1.0f);
    const auto wd = bfv((size_t) LR * D, 0.02f), wu = bfv((size_t) D * LR, 0.05f), wi = bfv((size_t) HC * D, 0.02f);
    const float* d_wn = (const float*) dev(wn.data(), wn.size() * 4);
    const uint16_t* d_wd = (const uint16_t*) dev(wd.data(), wd.size() * 2);
    const uint16_t* d_wu = (const uint16_t*) dev(wu.data(), wu.size() * 2);
    const uint16_t* d_wi = (const uint16_t*) dev(wi.data(), wi.size() * 2);
    const auto R0 = rnd((size_t) MT * D, 1.0f), bo0 = rnd((size_t) MT * N, 0.5f), ip0 = rnd((size_t) MT * HC, 1.0f);
    auto make = [&]() {
        Bufs b;
        b.R = (float*) dev(R0.data(), R0.size() * 4);
        b.bo = (float*) dev(bo0.data(), bo0.size() * 4);
        b.inj_prev = (float*) dev(ip0.data(), ip0.size() * 4);
        cudaMalloc(&b.lo, (size_t) MT * LR * 4); cudaMalloc(&b.rs, (size_t) MT * HC * 4);
        cudaMalloc(&b.inj_out, (size_t) MT * HC * 4); cudaMalloc(&b.mixed, (size_t) MT * N * 4);
        cudaMalloc(&b.xn, (size_t) fused_gr_scratch_floats(MT) * 4);
        return b;
    };
    auto reset = [&](Bufs& b) {
        cudaMemcpy(b.R, R0.data(), R0.size() * 4, cudaMemcpyHostToDevice);
        cudaMemset(b.lo, 0, (size_t) MT * LR * 4); cudaMemset(b.rs, 0, (size_t) MT * HC * 4);
        cudaMemset(b.inj_out, 0, (size_t) MT * HC * 4); cudaMemset(b.mixed, 0, (size_t) MT * N * 4);
    };
    Bufs A = make(), B = make();
    cudaStream_t st; cudaStreamCreate(&st);
    cudaEvent_t e0, e1; cudaEventCreate(&e0); cudaEventCreate(&e1);
    int bad = 0;
    for (int apply = 0; apply < 2; ++apply)
        for (int inject = 0; inject < 2; ++inject)
            for (int T = 1; T <= MT; ++T) {
                auto args = [&](Bufs& b, FusedGrArgs* fa) {
                    for (int t = 0; t < T; ++t) {
                        FusedGrArgs& a = fa[t];
                        a = FusedGrArgs{};
                        a.R = b.R + (size_t) t * D; a.R_out = b.R + (size_t) t * D; a.apply = apply;
                        a.bo_prev = b.bo + (size_t) t * N; a.inj_prev = b.inj_prev + t * HC;
                        a.w_norm = d_wn; a.w_down = d_wd; a.w_up = d_wu; a.w_inject = inject ? d_wi : nullptr;
                        a.eps = 1e-6f; a.lo = b.lo + t * LR; a.rs = b.rs + t * HC;
                        a.inject_out = b.inj_out + t * HC; a.mixed = b.mixed + (size_t) t * N;
                    }
                };
                FusedGrArgs fa[MT], fb[MT];
                reset(A); reset(B);
                args(A, fa); args(B, fb);
                { fused_gr_multi_set_old(true); fused_gr_read_multi(fa, T, A.xn, st); fused_gr_multi_set_old(false); }
                fused_gr_read_multi(fb, T, B.xn, st);
                cudaStreamSynchronize(st);
                auto cmp = [&](const float* x, const float* y, size_t n, const char* what) {
                    std::vector<float> hx(n), hy(n);
                    cudaMemcpy(hx.data(), x, n * 4, cudaMemcpyDeviceToHost);
                    cudaMemcpy(hy.data(), y, n * 4, cudaMemcpyDeviceToHost);
                    size_t d = 0; double mad = 0, mrel = 0;
                    for (size_t i = 0; i < n; ++i) {
                        if (std::memcmp(&hx[i], &hy[i], 4) == 0) continue;
                        ++d;
                        const double a = std::fabs((double) hx[i] - hy[i]);
                        mad = std::max(mad, a); mrel = std::max(mrel, a / std::max(1e-6, std::fabs((double) hx[i])));
                    }
                    if (d) { ++bad; if (T <= 4 && apply == 1) std::printf("  T=%d apply=%d inject=%d: %s %zu of %zu differ, max abs %.3g, max rel %.3g\n", T, apply, inject, what, d, n, mad, mrel); }
                };
                cmp(A.lo, B.lo, (size_t) T * LR, "lo");
                cmp(A.rs, B.rs, (size_t) T * HC, "rs");
                if (inject) cmp(A.inj_out, B.inj_out, (size_t) T * HC, "inject_out");
                cmp(A.mixed, B.mixed, (size_t) T * N, "mixed");
                cmp(A.R, B.R, (size_t) T * D, "R");
                if (apply == 1 && inject == 1) {         // timing, 200 launches each
                    // cold L2 like the real window (48 layers of other weights pass between two GR reads of a
                    // layer): a 192 MB write before every timed call; only the GR call is timed
                    static void* flush = nullptr;
                    if (!flush) cudaMalloc(&flush, 192u << 20);
                    float ms[2] = {0, 0};
                    for (int which = 0; which < 2; ++which) {
                        for (int r = 0; r < 100; ++r) {
                            cudaMemsetAsync(flush, r, 192u << 20, st);
                            cudaEventRecord(e0, st);
                            if (which == 0) { fused_gr_multi_set_old(true); fused_gr_read_multi(fa, T, A.xn, st); fused_gr_multi_set_old(false); }
                            else fused_gr_read_multi(fb, T, B.xn, st);
                            cudaEventRecord(e1, st);
                            cudaEventSynchronize(e1);
                            float t = 0; cudaEventElapsedTime(&t, e0, e1); ms[which] += t;
                        }
                    }
                    std::printf("T=%d: one GR read, cold L2: %.1f us (old) -> %.1f us (new)\n", T, ms[0] * 10.0f, ms[1] * 10.0f);
                }
            }
    std::printf("%s\n", bad ? "MISMATCH" : "all outputs BIT-IDENTICAL (T=1..8, apply on/off, inject on/off)");
    return bad ? 1 : 0;
}
