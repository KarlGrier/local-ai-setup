// q6k_parity.cu — round 11 F: the GPU embedding dequantizer for Q6_K (strata::kernels::iq_dequant_f32, type 14) against
// ggml's dequantize_row_q6_K from the build's libggml-base.a, bit for bit, on random Q6_K blocks (all byte patterns of
// ql / qh / scales, normal fp16 d of both signs and several scales).
#include <cuda_runtime.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
namespace strata::kernels { void iq_dequant_f32(int t, const void* src, int64_t n, float* dst, void* stream); }
extern "C" void dequantize_row_q6_K(const void* x, float* y, int64_t k);
int main() {
    const int NB = 20000, BB = 210;   // block_q6_K: ql 128, qh 64, scales 16, d 2
    std::vector<uint8_t> blk((size_t) NB * BB);
    std::mt19937 rng(14);
    for (auto& b : blk) b = (uint8_t) rng();
    std::uniform_real_distribution<float> u(-6.f, 6.f);
    for (int i = 0; i < NB; ++i) {   // d: a normal fp16 of either sign, 2^-14 .. 2^6
        const float v = std::ldexp(1.0f + (rng() % 1024) / 1024.f, (int) (rng() % 20) - 14) * ((rng() & 1) ? -1.f : 1.f);
        uint32_t f; std::memcpy(&f, &v, 4);
        const uint16_t h = (uint16_t) (((f >> 16) & 0x8000) | ((((f >> 23) & 0xff) - 112) << 10) | ((f >> 13) & 0x3ff));
        std::memcpy(&blk[(size_t) i * BB + 208], &h, 2);
    }
    std::vector<float> ref((size_t) NB * 256), gpu((size_t) NB * 256);
    dequantize_row_q6_K(blk.data(), ref.data(), (int64_t) NB * 256);
    void* d_b; float* d_y;
    cudaMalloc(&d_b, blk.size()); cudaMalloc(&d_y, gpu.size() * 4);
    cudaMemcpy(d_b, blk.data(), blk.size(), cudaMemcpyHostToDevice);
    strata::kernels::iq_dequant_f32(14, d_b, (int64_t) NB * 256, d_y, nullptr);
    cudaMemcpy(gpu.data(), d_y, gpu.size() * 4, cudaMemcpyDeviceToHost);
    long bad = 0;
    for (size_t i = 0; i < ref.size(); ++i)
        if (std::memcmp(&ref[i], &gpu[i], 4)) { if (bad < 5) std::printf("DIFF %zu: ref %.9g gpu %.9g\n", i, ref[i], gpu[i]); ++bad; }
    std::printf("q6k parity: %ld of %zu values differ (%s)\n", bad, ref.size(), cudaGetErrorString(cudaGetLastError()));
    return bad != 0;
}
