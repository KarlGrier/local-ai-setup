#!/usr/bin/env python3
"""apply_variant.py NAME SRC_DIR - 10-26 (the user): local test variants of Strata v0.2.6's DeepSeek engine, never shipped.
  fix   the one-line follow-up fix (the user, item 6: "build and test the one-line fix (slot keep off, the same 6
        follow-ups) so the issue can say the fix is tested"): ds4_main.cpp:835 pins the anchor whatever the slot setting
  test  two switches, both off unless their variable is set (so the binary otherwise serves and scores as stock v0.2.6):
        DS4_TEST_SEED_RESET=1  a request that carries a seed starts the sampler's draw counter at 0 (stock: the counter
                               runs on across requests, ds4_main.cpp:327) - item 2, the repeat-pair test
        DS4_SCORE_PIECES=K / DS4_SCORE_RESUME=1  in --score with DS4_SCORE_PREFIX: the prefix read in K pieces (as a
                               conversation's turns are read), then the state set aside and taken back (slot_save, reset,
                               slot_load, as a chat resumed from its slot) before the scored positions - item 3
  p343  the port of Maya #343 (the prompt skip on a layer split whose skip layer and every later one share a GPU)
  iqq8k the port of Maya's DS4_IQ_Q8K (low-bit experts' activations rounded as the CPU lane rounds them; =0 off)
  slotram STRATA_DS4_SLOT_RAM_GB caps the bytes of the conversations kept in RAM (10-26, Karl: "cap slot RAM (or long
        slots)" so 16 long chats cannot break the 14 GB rule): past it the least recently used goes to the folder,
        as past STRATA_DS4_SLOT_CAP; unset or 0 = no byte cap (stock)
NAME may join variants with "+" (e.g. p343+borrow: the combined config). Each replacement names its file and must match
exactly once (the tag's text), or nothing is written."""
import sys

