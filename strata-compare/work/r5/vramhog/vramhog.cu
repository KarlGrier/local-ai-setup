// vramhog.cu - round 5 phase 4: take N MiB of VRAM on the visible device (allocated and written, so it is really
// resident) and hold it until SIGTERM/SIGINT.  Prints the free VRAM before and after.
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <unistd.h>
#include <cuda_runtime.h>
static volatile sig_atomic_t stop = 0;
static void on_sig(int) { stop = 1; }
int main(int argc, char** argv) {
    long long want = argc > 1 ? atoll(argv[1]) : 400;   // negative: take all but that many MiB of what is free
    size_t mib = 0;
    std::signal(SIGTERM, on_sig); std::signal(SIGINT, on_sig);
    size_t f0, t0, f1, t1;
    cudaMemGetInfo(&f0, &t0);
    mib = want >= 0 ? (size_t) want : (size_t) ((long long) (f0 >> 20) + want);
    void* p = nullptr;
    cudaError_t e = cudaMalloc(&p, mib << 20);
    if (e != cudaSuccess) { printf("vramhog: cudaMalloc(%zu MiB) failed: %s (free %zu MiB)\n", mib, cudaGetErrorString(e), f0 >> 20); return 1; }
    cudaMemset(p, 0x5a, mib << 20);
    cudaDeviceSynchronize();
    cudaMemGetInfo(&f1, &t1);
    printf("vramhog: holding %zu MiB (free %zu -> %zu MiB)\n", mib, f0 >> 20, f1 >> 20);
    fflush(stdout);
    while (!stop) sleep(1);
    cudaFree(p);
    printf("vramhog: released\n");
    return 0;
}
