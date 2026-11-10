// warmpipe.cpp - round 12 A8-1 check (no engine change): does warming the NEXT layer's predicted CPU-side experts during
// the GPU's mixer phase shorten the CPU pool's next layer, on this machine, with the pool's way of splitting work?
// A simulated window = 48 layers. Each layer: E_TRUE experts (this model's layer-0 shape: gate/up 640 x 2560 IQ3_XXS,
// down 2560 x 640 IQ4_NL, ~2.2 MB), drawn at random from a 6 GB set (DRAM-resident, never cached in between), computed
// for one token by THREADS pinned workers, each taking a fixed slice of every expert's rows (gate/up rows, then down
// rows) - the pool's row split. Between layers the workers wait GAP_US (the GPU's mixer + HC read), then compute the
// next layer. Warm mode: during the gap each worker reads its OWN future slices of the predicted experts of the next
// layer: the true ones with probability RECALL (measured: 0.488) plus EXTRA x E_TRUE wrong ones (measured 1.34 x true
// predicted in all -> extra 0.34 + (1 - recall) ... approximated as EXTRA = 1.34 - RECALL). Reports the CPU pool's time
// per layer (compute only, the gaps excluded) with and without warming, and whether warming finished inside the gap.
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

int main(int argc, char** argv) {
    const int threads = argc > 1 ? std::atoi(argv[1]) : 15;
    const int e_true = argc > 2 ? std::atoi(argv[2]) : 4;
    const double recall = argc > 3 ? std::atof(argv[3]) : 0.488;
    const double extra = argc > 4 ? std::atof(argv[4]) : 0.85;
    const int gap_us = argc > 5 ? std::atoi(argv[5]) : 150;
    const int windows = argc > 6 ? std::atoi(argv[6]) : 40;
    ggml_cpu_init();
    const ggml_type tg = GGML_TYPE_IQ3_XXS, td = GGML_TYPE_IQ4_NL;
    const auto* trg = ggml_get_type_traits_cpu(tg);
    const auto* trd = ggml_get_type_traits_cpu(td);
    const size_t rg = ggml_row_size(tg, NE), rd = ggml_row_size(td, NF);
    const size_t eb = 2 * NF * rg + NE * rd;
    std::mt19937 rng(7);
    std::normal_distribution<float> nd(0.f, 0.02f);
    std::vector<float> w((size_t) NE * NF);
    for (auto& v : w) v = nd(rng);
    std::vector<uint8_t> one(eb);
    ggml_quantize_init(tg); ggml_quantize_init(td);
    ggml_quantize_chunk(tg, w.data(), one.data(), 0, NF, NE, nullptr);
    ggml_quantize_chunk(tg, w.data(), one.data() + NF * rg, 0, NF, NE, nullptr);
    ggml_quantize_chunk(td, w.data(), one.data() + 2 * NF * rg, 0, NE, NF, nullptr);
    const size_t nset = (size_t) (6e9 / (double) eb);
    std::vector<uint8_t> set(nset * eb);
    for (size_t i = 0; i < nset; ++i) std::memcpy(set.data() + i * eb, one.data(), eb);
    std::vector<float> x(NE);
    for (auto& v : x) v = nd(rng) * 50.f;
    const ggml_type vt = trg->vec_dot_type, vtd = trd->vec_dot_type;
    std::vector<uint8_t> xq(ggml_row_size(vt, NE));
    ggml_get_type_traits_cpu(vt)->from_float(x.data(), xq.data(), NE);
    // the plan: per window, per layer, the true experts and the predicted ones (for the NEXT layer's warming)
    const int L = 48;
    std::uniform_int_distribution<size_t> pick(0, nset - 1);
    std::uniform_real_distribution<double> u01(0, 1);
    std::vector<std::vector<size_t>> truth((size_t) windows * L), pred((size_t) windows * L);
    for (int k = 0; k < windows * L; ++k) {
        for (int e = 0; e < e_true; ++e) truth[(size_t) k].push_back(pick(rng));
        for (size_t t : truth[(size_t) k]) if (u01(rng) < recall) pred[(size_t) k].push_back(t);
        int ex = (int) std::lround(extra * e_true);
        for (int e = 0; e < ex; ++e) pred[(size_t) k].push_back(pick(rng));
    }
    auto run = [&](bool warm) {
        std::atomic<int> phase{0};          // even: compute layer phase/2; odd: gap
        std::atomic<int> done{0};
        std::vector<double> busy((size_t) threads, 0.0);
        std::atomic<int64_t> warm_late{0};
        std::vector<std::thread> th;
        const int steps = windows * L;
        for (int t = 0; t < threads; ++t)
            th.emplace_back([&, t] {
                cpu_set_t cs; CPU_ZERO(&cs); CPU_SET(1 + t, &cs);
                pthread_setaffinity_np(pthread_self(), sizeof cs, &cs);
                std::vector<float> gate(NF), out(NE), up(NF);
                std::vector<uint8_t> hq(ggml_row_size(vtd, NF));
                volatile uint64_t sink = 0;
                const int g0 = NF * t / threads, g1 = NF * (t + 1) / threads;   // this worker's gate / up rows
                const int d0 = NE * t / threads, d1 = NE * (t + 1) / threads;   // and down rows
                for (int s = 0; s < steps; ++s) {
                    while (phase.load() < 2 * s) {}
                    auto a = std::chrono::steady_clock::now();
                    for (size_t ex : truth[(size_t) s]) {
                        const uint8_t* e = set.data() + ex * eb;
                        for (int r = g0; r < g1; ++r) trg->vec_dot(NE, &gate[r], 0, e + (size_t) r * rg, 0, xq.data(), 0, 1);
                        for (int r = g0; r < g1; ++r) trg->vec_dot(NE, &up[r], 0, e + (size_t) (NF + r) * rg, 0, xq.data(), 0, 1);
                        ggml_get_type_traits_cpu(vtd)->from_float(gate.data(), hq.data(), NF);   // (the real pool combines the slices first)
                        for (int r = d0; r < d1; ++r) trd->vec_dot(NF, &out[r], 0, e + 2 * (size_t) NF * rg + (size_t) r * rd, 0, hq.data(), 0, 1);
                    }
                    busy[(size_t) t] += std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - a).count();
                    if (done.fetch_add(1) + 1 == threads * (s + 1)) phase.store(2 * s + 1);
                    // the gap: the GPU's mixer phase; warm the next layer's predicted experts (own slices)
                    while (phase.load() < 2 * s + 1) {}
                    if (warm && s + 1 < steps) {
                        for (size_t ex : pred[(size_t) s + 1]) {
                            const uint8_t* e = set.data() + ex * eb;
                            uint64_t acc = 0;
                            for (size_t o = (size_t) g0 * rg; o < (size_t) g1 * rg; o += 64) acc += e[o];
                            for (size_t o = (size_t) (NF + g0) * rg; o < (size_t) (NF + g1) * rg; o += 64) acc += e[o];
                            for (size_t o = 2 * (size_t) NF * rg + (size_t) d0 * rd; o < 2 * (size_t) NF * rg + (size_t) d1 * rd; o += 64) acc += e[o];
                            sink += acc;
                            if (phase.load() >= 2 * s + 2) { warm_late++; break; }   // the doorbell rang: stop warming
                        }
                    }
                }
            });
        // the "GPU": after every layer, a gap of gap_us, then the next layer's doorbell
        for (int s = 0; s < steps; ++s) {
            while (phase.load() < 2 * s + 1) {}
            auto g = std::chrono::steady_clock::now();
            while (std::chrono::duration<double, std::micro>(std::chrono::steady_clock::now() - g).count() < gap_us) {}
            phase.store(2 * s + 2);
        }
        for (auto& x2 : th) x2.join();
        double mx = 0; for (double b : busy) mx = std::max(mx, b);
        double mean = 0; for (double b : busy) mean += b; mean /= threads;
        std::printf("%s: CPU pool per layer %.4f ms (mean worker %.4f); warming cut short at the doorbell %lld times\n",
                    warm ? "warm" : "cold", mean / steps, mx / steps, (long long) warm_late.load());
        return mean / steps;
    };
    std::printf("threads %d, true experts per layer %d, recall %.3f, wrong predictions %.2f x true, gap %d us, %d windows x 48 layers\n",
                threads, e_true, recall, extra, gap_us, windows);
    const double c0 = run(false), w1 = run(true), c1 = run(false), w2 = run(true);
    std::printf("warm / cold CPU pool time per layer = %.3f\n", (w1 + w2) / (c0 + c1));
    return 0;
}
