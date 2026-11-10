# Basalt vs Strata: code diff and gap attribution (round 2)

Read-only study. Basalt at fb0944c7; Strata tags v0.1.37..v0.2.2 and our branch r22-port021 (v0.2.1 + our patches).
Nothing was built or run. Paths are repository-relative: "B:" = Basalt, "S:" = Strata (our branch unless a tag is named).
Tags: [E] = evidence (code, a commit message with a measurement, or our A/B engine logs); [I] = inference.
Basalt's measurements are from its author's RTX 5090 (170 SMs) + 5060 Ti peer at 400 W unless noted; ours is an RTX 5080 (84 SMs) alone.

## ODD FINDINGS

No telemetry, update checks, ~/.config or key-file reads, or obfuscated code found (grep over serve/, tools/, src/,
include/, CMake; the build fetches nothing). Minor items:
1. B: serve/engine/vision.py `load()`: an image source in a request may be an http(s) URL, which the server fetches
   from any host, or a plain local path, which the server reads if the file exists. Only with vision on (default
   `--vision off`). If vision is ever enabled, this is an outbound-fetch and local-file-read surface.
2. B: serve/security.py `lan_addresses()`: UDP `connect()` to 10.255.255.255:1 to learn the default-route address.
   A UDP connect sends no packet.
3. B: tools/convert/mtp_fetch.py downloads from the Hugging Face endpoint (converter only; not used by serve or engine).
4. Writes outside its folder: engine log and unpacked tokenizer under $BASALT_CACHE or ~/.cache/basalt; basalt-bench
   uses a hard-coded /tmp/basalt-bench-<pid>/ (removed at exit); vision and two tools use mkdtemp in /tmp; the engine
   writes 1000 to /proc/self/oom_score_adj (its own process only).
5. B: serve/api/responses.py names its reasoning-replay field `encrypted_content`, but it is plain base64 (the module
   docstring says so). A misleading name, not obfuscation.

## Summary

1. **Fork point = Strata v0.1.39 exactly** (2026-10-04). Basalt's history is upstream's original, pre-rewrite history:
   its first commit is the same commit object as tag v0.1.0. Its tree at the fork matches v0.1.39 in 852 of 852
   files. Since then: 878 commits (~830 own, 27 ports of upstream commits). Upstream has 2,979 non-merge commits from
   v0.1.39 to v0.2.1 that Basalt mostly does not have.
2. **Prompt reading (+14-16%)**: not the CPU share. Both engines use it only on chunks below the stream-all size, and
   W3/W4 chunks are above it. Not PCIe either: both are compute-bound. The gap is per-token GPU work: v2 fused expert
   kernels, a cheaper int8-KV prompt attention, a chunked GDN recurrence on tensor cores and faster dense dequant. W3
   also gets one chunk fewer (30,208-token cap vs our 16,384). Three of these have upstream switches we can test
   without porting.
3. **The struct +12% is not per-round efficiency.** Engine logs: acceptance per offered draft is the same (95.7% vs
   96.9%), but Basalt offers 5.74 drafts per window against our 3.03. It needs 1,103 windows for the 7,230 tokens;
   we need 1,854. At equal window width the two engines' windows cost the same (conv: 20.6-21.1 ms vs 20.3-21.6 ms).
   The cause is drafting: our greedy windows stop at the first draft below spec-min-p 0.5, while Basalt uses a
   cumulative, per-request adaptive rule and wider draft-head coverage.
4. Several of Basalt's showcase decode kernels are **off on an 84-SM card**: the fused hc read needs >= 168 SMs and
   mid_chain needs 170 (its own log says so); the glue launch needs the fused hc read.
5. **Best ports, in order:**
   - (a) an adaptive draft-length rule that also covers greedy windows: small and lossless;
   - (b) the v2 prompt expert kernels: medium, near-exact;
   - (c) the chunked GDN: medium, slightly lossy; measure on 84 SMs first;
   - (d) bitwise dequant: already upstream as STRATA_DEQUANT_WIDE=1.
   
   Do not port the two-stage head as is: it is lossy.

## 1. Fork point [E]

| Strata tag | files | same path + blob as Basalt e69c1fb6 |
|---|---|---|
| v0.1.37 | 576 | 456 |
| v0.1.38 | 584 | 471 |
| **v0.1.39** (6f32ec07, 2026-10-04 14:16 +0200) | 852 | **852** |
| v0.1.40 | 934 | 660 |

