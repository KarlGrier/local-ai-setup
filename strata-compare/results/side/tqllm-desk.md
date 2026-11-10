# tqLLM 1.4.1 for Qwen3.8 Flash-Next: desk study, Part 1 (11-05, read-only)

## Verdict: NO-GO for Part 2

tqLLM can run here: the 5080 alone in its "small card" mode, with the pinned expert pack in our RAM. Its sampled
speculative decoding is exact. It uses sample-and-match against the full-vocabulary target, so drafting does not change
the distribution. The third GO condition fails, though: **there is no plausible case that it beats P028x as served.**

- **Experts in VRAM.** On the 5080 it caches about as many experts as P028x does on the 5080 alone (est. ~3,900-4,700
  slots against 4,585). P028x as served has 7,885 across both cards.
- **No CPU lane.** Under its default `--exact on` it runs no CPU expert lane, so every miss (~31-36 % of routed experts)
  crosses PCIe. P028x on the 5080 alone sends only 8.5 % over PCIe (and 23 % to the CPU).
- **Fixed drafts and CPU sampling.** On a <16 GB card it fixes the draft at 3 tokens. It samples on the CPU over all
  248,320 logits of every verify row.
- **Its own figures are lower.** Its best published single-request numbers, all greedy, come from bigger cards: 3090
  chats 91.6-95.6 tok/s; 5090 chats 137-168 and 134 after 32-64K. P028x as served does 155-191 on short chats, 142-164
  after 54K and 153-158 after 20K, all sampled.
- **Its wins over 0.2.2 do not apply.** Our port already has the short-chat first token and the long-context decode that
  it claims over Strata 0.2.2 (section 4).

It also cannot reproduce our sampler. It has no min-p at all (min-p is silently ignored), and the Flash-Next engine
ignores the presence penalty.

Sources:
- The clone `tqllm-review/tqllm` at d93b26bd (2026-11-05 15:35 UTC, CHANGELOG "1.4.1 (2026-11-05)").
- The companion bundle at rev b8083ec0, read through the HF API listing. Files fetched into `tqllm-review/bundle/`:
  README.md, NOTICE, flashnext.tqfn, flashnext-tqllm.tqfn, atx_65536.txt, .gitattributes, tree.json, model-info.json.
- No separate expert-cache plan file exists: the plan is the manifest's `layer_slots=` line.
- Not fetched: the 10.9 MB tokenizer GGUF, the 1.46 GB MTP GGUF and the 82 GB `mixed/` shards.
- Nothing of theirs was built, configured or run. No GPU was used. The only local reads were our own GGUF header
  (`tqllm-review/scratch/gguf_types.py`) and our logs and results.

Paths below are relative to `tqllm-review/tqllm/` unless they say otherwise.

## 1. Sampled speculative decoding: exact, but not our sampler

**The rule.** `src/models/qwen/qwen4exp/fn_engine_decode.cpp:47-68` handles one sequence and `:136-158` handles
`--np` > 1.

- The block is `[last token, d1..dk]`. The drafts are either MTP argmax drafts or "copy drafts" (an n-gram continuation
  from this request or the last 4 requests).
- The target computes every row, and `pick()` (`:6-24`) draws one token per row from the target's own distribution.
- Drafts are kept while `v[m-1] == dr[m-1]`. The first mismatch, or the bonus row, emits the target's sample.
- The engine states the rule itself (`fn_engine.hpp:88-90`): "a draft is accepted only if it equals that sample, so the
  output follows the target exactly (greedy drafts just lower the acceptance)".

**Why this is exact.** The drafts are deterministic. For a point-mass draft, sample-and-match is identical in
distribution to min(1, p/q) plus the residual redraw:
- a draft is accepted with probability p(d);
- on a rejection, the emitted token is distributed as p conditioned on x ≠ d, which is the residual.

This is the scheme `results/sampling-assessment.md` described for Strata. Each emitted token is a fresh draw from p given
the accepted prefix. The draft length, the adaptive tau stop and the copy-draft source change only the speed.

**The draft vocabulary does not touch verification.**
- `atx_65536.txt` holds 65,536 of the 248,320 ids. It builds a draft-only head (`fn_checkpoint.hpp:422-436`): "Verification
  keeps the full head, so output is unchanged".
