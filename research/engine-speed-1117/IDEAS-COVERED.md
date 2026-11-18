# Engine-speed ideas already tried, measured, planned or backlogged (2026-11-17; final statuses 2026-11-18)

The companion of `ROUND-RESULTS.md` and `ROUND-FINAL.md` in this folder (the round closed 2026-11-18). Before suggesting a decode-speed idea for this setup, check it is not
here; if it is, say what is new about your version.

Setup these ideas were judged on: the Strata MoE engine serving Qwen3.8-Flash-Next (IQ3_S GSQ-RCO) on one desktop PC.
An RTX 5080 16 GB holds the main expert cache and runs the verifier. An RTX 4060 Ti 8 GB on a chipset PCIe x4 link
holds a static helper expert cache. The CPU expert pool runs on a Ryzen 9 9950X3D with 96 GB DDR5-6000, alongside a
PCIe share of missed experts copied from a pinned RAM arena. Drafting uses MTP speculative decoding plus a
prompt-lookup drafter, and the PLE n-gram table is read from the SSD. Rule: outputs stay exact, or rounding-level and
distribution-preserving where placement or sampling changes. A decode window is about 21 ms: the host's wait for the GPU
8.8 ms, per-layer host work 9.1 ms (the CPU pool 8.3 ms), drafting 2.3 ms (`ROUND-RESULTS.md` section 2).

Line format: `- **idea** - status - why (sources)`. Status is one of adopted / dropped / in progress / planned /
backlog.

Source keys:
- **tried** = the already-tried table of the 11-11 profile pack.
- **rN** = tuning round N (Sept-Oct 2026).
- **11-11** = the 11-11 deep-research report on untried lossless ideas.
- **Astra / Fable High / Fable xhigh / Fable Max / Fable moonshot / Pro plan #n** = the outside model reports, by
  idea number. "Fable moonshot" is the run the round plan cites as "xhigh #n".
- **Pro audits** = the audits of the plan and of the outside runs.
- **Astra 6.2 #n** = the outside report on this round's results (`Astra62_Ideas.pdf` in this folder), by experiment number.
- **r24** = this round, 2026-11-13..18. It covers A0 (desk), the gaps (A1-A5, A3c/A3p, GBAL, B1, X9, C256, BV, X11S, FE), the
  experimental items X1-X14, and phases C and D.
- **backlog X** = item X of the standing backlog.
- **upstream** = upstream Strata releases and notes.
- **engine B / I / M** = three other local inference engines whose ideas were reviewed.

## Expert placement and caching

