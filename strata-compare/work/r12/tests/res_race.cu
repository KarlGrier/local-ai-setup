// res_race.cu — round 11 Phase 0.3, the test for upstream PR #550 on this machine's driver and GPUs.
// The engine uploads its expert residency table (48 layers x 512 experts of int32 = 96 KiB, pageable host memory) with a
// plain cudaMemcpy on the legacy stream, then the verify window's kernels read it on a cudaStreamNonBlocking stream.
// This reproduces that pattern (each 'window' synced before the next upload, as the engine does): each iteration writes the value i into the whole host table, uploads it, and launches a
// kernel on a non-blocking stream that counts the entries that are not i.  mode 0 = the old upload, mode 1 = #550's
// res_put (cudaStreamSynchronize(cudaStreamLegacy) after the copy).  Also with the GPU kept busy by a spin kernel on a
// third stream, as during a served request.  Prints mismatching kernels / entries and the upload time.
#include <cuda_runtime.h>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <vector>

// counts the entries OLDER than the upload this kernel follows (the #550 hazard: the copy had not landed); one block
// per kernel so a kernel is counted once
__global__ void check(const int* t, int n, int want, unsigned long long* bad_entries, unsigned int* bad_kernels) {
    __shared__ int b;
    if (threadIdx.x == 0) b = 0;
    __syncthreads();
    int local = 0;
    for (int i = threadIdx.x; i < n; i += blockDim.x) local += t[i] < want;
    if (local) { atomicAdd(bad_entries, (unsigned long long) local); atomicAdd(&b, 1); }
    __syncthreads();
    if (threadIdx.x == 0 && b) atomicAdd(bad_kernels, 1u);
}

__global__ void busy(long long cycles) {
    const long long t0 = clock64();
    while (clock64() - t0 < cycles) {}
}

int main(int argc, char** argv) {
    const int dev = argc > 1 ? atoi(argv[1]) : 0, iters = argc > 2 ? atoi(argv[2]) : 20000;
    cudaSetDevice(dev);
    cudaDeviceProp p; cudaGetDeviceProperties(&p, dev);
    const int n = 48 * 512;
    std::vector<int> host((size_t) n);
    int* d = nullptr; unsigned long long* be = nullptr; unsigned int* bk = nullptr;
    cudaMalloc(&d, n * sizeof(int)); cudaMalloc(&be, sizeof(*be)); cudaMalloc(&bk, sizeof(*bk));
    cudaStream_t s, s2;
    cudaStreamCreateWithFlags(&s, cudaStreamNonBlocking);
    cudaStreamCreateWithFlags(&s2, cudaStreamNonBlocking);
    for (int load = 0; load < 2; ++load)
        for (int mode = 0; mode < 2; ++mode) {
            cudaMemset(be, 0, sizeof(*be)); cudaMemset(bk, 0, sizeof(*bk)); cudaDeviceSynchronize();
            double up_ms = 0;
            for (int i = 1; i <= iters; ++i) {
                if (load && (i % 64) == 1) busy<<<1, 32, 0, s2>>>(2000000);   // ~1 ms of another stream's work now and then
                for (int k = 0; k < n; ++k) host[(size_t) k] = i;
                const auto a = std::chrono::steady_clock::now();
                cudaMemcpy(d, host.data(), n * sizeof(int), cudaMemcpyHostToDevice);
                if (mode == 1) cudaStreamSynchronize(cudaStreamLegacy);
                up_ms += std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - a).count();
                check<<<1, 1024, 0, s>>>(d, n, i, be, bk);
                cudaStreamSynchronize(s);   // the engine waits for each window before the next upload
            }
            cudaDeviceSynchronize();
            unsigned long long hbe = 0; unsigned int hbk = 0;
            cudaMemcpy(&hbe, be, sizeof(hbe), cudaMemcpyDeviceToHost); cudaMemcpy(&hbk, bk, sizeof(hbk), cudaMemcpyDeviceToHost);
            std::printf("%s (dev %d) %s, %s: %d uploads, kernels that read a stale table %u (%.3f%%), stale entries %llu, "
                        "upload %.1f us each\n", p.name, dev, mode ? "#550 res_put (copy + legacy-stream sync)" : "old plain cudaMemcpy",
                        load ? "GPU busy now and then" : "GPU idle", iters, hbk, 100.0 * hbk / iters, hbe, 1000.0 * up_ms / iters);
        }
    const cudaError_t e = cudaGetLastError();
    std::printf("cuda: %s\n", cudaGetErrorString(e));
    return e != cudaSuccess;
}