- The first-commit comparison the task asked for is degenerate: Basalt f2a08d4b, 28c47b10 and 6da1f667 are the commit
  objects that tags v0.1.0, v0.1.1 and v0.1.2 still point at. 52 Basalt commits exist by hash in the Strata repo.
- Fork commit: e69c1fb6, the parent of Basalt's first own commit c7127829. It has the same date and subject as
  v0.1.39, and 845 commits of history in both repos.
- After the fork (e69c1fb6..HEAD, 878 commits, 26 of them merges):
  - ~830 by Basalt's author;
  - 27 subject-tagged ports of upstream work (serve fixes, the small-chunk CPU share d10989ca, K-quant MMQ 5aae531f,
    QSA early exit 79dd763d);
  - llama.cpp MMQ copied in (a47cab93, commit 3cf03257).
- At HEAD no file under src/ or include/ is byte-identical to v0.1.39 (namespace rename to basalt).
- On 2026-10-06 Basalt removed AMD/SYCL/Windows (later re-added Windows), baked its experiments in as defaults, and
  stripped the measurements from its code comments (277-279 in its log). Commit messages keep some numbers.

## 2. Basalt's own changes by category

"Active 5080" = runs on our card per Basalt's code gates and its engine log from our A/B. "Ours" = S v0.2.1 + our
patches with the A/B config.

### (a) MTP / drafting
| Change | Basalt commits | Claimed gain | Lossless | S v0.2.1 / ours |
|---|---|---|---|---|
| **Cumulative draft-length rule**: draft j stays while prod acc(p_i) >= th. Base th 0.35 times a pack factor of 1.0-1.5 (CPU MB per slot). **Per-request adaptation** lowers th to 0.25 x factor when drafts beat the table. Applies to greedy too. | 241b5b4c, be7147f3, 32e5522f, 47f6192f, 5ec431db, 7af4a2c6 | none stated | yes (proposals only) | upstream: per-step `p >= --spec-min-p`. Ours: cost gate 94b00fbe for sampled requests only; greedy keeps min-p; no per-request adaptation |
| Draft head carries 512 context rows: prompt/text tokens missing from the subset | 48989e13, 7c7c1445 | none | yes | none |
| 2-bit copy of draft-head rows, exact rescoring of near-best rows (Q5_K, Q6_K) | 29e71767, bded7685, dee7ac9e | before this, the head read 85 MB per draft step | output yes; picks = exact argmax in 99.93% | none |
| Draft chain: fused steps, PDL, one staging launch, graphs captured at start, fp16 tensor-core draft attention | d0a57b8e, d52c2dd6, d60df9f8, d7907bc3, ca533a53, a9d0c27a, 9e0239c1 | -0.025 and -0.010 ms/window; attention 74 -> 43 us at 50K | output yes | none |
| Self-distilled MTP dense layer (pack data) | 7ae9b813, e77e4307 | not stated | yes | tested on our build: no gain at T 1.0 |
| Relaxed drafting | 64072d5e, 3adbaa12 | +5-10% | **no** (off by default) | none |

**Inherited, not Basalt's** (all in S v0.1.39): Philox sample-match verification, suffix (prompt-lookup) drafts and
their tokens-per-ms policy, and the 106,299-id draft vocabulary (S e227683e).

### (b) Output head
| Change | Commits | Claimed | Lossless | S / ours |
|---|---|---|---|---|
| Two-stage Q6_K verify head: a 2-bit copy on int8 tensor cores; rows within 4 of a bound on the 64th are rescored exactly, at most 65,536 per window | 3545989d, 8c1f46e3, f214c883 | ms/window conv -3.0%, prose -3.3%, struct -1.8%; KLD +0.0017 | **no** (round 1: 2.2% of rows at spec 7) | none |
| Q6_K head kernel, one warp per row (exact); one-launch sampled pick (bitwise) | c2d7bbed, 07ee0b3b | none | yes | own native head and sampler |

