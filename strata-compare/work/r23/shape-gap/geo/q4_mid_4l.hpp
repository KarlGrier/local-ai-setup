// q4_mid_4l: written by tools/q4geo_synth.py from shape q4_mid, 4 layers.
// Take it with -DSTRATA_GEOMETRY_FILE=<this file>.
#pragma once

namespace strata::core {

inline constexpr const char* kGeometryName = "q4_mid_4l";
inline constexpr ModelGeometry kCompiledGeometry = [] {
    ModelGeometry g;
    g.n_embd = 3072;
    g.n_layers = 4;
    g.qsa_interval = 4;
    g.n_head = 32;
    g.n_head_kv = 2;
    g.head_dim = 256;
    g.n_rot = 64;
    g.ssm_state_size = 128;
    g.ssm_k_heads = 16;
    g.ssm_v_heads = 64;
    g.ssm_d_conv = 4;
    g.idx_q_heads = 4;
    g.idx_key_dim = 128;
    g.idx_block = 4;
    g.idx_top_k = 2048;
    g.hc = 4;
    g.hc_lr = 384;
    g.n_expert = 256;
    g.n_expert_used = 8;
    g.n_ff = 1024;
    g.n_ff_shexp = g.n_ff;
    g.ssm_conv_channels = 2 * g.ssm_state_size * g.ssm_k_heads + g.ssm_state_size * g.ssm_v_heads;
    g.ssm_value_dim = g.ssm_state_size * g.ssm_v_heads;
    return g;
}();

}  // namespace strata::core
