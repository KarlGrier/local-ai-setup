// gr_bench35.cu - round 10 B.3 (copy of round 9's gr_bench10.cu + #443's STRATA_GR_DOWN_MAX4 on upstream's reads):  the verify window's hyper-connection read (fused_gr_read_multi) from C*10's own kernel
// library, in ONE mode per process:  gr_bench v5 | v3 | old  OUT.bin
//   v5  = our GR v5 (C*10's default)        v3 = upstream's two-kernel read (STRATA_GR_V3=1, read once per process)
//   old = upstream's default read (STRATA_GR_OLD=1): on 0.1.32 the variant #315's check accepts (staged)
//   plain = upstream's plain read (STRATA_GR_OLD=1 + STRATA_HC_SPLIT=0: 0.1.31's default)
//   max4 / max4plain = old / plain with #443's STRATA_GR_DOWN_MAX4=1 (token storage bound to 4 for windows of <= 4)
// Model dimensions (n_embd 2560, 4 streams, low rank 320), random inputs from a fixed seed (identical in every mode),
// BF16 weights. For T = 1..8 and apply = 0 / 1 (inject always on, as in verify.cpp):
//   * time per call with a COLD L2 (192 MB written before every timed call: ~48 layers of other weights pass between two
//     reads of the same layer in a real window), median of 200 calls; and WARM (back-to-back), median of 200;
//   * all outputs (lo, rs, inject_out, mixed, R) written to OUT.bin for the cross-mode comparison (gr_compare.py).
#include "strata/kernels/fused_gr.hpp"

#include <cuda_runtime.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <string>
#include <vector>

using namespace strata::kernels;
constexpr int N = 2560, HC = 4, D = N * HC, LR = 320, MT = kFusedGrMaxT;

static uint16_t bf(float f) { uint32_t i; std::memcpy(&i, &f, 4); return (uint16_t) ((i + 0x7fff + ((i >> 16) & 1)) >> 16); }

