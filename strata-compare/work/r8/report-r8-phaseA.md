### Phase A — feasibility (2026-09-30 20:21 → )

Your time split from the 10.9-hour uptime monitor (529 requests): **94 % decode, 6 % prompt reading.** A prompt-side
gain is therefore worth about 1/15 of a decode-side gain of the same percentage.

#### A.1 Decode profile (nsys, served requests, NVTX ranges in the serve loop; engine-r8t = C\*8 + trace markers)
| per decode round (sampled, your settings) | ms | share |
|---|---|---|
| verify window (mean 2.6 tokens) | 19.86 | 91 % |
| – GPU working | 14.90 | 75 % of the window |
| – GPU waiting for the CPU experts (flag wait) | 3.54 | 18 % |
| – gaps | 0.24 | 1 % |
| commit | 0.62 | 3 % |
| drafting (2.34 drafts per round) | 1.35 | 6 % |
Greedy: window 18.88 ms (mean 2.8 tokens), flag wait 2.42 ms. The new split sampler costs 33 µs per window.

GPU time per window, with achieved bandwidth vs the measured read ceiling of **913 GB/s** (device copy: 818 GB/s):
| kernels | ms/window | bandwidth | of ceiling |
|---|---|---|---|
| GPU experts (native_down 3.49 + native_gu 2.04 + SwiGLU + quantize) | ~6.0 | gate/up ≈ 500 GB/s, down ≈ 200 GB/s (est.) | 55 % / 22 % |
| dense quantized GEMVs (mmvq) | 3.22 (+0.5 attention projections) | 568 GB/s | 62 % |
| hyper-connection reads (gr_up + gr_down + gr_norm) | 2.75 | 441 GB/s | 48 % |
| LM head Q6_K | 0.54 | 682 GB/s | 75 % |
| bf16 mmvf | 0.69 | 338 GB/s | 37 % |
| QSA attention 0.48, GDN step 0.56 | | | |
No hardware counters (profiling is admin-only here), so the roofline uses bytes read from the GGUF over kernel time.

**Sync audit:** between two windows the 5080 is idle 0.42 ms per round (1.9 %). Most of that sits in per-draft syncs
the floor rule needs. The commit → draft-1 sync could go (≈ 0.1–0.16 ms ≈ 0.5–0.7 %).

#### A.2 Prompt profile (STRATA_PREFILL_TIMING, cold CLI, 2 runs each)
| share of GPU time | 32K | 112K |
|---|---|---|
| GDN mixer (of which the recurrence) | 24.6 % (7.6 %) | 24.8 % (7.7 %) |
| expert GEMMs (MMQ gate/up + down) | 21.9 % | 22.0 % |
| expert group copies (gather, conversions, waiting for stream copies) | 15.3 % | 15.6 % |
| QSA | 14.8 % | 18.8 % |
| hyper-connection reads | 8.7 % | 8.6 % |
| router + shared expert + combine | 7.1 % | 7.1 % |
| draft layer's pass (share of wall time) | 694 ms = 6.7 % | 698 ms = 2.0 % |
| n-gram (GPU / host, share of wall time) | 0.4 % / 1.7 % | – / 0.5 % |
Wall: 32K 10.41 / 10.43 s, 112K 35.47 / 35.50 s.

#### A.3 Thread affinity
There are 90 engine threads. The 15 pool workers are pinned to cores 1–15, as designed. The host thread uses core 0
about 85 % of the time. **6 long-lived threads (the prompt stagers) inherited the host's core-0 mask** but are idle
because the whole arena is registered. The adaptive tier's thread and the chat cache's park-copy threads inherit it too
(from the source). Fix build: engine-r8a, which unpins helpers; STRATA_HELPER_UNPIN=0 restores the old behavior.
**Served A/B: no effect.** Decode 103.4 / 105.8 vs 104.2 / 105.8 tok/s; park times identical (40K chat: 78 vs 78 ms).
**Dropped.**

