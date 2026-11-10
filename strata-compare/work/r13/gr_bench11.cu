// gr_bench11.cu - round 11 B.1 (copy of round 10's gr_bench35.cu): the verify window's hyper-connection read
// (fused_gr_read_multi) from the B.1 branch's kernel library, ONE mode per process:  gr_bench11 v5 | v3 | fork  OUT.bin
//   v5 = our GR v5   v3 = upstream's two-kernel read (STRATA_GR_V3=1: C*12.1's read)   fork = STRATA_GR_FORK=1 (B.1)
// For T = 1..8 and apply = 0 / 1: the outputs of one call written to OUT.bin; cold-L2 (192 MB written before each call)
// and warm medians of 200 calls; and the SELF check: every token's outputs of the T-token call against that token's own
// 1-token call, bit for bit (lo, rs, inject, mixed, R_out).
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
    if (argc != 3) { std::fprintf(stderr, "usage: gr_bench11 v5|v3|fork OUT.bin\n"); return 2; }
    std::string mode = argv[1];
    unsetenv("STRATA_GR_DOWN_MAX4");
    if (mode == "v3") setenv("STRATA_GR_V3", "1", 1);
    else unsetenv("STRATA_GR_V3");
    if (mode == "fork") setenv("STRATA_GR_FORK", "1", 1);
    else unsetenv("STRATA_GR_FORK");
    unsetenv("STRATA_GR_OLD");
    if (mode == "plain") setenv("STRATA_HC_SPLIT", "0", 1);
    else unsetenv("STRATA_HC_SPLIT");
    if (mode == "old" || mode == "plain") {
        fused_gr_multi_set_old(true);
        fused_gr_check();   // as Verifier::init does: the card's checked variant (staged; plain with STRATA_HC_SPLIT=0)
    }
    else if (mode != "v5" && mode != "v3" && mode != "fork") { std::fprintf(stderr, "mode?\n"); return 2; }
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
    const size_t xn_bytes = (size_t) fused_gr_scratch_floats(MT) * 4 + (size_t) MT * HC * 2 * 400 * 4;   // + v3's partials (S = 2)
    cudaMalloc(&xn, xn_bytes);
    cudaMemset(xn, 0, xn_bytes);   // the fork read's counters start at 0 (the engine's arenas are zeroed)
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
            // 1b. the self check: each token's T-call outputs vs its own 1-token call
            auto grab = [&](std::vector<float>& h, const float* p, size_t n) { h.resize(n); cudaMemcpy(h.data(), p, n * 4, cudaMemcpyDeviceToHost); };
            std::vector<float> tl, tr, ti, tm, tR;
            grab(tl, lo, (size_t) T * LR); grab(tr, rs, (size_t) T * HC); grab(ti, io, (size_t) T * HC); grab(tm, mx, (size_t) T * N); grab(tR, R, (size_t) T * D);
            int self_bad = 0;
            for (int t = 0; t < T; ++t) {
                reset();
                fused_gr_read_multi(&fa[t], 1, xn, st);
                cudaStreamSynchronize(st);
                std::vector<float> ol, orr, oi, om, oR;
                grab(ol, lo + t * LR, LR); grab(orr, rs + t * HC, HC); grab(oi, io + t * HC, HC); grab(om, mx + (size_t) t * N, N); grab(oR, R + (size_t) t * D, D);
                const bool same = !std::memcmp(ol.data(), &tl[(size_t) t * LR], LR * 4) && !std::memcmp(orr.data(), &tr[(size_t) t * HC], HC * 4) &&
                                  !std::memcmp(oi.data(), &ti[(size_t) t * HC], HC * 4) && !std::memcmp(om.data(), &tm[(size_t) t * N], N * 4) &&
                                  !std::memcmp(oR.data(), &tR[(size_t) t * D], (size_t) D * 4);
                self_bad += !same;
            }
            std::printf("apply=%d T=%d self check: %d of %d tokens differ from their own 1-token read\n", apply, T, self_bad, T);
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