### (c) Decode kernels
| Change | Commits | Claimed | Lossless | Active 5080 | S / ours |
|---|---|---|---|---|---|
| Fused hc read + router on int8 hc copies | 87742367..4667eebb, 95e12421 | -0.06 / -0.07 ms/window | no (int8 hc) | **no**: needs SMs >= 168 (B: src/kernels/cuda/hc_fused.cu, dev_info) | ours: GR_FORK + GR_V3 hc read |
| mid_chain (GDN middle in one launch) + async commit finisher | 0fa6bd7e, 1340621b, 481be493, db90250e | none | yes | **no** (log: "need 170") | none |
| Glue launch (route and plan inside gate/up) | e7986c1f, b323deff, d7cfed04, 10dd14e3 | -0.4..-1.3 us per call | yes | **no** (needs the fused hc read) | none |
| Device-planned MoE tail, warp-scan grouping, early prologues | 8e78c35c, 95933fb9, 5aab9671, 62709f1e | -0.10, -0.09, -0.07 ms/window | yes | yes | host-planned token graph |
| dense_tc: int8 tensor-core verify projections, qkv+z pair (Q4_K/Q5_K/Q6_K/IQ4_XS all covered) | 8f768f68, d9c1955b, 15fb9872, e1bad20a | none stated | rounding differs from mmvq (~1e-7) | yes (no fallback lines) | dp4a mmvq, STRATA_MMVQ_IL rows |
| Fused GDN decode block (conv, gates, recurrence, norm, q8_1) | 9e04c17d, 8e72adb1 | none | yes | yes | separate kernels |
| QSA decode attention at 2 blocks/SM; register-query indexer, cluster top-k | c75ca21c, 8fe619d0, 1a80aa25 | 22.3 -> 20.4 us; 14.8 -> 10.2 us and 17.0 -> 8.8 us at 50K | yes | yes | ours: STRATA_QSA_SPLIT_ATTN |
| PDL through the window (324 per graph in our log); side branches at priority -5 | 6ce47297, cf3b6280, a9a16340, f55a6f08 | QSA PDL 6.794 -> 6.666 ms/window | yes | yes | upstream opt-in STRATA_DF_PDL / STRATA_DF_BRANCH, not in our env |

### (d) Prefill
| Change | Commits | Claimed | Lossless | S / ours |
|---|---|---|---|---|
| Chunked gated delta rule on tensor cores: 16-token chunks, BF16 q/k, FP32 state | 1d1159aa (B: src/prefill/gdn_chunked.cu) | layer at 16K 5.73 -> 2.31 ms; prefill +5.0 / +5.6 / +6.2% at 16.7K / 33.3K / 66.6K | **no** (rel RMS 2.9e-3; KLD 0.0687 -> 0.0706 over 20 chunks) | S: FP32 chunked STRATA_GDN_CHUNKED=1, opt-in, needs >= 128 SMs (=2 skips that check); ours: off, so gdn_rec_kh_kernel |
| **v2 fused prompt experts** for IQ3_XXS gate/up and IQ4_NL down: raw bytes by cp.async, decoded into mma fragments; a warp per 32 weight rows x up to 128 routed rows; atomic item queue | d9915bbc, default since 36afdf5e | not stated | near: same math, another order; H int8 codes "almost always" equal | none (S has v1 only) |
| int8-KV prompt attention: one FP16 MMA per product, per-warp tiles, one merge | f04e956a | 4.19 -> 2.84 ms per 4,096 queries at 16K; prefill +1.9 / +2.7 / +3.1% | **no** (1.5e-3 vs 1e-6) | S: STRATA_PROMPT_ATTN_IMMA=1 opt-in. Three INT8 MMAs, more accurate than the default, 1.35-1.53x a launch; 32K in 8K chunks 358 -> 312 ms |
| Dense-weight dequant with 16-byte stores | bae903f8 | 7x (376 -> 52 us); a prompt chunk -38 ms | yes (bitwise) | S: STRATA_DEQUANT_WIDE=1 (bitwise; default only on cc 6.1) covers Q4_K/Q5_K/Q6_K/IQ4_XS |
| Fewest equal chunks; bare auto up to 32,768 for blobs > 1.5 MB (lend-capped at 30,208 here) | 2c3a6209, 1814f315, f7c13c84, 2be39f75 | NVFP4: 33K 5,625 -> 6,393 tok/s | K/V rounding moves | ours: auto:16384 |
| Leaner prompt buffers: hc rows in scratch, 256-slot ring | ecf5157f, fdd29541 | lend -2.2 GiB at 32K (FP4) | yes | ours: 512-slot ring |
| Stream-all from 6,144 tokens; CPU share 0.6 below that | d0107d36, 74827639, 9d952fdb | TTFT 1-4K prompts -0.4..-1.0 s | CPU rounding | S: stream-all from 1,024; ours: share 0.4 up to 1,792 |

