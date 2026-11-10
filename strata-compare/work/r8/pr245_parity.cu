// pr245_parity.cu GGUF NATIVE_EXPERTS.TXT OUT_FILE — round 8: bitwise parity of the grouped native-expert kernels, the old
// four (STRATA_EXPERTS_OLD=1) vs PR245's two (default), on REAL experts: one layer of every gate/up + down format pair the
// model has (layers 0, 1, 2, 12, 17, 21, 47: 18/20, 22/42, 22/20, 18/42, 21/20, 21/42, 23/20), 16 experts each, random
// activations (fixed seed), windows of 1..8 tokens routed to 10 of the 16 experts (tokens share some), entries grouped by
// expert as the engine does.  Writes every output row to OUT_FILE; run once per path and compare the files byte for byte
// (`cmp`). Also prints the kernel time per call (CUDA events, median of 50, outside a graph).
#include "strata/kernels/iq_kernels.hpp"

#include <cuda_runtime.h>

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <random>
#include <string>
#include <vector>

using namespace strata::kernels;

int main(int argc, char** argv) {
    if (argc < 4) { std::fprintf(stderr, "usage: pr245_parity GGUF NATIVE_EXPERTS.TXT OUT\n"); return 2; }
    const int64_t H = 2560, FF = 640, K = 10, E = 16;
    FILE* gf = std::fopen(argv[1], "rb");
    FILE* nf = std::fopen(argv[2], "r");
    FILE* of = std::fopen(argv[3], "wb");
    if (!gf || !nf || !of) { std::fprintf(stderr, "cannot open inputs/output\n"); return 2; }
    std::map<int, std::vector<long long>> lay;   // layer -> gu d offset blob gate_off up_off down_off
    char line[512];
    while (std::fgets(line, sizeof line, nf)) {
        if (line[0] == '#') continue;
        long long v[8];
        if (std::sscanf(line, "%lld %lld %lld %lld %lld %lld %lld %lld", &v[0], &v[1], &v[2], &v[3], &v[4], &v[5], &v[6], &v[7]) == 8)
            lay[(int) v[0]] = std::vector<long long>(v, v + 8);
    }
    const char* old = std::getenv("STRATA_EXPERTS_OLD");
    std::printf("path: %s\n", old && old[0] == '1' ? "OLD (four kernels)" : "NEW (PR245, two kernels)");
    std::mt19937 rng(12345);
    std::normal_distribution<float> nd(0.0f, 1.0f);
    cudaStream_t st;
    cudaStreamCreate(&st);
    size_t rows_written = 0;
    for (int layer : {0, 1, 2, 12, 17, 21, 47}) {
        const auto& v = lay.at(layer);
        const int gu = (int) v[1], dt = (int) v[2];
        const NativeExpertLayout L = native_expert_layout(gu, dt, H, FF);
        if ((long long) L.bytes != v[4]) { std::fprintf(stderr, "layer %d: layout %zu bytes vs pack %lld\n", layer, L.bytes, v[4]); return 1; }
        // E experts' blobs (gate rows | up rows | down rows), read from the GGUF tensors (expert-major)
        const size_t gsz = (size_t) FF * L.gu_row, dsz = (size_t) H * L.d_row;
        std::vector<uint8_t> host(L.bytes * E);
        for (int e = 0; e < E; ++e) {
            const int eid = e * 31 % 512;   // spread over the layer's experts
            uint8_t* b = host.data() + (size_t) e * L.bytes;
            auto rd = [&](long long off, size_t n, uint8_t* dst) {
                std::fseek(gf, off, SEEK_SET);
                if (std::fread(dst, 1, n, gf) != n) { std::fprintf(stderr, "short read\n"); std::exit(1); }
            };
            rd(v[5] + (long long) eid * (long long) gsz, gsz, b);
            rd(v[6] + (long long) eid * (long long) gsz, gsz, b + L.up_off);
            rd(v[7] + (long long) eid * (long long) dsz, dsz, b + L.down_off);
        }
        uint8_t* dblob;
        cudaMalloc(&dblob, host.size());
        cudaMemcpy(dblob, host.data(), host.size(), cudaMemcpyHostToDevice);
        for (int T = 1; T <= 8; ++T) {
            // routing: each token picks K distinct experts of E (some shared across tokens)
            std::vector<std::vector<int>> pick(T);
            for (int t = 0; t < T; ++t) {
                std::vector<int> ids(E);
                for (int i = 0; i < E; ++i) ids[i] = i;
                std::shuffle(ids.begin(), ids.end(), rng);
                pick[t].assign(ids.begin(), ids.begin() + K);
            }
            std::vector<unsigned long long> gptr;
            std::vector<int32_t> gstart, edst, etok;
            for (int e = 0; e < E; ++e) {
                bool any = false;
                for (int t = 0; t < T; ++t)
                    for (int k = 0; k < K; ++k)
                        if (pick[t][k] == e) {
                            if (!any) { gptr.push_back((unsigned long long) (dblob + (size_t) e * L.bytes)); gstart.push_back((int32_t) edst.size()); any = true; }
                            edst.push_back(t * (int) K + k);
                            etok.push_back(t);
                        }
            }
            gstart.push_back((int32_t) edst.size());
            const int ng = (int) gptr.size();
            const int64_t cap = T * K;
            std::vector<float> x((size_t) T * H);
            for (float& f : x) f = nd(rng);
            float *dx, *dout;
            void *dxq, *scratch;
            unsigned long long* dgp;
            int32_t *dgs, *dng, *dd, *dtk;
            cudaMalloc(&dx, x.size() * 4); cudaMalloc(&dxq, (size_t) T * (H / 32) * 36);
            cudaMalloc(&dout, (size_t) cap * H * 4); cudaMalloc(&scratch, native_expert_scratch_bytes(cap, FF));
            cudaMalloc(&dgp, cap * 8); cudaMalloc(&dgs, (cap + 1) * 4); cudaMalloc(&dng, 4);
            cudaMalloc(&dd, cap * 4); cudaMalloc(&dtk, cap * 4);
            cudaMemcpy(dx, x.data(), x.size() * 4, cudaMemcpyHostToDevice);
            cudaMemcpy(dgp, gptr.data(), gptr.size() * 8, cudaMemcpyHostToDevice);
            cudaMemcpy(dgs, gstart.data(), gstart.size() * 4, cudaMemcpyHostToDevice);
            cudaMemcpy(dng, &ng, 4, cudaMemcpyHostToDevice);
            cudaMemcpy(dd, edst.data(), edst.size() * 4, cudaMemcpyHostToDevice);
            cudaMemcpy(dtk, etok.data(), etok.size() * 4, cudaMemcpyHostToDevice);
            cudaMemset(dout, 0, (size_t) cap * H * 4);
            quantize_q8_1_rows(dx, T, H, dxq, st);
            native_expert_grouped(L, dgp, dgs, dng, dd, dtk, cap, cap, dxq, scratch, dout, st);
            cudaStreamSynchronize(st);
            std::vector<float> out((size_t) cap * H);
            cudaMemcpy(out.data(), dout, out.size() * 4, cudaMemcpyDeviceToHost);
            std::fwrite(out.data(), 4, out.size(), of);
            rows_written += (size_t) cap;
            // timing
            cudaEvent_t e0, e1; cudaEventCreate(&e0); cudaEventCreate(&e1);
            std::vector<float> ms;
            for (int r = 0; r < 51; ++r) {
                cudaEventRecord(e0, st);
                native_expert_grouped(L, dgp, dgs, dng, dd, dtk, cap, cap, dxq, scratch, dout, st);
                cudaEventRecord(e1, st); cudaEventSynchronize(e1);
                float t; cudaEventElapsedTime(&t, e0, e1); if (r) ms.push_back(t);
            }
            std::sort(ms.begin(), ms.end());
            std::printf("layer %2d fmt %d/%d T=%d groups %2d entries %2d: %.1f us\n", layer, gu, dt, T, ng, (int) edst.size(), ms[ms.size() / 2] * 1000.0f);
            cudaFree(dx); cudaFree(dxq); cudaFree(dout); cudaFree(scratch); cudaFree(dgp); cudaFree(dgs); cudaFree(dng); cudaFree(dd); cudaFree(dtk);
        }
        cudaFree(dblob);
    }
    std::fclose(of);
    const cudaError_t e = cudaGetLastError();
    std::printf("rows written %zu; last CUDA error: %s\n", rows_written, cudaGetErrorString(e));
    return e == cudaSuccess ? 0 : 1;
}
