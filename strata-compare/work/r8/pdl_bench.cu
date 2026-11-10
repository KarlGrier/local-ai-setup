// pdl_bench.cu — round 8 A.1: what a kernel boundary costs inside a CUDA graph on this GPU, and how much programmatic
// dependent launch (PDL) recovers.  A chain of K dependent kernels (each block reads its slice of the previous kernel's
// output and writes its own: a true dependency) is captured into a graph three ways:
//   plain  — ordinary launches (what the verify window does today)
//   pdl    — cudaLaunchKernelEx with programmaticStreamSerializationAllowed; each kernel calls
//            cudaGridDependencySynchronize() before reading its input (the implicit trigger = the end of the previous kernel)
//   pdl+t  — as pdl, and each kernel triggers cudaTriggerProgrammaticLaunchCompletion() at its start (the next kernel's
//            blocks may be scheduled while this one runs; they still wait at the sync for its memory)
// For grids of 1..336 blocks and work of ~1-10 us per kernel; reports us per kernel.  sm_90+ only.
#include <cuda_runtime.h>

#include <algorithm>
#include <cstdio>
#include <vector>

__global__ void step(const float* __restrict__ in, float* __restrict__ out, int n_per_block, int iters, int mode) {
    if (mode == 2) cudaTriggerProgrammaticLaunchCompletion();
    if (mode >= 1) cudaGridDependencySynchronize();
    const int base = blockIdx.x * n_per_block;
    for (int i = threadIdx.x; i < n_per_block; i += blockDim.x) {
        float v = in[base + i];
#pragma unroll 1
        for (int k = 0; k < iters; ++k) v = v * 0.999f + 0.001f;   // a little ALU work per element
        out[base + i] = v;
    }
}

int main() {
    const int K = 2000;
    float *a, *b;
    const size_t cap = (size_t) 336 * 4096;
    cudaMalloc(&a, cap * 4); cudaMalloc(&b, cap * 4);
    cudaMemset(a, 0, cap * 4); cudaMemset(b, 0, cap * 4);
    cudaStream_t s;
    cudaStreamCreateWithFlags(&s, cudaStreamNonBlocking);
    std::printf("%-8s %-7s %-6s %12s %12s %12s   (us per kernel, graph of %d dependent kernels; median of 7)\n",
                "blocks", "n/blk", "iters", "plain", "pdl", "pdl+trigger", K);
    for (int blocks : {1, 8, 84, 336}) {
        for (int iters : {0, 64, 512}) {
            const int npb = 1024;
            double res[3];
            for (int mode = 0; mode < 3; ++mode) {
                cudaGraph_t g;
                cudaStreamBeginCapture(s, cudaStreamCaptureModeThreadLocal);
                for (int k = 0; k < K; ++k) {
                    const float* in = (k & 1) ? b : a;
                    float* out = (k & 1) ? a : b;
                    if (mode == 0) {
                        step<<<blocks, 256, 0, s>>>(in, out, npb, iters, 0);
                    } else {
                        cudaLaunchConfig_t cfg = {};
                        cfg.gridDim = dim3(blocks); cfg.blockDim = dim3(256); cfg.stream = s;
                        cudaLaunchAttribute at[1];
                        at[0].id = cudaLaunchAttributeProgrammaticStreamSerialization;
                        at[0].val.programmaticStreamSerializationAllowed = 1;
                        cfg.attrs = at; cfg.numAttrs = 1;
                        cudaLaunchKernelEx(&cfg, step, in, out, npb, iters, mode);
                    }
                }
                cudaStreamEndCapture(s, &g);
                cudaGraphExec_t ge;
                if (cudaGraphInstantiate(&ge, g, 0) != cudaSuccess) { std::printf("instantiate failed (mode %d): %s\n", mode, cudaGetErrorString(cudaGetLastError())); return 1; }
                cudaEvent_t e0, e1; cudaEventCreate(&e0); cudaEventCreate(&e1);
                std::vector<float> t;
                for (int r = 0; r < 8; ++r) {
                    cudaEventRecord(e0, s); cudaGraphLaunch(ge, s); cudaEventRecord(e1, s); cudaEventSynchronize(e1);
                    float ms; cudaEventElapsedTime(&ms, e0, e1); if (r) t.push_back(ms);
                }
                std::sort(t.begin(), t.end());
                res[mode] = t[t.size() / 2] * 1000.0 / K;
                cudaGraphExecDestroy(ge); cudaGraphDestroy(g);
            }
            std::printf("%-8d %-7d %-6d %12.3f %12.3f %12.3f\n", blocks, 1024, iters, res[0], res[1], res[2]);
        }
    }
    const cudaError_t e = cudaGetLastError();
    std::printf("last error: %s\n", cudaGetErrorString(e));
    return 0;
}