- **Helper GPU as a static expert cache (4060 Ti, 3,300 experts, whole arena pinned)** - adopted - +15 % screen decode; an earlier loss came from an 8 GiB pin cap (r5, r6; tried)
- **Helper slot count** - adopted - 3,300 best; 2,400 -3.9 %, 1,500 -7.3 %, 3,500 within noise (r11; tried)
- **Helper variants: per-layer cap, upstream remote-expert-opt, peer tier, selective use by layer or window size, helper set following the conversation** - dropped - -6 to -18 %, or noise (r6, r10, r11; tried)
- **Layer split across both GPUs, or a fork's per-layer second-GPU mode, instead of a helper cache** - dropped - would not fit / 35-40 ms of x4 round trips per window, 3x slower (r5, r10)
- **Adaptive helper cache (victim cache for main-cache evictions and hot CPU misses)** - backlog - the trace-replay policy set was not run this round (B1's trace holds the inputs); must charge uploads over the x4 link (Fable High #1; Fable xhigh #4; Pro audit of plan; r24 B1)
- **Main cache never pulls experts the helper already holds (disjoint, helper-aware adaptive tier)** - adopted - +5.3-5.4 % (r10, r14; tried: ADAPT_LAG=2 + DISJOINT_ADAPT)
- **Adaptive-tier tuning (decay 0.8/0.9, adapt-every 2/8, 48 swaps) and no adaptation at all** - dropped - noise; no adaptation -18 % (r1, r2, r10; tried)
- **Deterministic swap landing** - adopted - repeatability at no measurable cost; upstream's equivalent used since (r9, r14)
- **Asynchronous / overlapped adaptive tier (upstream adaptive overlap, STRATA_ADAPT_ASYNC)** - dropped - the overlap cost -11.4 % on the research screen; the async tier is pinned off (not bit-exact run to run, never priced on two cards) (r19; tried; 11-11)
- **Admit PCIe-fetched misses into the main cache with a helper-aware pick list (STRATA_ADAPT_FETCH=2)** - adopted - +12.7 % screen decode; main-cache share 62.6 -> 67.3 % (backlog I; tried)
- **ADAPT_FETCH=1 (tier's own swaps kept in every layer)** - dropped - +10.2 %, =2 a further +2.3 %; =1 kept as fallback (tried)
- **Admit CPU-served misses too, uploaded in idle link time** - backlog - not replayed this round; the replay must charge the new uploads, and extra link copies cut the CPU pool's DRAM rate ~12 % in X11S (Fable xhigh #2; Pro audit of plan; r24 B1, X11S)
- **Exact-size (per-expert) cache slots** - adopted - already in the engine: 0 bytes of padding; max-size slots would hold 1,053 fewer experts (r12; 11-11; Astra, Fable xhigh and Pro plan audits)
- **Per-quant-type frame pools (engine I)** - dropped - desk check: no extra experts on this file (backlog F1; tried)
- **Score-based eviction (HybriMoE-style) instead of recency** - dropped - covered: the tier already ranks by routing frequency (11-11; Fable xhigh and Pro plan audits)
- **Inter-layer expert affinity as a retention prior (ExFlow-style)** - dropped - an affinity A/B showed no measurable effect (11-11; Fable xhigh audit)
- **Alternative expert profiles (learned profile, make_profile)** - dropped - learned -4.2 % (helper overloaded); make_profile noise (r10; tried)
- **Cache budgets across layers and devices priced by exposed time saved per byte (cross-layer slot lending, joint helper assignment)** - backlog - not replayed this round; a round-6 per-layer budget replay was noise (+1.1 / +1.4 / -0.6 % held-out) (Astra #2; Pro plan #1; engine I; r6)
- **Future-aware eviction with a learned demand forecaster, bounded by a Belady-style oracle** - backlog - not replayed this round; oracle bound first (Fable moonshot #1; Pro audit of moonshot)
- **Commit-time admission: separate committed and speculative-only demand** - backlog - trace replay, not run this round (Pro plan #7; Fable moonshot #6)
- **Re-seed borrowed slots from the prompt's own routing; save residency per conversation** - backlog - trace replay not run this round; round 12 put a better starting cache near 0 % (Fable High #2; Fable Max #4; r2; r12)
- **Runtime split of VRAM between KV cells and expert slots** - dropped - round 12 found experts-vs-KV dead; a static --kv-resident 16384 was +1.2 %, within spread (Fable xhigh #8; r12; tried)
- **One-layer-ahead staging: router L+1 on layer L's input names non-resident experts, copied ahead into staging slots (X11)** - dropped - stage 1 measured the costs: router pass +0.74 %, shadow copies +11.95 % (the CPU pool's DRAM rate 54.8 -> 47.8 GB/s, ~12 %); realistic -3.1 % end-to-end against a 13.6-15.6 % bound; a round-7 oracle on the adaptive tier of that time found 0-3 % (Fable Max #1; Fable moonshot #1/#8/#9; Fable High #3; 11-11; r6, r7; r24 X11, X11S)
- **Other staging predictors: near-miss readahead from router ranks 11-32, miss-follows-miss table** - dropped - 10-13 % recall vs the router predictor's 26-31 % (Fable moonshot #9; Fable Max #1; r24 X11)
- **Full runahead (the GPU runs layer L+1 on the partial residual to learn routes early)** - backlog - X11's stage 1 stopped on the copies' DRAM cost, which runahead's copies would pay too (Fable Max #1; Fable moonshot #8; r24 X11S)
- **Whole-model shadow copy running ahead to predict routes (OD-MoE-style)** - dropped - no spare hardware can run a copy ahead of the target (Fable Max; Pro audit of Max)
- **Next-layer CPU-cache warming of expert weights** - dropped - exact but -6.5 % served: its reads compete with the pool for DRAM (r6, r7, r12; tried)
- **Draft-round warming; L3 hot set for CPU experts** - dropped - oracle <= 1.5 %; 0.9 % (r12; tried)
- **Router bias toward cached experts (STRATA_ROUTE_PRIOR)** - dropped - lossy: changes which experts run (tried; 11-11)
- **Tail skip of low-weight missed experts (STRATA_ROUTE_TAIL_SKIP)** - dropped - lossy; kept off on every config (r18; tried)
- **Lossy miss handling: expert deferral, low-precision or low-rank stand-ins, capped target expert sets (MoE-Spec, AcceptMoE)** - dropped - they change the output (11-11; Astra and Pro audits)
- **Pin experts by need (STRATA_PIN_BY_NEED)** - dropped - single-GPU only; refused with a helper cache (11-11; Fable High audit)
- **Partial-expert residency / expert splitting** - dropped - same value per VRAM byte as whole experts (Fable moonshot; r12)
- **Exclusive GPU residency: drop host copies of permanently GPU-held experts** - backlog - Phase D: the helper's 3,300 experts are fixed for a session; 6.2 GiB freeable with a compacted arena (1.0 GiB in place, one CUDA-registered range); decode ~0 %; parked until Qwen4 Flash's size is known, revisit if its experts miss the ~58 GiB arena limit by less than ~6 GiB (Astra #10; Pro plan #8; r24 D2)
- **Smaller VRAM reserve for more slots (512 MiB)** - dropped - +108 slots but decode -5.0 %, free VRAM under the floor (r21; tried)
- **Upstream ForesightSwap (per-layer swap slots, STRATA_FS_SLOTS)** - dropped - dropped upstream: the smaller cache cost more than it returned on every box measured (upstream)

## PCIe share and transfers

- **Engine-priced PCIe share of missed experts (--pcie-frac auto)** - adopted - +2.6-3.1 % (10-23); settles at 0.40-0.45 (tried)
- **Fixed PCIe shares (0, 0.05-0.2, a calibrated 0.2)** - dropped - 0 was best on early builds; superseded by the auto share (r1, r2, r5)
- **Start share from the CPU pool's size (STRATA_PCIE_START)** - planned - startup-only and not in the served build; Qwen4 day-one list (A0; Fable High #10; Pro audit of plan)
- **Timing-fed per-layer CPU/GPU split (STRATA_PCIE_BALANCE) and richer miss-cost models** - dropped - its +2.5-2.6 % screens were acceptance luck; -0.1 to +0.5 % at equal acceptance, within noise (11-11; Pro plan #2; r24 A3, A3c, GBAL)
- **At least one PCIe expert in layers with 2+ misses (STRATA_PCIE_MIN1)** - dropped - slower at equal acceptance (11-11; Fable xhigh #9; r24 A3, A3p)
- **Pinned PCIe share (0.40)** - dropped - no gain (r24 A3p)
- **PCIe picks = the layer's most-routed misses, helper-held excluded** - adopted - part of the fetch patch (A0; backlog I)
- **Rank PCIe picks by this window's saved CPU time (C1)** - dropped - the CPU pool's cost is per expert (~40 us), not per row (Astra #1; Fable xhigh #6; Fable High #10; r24 C1)
- **Gate/up/down transfers on three streams (PreScope-style)** - dropped - the streams share PCIe and DRAM; the gain estimate used GPU memory bandwidth (11-11; Astra, Fable xhigh and Pro audits)
- **PCIe expert groups computed beside the VRAM hits (P1)** - backlog - not measured; 0.44 ms of PCIe groups per window (tried)
- **DMA copy-engine mode instead of the copy kernel** - dropped - no measurable difference, measured at share 0 (r4)
- **Start the PCIe share's copy right after the plan, on a branch stream beside the VRAM groups (FE)** - backlog - parked: byte-identical; +1.3 % adjusted (+2.6 % at an 84-block grid, where a guard tripped), under +3 %; the copy takes SMs from the VRAM groups and costs the CPU pool 3-4 % (Astra 6.2 #01; r24 FE)
- **The same early copy on the copy engine at publish** - backlog - the PCIe share controller reads only the start-up link probe and the CPU pool's speed, so a hidden copy cannot move the share (Astra 6.2 #01; r24 FE desk)
- **A PCIe share rule that sees exposed time (the GPU's wait for CPU rows)** - backlog - about +2.5 % at most with today's copy (r24 FE desk)
- **GPU writes the CPU pool's quantized input rows (only what the CPU experts need)** - adopted - mapped copy 6.3 -> 3.4 us per layer; verify rounds 1.3 % shorter (r3, r11, r14)
- **Whole expert arena pinned for DMA** - adopted - needed for the helper and for DMA prompt streaming; upstream pins on Linux since (r6, r8; 11-11)
- **Upstream pinned stage buffers; upstream batched uploads** - dropped - stage buffers corrupted IQ3_S decode upstream; batched uploads cannot act with a helper (r14, r16)
- **Lossless compression of transferred or RAM-tier experts (GPU-side or in-cache decode)** - dropped - for today's speed: 400 real blobs in 6 formats, zstd 1.01x, entropy bound 1.04x (the codes are ~8 bits a byte); CPU decode 2.3 GB/s a core; even free GPU decoding +0.07 %; a re-check on Qwen4's files is on the day-one list (Astra #9; Fable High #8; r24 D3)
- **IOMMU passthrough, larger PCIe payload / read-request sizes** - backlog - boot-flag changes excluded this round; the IOMMU reads as translated (Fable Max #7; r24 X3)
- **Reserved hugetlbfs pages for the arena** - backlog - needs root; no evidence of page-walk cost yet (Fable Max #7; Fable xhigh #7; A0)
- **Transparent huge pages for the arena** - dropped - +0.01 %; CPU-pool time bimodal run to run (r1, r11; tried)
- **Direct NVMe-to-VRAM (GPUDirect Storage / P2PDMA)** - dropped - not supported on GeForce cards (Fable Max; Fable moonshot #10; Pro audits)
- **KV host copies by DMA (upstream STRATA_KV_HOST_DMA, v0.2.14)** - backlog - a candidate cherry-pick onto the Qwen4 base, to be priced on cold prompts (upstream notes)

## CPU expert pool and kernels

- **One pinned worker per physical core, spin then sleep after 20 ms, host thread computes too** - adopted - already the default; workers never sleep inside a request (A0; r1, r4; Fable High #5; Fable xhigh #7)
- **Worker count 12 / 8, one CCD only, 4+4 across CCDs, --aux-cpus auto / host-thread affinity** - dropped - no gain, or slower (r24 A4; r2, r8)
- **Governor, C-state caps, cpu_dma_latency, spin-policy changes** - dropped - already the performance governor and EPP; no in-request sleeps (Fable High #5; Fable xhigh #7; A0)
- **Faster CPU expert kernels (IQ3_XXS singleton repack, AVX-512 IQ4_NL down for small groups)** - dropped - the exposed CPU wait caps them at 3.6 %, 2.7-2.9 % at most; X11, which would have raised that, stopped (Pro plan #5; Astra #4; r24 Phase C, X11S)
- **Cost-weighted row partitioning, workload-dependent active worker count** - backlog - not scheduled; 95 % of CPU jobs are single-row and cost is per expert (Pro plan #9; r24 C1)
- **One pool batch per layer; helper launched after the pool starts** - dropped - exact; -0.33 % and -1.03 % (tried)
- **IQ gather / IQ prefetch switches** - dropped - no gain (r11; tried)
- **Q2_0 down path; hidden-activation quantization step** - dropped - 0.28 and 0.04 ms per window, under the bar (r11)
- **Revert the fused madd+add (vpdpwssd) in AVX-512 i-quant rows** - backlog - suspected +0.1-0.3 % per-window cost; needs a revert build (tried; 11-11)
- **512-bit IQ4_XS / Q5_0 CPU rows on or off** - planned - Qwen4 day-one list; acts on one layer of this file (tried)
- **Pre-expanded, decode-free CPU expert layout** - dropped - ~25 % more bytes on a bandwidth-bound path (Fable High #8; Fable Max)
- **Exact-zero census and zero-skipping in expert kernels (X7)** - backlog - needs its own logging switch and a gap; 5 % of CPU down bytes is worth ~0.8 % of a window (Fable moonshot #7; Pro audit of moonshot; backlog S)
- **Second PC as a remote CPU expert worker (send activations, return outputs)** - backlog - step 1 (X14, a CPU-only AVX2 kernel benchmark) is built and harness-checked here; the second-PC run is pending (Fable Max #2; Fable moonshot #2; backlog M)
- **Bit-identical expert arithmetic across tiers (fixed reductions, 16-bit-activation integer math)** - backlog - not a speed item; CPU and GPU quantize activations differently (Fable Max #10; Fable moonshot; engine I; backlog F1)
- **Give an outstanding GPU copy a short head start on DDR (stagger the CPU tile release)** - backlog - a 0-32 us delay sweep with a reverse-order control first; kill below 0.687 ms a window (Astra 6.2 #07)
- **Split one missed expert: gate/up on the CPU, the down projection on the GPU** - backlog - fit per-projection CPU and copy costs first; never expose a partly filled slot (Astra 6.2 #11)
- **AMX and dual-socket NUMA techniques** - dropped - no AMX; one NUMA node (Astra)
- **iGPU as a compute tier** - dropped - it shares the saturated DDR bus (Fable Max; Fable moonshot)
- **Second CCD for a predictor or polling thread** - dropped - the pool already spans both CCDs (Fable moonshot; Pro audit of moonshot)
- **RAM at 6200 MT/s** - dropped - unstable (memtest errors); 6000 MT/s since (r19; tried)

## GPU kernels (decode)

- **Fork hyper-connection read (STRATA_GR_FORK)** - adopted - +6.1 % over upstream's newer read; fork off costs +3.5-3.9 % step time (r11, r14; tried)
- **Other HC read variants: hand-tuned v2 / v4 kernels, staged read (HC_SPLIT)** - dropped - register pressure / L2 loads on the critical path; staged read bitwise identical but -1.4 % (r3, r4, r9; tried)
- **Upstream v3 HC read (STRATA_GR_V3)** - adopted - +1.6-2.7 % (r9; tried)
- **GR_V3_PF=133** - backlog - identity 7/7, +2.06 % within 5.6 % noise; parked (tried)
- **Exact-T 5-8-token HC kernels (STRATA_GR_R2)** - planned - masked by GR_FORK here; Qwen4 day-one list (A0; tried; 11-11)
- **Certified two-pass sparse-attention index selector (STRATA_SELECT_TWO_PASS, upstream v0.2.12)** - planned - Qwen4 day-one list: its check mode first (identical ordered ids), then cold 128K / 256K reads (Astra 6.2 #02; upstream)
- **Row-wise QSA block scores (STRATA_QSA_ROWS) on the 5080** - backlog - expected <= ~1 %; its bench faults below 32,768 cells of context (Niko1221/Strata#6209) and is not run again without a fix (Astra 6.2 #05; r24 FE)
- **GR_FORK generalised to other model shapes** - backlog - compiled out at new shapes until a gain warrants it (tried)
- **Persistent one-kernel HC read (STRATA_HC_PERSIST)** - dropped - fails the long-context KL check and is +2.9 % slower; a re-test at Qwen4 shapes is listed (Pro plan #3; r24 A2)
- **Fused Q8_1 quantize + interleave (STRATA_QIL)** - dropped - not faster at byte-identical output (Pro plan #6; r24 A2)
- **Producers emit their consumers' Q8_1 blocks (QFUSE-style fusion)** - backlog - not tested; conflicts with the one-token fast path and HC_PERSIST (Pro plan #6)
- **BF16 HC exponent packing + fused rebuild kernel (X1 -> X8)** - dropped - 19.7 % net bytes saved on paper, kernel 8.5 % slower (Fable Max #6; Fable moonshot #4; r24 X1, X8)
- **Int8 HC copies for decode (STRATA_HC_Q8 / HC_REQ8)** - dropped - prompt and decode would read different values (tried; 11-11)
- **Dense tensors kept in native quantized form** - adopted - already the native dense path (Fable moonshot #4; Pro audit of moonshot)
- **Interleaved mat-vec (MMVQ_IL) with a row table measured on this card** - adopted - +2.0 %; card table +0.2 %; an sm_89 table gained nothing (r11, r14, r18; tried)
- **Split decode attention (QSA_SPLIT_ATTN)** - adopted - +3.0-4.3 % (r11, r14; tried)
- **Side mixer on its own branch (SIDE_MIXER=2)** - adopted - +2.5 % (r14, r18; tried)
- **Q8_K router rows (ROUTER_Q8K); one-read multi-token BF16 router mat-vec** - adopted - +1.4 %; weights read once per window (r3, r14; tried)
- **Shared expert and mixer work on graph branches / a side stream** - adopted - default on CUDA; a fork's mixer branches -1.5-1.7 % per round (r10; A0; Fable xhigh #9)
- **Upstream decode gains carried: GPU expert kernels (PR245), batched verify window, async commit, cluster kernels, commit batching** - adopted - measured +1 to +4.5 % each where priced (r5, r8, r9, r10, r14, r20)
- **Programmatic dependent launch (DF_PDL), graph priority, fused wait** - dropped - ~0.14 us per boundary; all within noise (r8, r9; tried)
- **DF_PLE** - dropped - -2.2 %; main GPU free VRAM fell to 25 MiB (tried)
- **CUDA-graph capture of the whole window to remove CPU flag waits** - dropped - verify is already graphed; launch gaps 1.5-3 us per layer; the waits are real CPU work (11-11; Astra, Fable xhigh and Pro audits)
- **GPU-side MoE planning; one-graph draft chain; one fewer in-window sync** - dropped - bounds 0.6 %, 0.1-0.17 ms, ~0.6 % (r8; tried)
- **L2 prefetch of the next layer's weights (G5a)** - backlog - needs a probe (tried)
- **Helper rows written in place (H2)** - dropped - 0.108 ms per window, under the 0.15 ms bar (tried)
- **Draft-only persisting L2 window for MTP weights** - backlog - not scheduled; estimated <= 0.75 % (Astra #8)
- **Fuse the accepted GDN-state replay into the next verify pass** - backlog - not scheduled; commit is already batched and async, estimated 0-3 % (Astra #7)
- **Two-window pipelined decode with GDN snapshots (--pipeline-windows)** - dropped - needs a model layer split and refuses helper caches; verify already avoids state commits (11-11; Astra and Pro audits)
- **Small-unroll and IL-pad kernel defaults (SMALL_UNR, IL_PAD)** - backlog - bit-identical by upstream's hashes; never priced (tried)
- **Tiled dense layout (engine I, ~3 % claimed)** - backlog - not reviewed (backlog F1)

## Speculative decoding and drafting

- **MTP at --spec 7 with cumulative draft length (DRAFT_CUM)** - adopted - +3.2 % vs spec 4 (tried)
- **Other draft depths and floors (spec 3-8, min-p 0.3-0.7)** - dropped - flat optimum; --spec-min-p 0.5 kept (r2, r8, r9; tried)
- **Cost-aware draft length fitted on this PC (STRATA_COST_GATE)** - adopted - +3.4 % decode; -2.0 % after 120K prompts (r12, r14, r19; tried)
- **Exact speculative sampling with sampled drafts (STRATA_SPEC_EXACT)** - adopted - +2-3.5 % decode, higher acceptance; distribution checks pass (r9, r14; tried)
- **Upstream SPEC_PROB (also with GATE=top); upstream coupled drafting** - dropped - biased by min-p gating on the drawn token's q; slower (r8, r19; tried)
- **Upstream cost-aware window (STRATA_SPEC_COST), live miss-aware gate** - dropped - within noise (-0.48 %); incoherent stacked on COST_GATE + DRAFT_CUM (Fable High #6; 11-11; r24 A5)
- **Expected-miss feature in the cost gate (X12); pricing every draft depth** - dropped - feature -0.03 %, re-tuned per-depth stop +0.17 % on held-out requests (Fable Max #8; Fable xhigh #10; r24 X12)
- **Block verification of the single MTP chain** - dropped - +0.175 % committed tokens per window (95 %: +0.11 to +0.22 %), from a capture of the drafter's exact q and the target's top-64 rows; the prediction matched observed acceptance within 0.5 points at every depth (Astra #3; Fable xhigh #3; Fable High #4; Pro plan #4; 11-11; r24 BV)
- **Token recycling: the target's past distributions at the same recent ids as the first draft** - dropped - an oracle replay gains +0.062 commits a window, under the 0.12 hurdle; MTP's first draft already overlaps the target 80 % (Astra 6.2 #03; r24 BV capture)
- **Multi-draft / tree verification (GBV with K>1, traversal, OT multi-draft)** - dropped - tree drafting measured -10 %; wider expert unions per window (r12; 11-11; audits)
- **Relaxed verifiers that accept near-misses** - dropped - not distribution-preserving (Astra)
- **Prompt-lookup drafter (--suffix-draft 3)** - adopted - served default; longer matches (8, 16) gained nothing (r1, r10; tried)
- **Lookup windows up to 12 rows (--lookup-max-t)** - dropped - +0.96 % within noise and failed distribution checks; later traced to window numerics, wide lookup draws untested (tried; r24 X2)
- **Suffix-tree drafting, wider or slow-start copy windows, long copies verified as a prompt chunk (X10)** - dropped - best causal policy +0.3 %, hindsight ceiling ~5 %; each wrong copy row costs ~3 ms (Fable xhigh #5; Fable moonshot #3; r24 X10)
- **Copy drafts only where MTP's own first drafts agree** - backlog - offline test first; build only at ~+3 % (backlog R)
- **Cheaper draft-only drafter (fewer or lower-precision draft experts, smaller draft top-k, profiled draft step) (X13)** - dropped - ceiling 2.1 % central (3.1 % in the most optimistic corner) before any acceptance loss: drafting 2.33 of 21.7 ms, 205 MiB read a draft step, 3.31 drafts a window; fewer experts alone ~0.2 % (Fable High #7; Fable moonshot #5; r24 X13)
- **Engine B's tuned MTP draft layer** - dropped - a wash (tried)
- **Retrain the MTP head for acceptance length** - dropped - outside this round's lossless brief; low expectation after the tuned-layer wash (Fable High #9; Pro audit of Max)
- **Drafter adapter** - dropped - ~0.4 % (r12; tried)
- **Online draft calibration (per-depth temperature, token bias)** - backlog - the adapter's ~0.4 % lowers expectations (Fable Max #9; r24 backlog)
- **DFlash / DFlash2 drafters** - backlog - +7 % upstream at matched slots, a tie on two cards; model-specific (backlog P; tried)
- **Drafter on the helper GPU, trunk on the main GPU and CPU (DeepSeek config)** - adopted - about +10 % decode on that model (DeepSeek round)
- **Drafter on separate hardware or a second stream in the Qwen setup (fork two-GPU mode, MTP_ASYNC)** - dropped - 40 ms cross-GPU waits; second stream exact but +2.2 % slower (11-11; r9)
- **Drafting during verification** - dropped - MTP needs the verifier's final state; <= 2 % (Fable Max; Fable moonshot)
- **Lossy model twin as a self-drafter** - dropped - at most 1.7x over exact decode given the GPU floor (Fable moonshot)
- **Two-stage output head (Q6_K candidate head, sketch-certified bound)** - dropped - 2.2 % wrong top-20 where capped, +0.7 % within noise; the bound is too loose (tried; Fable Max)
- **Draft-head vocabulary list (English/code vs CJK)** - adopted - English/code list kept; the CJK list cost 1-2 % on English decode (r7, r9)
- **Smaller drafter attention window (16K)** - dropped - prompts <= 3 % faster, long-context decode risk (r8)
- **Faster sampler (upstream split top-k)** - adopted - 2.4-2.6 ms saved per round at top-k 20 (r8)
- **Faster draft sampler** - dropped - 0.8 % (r12)
- **Two token groups in one window (--spec-split)** - dropped - the GPU does the dense and HC work twice; spec 8 + split -3.6 % (r3, r4, r7; tried)
- **Gumbel-coupled drafter-invariant verification as a test mode** - backlog - not scheduled (Fable moonshot; Pro audit of moonshot)
- **A schema / edit-syntax drafter for tool calls** - backlog - needs ~30 % coverage on held-out agent sessions, scored against both lookup and MTP (Astra 6.2 #12)

## Prompt path (prefill)

- **HC up-projection + mix in one kernel (STRATA_HC_UPMIX)** - adopted - exact; pp16k +3.3 %, pp64k +4.5 % (tried; backlog H)
- **Prompt tail split (STRATA_PF_TAIL_SPLIT)** - backlog - +6.1 / +2.6 % but drops the 16K mid-prompt checkpoint; after Qwen4 day one (tried; backlog H)
- **Next chunk's expert fetch ahead (STRATA_PF_AHEAD)** - dropped - exact, +0.2 / +0.6 %, within noise (tried; 11-11)
- **Larger first chunk + 22,528-token cap stack** - backlog - prompt +15.9 / +8.9 % but decode -3 to -4 %; retry without the checkpoint pool (tried; backlog H)
- **Checkpoint pool (STRATA_CKPT_POOL)** - dropped - no gain; it excludes the chat cache (tried)
- **Larger prompt chunks (4K -> 8K -> 16K)** - adopted - 16K: TTFT -2.9 / -3.7 %; 12K and 32K rejected (r1, r2, r10, r11; tried)
- **Equal-size prompt chunks (#693)** - adopted - up to -12.4 % TTFT, never slower; dropped once in r11 for a lost checkpoint (r11; tried)
- **CPU share for short prompt chunks (0.4 below 1,792 tokens)** - adopted - first token -15 / -21 %; it costs above ~2K tokens (r16, r19; tried)
- **Fused int8 prompt experts (STRATA_PF_FUSED)** - adopted - TTFT -3.3 to -3.7 % (r10; tried)
- **v2 prompt-expert kernels + wide dequant (PREFILL_V2, DEQUANT_WIDE)** - adopted - TTFT -4 to -9 % (tried)
- **Prompt experts read in place (no copy into the MMQ group buffer)** - adopted - -3 % prompt time (r8)
- **Prompt MMQ tile sizes** - dropped - the best fixed tile saves 0.3 % of a 32K prompt (r9)
- **Int8 tensor-core prompt attention (PROMPT_ATTN_IMMA)** - dropped - TTFT -2.7 % but changed top-1 picks below the floor; retest against a higher-precision reference backlogged (tried; backlog D3)
- **Layer-major / layered prefill** - dropped - another summation order; upstream's switch targets layer splits; pinned off (11-11; Fable xhigh audit)
- **GDN chunked prefill (FlashQLA-style)** - dropped - BF16 ~1,600x less accurate; the recurrence is 7.6 % of prompt GPU time (r8; tried)
- **Upstream GDN prompt paths (GDN_TC, GDN_CONVL2)** - dropped - failed the 40-prompt KL band; pinned off (tried; backlog G2)
- **PF_HC_REGION with PREFILL_V2** - dropped - not exact (tried)
- **Fused QSA rms-norm + rope in the prompt (STRATA_QSA_FUSE_NR)** - backlog - never priced; its parity test was HIP-only (tried; 11-11)
- **Stream prompt experts from the helper's VRAM (PREFILL_HELPER_SOURCE)** - dropped - +0.2-2.2 % TTFT: the x4 link is the wrong pipe (r19; 11-11)
- **Draft-layer prompt pass on a second stream (MTP_ASYNC)** - dropped - exact but +2.2 % slower (r9; 11-11)
- **Residency- and multiplicity-aware short-prefill placement; no hot-set eviction between chunks (Ostinato-style)** - backlog - not scheduled (Astra #5; 11-11)
- **A restart checkpoint inside the fast prompt chunk (keeps the tail split's gain)** - backlog - count usable prefix boundaries on real edits first (Astra 6.2 #06)
- **Cancel unissued prompt uploads once the exact router runs** - backlog - count the bytes still cancellable at that point first (Astra 6.2 #09)
- **Strata's own prompt kernels without MMQ + equal-chunk cut (v0.2.14)** - backlog - not ported; would re-gate the passed baseline (upstream notes)

## PLE n-gram table

- **Larger PLE row cache (4M / 8M rows; 32M proposed)** - dropped - within noise / slower (11-11; Astra #6; Pro plan #10; r24 A3)
- **PLE table in RAM or fully in the page cache** - dropped - over the lock limit; a whole-table page cache gave <= 1.6 % prompt (r2; tried; 11-11)
- **mmap PLE reads with MADV hints** - dropped - cold mmap faults serially; direct reads used (r1; 11-11; audits)
- **Parallel PLE reads on a thread pool** - adopted - prompt reads +40 % then; upstream since (r1, r2, r5)
- **More PLE reads in flight (256)** - dropped - no gain (tried)
- **Batched layer-1 PLE and next-chunk PLE prefetch in the prompt** - adopted - prompt -7 % / -2 %; upstream since (r3)
- **Unblock gather_batch during an in-flight per-token read** - dropped - code misread: prefetch tickets are separate (11-11; Astra and Pro audits)
- **Stack fast path for small PLE batches (v0.2.13)** - planned - comes with the v0.2.13 port base (11-11; Pro audit)
- **Per-layer PLE cache split** - dropped - no-op with one table (11-11; Fable High audit)
- **PLE reads beside layer 0 on a thread; next window's first-token rows prefetched at commit** - dropped - the wait moved to the GPU; the commit prefetch gained 1-3.7 % once, nothing on later bases (r6, r14)
- **Prefetch-key matching fix (#2622)** - adopted - in the engine since v0.2.6 (11-11)
- **SSD keepalive (upstream default)** - adopted - first token ~10 ms sooner after idle, no cost (r9)

## Memory, KV and conversation caches

- **256K context (--max-context 262144)** - adopted - -0.63 % short decode accepted (r24 C256)
- **KV streaming with int8 KV (32,768 resident cells)** - adopted - streaming off -4 / -7 % (r1; tried)
- **--kv-resident 16384** - dropped - +1.2 %, within spread (tried)
- **Other KV formats (q4_0 and others)** - backlog - q4_0 gave nothing at <= 32K early on; no A/B on current builds (r1; tried)
- **Custom chat cache patch (park conversations in RAM, 16 slots / 12 GiB)** - adopted - back to a parked chat in 0.36-0.75 s (r3, r8, r9; tried)
- **Upstream conversation cache** - dropped - prompt -6.8 %; synchronous parks; ~3.5 GB more RAM (r8; tried)
- **Cached-turn re-encoding fix (#567)** - adopted - TTFT -31 / -61 % on cached 31K / 98K turns (r11, r18)
- **Prefix cache with RAM + file tiers that survives restarts (engine I)** - backlog - not reviewed (backlog F1)
- **Reuse chat-cache save buffers** - dropped - theory not supported by the page-fault data (tried)
- **Lazy CUDA module loading** - adopted - ~250 MiB more free VRAM after load (r4)
- **Experts beyond RAM: file tier with direct reads (used for DeepSeek; Qwen4 fallback)** - planned - Qwen4 day-one arm only if the quant doesn't fit RAM; direct reads +15-48 % over the page cache; stand-ins ran 14-51 tok/s (r15, r19; r24 X4; Fable Max #5)
- **New io_uring SSD expert reader / buffer manager; chat-cache spill to NVMe** - backlog - only if the existing O_DIRECT tier proves the bottleneck (Fable Max #5; Fable moonshot #10; r24 X4)
- **Lower swappiness for long-prompt swap-outs (DeepSeek)** - backlog - needs root (backlog D8)
- **Vision tower kept in RAM between pictures (DeepSeek, upstream v0.2.10)** - backlog - ~320 MiB more VRAM for experts; next DeepSeek round (backlog F2)
- **Share VRAM between scratch buffers with disjoint lifetimes** - backlog - a lifetime simulation over the worst legal schedule first; kill below 0.687 ms a window (Astra 6.2 #04)
- **Gather only the old KV pages a short warm suffix selects** - planned - Qwen4 day-one list; size it first by the warm-continuation staging cost at 128K / 200K (Astra 6.2 #08)
- **S3-FIFO-style protection of revisited sparse-attention KV pages** - backlog - matters only if sparse pages spill to host; log page sets and replay first (Astra 6.2 #10)
- **Lay cold SSD experts out in co-request order** - backlog - only if Qwen4 spills experts to the SSD (Astra 6.2 #13)

## Measurement and harness

- **Acceptance-adjusted speed metric** - adopted - detects ~0.7 % at 4 v 4 starts vs ~3.7 % for raw tok/s (r24 base-drift)
- **Fixed-work vs free-running tests (replayed histories, held placement, pinned share)** - adopted - separates kernel speed from acceptance and adaptation (Pro audit of plan; r24 plan)
- **Baseline diagnostics (widths, per-depth acceptance to depth 6/7, bytes, intervals, pool wake, exposed PLE wait, engagement lines)** - adopted - overhead within noise (A0; r24 A1; Fable xhigh #10)
- **Routing trace v2 + causal replay, with hindsight labelled as bounds** - adopted - 102,190 windows captured; dump-routing fixed to accepted rows earlier (r6; r24 B1)
- **GPU-clock phase stamps per layer-step (deadline map)** - adopted - distortion within noise (r24 X9)
- **Correctness gates: exact7, long40, sampled-distribution test, KL bands** - adopted - every speed change passes its contract first (tried; r24 plan)
- **Live admission read-back as part of a byte contract** - adopted - exact7 runs with the adaptive tier off, so a change that writes admitted slots also needs the live read-back (241 M slots read back in FE, 0 differ) (r24 FE)
- **Forced-path state fixtures (rejection at every depth, bonus token, admissions)** - adopted - built and run in A1; the state check against today's width-to-width differences failed narrowly, so no wider verifier is built (Pro audit of plan; r24 A1)
- **About +3 % predicted end-to-end gain before any build** - adopted - this round's build threshold (Pro audit of plan; r24 plan)
- **Bandwidth-wall probes: fewer workers, DDR / GPU memory clock steps, link cap, memory-controller counters (X5)** - dropped - the worker sweep ran (A4); the clock and counter arms need root or BIOS, recorded as limits (Fable Max; Fable moonshot; r24 X5)
- **In-run A/B (flip a switch every ~16 windows)** - backlog - not adopted; interleaved starts used instead (Fable moonshot; Pro audit of moonshot)
- **Served repeatability: fixed draft-cost table, placement from logical counters, upstream's share in the draft-cost table** - backlog - the daily stays adaptive (backlog K; Fable Max #10; upstream notes)
- **Many-position NLL gate on ~200 long texts** - backlog - parked (backlog G1)
- **Strata's own tuner (strata tune auto)** - backlog - never run (tried; Fable High #10)

## Other (concurrency, models, ports, serving)

- **Two requests in one verify window; --batch 4** - dropped - pairs finish 20 % later; batch slots cut the cache from 4,585 to 2,781 slots (r7, r12; tried)
- **Two column groups offset half a layer so GPU and CPU phases overlap (drafting hidden too)** - dropped - Phase D cost model: central +0.1 %; the GPU is ~95 % busy in a window and a second group adds a 101-112 us dense pass per layer; +3.0-4.2 % only with a PCIe copy that costs the GPU ~no compute; the earlier --spec-split lost (Fable xhigh #1; r24 D1)
- **Anti-phase interleave of two concurrent requests** - backlog - helps only with two requests at once; r7 estimated +28 % total at best (Fable Max #3; Fable High; r7)
- **Display on the iGPU, not the helper card** - adopted - desktop redraws on the helper cost up to ~17 % on research traffic (r11)
- **Reasoning effort medium by default** - adopted - suite 94.5 vs 90.7 for xhigh, in about 1/3 the time (r21; tried)
- **Picture reader on the CPU** - adopted - a GPU reader on the helper cost 1-2 % decode (tried)
- **IQ3_S GSQ-RCO quant** - adopted - top-1 87.4 % vs Q8_0 (tried)
- **NVFP4 / FP4 packs** - dropped - decode ~30 % slower (r20, r21; tried)
- **UD-Q4_K_XL, UD-IQ3_XXS and expert splices** - dropped - Q4 decode -51 %; the IQ3_XXS variants had worse KL for +2-3 % decode (r16; tried)
- **Engine-aware mixed quantization by placement tier** - backlog - desk study first (backlog L)
- **Engine B at its defaults, or made lossless** - dropped - not lossless at defaults; the lossless estimate was not built (tried)
- **DeepSeek prompt-path port ("BORROW") and engine M's prompt-compute ideas (helper read share, MMA attention, lean tiles, store huge pages, exact-size store slots)** - backlog - estimates only (backlog D5)
- **Long-context decode change (engine I, +25 % claimed at 250K)** - backlog - not reviewed (backlog F1)
- **Pin upstream 0.2.7 per-card defaults off (STRATA_DEFAULTS=026)** - adopted - the new defaults were never priced one by one (tried)
- **v0.2.10 port** - dropped - screen decode -0.87 %, fixture blend -2.5 % (tried)
- **v0.2.13 port as the next base** - planned - baseline pass vs the daily; the Qwen4 day-one base (tried; upstream notes)
- **Move to v0.2.14 / v0.2.15** - backlog - no capability we lack; would re-gate everything (upstream notes)

Measured and drafted with Claude Code.
