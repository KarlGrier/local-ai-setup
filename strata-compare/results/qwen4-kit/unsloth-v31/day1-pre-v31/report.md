# Qwen4 day one: header check (2026-11-04 12:03, day1.py 2026-11-04)

Headers only: no tensor data read, no download, no GPU, no engine. Engine tables from `strata-r22p0210` @ fdd2fffa8 (branch r22-port0210; build options STRATA_Q6K_EXPERTS=ON, STRATA_MMQ_KQUANTS=ON, STRATA_ORCA_Q4KS_MMQ=OFF, STRATA_MMQ_TQ_OVERLAY=ON; CUDA archs 89;120), read from its source at run time. Reference model: `Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf` (served, P028x).

## The engine's type tables (what Strata actually runs)

| path | types | source |
|---|---|---|
| routed experts, gate/up (both cards: one kernel set for sm_120 + sm_89) | IQ1_M, IQ2_S, IQ2_XS, IQ2_XXS, IQ3_S, IQ3_XXS, IQ4_XS, NVFP4, Q2_0, Q4_0, Q4_1, Q4_K, Q5_0, Q5_K, Q6_K, Q8_0, TQ2_T, TQK6, TQP5, TQP6, TQP7 | src/kernels/cuda/iq_kernels.cu:846 |
| routed experts, down (both cards) | IQ4_NL, IQ4_XS, NVFP4, Q2_0, Q4_0, Q4_1, Q5_0, Q5_1, Q5_K, Q6_K, Q8_0, TQ2_T, TQK7, TQP5, TQP6, TQP7 | src/kernels/cuda/iq_kernels.cu:851 |
| ... only with -DSTRATA_Q6K_EXPERTS=ON (here ON) | Q6_K | CMakeLists.txt / build/CMakeCache.txt |
| expert rule | same gate/up type a layer (pack), n_embd % 256 == 0, rows whole blocks, NVFP4 with .scale | src/kernels/cuda/iq_kernels.cu:5477, tools/iq_pack.py:460 |
| expert prompt path, MMQ | IQ2_S, IQ2_XS, IQ2_XXS, IQ3_S, IQ3_XXS, IQ4_NL, IQ4_XS, NVFP4, Q2_0, Q4_K, Q5_1, Q5_K, Q6_K, Q8_0, TQ2_T, TQK6, TQK7 (else the FP16 dequantizer: IQ1_M, Q3_K, Q4_0, Q4_1, Q5_0, TQP5, TQP6, TQP7) | src/prefill/moe_mmq.cu:318 |
| expert prompt path, fused int8 (5080 only: sm_120, 80+ SMs) | gate/up IQ2_S, IQ3_S, IQ3_XXS, IQ4_XS with down IQ4_NL, Q2_0 | src/prefill/moe_fused_iq.cu:2271, include/strata/core/sm120_series.hpp |
| CPU expert pool | any ggml-cpu dot product + trellis TQ2_T, TQK6, TQK7, TQP5, TQP6, TQP7; fast: AVX-512 IQ2_S, IQ2_XS, IQ2_XXS, IQ3_S, IQ3_XXS, multi-token IQ1_M, IQ2_S, IQ2_XS, IQ2_XXS, IQ3_S, IQ3_XXS, AVX2 IQ2_S, IQ2_XS, IQ2_XXS, IQ3_S, IQ3_XXS, IQ4_XS, K/Q Q4_K, Q5_1, Q8_0, IQ4_NL down, NVFP4 | src/kernels/cpu/native_expert.cpp:173, src/kernels/cpu/native_expert.cpp:163 |
| dense projections (attn, ssm_out, shared expert) + head | IQ1_M, IQ2_S, IQ2_XS, IQ2_XXS, IQ3_S, IQ3_XXS, IQ4_NL, IQ4_XS, Q2_0, Q3_K, Q4_0, Q4_K, Q5_0, Q5_1, Q5_K, Q6_K, Q8_0 (interleaved: IQ4_XS, Q3_K, Q4_K, Q5_K, Q6_K) or F32/F16/BF16 | src/kernels/cuda/native_mmvq.cu:3520, src/core/native_dense.cpp:199 |
| token embedding | BF16, IQ1_M, IQ2_S, IQ2_XS, IQ2_XXS, IQ3_S, IQ3_XXS, IQ4_NL, IQ4_XS, NVFP4, Q2_0, Q3_K, Q4_0, Q4_1, Q4_K, Q5_0, Q5_1, Q5_K, Q6_K, Q8_0, TQ2_T, TQK6, TQK7, TQP5, TQP6, TQP7 | src/kernels/cuda/iq_kernels.cu:5324 |
| float forms (router, hyper-connections, indexer, GDN gates, PLE key/value BF16; norms F32; PLE conv F16) | 31 roles | tools/iq_pack.py FORM (tools/iq_pack.py:72) |
| n-gram table | IQ4_NL (IQ4_NL), Q5_0 (Q5_0), F8_E4M3 (I8), Q5_1 (Q5_1), Q8_0 (Q8_0), Q4_0 (Q4_0), BF16 (BF16), NVFP4 (I8) | src/kernels/ngram.cpp:185 |
| architectures | qwen4exp -> Qwen4Exp, qwen35moe -> Qwen35Moe, deepseek41 -> DeepSeek41 (strata-dsv41, its own engine: not the Qwen path) | include/strata/artifact/model_family.hpp:22 |
| compiled geometry (pinned keys) | block_count, embedding_length, full_attention_interval, ssm.state_size, ssm.group_count, ssm.time_step_rank, ssm.conv_kernel, ssm.inner_size, attention.head_count, attention.head_count_kv, attention.key_length, rope.dimension_count, attention.indexer.head_count, attention.indexer.key_length, attention.compress_ratios, attention.indexer.top_k, hyper_connection.count, hyper_connection.low_rank, expert_feed_forward_length | include/strata/artifact/gguf_reader.hpp:805 |
| router top-k kernel | [(512, 10), (256, 8)] | src/kernels/cuda/native_router.cu:236 |
| setup.py name check (setup only) | refuses quant names not in its MODELS: Strata runs ISTA-DASLab's GSQ-RCO files (Qwen3.8-Flash-Next Q2_0, IQ2_XS, IQ3_XXS, IQ3_S; Swift 1.5's; the Coder's IQ1_M) and Unsloth's UD-IQ4_XS, UD-Q4_K_XL, UD-Q5_K_XL, UD-Q6_K_XL and Q8_0 only: oth... | setup.py:3252 |