### (e) Scheduling
| Change | Commits | Claimed | Lossless | S / ours |
|---|---|---|---|---|
| Adaptive-swap host work off the critical path; jobs on a persistent worker on the decode thread's SMT sibling | 5d3d48a9, a4d6ebf0 | prose 7.071 -> 6.920 ms/window | yes | ours: STRATA_ADAPT_LAG=2 |
| CPU activations quantized only for tokens with a CPU expert; AVX-512 Q8_K quantizer | dbeb79e1, 669349e6 | host 0.14 -> 0.07 ms/window | yes | ours: STRATA_ROUTER_Q8K (GPU writes the Q8_K rows) |
| One-token CPU groups on the multi-token kernels | 4933a4d6 | none | yes | S: opt-in STRATA_IQ_MT_MIN=1 |
| CPU pool warms the predicted next-layer expert | 7dcf8ac3 | flat | yes | none |
| PCIe share: default 0.55, scaled by the link probe | inherited (S v0.1.37 probe) | | | S v0.2.1 adds PcieAuto refinement; **ours: forced 0** |
| Pool = physical cores - 1, host thread joins | inherited | | | same (our log: 15 workers + host draining) |

### (f) Memory / IO
| Change | Commits | Claimed | Lossless | S / ours |
|---|---|---|---|---|
| Elastic KV: 32K cells backed at start; the rest borrowed from the expert cache's tail when needed | bd75554e, 17fe406c, 4eb19d96 | none | yes | ours: KV streaming, 32K resident; S --vram-elastic covers the cache only |
| RAM tier and VRAM caches filled by O_DIRECT reads; pinned memory registered after the fill | 2268bec0, 4f1765d4, 41aa7b6a | load time only | yes | load path only |
| PLE O_DIRECT reads | inherited (S default `--ple-io direct`, 256 in flight) | | | **ours: --ple-inflight 128** |
| Checkpoint buffers pooled; GDN state copied device-to-device, then to the host on a helper | f0f637c4, 426f552f | none | yes | none |

## 3. The two measured gaps

### 3.1 Prompt reading, Basalt +14-16%

Facts from the A/B engine logs (results/a1, results/c1) [E]:

| | Ours | Basalt |
|---|---|---|
| Chunk cap | 16,384 | 30,208 |
| Ring | 512 slots | 256 slots |
| Lent cache slots | 3,228 (6.13 GiB) | 3,816 (7.26 GiB) |
| 26.7K prompt | 2 chunks, 6.15-6.36 s | 1 chunk, 5.25-5.54 s |
| 32.7K prompt | 2 chunks, 7.49-7.65 s | 2 equal chunks, 6.53-6.77 s |

Both logs say the prompt experts run on the fused int8 kernels; Basalt's also says "v2 native kernels".

**Ruled out:**
- **CPU share** [E]. Both engines gate it on a non-stream-all chunk: B: src/prefill/prefill.cpp, `cpu_maybe = ... && !stream_all`; S: the same in src/prefill/prefill.cpp. Every W3/W4 chunk streams all experts, so 0.6 vs 0.4 plays no part.
- **PCIe** [I]. One pass streams ~23.5K non-resident blobs x 2.05 MB = ~48 GB, about 0.85 s at the probed 57.8 GB/s, so two passes take ~1.7 s of 6.5-7.5 s. The copies overlap compute by design.
- **Chunk count** [I]. W4 has 2 chunks in both engines and still shows +14%. Chunking adds at most a few points on W3.

Ranked contributors (per-token GPU work):
1. **v2 expert kernels** [E code, size I]. In this pack, IQ4_NL down is on 39 of 48 layers and IQ3_XXS gate/up on 17, so
   v2 covers ~51% of routed-expert MACs. Routed experts are the largest prefill item. Basalt states no measurement.
2. **int8-KV prompt attention** [E +2.7% at 33K on the 5090]. A similar share is likely here [I].
3. **Chunked GDN** [E +5.6% at 33K on 170 SMs]. On the 5080 the gain is likely smaller [I]: the scan launches 96
   blocks of ~64.5 KB shared memory (one block per SM), so it runs in two waves on 84 SMs. Upstream's FP32 version
   has the same problem; its own comment expects it to be slower below 128 SMs.