- `pick()` reads `head_logits_device` (`fn_checkpoint.hpp:404-413`), whose V is the full `output.weight` rows.
- Tokens outside the draft vocabulary can be sampled but never drafted. That costs acceptance, not exactness.

**No shortlist on this model.**
- The README's "not a certified full-vocabulary argmax" and the 16-candidate sampling cap
  (`docs/reference/options.md:166, 171-181`) belong to the 27B / MiniMax engines (`src/spec/token_sampling.hpp`,
  `qwen35_*`).
- Flash-Next's greedy path is a full-vocabulary argmax with ties going to the lowest id (`fn_checkpoint.hpp:372-390,
  396-402`).
- Its sampled path uses the whole vocabulary on the host.

**Sampler differences from ours.** Ours is top-k → top-p (at T = 1) → min-p → temperature
(`strata-r22p028x/src/kernels/cuda/sampler.cu:1-11, 384-425`).

| | tqLLM Flash-Next (`fn_engine_decode.cpp:6-24`) | effect at T 1.0 / 0.95 / 20 / 0.05 |
|---|---|---|
| order | temperature first, then a 1e-9 relative cut, top-k, top-p on the renormalised top-k, then the draw | Equal to ours at T = 1. At T ≠ 1 the top-p cut sees the tempered distribution, unlike ours. Check (2) runs at T 0.6, so the two differ there. |
| min-p | **not implemented**: no `min_p` anywhere in the tree; the request parser ignores unknown keys (`tools/serve/session.hpp:211-236`) | **Different target distribution.** Tokens under 0.05 × p_max survive. |
| presence penalty | parsed, then dropped by Flash-Next's `set_sampling` (`fn_engine.hpp:155-158`, `(void) presence`) | ignored |
| repeat / frequency penalty | 27B engine only (`options.md:37`) | n/a |
| 1e-9 cut | drops tokens with p / p_max ≤ 1e-9 | Negligible: with top-k 20, only the 20th-or-lower candidates can be hit. |
| seed | Random per request unless given (`session.hpp:226-236`). One mt19937_64 per slot, one uniform per verify row. | Seeded replays depend on the draft count. That is not a bias. |

**Caveats on exactness.**
- **Verify rows must match one-row arithmetic.** "Exact" assumes a verify row computes the same as a one-row step. The
  engine claims batch invariance: the verify block size never changes the greedy text, and there are tests in
  `tests/bf16_gemv*`, `gemv_seg`, `topk2`, `matvec_wide`.
- **Known exception: the waves path.** It sums the down projection in another order whenever a block's distinct experts
  exceed a layer's bank (F39, `decode_rules.hpp:13-23`). Small cards keep a floor of 40 slots so that one sequence never
  takes it (`decode_rules.hpp:68-70`, `fn_engine_load.cpp:449-457`).
- **The prompt cache is not exact.** It exists only at `--np` > 1, and the engine itself says a reused prompt "is not
  byte-identical to an uncached one" (`fn_engine.hpp:66-70`).

**Speed cost under sampling.** These are estimates; nothing was measured.
- Every step copies n × 248,320 FP32 logits to the host, about 1 MB per row.
- Each row then runs a single-threaded `exp` over all of them, plus a full `std::sort` of every candidate within 20.7
  nats of the max (no partial sort before top-k).
- That is likely 2-6 ms of CPU per row, or 8-25 ms per 4-row step, against the engine's own ~26 ms 3090 step
  (`decode_rules.hpp:211-212`).
- On top of that, acceptance falls from 1[argmax] to p(d).
- Every published tqLLM speed is greedy (`docs/BENCHMARKS.md:35`, `docs/guides/rtx-5090.md:9`).

**Our checks.**
- **Check (2) cannot run as written.** It needs the engine's own probabilities (`sampling_probe.py strata_logp` and
  1-token windows), and tqLLM's server has no logprobs.
- **A two-sample substitute would work but needs a new harness.** It would compare the default arm against a
  manifest with `drafts=0`, which is plain decoding (`fn_mtp.cpp:187-188`).

## 2. Other output-changing steps with the defaults

Defaults that matter here:
- `--exact on` (`include/tqllm/options.hpp:20`). It turns off the CPU miss pool and conflicts with tail skip,
  `TQFN_PREFILL_INT8` and `TQFN_DENSE_INT8`.
- KV in BF16.
- Tail skip opt-in (`fn_layer_forward.cpp:461`).
- No kv-compact, no prefill-fp8.

**Nothing beyond rounding changes the output.** But almost every kernel family rounds differently from ours. Greedy or
bitwise parity with P028x is not to be expected, and a switch would need its own KL yardstick run.

| step | tqLLM (defaults) | P028x | note |
|---|---|---|---|
| Decode expert matmuls | Input rounded F32→FP16 (`fn_layer_forward.cpp:413, 458`). IQ3_S weights decoded to FP16 by HFMA2, with the block scale d(1+2sc) itself rounded to FP16 (`formats/weight/quant_u4h.inc:34-38`). FP16 tensor-core MMA, FP32 accumulate (`:527`). Gate / up / down outputs **stored as BF16** (`:535`; `fn_layer_forward.cpp:554`). SwiGLU to FP16 (`:617-622`). | llama.cpp-style Q8_1 int8 activations, integer dot, FP32 (`src/kernels/cuda/native_mmvq.cu`, adapted from llama.cpp) | Both rounding-level. Theirs is finer on activations, coarser on the stored intermediates and the weight scale. |
| Prefill expert GEMMs | **llama.cpp MMQ with Q8_1 int8 activations by default, even under `--exact on`** for IQ3_S / IQ3_XXS / IQ2_S / IQ4_XS / IQ4_NL (`fn_prefill.cpp:193-248`, `experts/mmq_experts.cu:193-196`). The unit is built with `-use_fast_math` (`CMakeLists.txt:140-144`). Other formats use the FP16 grouped kernel. | int8 as well (our v2 term) | Their docs say exact on means "no int8 / FP8 GEMMs" (`options.md:59`). The code disagrees for these expert GEMMs. Prompt and decode use different arithmetic. |
| Dense quantised projections | FP16 input image, native matvec, FP32 accumulate. Prefill uses an FP16 weight copy and a cuBLAS FP16 GEMM with FP32 accumulate (`fn_checkpoint.hpp:570-640`). | Q8_1 MMVQ | rounding-level |
| BF16 weights | HC mixers (1.26 GB), router, indexer q/k, ssm α/β. "activations round to BF16 ... F32 accumulate" (`fn_checkpoint.hpp:645`). The HC low-rank output is also rounded to BF16 (`fn_layers.hpp:311-333`). | BF16 weights, FP32 accumulate. Our HC gate also reads a BF16 low-rank image (`gr.cu:247`). | Similar; the input rounding differs in places. |
| KV cache | BF16 (`fn_layers.hpp:194`). Host K/V only for contexts > 64K (`fn_engine_load.cpp:359-363`). | **int8** (`--kv int8`) | Theirs is closer to exact. |
| GDN | FP32 state and history (`fn_layers.hpp:95-105`) | FP32 | — |
| Indexer (the model's own sparse attention, top-2048 per head group) | FP32 scores, top-k on the score bits with ties broken by index (`qwen4exp_qsa.cu:22-40`) | own kernels | A discrete selection: rounding can flip blocks (both engines). |
| Head | Hidden rounded to FP16; native Q6_K matvec over the full vocabulary, FP32 out | full vocabulary | rounding-level |
| IQ4 MTP layer (bundle) | drafts only | MTP rt from strata-v0115 | Changes acceptance, not output. |
| Embedding / PLE n-gram rows | the same GGUF rows, read from the page cache | O_DIRECT reads with a 1M-row cache | Same values. Projection rounding as in the rows above. |

Non-arithmetic output changes:
- `--repeat-limit 256` ends a request after 256 identical tokens in a row (`options.md:26`).
- `--max-tokens` defaults to 16,384, with thinking counted inside it (`options.md:21`).
- `--reasoning off` is the default.
- min-p and presence are ignored (see section 1).
- At `--np 1` nothing is reused between turns (`caching()` needs more than one slot, `fn_engine.hpp:70`). Every follow-up
  re-prefills the whole conversation, which our follow-up rule counts as a bug.

## 3. 16 GB card + 96 GB RAM: it runs, but with fewer experts than P028x as served

**Mode.** The 5080 shows 15,919 MiB free with no engine (gap 16 log). That is under 16 GB, so `small_card` is set
(`fn_engine_load.cpp:128`). The mode is a supported path; they tested a 3090 held to 12 GB. It means:
- 64 MTP slots instead of 256 (`:331`);
- banks fill everything except a 512 MB keep (`:434`);
- a 160 MB dense FP16 pool and 128-expert staging (`:141-146`);
- **3 fixed drafts, with no adaptive length** (`decode_rules.hpp:189-193`). The CPU pool is assumed even though
  `--exact on` turns it off;
- no CPU miss pool under `--exact on` (`fn_layer_forward.cpp:442-443`);
- no bank growth after the first decode step (`fn_engine_decode.cpp:73`).

**Expert slots (estimate).**
- Slots are uniform per layer: (free − keep) / Σ blocks (`fn_engine_load.cpp:423-447`). Σ blocks is 46.84 GiB / 512 =
  93.7 MiB per slot-per-layer.
- The manifest's `layer_slots=` is the expert-cache plan: 48 values, sum 8,539, mean 178, range 128-314. It is a 3090
  routing shape, rescaled to the device's count (`decode_rules.hpp:265-274`).
- The resident non-expert weights of the IQ3_S file total 4.51 GB: Q6_K head 0.52, IQ4_XS embedding 0.34, BF16 HC
  mixers 1.26, attention / GDN / shared expert ~2.2 (our header read).
- Estimated non-bank use is ~6.7-8.2 GB: context, MMQ modules, MTP layer and slots, draft head, arena, staging, GDN
  state, keep. The bound comes from code and from their 3090 figure of 157 slots / layer.

| | 5080 expert slots | other tier |
|---|---|---|
| tqLLM, short context (est.) | **~3,900-4,700** (82-100 per layer) | none: PCIe misses only |
| tqLLM after a 32K / 64K prompt (est.; BF16 K/V 24 KB / token on the GPU up to 64K) | ~3,500-4,300 | none |
| P028x, 5080 alone (UPGRADE-ESTIMATE §6.5) | 4,585: hit 68.5 %, PCIe 8.5 %, CPU 23 % | CPU lane |
| P028x as served | 4,585 + 3,300 on the 4060 Ti: miss 19.6 % | CPU lane + helper |

The real count prints at start-up ("expert slots auto: ... -> N slots/layer").

**What the idle 4060 Ti costs.**
- For P028x, the 4060 Ti is worth +15 % decode: 134.5 → 154.8 tok/s client clock, miss 31.5 → 19.6 %. Prompts stay
  unchanged at −0.6 to −1.4 % (§6.5; F1-frame-pools.md).
- tqLLM is stuck at the 5080-alone slot count, and without our CPU lane all of its ~31-36 % misses become ~2 MB PCIe
  copies. That is about 4x the PCIe expert traffic of P028x on the 5080 alone.

**RAM.**
- **Pinned pack.** The pack is pinned when 1.02 × the expert bytes are at most 0.6 × RAM (`decode_rules.hpp:242-244`).
  Here that is 51.3 GB against 59.2 GB, so it is built in pinned memory at every start (~50 s; server ready ~2 min) and
  the GGUF expert pages are dropped (`fn_engine_load.cpp:253-256`).
- **Locked total.** ~50.3 GB experts, ~1.4 GB MTP experts, and the pinned prefill-residual buffer (context × 40 KB:
  2.7 GB at 64K, 5.4 GB at 128K; `decode_rules.hpp:129-131`). Host K/V past 64K adds 1.6 GB at 128K. In total
  **~52-58 GB locked**, about the same as P028x's RSS of 51-59 GB.
- **PLE page cache.** It also wants the 28.8 GB per-layer embedding resident in page cache (`decode_rules.hpp:245-256`,
  warmed at start). If those pages are evicted, chats lose ~15 % (CHANGELOG 1.2.3: 79-88 against 94-103).
- **Against our floor.** MemAvailable counts that cache, so the 12 GB guard would not trip. The real slack after the
  PLE stays hot is only ~5-10 GB, against ~35 GB with P028x, which streams the PLE with O_DIRECT. That is tight for the
  daily services and fine for a screen with 8080 down. The two engines cannot both be loaded.

## 4. Its wins over Strata 0.2.2: what we already have

Their figures (`docs/BENCHMARKS.md:37-48`) are 3090, greedy.

| claim vs 0.2.2 | tqLLM / 0.2.2 | ours | have it? |
|---|---|---|---|
| first token, short chat | 0.32-0.41 s / 1.07-1.29 s, each a **fresh server's first request** | P028x warm, 111-126-token prompts: **0.29-0.32 s** (gap16 X1n-X3n). TTFT 1K 0.78 s on the 10-21 port (gap7). | Yes in steady state. A fresh server's first request may still pay the lazy verify-graph captures (engine-P028x.log:59-78); not measured. |
| decode after 64K | 85.1 / 63.6 | P028x: 142-164 after 54K, 153-158 after 20K, 157-170 after 26.7K (gap16, sampled) | Yes: no collapse. |
| decode after 128K | 77.1 / 47.2 | 0.2.2-era port r22n: **157-163 after 120K**, 146-148 after 32K, TTFT 120K 28.2-29.5 s (gap7 summary:269-274). The 5090 (tqLLM): 83-127. | Yes. Mechanisms: int8 KV with 32K resident cells and the rest streamed from pinned RAM (99.8 % VRAM hits, engine-P028x.log:17, 85); the prompt's slot loan returned (`:47`); the helper tier. Their equivalents: host K/V past 64K, bank refill, indexer-key ring. |
| prefill 32K / 64K / 128K | ~1-3 % ahead (14.98 / 28.01 / 56.53 s on a 3090) | 4,441-4,505 tok/s at 20-54K; 16K cold 3,827; 64K 4,382 | Ahead of their 3090 figures. Their 5090 does 4,800-5,200. On the 5080 (about half the 5090's FP16 tensor rate) they are plausibly 2,800-3,800. |
| 1.4x 0.2.10 with two requests (CHANGELOG:11-14, `--np 2` 113 / 93 against 72-79) | — | single request in daily use | n/a |

## 5. sm_120 and CUDA

- **The CMake default is `native`** (`CMakeLists.txt:2-3`), so the build targets every GPU in the machine.
- **Toolchain.** CMake 3.25 or newer is required for CUDA C++20 (`:102-104`). The docs say CUDA 12.9 and 13.0 were
  tested (`quickstart.md:61-62`, CONTRIBUTING:24).
- **The image covers sm_120.** It builds with `nvidia/cuda:13.0.1-devel`, using `86;89;120` on x86 and 121 on arm64
  (`Dockerfile:1-18`). Its tags are `1.4.1` and `-cu13`.
- **sm_120 is exercised.**
  - It ran on an RTX 5090 (`docs/guides/rtx-5090.md`) and on a 5060 Ti for the 27B model.
  - Blackwell PCIe cards skip the per-layer CUDA graphs (`decode_rules.hpp:91-94`).
  - No kernel is gated off at sm_120: the `__CUDA_ARCH__` checks are ≥ 800 only.
- **Ours.** CUDA 13.3.1 (`/usr/local/cuda-13.3`), driver 615.71 and CMake 3.28.3 would all do. Docker plus the NVIDIA
  Container Toolkit was not checked.

## GO / NO-GO

| condition | result |
|---|---|
| runs here | yes: small-card mode on the 5080; RAM fits with 8080 down |
| sampled spec path exact | yes for its own sampler (sample-and-match on the full head). It cannot run min-p 0.05, so a screen would have to set min-p 0 on both arms. |
| plausible to beat P028x as served | **no**: decode, long-context decode and prompts are all at or below P028x |

**NO-GO.** Nothing to run. If Karl ever wants a look anyway, a screen would need:
- the 5080 alone via CUDA_VISIBLE_DEVICES, with 8080 down for RAM;
- min-p 0 and no presence penalty on every arm;
- the two-sample exactness test against `drafts=0`;
- the image or a native build of untrusted code, which is Karl's call.

**Worth a re-check** only if a later release brings any of: a second-GPU expert tier, an exact CPU expert lane, min-p,
logprobs, or a turn cache at `--np 1`.

**Possible ideas for us later** (read-only, not ported, no action):
- FP16-activation tensor-core expert decode (the u4h kernel), as a precision reference;
- cross-request copy drafts.