Extra type ids from the tree's tools/gguf_reader.py: PTQ1_0 = 143, TQ2_T = 144, TQK6 = 145, TQK7 = 146, TQP5 = 147, TQP6 = 148, TQP7 = 149.

## Expert room today (Karl's quant rule: the largest quant whose experts fit RAM + VRAM)

Every input is a parameter of `day1.py check` (defaults: this PC, measured). Per model the dense weights, the K/V at the served context, the embedding and the drafter change the 5080's share and the RAM tier:

| input | value | where it comes from |
|---|---|---|
| RAM: MemTotal | 92.0 GiB (now 92.0 GiB) | 96 GB DDR5-6000; the engine's guard line "limit 92.0 GiB (source: meminfo)" (logs/engine-P028x.log) |
| RAM: MemAvailable floor | 12.0 GiB | Karl's rule since 10-19 (memory: MemAvailable floor 12 GB) |
| RAM: everything else | 16.3 GiB at Flash-Next's K/V and a 2 GiB chat cache | engine outside the tier + pinned K/V 1.55 GiB + chat cache 2 GiB + OS, desktop and the daily services (SearXNG x3, LDR, Jan, watchers): the 64 GiB splice arms hit the 12 GiB guard (results/sweep-1103/summary.txt, 11.7-12.0 GiB; results/sweep-1103/UPGRADE-ESTIMATE.md 7.3) |
| RAM: headroom | 5.7 GiB | the 58 GiB tier ran clean (splice58 arms); chat parking grows ~3 GiB/h; the NVFP4 pack's 63.3 GiB arena dipped to 6.7 GiB MemAvailable (10-16) |
| RAM: chat cache cap | 2 GiB | the splice58 arms' --chat-cache-mib 2048 (P028x serves 12288: up to 10 GiB less tier) |
| 5080 | 16303 MiB - 2.11 GiB overhead - dense - resident K/V (32768 cells) - 713 + 89 MiB | bringup/fitplan.py's calibration (P021m/P028x start: 9.53 GiB free before the cache, 4,585 slots = 8.75 GiB); the overhead holds Flash-Next's 0.82 GiB drafter |
| helpers | 7.56 GiB free @ 288.0 GB/s - 512 MiB each | the 4060 Ti's "7.56 GiB free before expert arena registration"; the engine keeps 512 MiB free (remote_experts.cpp) |
| context | 131072 cells, K/V int8 | the served --max-context |

