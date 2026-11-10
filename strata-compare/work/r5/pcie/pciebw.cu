// pciebw.cu - pinned host<->device copy bandwidth on the visible device 0 for `secs` seconds (round 5 PCIe check)
#include <cstdio>
#include <cstdlib>
#include <chrono>
#include <cuda_runtime.h>
int main(int argc, char** argv) {
    double secs = argc > 1 ? atof(argv[1]) : 6.0;
    const char* dir = argc > 2 ? argv[2] : "h2d";
    size_t bytes = 256ull << 20;
    void *h, *d;
    cudaDeviceProp p; cudaGetDeviceProperties(&p, 0);
    if (cudaMallocHost(&h, bytes) != cudaSuccess || cudaMalloc(&d, bytes) != cudaSuccess) { printf("alloc failed\n"); return 1; }
    memset(h, 1, bytes);
    bool h2d = dir[0] == 'h';
    cudaEvent_t a, b; cudaEventCreate(&a); cudaEventCreate(&b);
    auto t0 = std::chrono::steady_clock::now();
    double best = 0, sum = 0; int n = 0;
    while (std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count() < secs) {
        cudaEventRecord(a);
        for (int i = 0; i < 8; ++i)
            h2d ? cudaMemcpyAsync(d, h, bytes, cudaMemcpyHostToDevice) : cudaMemcpyAsync(h, d, bytes, cudaMemcpyDeviceToHost);
        cudaEventRecord(b); cudaEventSynchronize(b);
        float ms; cudaEventElapsedTime(&ms, a, b);
        double gbs = 8.0 * bytes / (ms * 1e-3) / 1e9;
        if (gbs > best) best = gbs; sum += gbs; ++n;
    }
    printf("%s %s (%s): %s mean %.2f GB/s, best %.2f GB/s over %d x 2 GiB\n", p.name, p.pciBusID == 1 ? "bus 01" : "bus 10",
           dir, h2d ? "host->device" : "device->host", sum / n, best, n);
    return 0;
}