int main(int argc, char** argv) {
    if (argc != 3) { std::fprintf(stderr, "usage: gr_bench35 v5|v3|old|plain|max4|max4plain OUT.bin\n"); return 2; }
    std::string mode = argv[1];
    if (mode == "max4" || mode == "max4plain") { setenv("STRATA_GR_DOWN_MAX4", "1", 1); mode = mode == "max4" ? "old" : "plain"; }
    else unsetenv("STRATA_GR_DOWN_MAX4");
    if (mode == "v3") setenv("STRATA_GR_V3", "1", 1);
    else unsetenv("STRATA_GR_V3");
    unsetenv("STRATA_GR_OLD");
    if (mode == "plain") setenv("STRATA_HC_SPLIT", "0", 1);
    else unsetenv("STRATA_HC_SPLIT");
    if (mode == "old" || mode == "plain") {
        fused_gr_multi_set_old(true);
        fused_gr_check();   // as Verifier::init does: the card's checked variant (staged; plain with STRATA_HC_SPLIT=0)
    }
    else if (mode != "v5" && mode != "v3") { std::fprintf(stderr, "mode?\n"); return 2; }
    FILE* out = std::fopen(argv[2], "wb");
    std::mt19937 rng(7);
    std::normal_distribution<float> nd(0.0f, 1.0f);
    auto rnd = [&](size_t n, float s) { std::vector<float> v(n); for (auto& x : v) x = nd(rng) * s; return v; };
    auto bfv = [&](size_t n, float s) { std::vector<uint16_t> v(n); for (auto& x : v) x = bf(nd(rng) * s); return v; };
    auto dev = [](const void* h, size_t bytes) { void* d; cudaMalloc(&d, bytes); cudaMemcpy(d, h, bytes, cudaMemcpyHostToDevice); return d; };
    const auto wn = rnd(D, 1.0f);
    const auto wd = bfv((size_t) LR * D, 0.02f), wu = bfv((size_t) D * LR, 0.05f), wi = bfv((size_t) HC * D, 0.02f);
    const float* d_wn = (const float*) dev(wn.data(), wn.size() * 4);
    const uint16_t* d_wd = (const uint16_t*) dev(wd.data(), wd.size() * 2);
    const uint16_t* d_wu = (const uint16_t*) dev(wu.data(), wu.size() * 2);
    const uint16_t* d_wi = (const uint16_t*) dev(wi.data(), wi.size() * 2);
    const auto R0 = rnd((size_t) MT * D, 1.0f), bo0 = rnd((size_t) MT * N, 0.5f), ip0 = rnd((size_t) MT * HC, 1.0f);
    float *R = (float*) dev(R0.data(), R0.size() * 4), *bo = (float*) dev(bo0.data(), bo0.size() * 4),
          *ip = (float*) dev(ip0.data(), ip0.size() * 4);
    float *lo, *rs, *io, *mx, *xn;
    cudaMalloc(&lo, (size_t) MT * LR * 4); cudaMalloc(&rs, (size_t) MT * HC * 4);
    cudaMalloc(&io, (size_t) MT * HC * 4); cudaMalloc(&mx, (size_t) MT * N * 4);
    cudaMalloc(&xn, (size_t) fused_gr_scratch_floats(MT) * 4 + (size_t) MT * HC * 2 * 400 * 4);   // + v3's partials (S = 2)
    void* flush = nullptr; cudaMalloc(&flush, 192u << 20);
    cudaStream_t st; cudaStreamCreate(&st);
    cudaEvent_t e0, e1; cudaEventCreate(&e0); cudaEventCreate(&e1);
    std::printf("mode %s%s\n", mode.c_str(), std::getenv("STRATA_GR_DOWN_MAX4") ? " + STRATA_GR_DOWN_MAX4" : "");
    for (int apply = 0; apply < 2; ++apply)
        for (int T = 1; T <= MT; ++T) {
            FusedGrArgs fa[MT];
            for (int t = 0; t < T; ++t) {
                FusedGrArgs& a = fa[t];
                a = FusedGrArgs{};
                a.R = R + (size_t) t * D; a.R_out = R + (size_t) t * D; a.apply = apply;
                a.bo_prev = bo + (size_t) t * N; a.inj_prev = ip + t * HC;
                a.w_norm = d_wn; a.w_down = d_wd; a.w_up = d_wu; a.w_inject = d_wi;
                a.eps = 1e-6f; a.lo = lo + t * LR; a.rs = rs + t * HC;
                a.inject_out = io + t * HC; a.mixed = mx + (size_t) t * N;
            }
            auto reset = [&] {
                cudaMemcpyAsync(R, R0.data(), R0.size() * 4, cudaMemcpyHostToDevice, st);
                cudaMemsetAsync(lo, 0, (size_t) MT * LR * 4, st); cudaMemsetAsync(rs, 0, (size_t) MT * HC * 4, st);
                cudaMemsetAsync(io, 0, (size_t) MT * HC * 4, st); cudaMemsetAsync(mx, 0, (size_t) MT * N * 4, st);
            };
            // 1. the outputs of one call from the reset state
            reset();
            fused_gr_read_multi(fa, T, xn, st);
            cudaStreamSynchronize(st);
            auto dump = [&](const float* p, size_t n) { std::vector<float> h(n); cudaMemcpy(h.data(), p, n * 4, cudaMemcpyDeviceToHost); std::fwrite(h.data(), 4, n, out); };
            dump(lo, (size_t) T * LR); dump(rs, (size_t) T * HC); dump(io, (size_t) T * HC); dump(mx, (size_t) T * N); dump(R, (size_t) T * D);
            // 2. timing (R is updated in place when apply = 1: the values drift, the work does not)
            std::vector<float> cold, warm;
            for (int r = 0; r < 200; ++r) {
                cudaMemsetAsync(flush, r & 0xff, 192u << 20, st);
                cudaEventRecord(e0, st);
                fused_gr_read_multi(fa, T, xn, st);
                cudaEventRecord(e1, st);
                cudaEventSynchronize(e1);
                float ms = 0; cudaEventElapsedTime(&ms, e0, e1); cold.push_back(ms * 1000.0f);
            }
            for (int r = 0; r < 220; ++r) {
                cudaEventRecord(e0, st);
                fused_gr_read_multi(fa, T, xn, st);
                cudaEventRecord(e1, st);
                cudaEventSynchronize(e1);
                float ms = 0; cudaEventElapsedTime(&ms, e0, e1); if (r >= 20) warm.push_back(ms * 1000.0f);
            }
            auto med = [](std::vector<float> v) { std::sort(v.begin(), v.end()); return v[v.size() / 2]; };
            const cudaError_t e = cudaGetLastError();
            std::printf("apply=%d T=%d cold_us %.2f warm_us %.2f %s\n", apply, T, med(cold), med(warm), e == cudaSuccess ? "" : cudaGetErrorString(e));
        }
    std::fclose(out);
    return 0;
}