For Flash-Next (the served IQ3_S, as a check of the inputs): 5080 8.75 GiB (measured 8.75) + helper 7.06 + RAM tier 58.00 = **73.8 GiB**. With section 8's Qwen4 guess (dense 3.7-4.6 GiB, more K/V and a larger drafter: 5080 ~7.3 GiB) the same sum is the plan's **about 72 GiB**.

## Candidates and the pick

### Model group: qwen4exp, 48 layers x 512 experts, n_embd 2560

| file | general.name | quant | experts | dense (GPU) | fits | runs | verdict |
|---|---|---|---|---|---|---|---|
| `Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00003.gguf` | Qwen3.8 Flash Next | UD-IQ3_XXS | 45.29 GiB (3.22 bpw) | 4.15 GiB | yes | yes | RUNS WITH A PACK CONVERSION **<- PICK** |
| `Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf` | Qwen3.8 Flash Next | UD-Q2_K_XL | 42.92 GiB (3.05 bpw) | 3.71 GiB | yes | yes | RUNS WITH A PACK CONVERSION |

**Pick:** `Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00003.gguf` - the largest that fits and runs: 45.29 GiB of experts in 73.38 GiB of room (margin 28.10 GiB)

## `Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00003.gguf`

- **RUNS WITH A PACK CONVERSION** - arch `qwen4exp`, name 'Qwen3.8 Flash Next', 3 shard(s) (HEAD-ONLY: sizes from NAME.size), 82.0 GB; per-tensor table: `files/Qwen3.8-Flash-Next-UD-IQ3_XXS.tensors.tsv`, keys: `files/Qwen3.8-Flash-Next-UD-IQ3_XXS.keys.txt`
- conversion: GDN (linear attention): F32 -> BF16: exact when every value is BF16 (iq_pack checks the low 16 bits at pack time); else --compat-bf16 (nearest-even rounding)
- conversion: hyper-connections: F32 -> BF16: exact when every value is BF16 (iq_pack checks the low 16 bits at pack time); else --compat-bf16 (nearest-even rounding)
- conversion: hyper-connections: Q8_0 -> BF16 needs iq_pack --compat-bf16 (tools/iq_pack.py:245)
- conversion: n-gram (PLE) projections: F32 -> F16 by the loader (index kind 3, nearest-even): exact only if the values are F16's
- conversion: n-gram (PLE) projections: Q8_0 -> BF16 needs iq_pack --compat-bf16 (tools/iq_pack.py:245)
- conversion: router: F32 -> BF16: exact when every value is BF16 (iq_pack checks the low 16 bits at pack time); else --compat-bf16 (nearest-even rounding)
- conversion: shared expert: F32 -> BF16: exact when every value is BF16 (iq_pack checks the low 16 bits at pack time); else --compat-bf16 (nearest-even rounding)
- setup.py would refuse this file by its name (UD-IQ3_XXS); our configs do not go through setup
- present: MTP/nextn none; n-gram table yes (blk.N.ple_conv1d.weight, blk.N.ple_key.weight, blk.N.ple_norm_conv.weight, blk.N.ple_norm_key.weight, blk.N.ple_norm_query.weight, blk.N.ple_value.weight); vision tensors 0; NVFP4 scales 0; prism keys -
- shape keys (37): block_count=48, context_length=262144, embedding_length=2560, attention.head_count=24, attention.head_count_kv=2, rope.dimension_sections=[11, 11, 10, 0], rope.freq_base=10000000.0, attention.layer_norm_rms_epsilon=9.999999974752427e-07, expert_count=512, expert_used_count=10, attention.key_length=256, attention.value_length=256, expert_feed_forward_length=640, expert_shared_feed_forward_length=640, ssm.conv_kernel=4, ssm.state_size=128, ssm.group_count=16, ssm.time_step_rank=48, ssm.inner_size=6144, full_attention_interval=4, rope.dimension_count=64, hyper_connection.count=4, hyper_connection.low_rank=320, attention.indexer.head_count=4, attention.indexer.key_length=128, attention.indexer.top_k=2048, attention.compress_ratios=[48 items] [0, 0, 0, 4, 0, 0] ..., ple.layers=[1], ple.ngram_size=3, ple.heads_per_ngram=8, ple.conv_kernel=4, ple.eos_token_id=248044, embedding_length_per_layer_input=160, ple.layer_multipliers=[23703573157769, 20109073645365, 8052911324071], ple.head_offsets=[0, 20000003, 40000026, 60000059, 80000106, 100000165, 120000228, 140000297, 160000374, 180000455, 200000548, 220000655, 240000802, 260000955, 280001114, 300001275], ple.head_vocab_sizes=[20000003, 20000023, 20000033, 20000047, 20000059, 20000063, 20000069, 20000077, 20000081, 20000093, 20000107, 20000147, 20000153, 20000159, 20000161, 20000171], ple.image_token_id=248056
- tokenizer: gpt2 / qwen35, vocab 248320, eos [248046, '<|im_end|>'], bos [248044, '<|endoftext|>'], pad [248044, '<|endoftext|>'], think tags [248068, 248069], im_start 248045; template 9993 chars, efforts ['low', 'medium', 'xhigh'] (default xhigh), thinking off yes, tools XML <function=...><parameter=...> in <tool_call>, context_length 262144
- vs Flash-Next: same tokenizer: the frozen prompt token files are valid (tokens_sha =, merges_sha =, types_sha =, template_sha =, special_ids =)