4. **Dense dequant with 16-byte stores** [E: -38 ms per chunk on the 5090]. Worth ~1-2% over two chunks here [I].
5. **One chunk fewer between 16K and 30K** (W3 only), ~1-3% [I]. It needs leaner prompt buffers: our 16K lend is
   already 6.13 GiB.
6. Small items:
   - our --ple-inflight 128 vs the upstream default 256. Upstream measured the 32K prompt's PLE reads at 303 ms with
     64 in flight and 189 ms with 256 [E];
   - checkpoint pooling [I].

Items 2-6 add up to ~6-10% [I]. The v2 kernels most likely carry the rest; this is untested.

### 3.2 Decode at spec 7: "struct +12% at equal acceptance"

Per-window arithmetic from the same logs (5080 alone, spec 7; windows = generated - accepted) [E]:

| Run | Engine | Accepted / offered | Windows | Drafts / window | Tokens / window | ms / window | ms / token |
|---|---|---|---|---|---|---|---|
| struct, 7,230 tokens | ours | 5,376 / 5,616 (95.7%) | 1,854 | 3.03 | 3.90 | 22.4 | 5.74 |
| struct, 7,230 tokens | Basalt | 6,127 / 6,326 (96.9%) | 1,103 | **5.74** | **6.55** | 33.7 | **5.14** |
| conv, 2 runs | ours | 67%, 64% | 384, 434 | 2.40, 2.38 | 2.61, 2.53 | 21.1, 20.6 | 8.1 |
| conv, 2 runs | Basalt | 72%, 75% | 369, 433 | 2.12, 2.34 | 2.52, 2.76 | 20.3, 21.6 | 7.9 |
| prose, 2 runs | ours | 50%, 50% | 558, 383 | 2.28, 2.26 | 2.15, 2.12 | 18.8, 18.3 | 8.7 |
| prose, 2 runs | Basalt | 68%, 67% | 513, 546 | 1.69, 1.78 | 2.15, 2.20 | 17.1, 16.4 | 7.9, 7.5 |
| W1 normal text (T 1.0) | ours / Basalt | 71% / 70% | 1,191 / 1,170 | 2.22 / 2.31 | 2.58 / 2.63 | 17.2 / 17.9 | 6.7 / 6.8 |

**Reading** [I]:
- **The premise does not hold.** Acceptance per offered draft is equal, but Basalt offers 1.9x as many drafts per
  window. The 12% is the per-window fixed cost spread over more tokens, not faster rounds.
- **At equal width the windows cost the same** (conv; W1 at T 1.0). An extra row costs ~3.5-5 ms on this machine:
  82% of expert bytes live in RAM, so CPU-tier reads dominate. That dwarfs the sub-ms GPU savings of Basalt's decode
  kernels, three of which are off on 84 SMs anyway.
- **Prose at T 0.6:** Basalt gets the same tokens per window (2.15) from fewer drafts (1.7 vs 2.3). Its windows are
  narrower and ~9% cheaper.
- **PCIe share:** Basalt runs 0.55 and ours 0, yet the per-window costs match. That argues against a large PCIe-share
  effect here (DRAM bandwidth is shared), but the flag is cheap to test.

Ranked contributors to the struct gap:
1. **Draft-length rule** [E code, size I].
   - Ours (upstream): a greedy window ends at the first draft with top prob < spec-min-p 0.5 (S:
     src/program/generate.cpp, the `pr[from + T - 1] >= req_spec_min_p` loop). Our cost gate explicitly leaves greedy
     unchanged (S: include/strata/spec/cost_gate.hpp header).
   - Basalt: B: include/basalt/core/draft_cum.hpp, used at every window-size site in B: src/program/generate.cpp and
     in the device draft chain (B: src/core/mtp.cpp).
2. **Draft-head coverage** [I]. Ours covers 40,525 ids; Basalt 106,299 plus 512 prompt-context rows. A token outside
   our subset gives a low draft probability, so the window ends early without a rejection. That lowers drafts per
   window and leaves acceptance unchanged, which is the pattern in the logs.
3. **Tuned MTP layer** [I]: more confident drafts pass more steps. It gave no gain at T 1.0 on our build; it is
   untested on struct.
4. **Head and kernel changes**: not visible in per-window cost at equal width. The two-stage head is worth -1.8% on
   struct on the 5090 [E] and is lossy.

## 4. Portability into our build