#### A.4 Speculation oracle (engine-r8o; p and q after the full sampler chain; 9,007 drafted positions)
Scenarios: math, code, prose, web-result synthesis (~11K-token prompt), doc 64K, doc 120K, web synthesis ~102K. Your
settings, fixed seeds.
- **The oracle checks out:** draft-1 acceptance observed 0.737, predicted from p(d) 0.735.
- **Exact speculative sampling, Σmin(p,q):** draft 1 0.778; all drafts 0.791 vs 0.757 today. Expected tokens per MTP
  window 2.393 → 2.486 (**+3.9 %**). By scenario: math +4.8, code +4.9, prose +3.6, web synthesis +5.1, doc 64K +3.0,
  doc 120K +2.7, web synthesis 102K +3.2 %. About a third of windows are prompt-lookup windows, so it's ≈ +3 % overall.
- **Coupled drafting (STRATA_SPEC_COUPLED):** tokens per window over all windows 1.915 vs greedy 1.952 (**−1.9 %**).
  Its higher draft-1 acceptance (0.772) is selection bias: draft length is gated on the probability of the *sampled*
  draft. Checks: p and q are calibrated, the uniforms are shared, Monte Carlo matches the closed form. Upstream also
  found "no clear gain". **Dropped.**
- **Window times W(T)** (ms per round incl. commit + drafting): ≈ 16.0 ms + 3.9 ms per extra token (T2 16.0 … T8 38.2).
- **Policy model** (7-draft arm, 3,472 windows): raising the greedy floor from 0.5 to 0.7 / 0.8 / 0.9 gives
  **+4.0 / +5.0 / +5.5 %** (a config change). Exact sampling gives +9.2 to +12.1 % vs today, i.e. **~+6 % over the
  best config**. Longer caps don't help.
- **Drafter window at long context:** with the 32K window, draft-1 acceptance at 64K–120K is 0.74–0.77, the same as
  short context. Attending to every cell (window 0) drops it to 0.49–0.64. Sparse drafter attention has nothing to
  recover. **Dropped.**
- Sampling the drafts costs +0.03 ms per round.

#### A.5 GDN prompt kernel (Strata's gdn_recurrence vs QwenLM FlashQLA 0.1.3)
Strata's kernel is token-by-token, as suspected. Fixture: GDN layer 10, the 2nd 8,192-token chunk of a 32K prompt. The
harness is bit-identical to the engine.
| arm | rel. rms error vs FP64, y / state | time per layer-chunk |
|---|---|---|
| Strata FP32 recurrence | 2.3e-6 / 1.1e-5 | **5.44 ms** (pre-#188: 6.31) |
| PyTorch FP32 chunked WY form (C = 64, eager) | 2.6e-7 / 3.6e-7 | 28.3 ms |
| FlashQLA (BF16 q/k/v only) | **3.7e-3 / 2.3e-3** | 1.09 ms kernel; **6.02 ms** with conversions and norm |
FlashQLA needed two workarounds to run on the 5080 at all:
- a missing `aggregate_card_state` symbol;
- a kernel asking for 110 KiB of shared memory per block, when the card allows 99 KiB.

Its BF16 inputs are ~1,600× less accurate than today's FP32, which isn't allowed here. With conversions it isn't faster
anyway. The recurrence is 7.6 % of prompt GPU time, or < 0.5 % of your time. **Dropped.**

#### A.5b Kernel experiments
- **PDL** (microbenchmark of 2,000 dependent graph kernels): saves 0.14 µs per kernel boundary. Over ~2,576 kernels
  per window that's ≈ 0.36 ms ≈ **1.8 %** of a window. The early trigger slows real work (47 vs 33 µs). Effort: every
  kernel in the window graph. → backlog.
- **PR245 grouped experts** (fork commits cf307ea + 8208f3f, transplanted behind STRATA_EXPERTS_OLD=1):
  - Real-expert parity is **bitwise identical on sm_120 and sm_89**.
  - Kernel time per call ×0.743 (5080) / ×0.749 (4060 Ti).
  - Engine exact runs: output identical; −6.0 % (math) / −8.0 % (code) per round.
  - **Served A/B: +4.5 % decode** (109.8 / 111.6 vs 107.1 / 104.6 tok/s; ms per round −4.2 %).