| tensor group | tensors | GiB | types | verdict | why |
|---|---|---|---|---|---|
| head | 1 | 0.486 | Q6_K 1 | OK | OK: native head (native_mmvq_supported src/kernels/cuda/native_mmvq.cu:3520) (1x, e.g. output.weight) |
| hyper-connections | 387 | 0.647 | Q8_0 194, F32 193 | PACK (rounding) | PACK (rounding): Q8_0 -> BF16 needs iq_pack --compat-bf16 (tools/iq_pack.py:245) (194x, e.g. output_hc_down.weight); OK: in the pack (dense.bin) as stored: the engine reads F32 (iq_pack FORM tools/iq_pack.py:72) (97x, e.g. output_hc_norm.weight); PACK (exact if the values allow): F32 -> BF16: exact when every value is BF16 (iq_pack checks the low 16 bits at pack time); else --compat-bf16 (nearest-even rounding) (96x, e.g. blk.0.hc_attn_inject.weight) |
| n-gram (PLE) table | 1 | 26.822 | IQ4_NL 1 | OK | OK: n-gram table read from its GGUF (IQ4_NL; ngram.cpp kPleFormats src/kernels/ngram.cpp:185) (1x, e.g. per_layer_token_embd.weight) |
| token embedding | 1 | 0.486 | Q6_K 1 | OK | OK: native embedding from the GGUF (embed_type_supported src/kernels/cuda/iq_kernels.cu:5324) (1x, e.g. token_embd.weight) |
| attention | 144 | 1.620 | Q6_K 118, Q8_0 2, F32 24 | OK | OK: native dense projection from the GGUF (+ the interleaved MMVQ_IL kernel) (src/core/native_dense.cpp:199) (118x, e.g. blk.0.attn_gate.weight); OK: native dense projection from the GGUF (src/core/native_dense.cpp:199) (2x, e.g. blk.2.attn_gate.weight); OK: in the pack (dense.bin) as stored: the engine reads F32 (iq_pack FORM tools/iq_pack.py:72) (24x, e.g. blk.3.attn_k_norm.weight) |
| routed experts | 144 | 45.288 | IQ4_NL 48, IQ2_S 94, IQ3_S 2 | OK | per layer: see below |
| shared expert | 192 | 0.199 | Q8_0 50, F32 48, Q6_K 94 | PACK (exact if the values allow) | OK: native dense projection from the GGUF (src/core/native_dense.cpp:199) (50x, e.g. blk.0.ffn_down_shexp.weight); PACK (exact if the values allow): F32 -> BF16: exact when every value is BF16 (iq_pack checks the low 16 bits at pack time); else --compat-bf16 (nearest-even rounding) (48x, e.g. blk.0.ffn_gate_inp_shexp.weight); OK: native dense projection from the GGUF (+ the interleaved MMVQ_IL kernel) (src/core/native_dense.cpp:199) (94x, e.g. blk.0.ffn_gate_shexp.weight) |
| router | 48 | 0.234 | F32 48 | PACK (exact if the values allow) | PACK (exact if the values allow): F32 -> BF16: exact when every value is BF16 (iq_pack checks the low 16 bits at pack time); else --compat-bf16 (nearest-even rounding) (48x, e.g. blk.0.ffn_gate_inp.weight) |
| GDN (linear attention) | 252 | 0.471 | F32 216, Q6_K 36 | PACK (exact if the values allow) | OK: in the pack (dense.bin) as stored: the engine reads F32 (iq_pack FORM tools/iq_pack.py:72) (144x, e.g. blk.0.ssm_a); PACK (exact if the values allow): F32 -> BF16: exact when every value is BF16 (iq_pack checks the low 16 bits at pack time); else --compat-bf16 (nearest-even rounding) (72x, e.g. blk.0.ssm_alpha.weight); OK: native dense projection from the GGUF (+ the interleaved MMVQ_IL kernel) (src/core/native_dense.cpp:199) (36x, e.g. blk.0.ssm_out.weight) |
| n-gram (PLE) projections | 6 | 0.033 | F32 4, Q8_0 2 | PACK (rounding) | PACK (exact if the values allow): F32 -> F16 by the loader (index kind 3, nearest-even): exact only if the values are F16's (1x, e.g. blk.1.ple_conv1d.weight); OK: native PLE key (Q8_0, iq_pack NATIVE_PLE_KEY) (1x, e.g. blk.1.ple_key.weight); OK: in the pack (dense.bin) as stored: the engine reads F32 (iq_pack FORM tools/iq_pack.py:72) (3x, e.g. blk.1.ple_norm_conv.weight); PACK (rounding): Q8_0 -> BF16 needs iq_pack --compat-bf16 (tools/iq_pack.py:245) (1x, e.g. blk.1.ple_value.weight) |
| attention indexer | 48 | 0.037 | F32 24, BF16 24 | OK | OK: in the pack (dense.bin) as stored: the engine reads F32 (iq_pack FORM tools/iq_pack.py:72) (24x, e.g. blk.3.indexer.k_norm.weight); OK: in the pack (dense.bin) as stored: the engine reads BF16 (iq_pack FORM tools/iq_pack.py:72) (24x, e.g. blk.3.indexer.k_proj.weight) |