names, src = sys.argv[1].split("+"), sys.argv[2]
MAIN, MODEL, GG = "ds4_main.cpp", "ds4_model.cu", "ds4_gguf.cu"
R = []   # (file, old, new)
for name in names:
  if name == "fix":
      R.append((MAIN, "        if (!continued && slot_max > 0) m.pin();",
                "        if (!continued) m.pin();   // (10-26 local fix: the anchor whatever the slot setting)"))
  elif name == "test":
      R.append((MAIN, "        const double t0 = now_ms();\n        std::vector<Pic> pics;",
                "        const double t0 = now_ms();\n"
                "        if (r.seed != 0 && std::getenv(\"DS4_TEST_SEED_RESET\") && std::atoi(std::getenv(\"DS4_TEST_SEED_RESET\")) != 0)\n"
                "            counter = 0;   // (10-26 local test: a seeded request draws from the start of its seed's stream)\n"
                "        std::vector<Pic> pics;"))
      R.append((MAIN, "            a0 = (size_t) prefix_n;\n"
                "            if (!m.feed(ids.data(), (int) a0, 1, err)) {\n"
                "                std::fprintf(stderr, \"strata-dsv41: %s\\n\", err.c_str());\n"
                "                return 1;\n"
                "            }\n",
                "            a0 = (size_t) prefix_n;\n"
                "            // (10-26 local test) DS4_SCORE_PIECES=K: the prefix in K pieces; DS4_SCORE_RESUME=1: then set aside and\n"
                "            // taken back (slot_save, reset, slot_load) before the scored positions\n"
                "            const int pieces = std::getenv(\"DS4_SCORE_PIECES\") ? std::max(1, std::atoi(std::getenv(\"DS4_SCORE_PIECES\"))) : 1;\n"
                "            for (int pc = 0; pc < pieces; ++pc) {\n"
                "                const size_t b = a0 * (size_t) pc / (size_t) pieces, e = a0 * (size_t) (pc + 1) / (size_t) pieces;\n"
                "                if (!m.feed(ids.data() + b, (int) (e - b), 1, err)) {\n"
                "                    std::fprintf(stderr, \"strata-dsv41: %s\\n\", err.c_str());\n"
                "                    return 1;\n"
                "                }\n"
                "            }\n"
                "            if (std::getenv(\"DS4_SCORE_RESUME\") && std::atoi(std::getenv(\"DS4_SCORE_RESUME\")) != 0) {\n"
                "                std::vector<uint8_t> slot;\n"
                "                const uint64_t sb = m.slot_save(slot, err);\n"
                "                if (sb == 0) {\n"
                "                    std::fprintf(stderr, \"strata-dsv41: slot_save: %s\\n\", err.c_str());\n"
                "                    return 1;\n"
                "                }\n"
                "                m.reset();\n"
                "                if (!m.slot_load(slot.data(), slot.size(), (int64_t) a0, err)) {\n"
                "                    std::fprintf(stderr, \"strata-dsv41: slot_load: %s\\n\", err.c_str());\n"
                "                    return 1;\n"
                "                }\n"
                "                std::fprintf(stderr, \"ds4 score: the prefix (%zu tokens, %d pieces) set aside (%llu bytes) and taken back\\n\",\n"
                "                             a0, pieces, (unsigned long long) sb);\n"
                "            }\n"))
  elif name == "p343":
      # Maya #343 (7644743, v1.1.26), the part this engine needs: the prompt skip on a layer split whose skip layer (V4.1:
      # 20) and every layer after it share one GPU (the 4060 Ti first with 10 layers, the 5080 with 30: layers 10-39).
      # run_dev_chunks already runs the skip per (chunk, layer) - the earlier group hands off every row of every chunk, the
      # 5080 takes each hand-off, runs layer 20 kv_only for the chunks before the cut and stops there (runs()); the cut
      # mid-chunk as on one GPU (Maya's cut_rows for this case). Ported: the eligibility (yoco_suffix_gpu, Engram layers
      # from the skip layer on excluded off one GPU), the expert flow's seed for a group that starts at or after the skip
      # layer (not this split's - ported for the general case), and a line in the engine log when the skip engages.
      R.append((MODEL, "        if (yl <= 0 || !L[(size_t) yl].kv_src) return -1;\n"
                "        for (int il = 0; il < g.nl; ++il) {\n"
                "            const Layer& l = L[(size_t) il];\n"
                "            if (l.nm != 1 || l.dev != L[0].dev) return -1;\n"
                "            if (il > yl && (g.ratios[(size_t) il] != 1 || l.kv_src)) return -1;\n"
                "        }\n"
                "        return yl;\n",
                "        if (yl <= 0 || !L[(size_t) yl].kv_src) return -1;\n"
                "        // (10-26 port of Maya #343) every layer on one device, and the skip layer and every one after it on one\n"
                "        // GPU: all of them (as before), or a layer split's last group (the earlier groups hand off every row - the\n"
                "        // skip layer's kv_only needs them - and no Engram layer from the skip layer on)\n"
                "        bool one = true;\n"
                "        for (int il = 0; il < g.nl; ++il) {\n"
                "            const Layer& l = L[(size_t) il];\n"
                "            if (l.nm != 1 || (il >= yl && l.dev != L[(size_t) yl].dev)) return -1;\n"
                "            if (l.dev != L[0].dev) one = false;\n"
                "        }\n"
                "        for (int il = 0; il < g.nl; ++il) {\n"
                "            const Layer& l = L[(size_t) il];\n"
                "            if (il > yl && (g.ratios[(size_t) il] != 1 || l.kv_src)) return -1;\n"
                "            if (!one && il >= yl && l.eg >= 0) return -1;\n"
                "        }\n"
                "        return yl;\n"))
      R.append((MODEL, "            if (!c.fl_layers.empty()) {\n"
                "                flow_spec(c, 0, c.fl_layers[0], run.T[0]);\n",
                "            if (!c.fl_layers.empty()) {\n"
                "                // (10-26 port of Maya #343) a group starting at or after the skip layer has only KV work before the\n"
                "                // cut: its stream starts at the cut's chunk and rows\n"
                "                const int il0 = c.fl_layers[0], k0 = run.yoco >= 0 && il0 >= run.yoco ? run.cut_k : 0;\n"
                "                flow_spec(c, k0, il0, fl_rows(c, k0, il0));\n"))
      R.append((MODEL, "        if (a > 0) {\n"
                "            run.yoco = yl;\n"
                "            run.cut_k = a / per;\n"
                "            run.cut_r = a - run.cut_k * per;\n"
                "        }\n",
                "        if (a > 0) {\n"
                "            run.yoco = yl;\n"
                "            run.cut_k = a / per;\n"
                "            run.cut_r = a - run.cut_k * per;\n"
                "            std::fprintf(stderr, \"ds4: prompt skip: layers %d-%d from CUDA%d, %d early rows KV-only, %d kept\\n\",\n"
                "                         yl, g.nl - 1, devs[(size_t) L[(size_t) yl].dev].id, a, n - a);   // (10-26 port of Maya #343)\n"
                "        }\n"))
  elif name == "iqq8k":
      # Maya's DS4_IQ_Q8K (7a15afc, v1.1.18; default on there): the GPU's low-bit expert kernels take their activations
      # rounded as the CPU lane rounds them (ggml's Q8_K: per 256 values, the first largest magnitude, iscale -127 / max,
      # q = min(127, nearest(iscale x)), d = 1 / iscale written to each of the 256's eight 32-blocks, so the kernels'
      # interface - int8 + one scale per 32 - stays), instead of q8_1's per-32 rounding: an expert then gives the same
      # sums on either lane, up to their order. Default on in this variant; DS4_IQ_Q8K=0 = the per-32 rounding as before
      # (the same binary for the with / without comparisons). Kernel copied from Maya v1.1.28 ds4_gguf.cu:244-298.
      R.append((GG, "void q8_quant(const float* x, size_t ldx, int rows, int k, int8_t* q, float* d, cudaStream_t s) {\n"
                    "    const dim3 grid((unsigned) ((k / 32 + kWarps - 1) / kWarps), (unsigned) rows);\n"
                    "    q8_quant_kernel<<<grid, kThreads, 0, s>>>(x, ldx, k, q, d);\n"
                    "}\n",
                    "void q8_quant(const float* x, size_t ldx, int rows, int k, int8_t* q, float* d, cudaStream_t s) {\n"
                    "    const dim3 grid((unsigned) ((k / 32 + kWarps - 1) / kWarps), (unsigned) rows);\n"
                    "    q8_quant_kernel<<<grid, kThreads, 0, s>>>(x, ldx, k, q, d);\n"
                    "}\n"
                    "\n"
                    "// ---- (10-26 port of Maya's DS4_IQ_Q8K, v1.1.18) the low-bit experts' activations as the CPU lane rounds them (ggml's\n"
                    "// Q8_K, quantize_row_q8_K_ref): per 256 values max = the signed value of the largest magnitude (the first one),\n"
                    "// iscale = -127 / max, q = min(127, nearest_int(iscale x)) - the product rounded to F32 before the magic-number\n"
                    "// rounding, as the source does - and d = 1 / iscale, written to each of the 256's eight 32-blocks of d: the kernels'\n"
                    "// sums then take the CPU lane's int8 values and scale, so an expert gives the same sums on either lane (up to their\n"
                    "// order) wherever the placement or the expert cache puts it.  DS4_IQ_Q8K=0: the per-32 rounding (q8_1's), as before\n"
                    "__device__ __forceinline__ int q8k_nearest(float fval) {   // ggml's nearest_int\n"
                    "    const float val = __fadd_rn(fval, 12582912.0f);\n"
                    "    int i;\n"
                    "    memcpy(&i, &val, 4);\n"
                    "    return (i & 0x007fffff) - 0x00400000;\n"
                    "}\n"
                    "__global__ void __launch_bounds__(256) q8k_quant_kernel(const float* __restrict__ x, size_t ldx, int k,\n"
                    "                                                        int8_t* __restrict__ q, float* __restrict__ d) {\n"
                    "    __shared__ float s_am[8];\n"
                    "    __shared__ int s_at[8];\n"
                    "    const int r = blockIdx.y, j = (int) threadIdx.x, lane = j & 31, w = j >> 5;\n"
                    "    const size_t at = (size_t) blockIdx.x * 256 + (size_t) j;\n"
                    "    const float v = x[(size_t) r * ldx + at];\n"
                    "    float am = fabsf(v);\n"
                    "    int ix = j;   // (the first index of the largest magnitude: ties keep the lower one)\n"
                    "#pragma unroll\n"
                    "    for (int o = 16; o > 0; o >>= 1) {\n"
                    "        const float oa = __shfl_xor_sync(0xffffffffu, am, o);\n"
                    "        const int oi = __shfl_xor_sync(0xffffffffu, ix, o);\n"
                    "        if (oa > am || (oa == am && oi < ix)) am = oa, ix = oi;\n"
                    "    }\n"
                    "    if (lane == 0) s_am[w] = am, s_at[w] = ix;\n"
                    "    __syncthreads();\n"
                    "    if (j == 0) {\n"
                    "        for (int i = 1; i < 8; ++i)\n"
                    "            if (s_am[i] > s_am[0] || (s_am[i] == s_am[0] && s_at[i] < s_at[0])) s_am[0] = s_am[i], s_at[0] = s_at[i];\n"
                    "    }\n"
                    "    __syncthreads();\n"
                    "    const float amax = s_am[0];\n"
                    "    int8_t qv = 0;\n"
                    "    float dv = 0.0f;\n"
                    "    if (amax > 0.0f) {\n"
                    "        const float mx = x[(size_t) r * ldx + (size_t) blockIdx.x * 256 + (size_t) s_at[0]];\n"
                    "        const float iscale = __fdiv_rn(-127.0f, mx);\n"
                    "        qv = (int8_t) min(127, q8k_nearest(__fmul_rn(iscale, v)));\n"
                    "        dv = __fdiv_rn(1.0f, iscale);\n"
                    "    }\n"
                    "    q[(size_t) r * k + at] = qv;\n"
                    "    if (lane == 0) d[(size_t) r * (k / 32) + at / 32] = dv;\n"
                    "}\n"
                    "void q8k_quant(const float* x, size_t ldx, int rows, int k, int8_t* q, float* d, cudaStream_t s) {\n"
                    "    q8k_quant_kernel<<<dim3((unsigned) (k / 256), (unsigned) rows), 256, 0, s>>>(x, ldx, k, q, d);\n"
                    "}\n"
                    "bool iq_q8k() {\n"
                    "    static const bool on = [] {\n"
                    "        const char* v = std::getenv(\"DS4_IQ_Q8K\");\n"
                    "        return v == nullptr || std::atoi(v) != 0;\n"
                    "    }();\n"
                    "    return on;\n"
                    "}\n"
                    "void iq_act_quant(const float* x, size_t ldx, int rows, int k, int8_t* q, float* d, cudaStream_t s) {\n"
                    "    if (iq_q8k() && k % 256 == 0) q8k_quant(x, ldx, rows, k, q, d, s);\n"
                    "    else q8_quant(x, ldx, rows, k, q, d, s);\n"
                    "}\n"))
      R.append((GG, "        q8_quant(x, (size_t) a.n_embd, 1, a.n_embd, sc->xq, sc->xd, s);\n        iq::gate_up(ia, a.k, 1, s);\n",
                    "        iq_act_quant(x, (size_t) a.n_embd, 1, a.n_embd, sc->xq, sc->xd, s);   // (10-26 IQ_Q8K port)\n"
                    "        iq::gate_up(ia, a.k, 1, s);\n"))
      R.append((GG, "    q8_quant(h, (size_t) a.n_ff, a.k, a.n_ff, sc->hq, sc->hd, s);\n",
                    "    (mx_experts(a.lay) ? q8_quant : iq_act_quant)(h, (size_t) a.n_ff, a.k, a.n_ff, sc->hq, sc->hd, s);   // (IQ_Q8K)\n"))
      R.append((GG, "    q8_quant(a.x, a.x_stride, a.T, a.n_embd, sc->xq, sc->xd, s);\n",
                    "    (mx_experts(a.lay) ? q8_quant : iq_act_quant)(a.x, a.x_stride, a.T, a.n_embd, sc->xq, sc->xd, s);   // (IQ_Q8K)\n"))
      R.append((GG, "    q8_quant(a.h, (size_t) a.n_ff, a.T * 8, a.n_ff, sc->hq, sc->hd, s);   // (rows of picks not on the device: unused)\n",
                    "    (mx_experts(a.lay) ? q8_quant : iq_act_quant)(a.h, (size_t) a.n_ff, a.T * 8, a.n_ff, sc->hq, sc->hd, s);   // (rows of picks\n"
                    "    // not on the device: unused; IQ_Q8K)\n"))
  elif name == "slotram":
      R.append((MAIN, "    const uint64_t slot_budget = (uint64_t) (env_num(\"STRATA_DS4_SLOT_GB\", 16) * 1073741824.0);\n",
                "    const uint64_t slot_budget = (uint64_t) (env_num(\"STRATA_DS4_SLOT_GB\", 16) * 1073741824.0);\n"
                "    // (10-26 local) STRATA_DS4_SLOT_RAM_GB: the bytes of the conversations kept in RAM, past which the least recently\n"
                "    // used goes to the folder as past STRATA_DS4_SLOT_CAP (0 or unset: no byte cap)\n"
                "    const uint64_t slot_ram_budget = (uint64_t) (env_num(\"STRATA_DS4_SLOT_RAM_GB\", 0) * 1073741824.0);\n"))
      R.append((MAIN, "            slot_count(ram, disk);\n            if (ram <= slot_max) break;\n",
                "            slot_count(ram, disk);\n"
                "            uint64_t ram_bytes = 0;\n"
                "            for (const Slot& s : slots)\n"
                "                if (s.data) ram_bytes += s.data->size();\n"
                "            if (ram <= slot_max && (slot_ram_budget == 0 || ram_bytes <= slot_ram_budget)) break;   // (10-26 local)\n"))
  else:
      sys.exit(f"unknown variant {name}")
texts = {}
for fn, old, new in R:
    path = f"{src}/src/dsv41/{fn}"
    t = texts.setdefault(path, open(path).read())
    if t.count(old) != 1:
        sys.exit(f"{sys.argv[1]}: the text to replace occurs {t.count(old)} times in {fn} (expected 1): {old[:80]!r}")
    texts[path] = t.replace(old, new)
for path, t in texts.items():
    open(path, "w").write(t)
print(f"{sys.argv[1]}: {len(R)} change(s) in {', '.join(sorted(texts))}")
