// q8k_parity.cu — round 11 A.2: the GPU's Q8_K rows (strata::kernels::quantize_q8k_rows, the same block code as the
// doorbell's) against ggml's own quantize_row_q8_K_ref (linked from the build's libggml-base.a, the function the CPU
// pool's quantize_row_q8_K calls), byte for byte (d, qs; bsums except where amax is 0, which ggml leaves unwritten).
// Inputs: Gaussian activations at several scales, rows with ties of |max| (+x and -x, first wins), a zero block,
// denormals, huge values, and real-scale FFN inputs (|x| up to ~50).
#include <cuda_runtime.h>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
namespace strata::kernels { void quantize_q8k_rows(const float* x, int n_tok, int n_embd, uint8_t* out, void* stream); }
extern "C" void quantize_row_q8_K_ref(const float* x, void* y, int64_t k);
int main() {
    const int N = 2560, NB = N / 256, B = 292, T = 512;
    std::vector<float> x((size_t) T * N);
    std::mt19937 rng(11);
    std::normal_distribution<float> g(0.f, 1.f);
    for (int t = 0; t < T; ++t) {
        const float sc = t < 128 ? 1.f : t < 256 ? 0.03f : t < 384 ? 7.f : 50.f;
        for (int i = 0; i < N; ++i) x[(size_t) t * N + i] = g(rng) * sc;
    }
    // edge rows: ties of |max| with both signs (first wins), a zero block, denormals, huge, exact halves
    for (int i = 0; i < N; ++i) x[(size_t) 0 * N + i] = (i % 7) * 0.5f - 1.5f;
    x[(size_t) 1 * N + 3] = 4.f; x[(size_t) 1 * N + 9] = -4.f;
    x[(size_t) 2 * N + 3] = -4.f; x[(size_t) 2 * N + 9] = 4.f;
    for (int i = 0; i < 256; ++i) x[(size_t) 3 * N + i] = 0.f;
    for (int i = 256; i < 512; ++i) x[(size_t) 3 * N + i] = 1e-40f * (i - 300);
    for (int i = 0; i < N; ++i) x[(size_t) 4 * N + i] = (i & 1 ? 1e30f : -3e29f) * (i % 13);
    for (int i = 0; i < N; ++i) x[(size_t) 5 * N + i] = (float) ((i % 255) - 127) / 127.f;
    std::vector<uint8_t> ref((size_t) T * NB * B), gpu((size_t) T * NB * B);
    for (int t = 0; t < T; ++t) quantize_row_q8_K_ref(&x[(size_t) t * N], &ref[(size_t) t * NB * B], N);
    float* dx; uint8_t* dq;
    cudaMalloc(&dx, x.size() * 4); cudaMalloc(&dq, gpu.size());
    cudaMemcpy(dx, x.data(), x.size() * 4, cudaMemcpyHostToDevice);
    strata::kernels::quantize_q8k_rows(dx, T, N, dq, nullptr);
    cudaMemcpy(gpu.data(), dq, gpu.size(), cudaMemcpyDeviceToHost);
    long bad = 0, blocks = 0, zero = 0;
    for (int t = 0; t < T; ++t)
        for (int b = 0; b < NB; ++b) {
            const uint8_t* r = &ref[((size_t) t * NB + b) * B];
            const uint8_t* q = &gpu[((size_t) t * NB + b) * B];
            float d; std::memcpy(&d, r, 4);
            const size_t cmp = d == 0.f ? 4 + 256 : (size_t) B;   // ggml leaves a zero block's bsums unwritten
            zero += d == 0.f;
            ++blocks;
            if (std::memcmp(r, q, cmp) != 0) {
                if (bad < 5) {
                    int j = 0; while (j < (int) cmp && r[j] == q[j]) ++j;
                    std::printf("DIFF token %d block %d first byte %d: ref %u gpu %u\n", t, b, j, r[j], q[j]);
                }
                ++bad;
            }
        }
    std::printf("q8k parity: %ld of %ld blocks differ (%ld zero blocks compared on d + qs) on %s\n", bad, blocks, zero,
                cudaGetErrorString(cudaGetLastError()));
    return bad != 0;
}