| routed experts gate/up | down | layers | verdict | why | prompt path | CPU pool |
|---|---|---|---|---|---|---|
| IQ2_S | IQ4_NL | 47 | OK | GPU kernels on both cards (one iq_kernels.cu, built for 89;120; the 4060 Ti helper uses the same native_expert_layout, src/core/remote_experts.cpp:340) | gate/up MMQ; down MMQ + fused int8 prompt kernels on the 5080 (sm_120, 84 SMs), v2 prompt kernels (our STRATA_PREFILL_V2; compiled for 2560 / 640) | gate/up AVX-512 IQ, down IQ4_NL AVX2 |
| IQ3_S | IQ4_NL | 1 | OK | GPU kernels on both cards (one iq_kernels.cu, built for 89;120; the 4060 Ti helper uses the same native_expert_layout, src/core/remote_experts.cpp:340) | gate/up MMQ; down MMQ + fused int8 prompt kernels on the 5080 (sm_120, 84 SMs), v2 prompt kernels (our STRATA_PREFILL_V2; compiled for 2560 / 640) | gate/up AVX-512 IQ, down IQ4_NL AVX2 |

**Fit:** experts **45.29 GiB** (blob 1.89 MiB mean / 2.22 max, 3.22 bpw), dense on the GPU 4.15 GiB, embedding 0.49 GiB (host), n-gram table 26.82 GiB (read from the file), in-file MTP 0.00 GiB; active parameters 6.67 B (dense 4.31 B); K/V at 131,072 cells 1.55 GiB (12 attention layers; 0.39 GiB resident in VRAM). Room: 5080 8.49 + helpers 7.06 + RAM tier 57.83 = **73.38 GiB** -> **fits** (every expert in the RAM arena, page-locked). Disk: 82.0 GB, to download, 75.9 GB free after (UNDER 100 GB: ask Karl).

**Tier split and decode** (results/sweep-1103/UPGRADE-ESTIMATE.md sections 8-9: the splice's hit curve at this model's fraction of experts held, helper slot = 0.7 of a main slot, CPU 65 us per 4.0 MB entry, SSD 0.80 ms per 3.1 MB read, serial GPU part 2.2 ms x the active-parameter ratio 1.00 vs Flash-Next): slots 5080 4,609 + helpers [3831] + RAM all (arena) of 24,576; cold set 0.0 %; 600 routed lookups per token. Decode lookups: 5080 67.4 %, helpers 5.1 %, PCIe from RAM 6.1 %, CPU from RAM 21.5 %, SSD 0.0 % (0 MB/token). **Decode ~148 tok/s** (range 120-183; compute-bound) against Karl's 40-60 target: above. Section 9: helper 1: 30.4 entries/token, 0.21 ms, exposed wait 0.05 ms.

