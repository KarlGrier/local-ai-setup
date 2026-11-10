// hotcold.cpp - round 12 A8 (next-layer warming): how much faster is one CPU-side expert for ONE token when its
// weights are already in the CPU's caches than when they stream from DRAM? ggml's own CPU dot products (the ones the
// pool uses for one-token experts: vec_dot of the gate / up rows against the Q8_K input, then the down rows), on this
// model's layer-0 expert shapes: gate / up 640 rows of 2560 (IQ3_XXS), down 2560 rows of 640 (IQ4_NL).
// THREADS workers pinned to cores 1..THREADS (as the pool's), each computing experts:
//   cold: worker w walks its own experts through a working set far larger than the caches (DRAM-bound, all at once)
//   hot : worker w repeats one expert of its own (2.2 MB: fits the L3), so its weights stay cached
//   warm: like hot, but each worker first READS (touches) the expert, then computes it: the cost of warming
// Prints per-expert ms (mean over workers) and the aggregate weight bandwidth.  Measurement only.
#include "ggml.h"
#include "ggml-cpu.h"

#include <pthread.h>
#include <sched.h>

#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <thread>
#include <vector>

static const int NE = 2560, NF = 640;

struct Expert { std::vector<uint8_t> gu; };   // gate rows, up rows, down rows packed

int main(int argc, char** argv) {
    const int threads = argc > 1 ? std::atoi(argv[1]) : 15;
    const double set_gb = argc > 2 ? std::atof(argv[2]) : 6.0;
    const int reps = argc > 3 ? std::atoi(argv[3]) : 40;
    ggml_cpu_init();
    const ggml_type tg = GGML_TYPE_IQ3_XXS, td = GGML_TYPE_IQ4_NL;
    const auto* trg = ggml_get_type_traits_cpu(tg);
    const auto* trd = ggml_get_type_traits_cpu(td);
    const size_t rg = ggml_row_size(tg, NE), rd = ggml_row_size(td, NF);
    const size_t eb = 2 * NF * rg + NE * rd;           // bytes of one expert
    // one quantized expert from random weights, copied to fill the working set
    std::mt19937 rng(1);
    std::normal_distribution<float> nd(0.f, 0.02f);
    std::vector<float> w((size_t) NE * NF);
    for (auto& v : w) v = nd(rng);
    std::vector<uint8_t> one(eb);
    ggml_quantize_init(tg);
    ggml_quantize_init(td);
    ggml_quantize_chunk(tg, w.data(), one.data(), 0, NF, NE, nullptr);
    ggml_quantize_chunk(tg, w.data(), one.data() + NF * rg, 0, NF, NE, nullptr);
    ggml_quantize_chunk(td, w.data(), one.data() + 2 * NF * rg, 0, NE, NF, nullptr);
    const size_t nset = (size_t) (set_gb * 1e9 / (double) eb);
    std::vector<uint8_t> set(nset * eb);
    for (size_t i = 0; i < nset; ++i) std::memcpy(set.data() + i * eb, one.data(), eb);
    std::printf("expert %.3f MB (gate/up IQ3_XXS %zu B/row, down IQ4_NL %zu B/row); working set %zu experts = %.1f GB; %d threads\n",
                eb / 1e6, rg, rd, nset, nset * eb / 1e9, threads);
    // the token's input, quantized to the vec_dot type
    std::vector<float> x(NE), h(NF);
    for (auto& v : x) v = nd(rng) * 50.f;
    const ggml_type vt = trg->vec_dot_type, vtd = trd->vec_dot_type;
    std::vector<uint8_t> xq(ggml_row_size(vt, NE));
    ggml_get_type_traits_cpu(vt)->from_float(x.data(), xq.data(), NE);   // the vec_dot type (Q8_K), as the CPU path quantizes
    auto run_expert = [&](const uint8_t* e, std::vector<float>& gate, std::vector<float>& out, std::vector<uint8_t>& hq) {
        for (int r = 0; r < NF; ++r) trg->vec_dot(NE, &gate[r], 0, e + (size_t) r * rg, 0, xq.data(), 0, 1);
        float up;
        for (int r = 0; r < NF; ++r) {
            trg->vec_dot(NE, &up, 0, e + (size_t) (NF + r) * rg, 0, xq.data(), 0, 1);
            const float g = gate[r];
            gate[r] = g / (1.f + std::exp(-g)) * up;
        }
        ggml_get_type_traits_cpu(vtd)->from_float(gate.data(), hq.data(), NF);
        for (int r = 0; r < NE; ++r) trd->vec_dot(NF, &out[r], 0, e + 2 * (size_t) NF * rg + (size_t) r * rd, 0, hq.data(), 0, 1);
    };
    auto bench = [&](int mode) {   // 0 cold, 1 hot, 2 warm (touch, then compute)
        std::atomic<int> ready{0};
        std::atomic<bool> go{false};
        std::vector<double> ms((size_t) threads, 0.0);
        std::vector<std::thread> th;
        for (int t = 0; t < threads; ++t)
            th.emplace_back([&, t] {
                cpu_set_t cs;
                CPU_ZERO(&cs);
                CPU_SET(1 + t, &cs);
                pthread_setaffinity_np(pthread_self(), sizeof cs, &cs);
                std::vector<float> gate(NF), out(NE);
                std::vector<uint8_t> hq(ggml_row_size(vtd, NF));
                volatile uint64_t sink = 0;
                const uint8_t* mine = set.data() + (size_t) t * eb;
                if (mode != 0) run_expert(mine, gate, out, hq);   // bring it in once
                ready++;
                while (!go) {}
                auto a = std::chrono::steady_clock::now();
                for (int i = 0; i < reps; ++i) {
                    const uint8_t* e = mode == 0 ? set.data() + ((size_t) (t + (size_t) i * threads) % nset) * eb : mine;
                    if (mode == 2) { uint64_t s = 0; for (size_t o = 0; o < eb; o += 64) s += e[o]; sink += s; }
                    run_expert(e, gate, out, hq);
                }
                ms[(size_t) t] = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - a).count() / reps;
            });
        while (ready < threads) {}
        go = true;
        for (auto& x2 : th) x2.join();
        double m = 0; for (double v : ms) m += v; m /= threads;
        std::printf("%s: %.4f ms per expert per worker; aggregate %.1f GB/s of weights\n", mode == 0 ? "cold (DRAM)" : mode == 1 ? "hot (cached)" : "touch+compute",
                    m, threads * eb / (m * 1e-3) / 1e9);
        return m;
    };
    const double c = bench(0), hot = bench(1), warm = bench(2);
    bench(0);
    std::printf("hot / cold = %.3f; touch+compute / cold = %.3f\n", hot / c, warm / c);
    return 0;
}
