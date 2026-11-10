// gdn_bench.cu DIR [REPS] — round 8 A.5: Strata's own prompt-path GDN recurrence (strata::prefill::gdn_recurrence, the
// kernels.cu of the build it is compiled with) on a fixture captured by STRATA_GDN_CAPTURE (engine-r8o).  Checks that it
// reproduces the engine's result bit for bit (state1, y) and times it with CUDA events (state restored before each rep).
// Build: nvcc -O3 -std=c++20 -arch=sm_120 -I strata-r8/include gdn_bench.cu strata-r8/src/prefill/kernels.cu ...
#include "strata/prefill/kernels.hpp"

#include <cuda_runtime.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

static std::vector<float> rd(const std::string& p, size_t n) {
    std::vector<float> v(n);
    FILE* f = std::fopen(p.c_str(), "rb");
    if (!f || std::fread(v.data(), 4, n, f) != n) { std::fprintf(stderr, "cannot read %s\n", p.c_str()); std::exit(1); }
    std::fclose(f);
    return v;
}

int main(int argc, char** argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: gdn_bench DIR [REPS]\n"); return 2; }
    const std::string d = argv[1];
    const int reps = argc > 2 ? std::atoi(argv[2]) : 20;
    long long T = 0;
    if (FILE* f = std::fopen((d + "/meta.txt").c_str(), "r")) { if (std::fscanf(f, "T=%lld", &T) != 1) T = 0; std::fclose(f); }
    if (T <= 0) { std::fprintf(stderr, "no T in meta.txt\n"); return 2; }
    const size_t NS = 128 * 48 * 128, C = 10240, HV = 48, S = 128;
    auto s0 = rd(d + "/state0.f32", NS), s1 = rd(d + "/state1.f32", NS), h = rd(d + "/h.f32", T * C),
         gate = rd(d + "/gate.f32", T * HV), beta = rd(d + "/beta.f32", T * HV), z = rd(d + "/z.f32", T * HV * S),
         gamma = rd(d + "/gamma.f32", S), y = rd(d + "/y.f32", T * HV * S);
    float *ds, *dh, *dg, *db, *dz, *dgm, *dy;
    uint16_t* dy16;
    cudaMalloc(&ds, NS * 4); cudaMalloc(&dh, h.size() * 4); cudaMalloc(&dg, gate.size() * 4);
    cudaMalloc(&db, beta.size() * 4); cudaMalloc(&dz, z.size() * 4); cudaMalloc(&dgm, S * 4);
    cudaMalloc(&dy, y.size() * 4); cudaMalloc(&dy16, y.size() * 2);
    cudaMemcpy(dh, h.data(), h.size() * 4, cudaMemcpyHostToDevice);
    cudaMemcpy(dg, gate.data(), gate.size() * 4, cudaMemcpyHostToDevice);
    cudaMemcpy(db, beta.data(), beta.size() * 4, cudaMemcpyHostToDevice);
    cudaMemcpy(dz, z.data(), z.size() * 4, cudaMemcpyHostToDevice);
    cudaMemcpy(dgm, gamma.data(), S * 4, cudaMemcpyHostToDevice);
    cudaStream_t st;
    cudaStreamCreate(&st);
    cudaEvent_t e0, e1;
    cudaEventCreate(&e0); cudaEventCreate(&e1);
    std::vector<float> ms;
    for (int r = 0; r < reps + 1; ++r) {
        cudaMemcpy(ds, s0.data(), NS * 4, cudaMemcpyHostToDevice);
        cudaEventRecord(e0, st);
        strata::prefill::gdn_recurrence(ds, dh, dg, db, dz, dgm, 1e-6f, dy, dy16, T, st);
        cudaEventRecord(e1, st);
        cudaEventSynchronize(e1);
        float t = 0;
        cudaEventElapsedTime(&t, e0, e1);
        if (r > 0) ms.push_back(t);   // rep 0 = warm-up (module load)
    }
    std::vector<float> o1(NS), oy(y.size());
    cudaMemcpy(o1.data(), ds, NS * 4, cudaMemcpyDeviceToHost);
    cudaMemcpy(oy.data(), dy, y.size() * 4, cudaMemcpyDeviceToHost);
    size_t ds_n = 0, dy_n = 0;
    for (size_t i = 0; i < NS; ++i) ds_n += std::memcmp(&o1[i], &s1[i], 4) != 0;
    for (size_t i = 0; i < y.size(); ++i) dy_n += std::memcmp(&oy[i], &y[i], 4) != 0;
    std::sort(ms.begin(), ms.end());
    std::printf("gdn_recurrence T=%lld pipeline=%s: min %.3f median %.3f max %.3f ms over %d reps; vs the engine's own "
                "result: state1 %zu of %zu floats differ, y %zu of %zu differ\n",
                T, std::getenv("STRATA_GDN_PIPELINE") ? std::getenv("STRATA_GDN_PIPELINE") : "default", ms.front(),
                ms[ms.size() / 2], ms.back(), reps, ds_n, NS, dy_n, y.size());
    return (ds_n || dy_n) ? 1 : 0;
}