**Day-one pieces:** config `/home/USER/ai-speed-testing/strata-compare/results/qwen4-kit/unsloth-v31/day1-pre-v31/day1/udpre31.json` (+ `.shared-settings.json`), parameters `/home/USER/ai-speed-testing/strata-compare/results/qwen4-kit/unsloth-v31/day1-pre-v31/day1/params-udpre31.json`, commands `/home/USER/ai-speed-testing/strata-compare/results/qwen4-kit/unsloth-v31/day1-pre-v31/day1/commands-udpre31.txt`.

## `Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf`

- **RUNS WITH A PACK CONVERSION** - arch `qwen4exp`, name 'Qwen3.8 Flash Next', 3 shard(s) (HEAD-ONLY: sizes from NAME.size), 78.9 GB; per-tensor table: `files/Qwen3.8-Flash-Next-UD-Q2_K_XL.tensors.tsv`, keys: `files/Qwen3.8-Flash-Next-UD-Q2_K_XL.keys.txt`
- conversion: GDN (linear attention): F32 -> BF16: exact when every value is BF16 (iq_pack checks the low 16 bits at pack time); else --compat-bf16 (nearest-even rounding)
- conversion: hyper-connections: F32 -> BF16: exact when every value is BF16 (iq_pack checks the low 16 bits at pack time); else --compat-bf16 (nearest-even rounding)
- conversion: hyper-connections: Q8_0 -> BF16 needs iq_pack --compat-bf16 (tools/iq_pack.py:245)
- conversion: n-gram (PLE) projections: F32 -> F16 by the loader (index kind 3, nearest-even): exact only if the values are F16's
- conversion: n-gram (PLE) projections: Q8_0 -> BF16 needs iq_pack --compat-bf16 (tools/iq_pack.py:245)
- conversion: router: F32 -> BF16: exact when every value is BF16 (iq_pack checks the low 16 bits at pack time); else --compat-bf16 (nearest-even rounding)
- conversion: shared expert: F32 -> BF16: exact when every value is BF16 (iq_pack checks the low 16 bits at pack time); else --compat-bf16 (nearest-even rounding)
- setup.py would refuse this file by its name (UD-Q2_K_XL); our configs do not go through setup
- present: MTP/nextn none; n-gram table yes (blk.N.ple_conv1d.weight, blk.N.ple_key.weight, blk.N.ple_norm_conv.weight, blk.N.ple_norm_key.weight, blk.N.ple_norm_query.weight, blk.N.ple_value.weight); vision tensors 0; NVFP4 scales 0; prism keys -
- shape keys (37): block_count=48, context_length=262144, embedding_length=2560, attention.head_count=24, attention.head_count_kv=2, rope.dimension_sections=[11, 11, 10, 0], rope.freq_base=10000000.0, attention.layer_norm_rms_epsilon=9.999999974752427e-07, expert_count=512, expert_used_count=10, attention.key_length=256, attention.value_length=256, expert_feed_forward_length=640, expert_shared_feed_forward_length=640, ssm.conv_kernel=4, ssm.state_size=128, ssm.group_count=16, ssm.time_step_rank=48, ssm.inner_size=6144, full_attention_interval=4, rope.dimension_count=64, hyper_connection.count=4, hyper_connection.low_rank=320, attention.indexer.head_count=4, attention.indexer.key_length=128, attention.indexer.top_k=2048, attention.compress_ratios=[48 items] [0, 0, 0, 4, 0, 0] ..., ple.layers=[1], ple.ngram_size=3, ple.heads_per_ngram=8, ple.conv_kernel=4, ple.eos_token_id=248044, embedding_length_per_layer_input=160, ple.layer_multipliers=[23703573157769, 20109073645365, 8052911324071], ple.head_offsets=[0, 20000003, 40000026, 60000059, 80000106, 100000165, 120000228, 140000297, 160000374, 180000455, 200000548, 220000655, 240000802, 260000955, 280001114, 300001275], ple.head_vocab_sizes=[20000003, 20000023, 20000033, 20000047, 20000059, 20000063, 20000069, 20000077, 20000081, 20000093, 20000107, 20000147, 20000153, 20000159, 20000161, 20000171], ple.image_token_id=248056
- tokenizer: gpt2 / qwen35, vocab 248320, eos [248046, '<|im_end|>'], bos [248044, '<|endoftext|>'], pad [248044, '<|endoftext|>'], think tags [248068, 248069], im_start 248045; template 9993 chars, efforts ['low', 'medium', 'xhigh'] (default xhigh), thinking off yes, tools XML <function=...><parameter=...> in <tool_call>, context_length 262144
- vs Flash-Next: same tokenizer: the frozen prompt token files are valid (tokens_sha =, merges_sha =, types_sha =, template_sha =, special_ids =)