| # | Candidate | Basalt source | Size | Lossless | Conflicts with our patches | Effort |
|---|---|---|---|---|---|---|
| 1 | Adaptive draft-length: cumulative rule + per-request scale, also for greedy and lookup windows; or an adaptive multiplier on our cost gate's theta | include/basalt/core/draft_cum.hpp (78 lines); call sites in generate.cpp and mtp.cpp | ~100-150 lines | yes | same sites as cost gate 94b00fbe and exact sampling ad022192 (S: generate.cpp window loop, src/core/mtp.cpp draft stop rule) | S |
| 2 | v2 prompt expert kernels (IQ3_XXS gate/up, IQ4_NL down) | src/prefill/moe_fused_iq.cu v2 section, moe_fused.cu group_bytes(+64) | ~480 (d9915bbc) | near (rounding order) | none: our patches do not touch src/prefill | M |
| 3 | Chunked GDN prefill on tensor cores | src/prefill/gdn_chunked.cu (435); work buffer aliases the qkv buffer | ~450 | no (small; see 2(d)) | none | M; measure on 84 SMs, try DV 32 for more blocks |
| 4 | Dense dequant 16-byte stores | already upstream: STRATA_DEQUANT_WIDE=1, or extend S: src/kernels/cuda/dequant_bf16.cu VEC beyond sm_75 | env / ~5 lines | yes (bitwise) | none | S |
| 5 | int8-KV prompt attention | prefer upstream STRATA_PROMPT_ATTN_IMMA=1 over B f04e956a (lossy) | env | IMMA is closer to FP32 than our default | none | S |
| 6 | 512 context rows in the draft head | 48989e13, 7c7c1445 (mtp.cpp, head kernels) | ~200 | yes, if exact sampling's q includes the rows | our SPEC_EXACT q over the draft vocab (sampler.cu, mtp.cpp) | M |
| 7 | 30K prompt chunks via leaner buffers | ecf5157f; 256-slot ring | ~100 | K/V rounding moves | none | M |
| 8 | 2-bit draft head | head_proxy.cuh (243), q6k_head.cu argmax, mtp.cpp | ~500 | output yes; our exact sampling must draw from and accept with the same approximate q | SPEC_EXACT | M, small gain |
| 9 | Checkpoint buffer pool + D2D GDN state copy | f0f637c4, 426f552f | ~150 | yes | chat-cache patches touch park/checkpoint paths | S-M, tens of ms TTFT |
| 10 | Two-stage Q6_K head | 3545989d, 8c1f46e3 | ~750 | **no**; an exact variant needs a fallback on cap and a proven margin | verify.cpp head call | M-L, 2-3% ms/window; skip as is |
| 11 | dense_tc, device-planned MoE tail, fused hc read | dense_tc.cu (1,211), dec_moe.cuh (2,048), hc_fused.cu (1,550) | L | dense_tc rounding differs; hc_fused lossy | ROUTER_Q8K doorbell, GR_FORK, MMVQ_IL | L; no per-window gain visible on the 5080; skip |

Licences: Basalt is MIT and keeps upstream's notice in THIRD_PARTY_LICENSES. gdn_chunked.cu, the int8 prompt attention
and the FP4 GEMM adapt Apache-2.0 code (Infernix). A port carries both notices.

## 5. Zero-code checks on our build first

Each is one flag on the 5080-alone arm; lossless unless noted.

**Prefill:**
- STRATA_DEQUANT_WIDE=1 (bitwise).
- STRATA_PROMPT_ATTN_IMMA=1 (more accurate than our default).
- STRATA_GDN_CHUNKED=2 (FP32; it may lose on 84 SMs).
- --ple-inflight 256.

**Decode:**
- Drop `--pcie-frac 0`, so upstream's probe plus PcieAuto picks the share (placement only).
- STRATA_DF_PDL=1, STRATA_DF_BRANCH=1 and STRATA_DF_PLE=1 (bitwise upstream opt-ins). Check the earlier round notes
  in case they were already screened.

**Struct decomposition:**
- Rerun struct at spec 7 with --spec-min-p 0.3 and 0.2. Only greedy and lookup windows read it, because the cost gate
  owns sampled requests.
- Rerun struct with the existing b7 / b7v arms (tuned layer, plus the 106K vocabulary).

Upstream v0.2.2 adds nothing aimed at either gap: its changes are trellis "Gyro" packs, a NUMA pool and fixes.
