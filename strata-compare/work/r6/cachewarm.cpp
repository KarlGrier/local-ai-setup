// cachewarm.cpp — round 6, item 4: does a CPU-cache warm-up of an expert's rows make the pool's expert work faster?
//
// A layer is emulated the way the engine's pool runs it (kernels/cpu/pool.cpp run_split_multi_native): NB real experts
// (IQ3_XXS gate/up + IQ4_NL down, layers 14/16 of the model, extracted by work/r6 into tmp/r6), every expert used by
// NT tokens; phase 1 = gate/up rows of all experts split into 3 x threads tasks, the host quantizes h, phase 2 = down
// rows split the same way.  Threads: the host on the first physical core + 15 workers on the others (the engine's
// placement).  Unlike the engine, tasks are assigned STATICALLY (task i -> thread i % threads), so a thread can warm
// exactly the rows it will compute.
//
//   cold : the experts were last touched ~2 GB of traffic ago (a shuffled cycle over 1,024 experts)
//   warm : each thread first reads every cache line of its own rows (both phases), then waits DELAY us; during the
//          wait COMPETE MB of other memory are streamed by SMT-sibling threads (0 = none); then the layer runs.
// Reported per case: the layer's compute time (median/mean of ITERS layers), the touch time (the prefetch window it
// needs) and bytes.  Byte figures are software-counted (no perf counters without root).
#include "strata/kernels/cpu/native_expert.hpp"
#include "strata/kernels/cpu/pool.hpp"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <numeric>
#include <pthread.h>
#include <random>
#include <sched.h>
#include <string>
#include <sys/mman.h>
#include <thread>
#include <unistd.h>
#include <vector>
#include <immintrin.h>

using namespace strata::kernels::cpu;
using Clock = std::chrono::steady_clock;
static double us(Clock::time_point a, Clock::time_point b) { return std::chrono::duration<double, std::micro>(b - a).count(); }

static void pin(int cpu) {
    cpu_set_t s; CPU_ZERO(&s); CPU_SET(cpu, &s); pthread_setaffinity_np(pthread_self(), sizeof s, &s);
}

struct Barrier {
    std::atomic<int> count{0}; std::atomic<int> gen{0}; int n;
    explicit Barrier(int n_) : n(n_) {}
    void wait() {
        const int g = gen.load(std::memory_order_acquire);
        if (count.fetch_add(1, std::memory_order_acq_rel) == n - 1) { count.store(0); gen.fetch_add(1, std::memory_order_release); }
        else while (gen.load(std::memory_order_acquire) == g) _mm_pause();
    }
};