| tensor group | tensors | GiB | types | verdict | why |
|---|---|---|---|---|---|
| head | 1 | 0.333 | Q4_K 1 | OK | OK: native head (native_mmvq_supported src/kernels/cuda/native_mmvq.cu:3520) (1x, e.g. output.weight) |
| hyper-connections | 387 | 0.647 | Q8_0 194, F32 193 | PACK (rounding) | PACK (rounding): Q8_0 -> BF16 needs iq_pack --compat-bf16 (tools/iq_pack.py:245) (194x, e.g. output_hc_down.weight); OK: in the pack (dense.bin) as stored: the engine reads F32 (iq_pack FORM tools/iq_pack.py:72) (97x, e.g. output_hc_norm.weight); PACK (exact if the values allow): F32 -> BF16: exact when every value is BF16 (iq_pack checks the low 16 bits at pack time); else --compat-bf16 (nearest-even rounding) (96x, e.g. blk.0.hc_attn_inject.weight) |
| n-gram (PLE) table | 1 | 26.822 | IQ4_NL 1 | OK | OK: n-gram table read from its GGUF (IQ4_NL; ngram.cpp kPleFormats src/kernels/ngram.cpp:185) (1x, e.g. per_layer_token_embd.weight) |
| token embedding | 1 | 0.407 | Q5_K 1 | OK | OK: native embedding from the GGUF (embed_type_supported src/kernels/cuda/iq_kernels.cu:5324) (1x, e.g. token_embd.weight) |
| attention | 144 | 1.359 | Q5_K 94, Q6_K 26, F32 24 | OK | OK: native dense projection from the GGUF (+ the interleaved MMVQ_IL kernel) (src/core/native_dense.cpp:199) (120x, e.g. blk.0.attn_gate.weight); OK: in the pack (dense.bin) as stored: the engine reads F32 (iq_pack FORM tools/iq_pack.py:72) (24x, e.g. blk.3.attn_k_norm.weight) |
| routed experts | 144 | 42.920 | IQ4_NL 48, IQ2_XS 94, IQ3_XXS 2 | OK | per layer: see below |
| shared expert | 192 | 0.179 | Q8_0 48, F32 48, Q5_K 94, Q6_K 2 | PACK (exact if the values allow) | OK: native dense projection from the GGUF (src/core/native_dense.cpp:199) (48x, e.g. blk.0.ffn_down_shexp.weight); PACK (exact if the values allow): F32 -> BF16: exact when every value is BF16 (iq_pack checks the low 16 bits at pack time); else --compat-bf16 (nearest-even rounding) (48x, e.g. blk.0.ffn_gate_inp_shexp.weight); OK: native dense projection from the GGUF (+ the interleaved MMVQ_IL kernel) (src/core/native_dense.cpp:199) (96x, e.g. blk.0.ffn_gate_shexp.weight) |
| router | 48 | 0.234 | F32 48 | PACK (exact if the values allow) | PACK (exact if the values allow): F32 -> BF16: exact when every value is BF16 (iq_pack checks the low 16 bits at pack time); else --compat-bf16 (nearest-even rounding) (48x, e.g. blk.0.ffn_gate_inp.weight) |
| GDN (linear attention) | 252 | 0.471 | F32 216, Q6_K 36 | PACK (exact if the values allow) | OK: in the pack (dense.bin) as stored: the engine reads F32 (iq_pack FORM tools/iq_pack.py:72) (144x, e.g. blk.0.ssm_a); PACK (exact if the values allow): F32 -> BF16: exact when every value is BF16 (iq_pack checks the low 16 bits at pack time); else --compat-bf16 (nearest-even rounding) (72x, e.g. blk.0.ssm_alpha.weight); OK: native dense projection from the GGUF (+ the interleaved MMVQ_IL kernel) (src/core/native_dense.cpp:199) (36x, e.g. blk.0.ssm_out.weight) |
| n-gram (PLE) projections | 6 | 0.033 | F32 4, Q8_0 2 | PACK (rounding) | PACK (exact if the values allow): F32 -> F16 by the loader (index kind 3, nearest-even): exact only if the values are F16's (1x, e.g. blk.1.ple_conv1d.weight); OK: native PLE key (Q8_0, iq_pack NATIVE_PLE_KEY) (1x, e.g. blk.1.ple_key.weight); OK: in the pack (dense.bin) as stored: the engine reads F32 (iq_pack FORM tools/iq_pack.py:72) (3x, e.g. blk.1.ple_norm_conv.weight); PACK (rounding): Q8_0 -> BF16 needs iq_pack --compat-bf16 (tools/iq_pack.py:245) (1x, e.g. blk.1.ple_value.weight) |
| attention indexer | 48 | 0.037 | F32 24, BF16 24 | OK | OK: in the pack (dense.bin) as stored: the engine reads F32 (iq_pack FORM tools/iq_pack.py:72) (24x, e.g. blk.3.indexer.k_norm.weight); OK: in the pack (dense.bin) as stored: the engine reads BF16 (iq_pack FORM tools/iq_pack.py:72) (24x, e.g. blk.3.indexer.k_proj.weight) |