int main(int argc, char** argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: cachewarm BLOBFILE [iters=200] [nb=7]\n"); return 2; }
    const int iters = argc > 2 ? std::atoi(argv[2]) : 200;
    const int NB = argc > 3 ? std::atoi(argv[3]) : 7;
    NativeFmt f; std::string err;
    if (!native_fmt(18 /*IQ3_XXS*/, 20 /*IQ4_NL*/, 2560, 640, f, err)) { std::fprintf(stderr, "%s\n", err.c_str()); return 1; }
    std::printf("fmt: gu_row %zu d_row %zu up_off %zu down_off %zu bytes %zu act %zu h %zu\n", f.gu_row, f.d_row, f.up_off,
                f.down_off, f.bytes, f.act_bytes, f.h_bytes);
    // the arena: 4 KB pages like the engine's (no hugetlb pool, THP only on madvise)
    const int fd = open(argv[1], O_RDONLY);
    const off_t fsz = lseek(fd, 0, SEEK_END);
    const int NE = (int) (fsz / (off_t) f.bytes);
    uint8_t* arena = (uint8_t*) mmap(nullptr, (size_t) fsz, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    for (off_t o = 0; o < fsz;) { ssize_t r = pread(fd, arena + o, (size_t) std::min<off_t>(fsz - o, 1 << 26), o); if (r <= 0) return 1; o += r; }
    close(fd);
    std::printf("arena: %d experts, %.2f GiB\n", NE, fsz / 1073741824.0);
    // competing traffic source: 1 GiB, written once so it is resident
    const size_t CB = 1ull << 30;
    uint8_t* comp = (uint8_t*) mmap(nullptr, CB, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    std::memset(comp, 1, CB);

    std::vector<int> cores = physical_cores(false);   // first thread of each physical core, in order
    const int NTH = (int) std::min<size_t>(16, cores.size());
    std::printf("threads: %d on cpus", NTH);
    for (int i = 0; i < NTH; ++i) std::printf(" %d", cores[(size_t) i]);
    std::printf("\n");
    // SMT siblings for the competing streamers: logical cpus not in `cores`
    std::vector<int> sib;
    for (int c = 0; c < (int) std::thread::hardware_concurrency(); ++c)
        if (std::find(cores.begin(), cores.end(), c) == cores.end()) sib.push_back(c);

    const int TASKS = 3 * NTH;
    // per-layer shared state
    struct Layer { const uint8_t* blob[16]; int nb, nt; } L{};
    std::vector<float> xs(4 * 2560);
    std::mt19937 rng(1);
    for (float& v : xs) v = std::uniform_real_distribution<float>(-1.f, 1.f)(rng);
    alignas(64) static uint8_t act[4][kNativeActBytes];
    for (int t = 0; t < 4; ++t) native_quant_act(f, xs.data() + t * 2560, act[t]);
    static float ff[16][4][640];
    static uint8_t hq[16][4][2048];
    static float outb[16][4][2560];

    std::atomic<int> cmd{0};          // 0 idle, 1 run layer, -1 exit
    std::atomic<int> seq{0};
    int mode_warm = 0; double delay_us = 0; size_t compete = 0;
    Barrier bar(NTH);
    std::vector<double> touch_us(NTH);
    std::atomic<int> streamers_go{0}; std::atomic<int> streamers_done{0};
    const int NSTREAM = 4;
    std::atomic<uint64_t> sink{0};

    auto rows_task = [&](int phase, int task, int& e0, int& r0, int64_t& g0, int64_t& g1) {
        const int per = phase == 1 ? 640 : 2560;
        const int64_t rows = (int64_t) L.nb * per;
        g0 = rows * task / TASKS; g1 = rows * (task + 1) / TASKS; (void) e0; (void) r0;
    };
    auto run_phase = [&](int phase, int tid) {
        const int per = phase == 1 ? 640 : 2560;
        for (int task = tid; task < TASKS; task += NTH) {
            int e0 = 0, r0 = 0; int64_t g0, g1; rows_task(phase, task, e0, r0, g0, g1);
            for (int64_t r = g0; r < g1;) {
                const int e = (int) (r / per), a = (int) (r % per);
                const int b = (int) std::min<int64_t>(per, a + (g1 - r));
                if (phase == 1) {
                    const void* ap[4]; float* fp[4];
                    for (int t = 0; t < L.nt; ++t) { ap[t] = act[t]; fp[t] = ff[e][t]; }
                    native_gu_rows(f, L.blob[e], ap, L.nt, fp, a, b);
                } else {
                    const void* hp[4]; float* op[4];
                    for (int t = 0; t < L.nt; ++t) { hp[t] = hq[e][t]; op[t] = outb[e][t]; }
                    native_down_rows(f, L.blob[e], hp, L.nt, op, a, b);
                }
                r += b - a;
            }
        }
    };
    auto touch = [&](int tid) -> uint64_t {   // read one word of every line of this thread's rows (both phases)
        uint64_t s = 0;
        for (int phase = 1; phase <= 2; ++phase) {
            const int per = phase == 1 ? 640 : 2560;
            for (int task = tid; task < TASKS; task += NTH) {
                int e0 = 0, r0 = 0; int64_t g0, g1; rows_task(phase, task, e0, r0, g0, g1);
                for (int64_t r = g0; r < g1;) {
                    const int e = (int) (r / per), a = (int) (r % per);
                    const int b = (int) std::min<int64_t>(per, a + (g1 - r));
                    auto rd = [&](const uint8_t* p, size_t n) { for (size_t o = 0; o < n; o += 64) s += *(const volatile uint64_t*) (p + o); };
                    if (phase == 1) {
                        rd(L.blob[e] + (size_t) a * f.gu_row, (size_t) (b - a) * f.gu_row);
                        rd(L.blob[e] + f.up_off + (size_t) a * f.gu_row, (size_t) (b - a) * f.gu_row);
                    } else {
                        rd(L.blob[e] + f.down_off + (size_t) a * f.d_row, (size_t) (b - a) * f.d_row);
                    }
                    r += b - a;
                }
            }
        }
        return s;
    };
    Clock::time_point t_release;
    auto worker = [&](int tid) {
        pin(cores[(size_t) tid]);
        int seen = 0;
        for (;;) {
            while (seq.load(std::memory_order_acquire) == seen) _mm_pause();
            seen = seq.load();
            if (cmd.load() < 0) return;
            if (mode_warm) {
                const auto a = Clock::now();
                sink += touch(tid);
                touch_us[(size_t) tid] = us(a, Clock::now());
                bar.wait();
                if (tid == 0) {
                    const auto t0 = Clock::now();
                    if (compete) { streamers_done = 0; streamers_go.fetch_add(1); while (streamers_done.load() < NSTREAM) _mm_pause(); }
                    while (us(t0, Clock::now()) < delay_us) _mm_pause();
                    t_release = Clock::now();
                }
                bar.wait();
            } else {
                bar.wait();
                if (tid == 0) t_release = Clock::now();
                bar.wait();
            }
            run_phase(1, tid);
            bar.wait();
            if (tid == 0)
                for (int e = 0; e < L.nb; ++e) for (int t = 0; t < L.nt; ++t) native_quant_h(f, ff[e][t], hq[e][t]);
            bar.wait();
            run_phase(2, tid);
            bar.wait();
        }
    };
    auto streamer = [&](int i) {
        pin(sib[(size_t) i * sib.size() / NSTREAM]);
        int seen = 0; size_t off = (size_t) i * (CB / NSTREAM);
        for (;;) {
            while (streamers_go.load() == seen) { if (cmd.load() < 0) return; _mm_pause(); }
            seen = streamers_go.load();
            uint64_t s = 0; const size_t n = compete / NSTREAM;
            for (size_t o = 0; o < n; o += 64) { s += *(const volatile uint64_t*) (comp + (off + o) % CB); }
            off = (off + n) % CB;
            sink += s; streamers_done.fetch_add(1);
        }
    };
    std::vector<std::thread> th;
    for (int i = 1; i < NTH; ++i) th.emplace_back(worker, i);
    std::vector<std::thread> st;
    for (int i = 0; i < NSTREAM && !sib.empty(); ++i) st.emplace_back(streamer, i);
    pin(cores[0]);

    std::vector<int> order((size_t) NE);
    std::iota(order.begin(), order.end(), 0);
    std::shuffle(order.begin(), order.end(), rng);
    size_t cur = 0;
    auto next_layer = [&](int nt) {
        L.nb = NB; L.nt = nt;
        for (int e = 0; e < NB; ++e) { L.blob[e] = arena + (size_t) order[cur % (size_t) NE] * f.bytes; ++cur; }
    };
    auto one_layer = [&](bool warm, double dly, size_t comp_b, double& tl, double& tt) {
        mode_warm = warm; delay_us = dly; compete = comp_b;
        seq.fetch_add(1, std::memory_order_release);
        // the host is thread 0: run its share inline
        if (warm) {
            const auto a = Clock::now(); sink += touch(0); touch_us[0] = us(a, Clock::now());
            bar.wait();
            const auto t0 = Clock::now();
            if (compete) { streamers_done = 0; streamers_go.fetch_add(1); while (streamers_done.load() < NSTREAM) _mm_pause(); }
            while (us(t0, Clock::now()) < delay_us) _mm_pause();
            t_release = Clock::now();
            bar.wait();
        } else { bar.wait(); t_release = Clock::now(); bar.wait(); }
        run_phase(1, 0); bar.wait();
        for (int e = 0; e < L.nb; ++e) for (int t = 0; t < L.nt; ++t) native_quant_h(f, ff[e][t], hq[e][t]);
        bar.wait(); run_phase(2, 0); bar.wait();
        tl = us(t_release, Clock::now());
        tt = *std::max_element(touch_us.begin(), touch_us.end());
    };
    // the worker lambda above runs the host share too when tid == 0; here the host drives, so workers are 1..NTH-1
    auto stats = [](std::vector<double> v) { std::sort(v.begin(), v.end()); double m = 0; for (double x : v) m += x; return std::pair<double, double>(v[v.size() / 2], m / v.size()); };
    std::printf("%-6s %-3s %-9s %-10s %-12s %-12s %-12s %-10s\n", "case", "NT", "delay_us", "compete_MB", "layer_med_us", "layer_mean_us", "touch_med_us", "GB/s(med)");
    const double MB = (double) NB * (double) f.bytes / 1e6;
    for (int nt = 1; nt <= 4; ++nt) {
        struct C { const char* name; bool warm; double dly; size_t comp; };
        const C cases[] = {{"cold", false, 0, 0}, {"warm", true, 0, 0}, {"warm", true, 100, 0}, {"warm", true, 200, 0},
                           {"warm", true, 200, 16u << 20}, {"warm", true, 200, 64u << 20}, {"cold", false, 0, 0}};
        for (const C& c : cases) {
            std::vector<double> tl, tt;
            for (int i = 0; i < 10; ++i) { next_layer(nt); double a, b; one_layer(c.warm, c.dly, c.comp, a, b); }   // warm-up
            for (int i = 0; i < iters; ++i) {
                next_layer(nt);
                double a, b; one_layer(c.warm, c.dly, c.comp, a, b);
                tl.push_back(a); tt.push_back(b);
            }
            const auto [lm, la] = stats(tl);
            const auto [tm, ta] = stats(tt);
            std::printf("%-6s %-3d %-9.0f %-10zu %-12.1f %-12.1f %-12.1f %-10.1f\n", c.name, nt, c.dly, c.comp >> 20, lm, la,
                        c.warm ? tm : 0.0, MB * 1e6 / lm / 1e3);
            (void) ta;
        }
    }
    // single core, one expert: cold vs just touched (no other threads working)
    std::printf("\nsingle core, one expert (%.2f MB), core %d:\n", f.bytes / 1e6, cores[0]);
    for (int nt = 1; nt <= 4; ++nt) {
        for (int warm = 0; warm <= 1; ++warm) {
            std::vector<double> v;
            for (int i = 0; i < 60; ++i) {
                const uint8_t* b = arena + (size_t) order[cur++ % (size_t) NE] * f.bytes;
                if (warm) { uint64_t s = 0; for (size_t o = 0; o < f.bytes; o += 64) s += *(const volatile uint64_t*) (b + o); sink += s; }
                const auto a = Clock::now();
                const void* ap[4]; float* fp[4]; const void* hp[4]; float* op[4];
                for (int t = 0; t < nt; ++t) { ap[t] = act[t]; fp[t] = ff[0][t]; hp[t] = hq[0][t]; op[t] = outb[0][t]; }
                native_gu_rows(f, b, ap, nt, fp, 0, 640);
                for (int t = 0; t < nt; ++t) native_quant_h(f, ff[0][t], hq[0][t]);
                native_down_rows(f, b, hp, nt, op, 0, 2560);
                v.push_back(us(a, Clock::now()));
            }
            const auto [m, mean] = stats(v);
            std::printf("  NT %d %-4s median %.1f us (%.1f GB/s), mean %.1f us\n", nt, warm ? "warm" : "cold", m, f.bytes / m / 1e3, mean);
        }
    }
    cmd = -1; seq.fetch_add(1); streamers_go.fetch_add(1);
    for (auto& t : th) t.join();
    for (auto& t : st) t.join();
    std::printf("(sink %llu)\n", (unsigned long long) sink.load());
    return 0;
}