| routed experts gate/up | down | layers | verdict | why | prompt path | CPU pool |
|---|---|---|---|---|---|---|
| IQ2_XS | IQ4_NL | 47 | OK | GPU kernels on both cards (one iq_kernels.cu, built for 89;120; the 4060 Ti helper uses the same native_expert_layout, src/core/remote_experts.cpp:340) | gate/up MMQ; down MMQ + v2 prompt kernels (our STRATA_PREFILL_V2; compiled for 2560 / 640) | gate/up AVX-512 IQ, down IQ4_NL AVX2 |
| IQ3_XXS | IQ4_NL | 1 | OK | GPU kernels on both cards (one iq_kernels.cu, built for 89;120; the 4060 Ti helper uses the same native_expert_layout, src/core/remote_experts.cpp:340) | gate/up MMQ; down MMQ + fused int8 prompt kernels on the 5080 (sm_120, 84 SMs), v2 prompt kernels (our STRATA_PREFILL_V2; compiled for 2560 / 640) | gate/up AVX-512 IQ, down IQ4_NL AVX2 |

**Fit:** experts **42.92 GiB** (blob 1.79 MiB mean / 2.08 max, 3.05 bpw), dense on the GPU 3.71 GiB, embedding 0.41 GiB (host), n-gram table 26.82 GiB (read from the file), in-file MTP 0.00 GiB; active parameters 6.67 B (dense 4.31 B); K/V at 131,072 cells 1.55 GiB (12 attention layers; 0.39 GiB resident in VRAM). Room: 5080 8.93 + helpers 7.06 + RAM tier 57.91 = **73.90 GiB** -> **fits** (every expert in the RAM arena, page-locked). Disk: 78.9 GB, to download, 79.0 GB free after (UNDER 100 GB: ask Karl).

**Tier split and decode** (results/sweep-1103/UPGRADE-ESTIMATE.md sections 8-9: the splice's hit curve at this model's fraction of experts held, helper slot = 0.7 of a main slot, CPU 65 us per 4.0 MB entry, SSD 0.80 ms per 3.1 MB read, serial GPU part 2.2 ms x the active-parameter ratio 1.00 vs Flash-Next): slots 5080 5,112 + helpers [4042] + RAM all (arena) of 24,576; cold set 0.0 %; 600 routed lookups per token. Decode lookups: 5080 68.8 %, helpers 4.7 %, PCIe from RAM 5.8 %, CPU from RAM 20.7 %, SSD 0.0 % (0 MB/token). **Decode ~157 tok/s** (range 127-193; compute-bound) against Karl's 40-60 target: above. Section 9: helper 1: 28.2 entries/token, 0.18 ms, exposed wait 0.05 ms.

## Notes

- The tier/decode numbers are results/sweep-1103/UPGRADE-ESTIMATE.md's model (guesses on guesses, its section 8.5): use them to compare quants and layouts, not as forecasts. On the served Flash-Next the main-card curve under-predicts the measured hits (section 4.1: 73.7-79 % at 4,790 slots vs the curve's 68 %).
- Shapes the kernels are compiled for: the other helper's results/qwen4-kit/SHAPES.md lists every hard-coded site; this report only applies the load gate (read_geometry + geometry_unsupported).
- The quant rule and the day-one order are Karl's (/home/USER/ai/deep-research/results/bench2/QWEN4-DAY1-PLAN.md, "Quant choice" 11-03).
