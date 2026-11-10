### Phase 0 — the update to Strata v0.1.30 (v0.1.28, v0.1.29, v0.1.30)

Round 8a never ran, so Phase 0 started from C\*7 (v0.1.27 + 13 patches). The tag watcher found **v0.1.30** (the newest
release; branches `main` and `rc/0.1.30`). v0.1.27 → v0.1.30 is 103 commits in 120 files.

**What matters for this PC and config** (release notes in `work/r8/release-notes.txt`):

| release | change | on our config |
|---|---|---|
| 0.1.28 | the expert cache reserves the draft head's VRAM (+86 MiB here) | applies: −47 cache slots at the same `--vram-reserve-mib`; compensated (below) |
| 0.1.28 | a request cancelled during its prompt read no longer fails the next one (#183/#205) | applies: the same bug as our patch 0013, fixed another way (clear the stale error per request and in `Prefill::run`) |
| 0.1.28 | `/status` needs the API key, constant-time key check, tool calls with `</parameter>` in values | applies (harmless; we bind 127.0.0.1 without a key) |
| 0.1.29 | **sampled answers: split top-k over the whole GPU (#197)** — the same tokens | **applies: the big win** (below) |
| 0.1.29 | QSA block scores read once per window (#187), GDN prompt recurrence pipelined (#188), both bit-identical | applies |
| 0.1.29 | correctness fixes (#154): NaN in bf16, the q8 split GEMV barrier, unresolved KV-streaming blocks masked | applies (no change on our texts: see accuracy) |
| 0.1.29 | pinning with a helper GPU still capped at 8 GiB | our Linux fix (patch 0011) kept and verified |
| 0.1.30 | every expert streams from 1,024-token chunks (was 2,048) | applies to prompts / appended reads of 1,024–2,047 tokens |
| 0.1.30 | conversation cache (#189, opt-in) | compared with ours (below) |
| 0.1.30 | `STRATA_IQ_MT_MIN=1` (opt-in), coupled draft sampling (opt-in), idle unload, rope scaling, resident low-RAM variant, shared arena, layer-split carve | off (as you asked); `STRATA_IQ_MT_MIN` / coupled drafting are Phase A test settings only |

**The port** (branch `r8-port`, `patches/r8/`): C\*7's patches 0001–0012 on v0.1.30; **0013 not ported** (upstream's
fix). Merges: `server.py` twice (both sides kept), our GR v5 kernel file (Round 7's merge + upstream's pre-Volta
capacity rule), and the pin-cap patch (upstream moved the code; re-applied where it now lives). **One real port bug,
found by the compiler:** upstream's new conversation cache declares a local `parked` that hid our chat cache's store of
the same name inside the request loop. Our store is renamed `chat_parked`.

**VRAM.** 0.1.28 now reserves the draft head (+86 MiB) inside the cache: 4,513 instead of 4,560 slots at our 800 MiB
reserve. `--vram-reserve-mib 713` gives exactly C\*7's 4,560 slots and 490 MiB free, so C\*8 keeps C\*7's memory
layout.

**Pinning (0.1.29 still caps it at 8 GiB with a helper GPU):** our fix keeps the whole arena registered on Linux.
Verified: the engine logs "cudaHostRegister PORTABLE ok" (not "limited to 8 GiB"), and every expert the prompt path
streams goes by DMA (32K: 89,692 of 89,692; 112K: 313,922 of 313,922), which is only possible from registered memory
(with the cap, Round 6: 15,120 of 88,032). The process's VmPin counter cannot show it: it reads 0 for C\*7 too, because
the NVIDIA driver's pins are not counted there.

**Measured on its own** (engine level, cold page cache, guarded; `results/r8/…`):

| check | result |
|---|---|
| greedy decode, exact flags, **binding fixed cache** (`--expert-cache 3500` = 4,551 experts), math / code, helper and one GPU | **bit-identical to C\*7** (ab1c7748 / 58cd4381 / one-GPU 9ad3650e), same window histograms, same ms per round |
| the same sampled (seed, T 1.0, top-p 0.95, top-k 20), all sampler variants | **the same tokens** in C\*7, the port's default split sampler, `STRATA_OLD_SAMPLER=1` and `STRATA_SAMPLER_ONE_BLOCK=1` |
| ms per verify round, sampled, math / code (2 runs each) | C\*7 34.31 / 22.36 → **split 32.06 / 19.80** (−2.4…−2.6 ms per round; old sampler = C\*7) |
| prompts 32K / 112K (cold, CLI) | 9.59–9.64 → 9.47–9.50 s (−1.3 %); 32.30 → 31.92–31.94 s (−1.1 %) |
| 1,024-token stream threshold, 1,100–4,000-token prompts, fixed cache | the same output at either threshold |

My mistake on the way: the first exact pairs looked different (first difference at tokens 345 / 89). The cause was my
method, not the update: in CLI runs the port sizes its draft-head reservation from the prompt length (85 or 86 MiB), so
its cache came out 1–2 slots bigger than C\*7's, and an explicit `--expert-cache N` larger than fits is capped by free
VRAM. With a binding explicit size the outputs are bit-identical. Every exact comparison this round uses
`--expert-cache 3500`.

**Served A/B, C\*7 vs the port, 4 alternating pairs** (fresh guarded server and cold page cache each; your settings;
`results/r8/ab-c7-r8.md`):

| | C\*7 (4 runs) | **v0.1.30 port (4 runs)** | change |
|---|---|---|---|
| decode, all 768+-token answers | 92.3–95.5 (93.7) tok/s | **105.2–106.1 (105.8)** | **+13 %**, no overlap |
| ms per verify round (≈ 2.0 tokens per round, acceptance 0.64–0.66 both) | 20.7–21.5 | 18.4–19.0 | −2.4 ms |
| long reasoning math / code (8K) | 104.3 / 86.7 tok/s | 116.6 / 98.9 | +12 % / +14 % |
| 32K / 64K / 120K prompt | 9.64–9.68 / 18.64–18.70 / 35.16–35.31 s | 9.51–9.54 / 18.38–18.42 / 34.75–34.78 s | −1.2…−1.4 % |
| 1K prompt | 0.96–0.98 s | 0.98–1.01 s | +3 % (below) |
| memory | 15,418 MiB, MemAvailable ≥ 27.3 GB, RSS 57.5 GB | the same | = |

**Short prompts (0.1.30's 1,024-token rule)**, served with warm-up, 2 fresh servers per arm, engine prompt time
(`results/r8/shortprompt-table.md`): 1,066 tokens 838 → 892 ms (+6 %, slower); 1,578: 1,011 → 909 ms (−10 %);
2,042: 1,208 → 957 ms (−21 %); 3K–5K unchanged; a 1,853-token tool result 1,147 → 1,051 ms (−8.5 %); short follow-ups
(60–145 tokens, read by verify windows) unchanged. The break-even on this PC is ~1.25K tokens (upstream measured 1,024
on an RTX 5070 with Q2_0). Output is the same either way, so the threshold is a free config choice (Phase A).

**Conversation cache: upstream's #189 vs ours** (same binary, KV streaming + helper; switch test + an 8-chat test;
3 runs each; `results/r8/conversation-cache-table.md`):

| | our chat cache | #189 |
|---|---|---|
| back to a parked chat | 0.36–0.75 s | 0.36–0.78 s |
| first request of the other chat: short / reasoning / 64K paste | **0.51–0.52 / 0.57–0.58 / 18.29–18.31 s** | 0.67–0.69 / 0.63–0.64 / 18.39–18.45 s |
| park 40K / 64K | 78 / 128 ms | 215 / 260 ms |
| 8 chats: 6 slots / 8 slots | LRU thrash / all kept | the same |
| engine peak RSS / lowest MemAvailable | **53.8–54.7 / 31.3–32.3 GB** | 57.3–58.4 / 27.4–28.6 GB |
| park → resume, resume + edit (static experts, 1,536 forced tokens) | **exact** | **exact** |

**Kept ours.** #189 snapshots the outgoing chat before every switch and every rewind (edit, regenerate), also for
tiny chats, 2–3× slower per park, and retains ~3.5 GB more RAM in this traffic — against your 20 GB MemAvailable floor
that matters. It does some things better (validation before restore, a RAM admission floor, keeping the pre-edit
branch). Written up for upstream: `pr-drafts/27-conversation-cache-vs-chat-cache.md`.

**Checks on the candidate** (C\*8 = v0.1.30 + `patches/r8/0001–0012`):

| check | result |
|---|---|
| accuracy: teacher-forced, 7 texts, one GPU and helper, binding fixed cache | **bit-identical to C\*7**: 1,536/1,536 NLL values equal on every text (`results/r8/tf-compare.txt`) |
| harder needle set (12 documents × 6 questions, 32K/64K/120K) | **72/72** (TTFT 9 / 18 / 35 s) |
| chat-cache round trip | **exact** |
| stop120k (Stop during a 120K read, next request, back to the parked chat) — upstream's fix alone | **7/7** (unfixed v0.1.27 failed "back to chat A") → 0013 dropped |
| headless-Chrome browser test (on a config copy) | **52/56**: the two known non-bugs (a 110-token chat is not parked by design; favicon 404) + 2 web checks blocked by SearXNG (both engines "too many requests": 0 results, so nothing to cite); all web mechanics pass; Stop during a 32K read → idle in 1.3 s, next request normal |
| clean build | `engine-cstar8/strata` sha256 `381892ab…`, tree `1bc2dce5` = the tested port (`work/r8/build-cstar8.sh`) |
| launcher fallback (4060 Ti short of memory) | pass |
| 2-hour soak (SOAK8, 8080) | **pass**: 351 requests, 0 errors, Stop pressed 137×; MemAvailable ≥ 25.0 GB, RSS 50.4–60.8 GB with no growth; fresh 32K probe 9.43–9.53 s throughout |
| promotion (20:21) | launchers default to C\*8; **rollback test pass** (stop 8080 → C\*7 answers → stop → C\*8 answers; different processes) |

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
- **Policy model** (7-draft arm, 3,317 windows; `work/r8/policy2.py`), with the engine's real draft-length rule (the
  floor gates draft 1 too). My first model assumed draft 1 is always proposed and overstated both results below;
  corrected:
  - A higher greedy floor is worth **at most +1–2 %**. The 37 screens agree to within 2–3 %; the best measured is +0.9 %.
  - Exact speculative sampling gives **+3.5 % vs today**, about +1.5–2.5 % over the best greedy setting.
  - Longer caps don't help.
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

#### A.6 Config screens
- **Draft length / floor** (37 decode screens, 8 baselines at 104.0–107.5 tok/s = ±1.6 % run to run;
  `results/r8/a6-spec-grid.md`): no setting beats today's `--spec 4 --spec-min-p 0.5` beyond noise.
  - Best: spec 4 / floor 0.7 at +0.9 %.
  - Floor 0.9: −5 to −7 %. Floor 0.3: −4.5 to −26 %. Every `--spec-split` arm: −9 to −26 %.
  - Exactness under the fixed-computation setting (`STRATA_IQ_MT_MIN=1`, fixed cache, fixed seed): the sampled text
    is identical at every draft length (4 settings, math and code). Draft length changes speed only.
- **`--mtp-window 16384`:** prompts −1.1 to −3.4 % (the draft layer's pass is lighter), with a long-context decode risk.
  Worth ≈ 0.1–0.2 % of your time. Not promising, so 8192 wasn't screened.
- **Chat-cache slots** (16 conversations of 4K–30K tokens, 212K tokens in all; same 16 GiB cap; `results/r8/a6-slots.md`):
  | slots | back to a chat, 1st pass: median TTFT, from cache | 2nd pass | peak RSS / lowest MemAvailable |
  |---|---|---|---|
  | 6 | 3.63 s, 0/16 | 2.94 s, 2/16 | 52.7 / 33.2 GB |
  | 12 | 3.63 s, 0/16 | 1.18 s, 8/16 | 55.3 / 30.6 GB |
  | 16 | **0.22–0.23 s, 16/16** | 0.22 s, 16/16 | 59.1 / 26.8 GB |
  Adopted at first, then **reverted in Phase C**. With many big pasted chats (the needle test), 16 slots let the cache
  fill its whole 16 GiB, and MemAvailable reached the 20 GB guard floor; with 6 slots, C\*8 bottomed at 23.7 GB.
  Your call; see "Open decisions".
- **Stream-all threshold 1,280 vs 1,024** (`results/r8/a6-stream-threshold.md`): 1,066-token prompts −2.5 %, a
  1,253-token tool append +2.8 %, everything else equal. No change.

### Decision point (end of Phase A)

Ranked by measured recoverable time × confidence ÷ effort; see the table in results/round8-summary.md and NOTES.md.
Two of my own Phase A estimates were wrong and are corrected here:
- **Policy model.** My first model assumed draft 1 is always proposed. The engine applies `--spec-min-p` to draft 1
  too (`T = 1; while T < S && dprob[T-1] >= floor: ++T`). With the real rule, a higher draft floor is worth ≤ +1–2 %
  (not +4–5.5 %), and exact speculative sampling +3.5 % vs today (not +9–12 %). The corrected model tracks the 37
  decode screens to within 2–3 %.
- **Group copies.** The A.2 profile put the per-expert MMQ group copy at 10.4 % of prompt GPU time. Removing it saved
  1 %, because the copy had left the weights hot in L2 for the matrix kernels.

### Phase B — build tracks

**Track 1: upstream PR245** (fork Eddoursul `cf307ea` + `8208f3f`, transplanted behind `STRATA_EXPERTS_OLD=1`;
`patches/r8-B/0013`)
- Real-expert parity is bitwise identical on sm_120 and sm_89 (7 format pairs × windows 1–8; 2,520 rows each).
- Engine greedy output is identical with a fixed cache.
- Exact mode: −6.0 % (math) / −8.0 % (code) per round.
- **Served A/B (2 alternating pairs, your settings): +4.5 % decode** (109.8 / 111.6 vs 107.1 / 104.6 tok/s), ms per
  round −4.2 %; prompts unchanged.

**Track 2: the prompt's MMQ reads streamed experts in place** (`patches/r8-B/0014`; pr-drafts/31)
- **Mechanism:** per-expert byte offsets in MMQ, stored below the weight address so the weight pointer stays derived
  from the kernel's restrict parameter (mmq.cuh edited in the build tree, the pinned checkout untouched). Blobs are
  DMA'd to the end of 4 KiB-padded ring slots, and slots are held until their group's products are queued. A group
  whose slots span half the ring or more falls back to the gather; groups never change.
- **Exactness:** greedy output is identical at 2K, 32K and 112K and on repeated-token 4K / 9K prompts; forced fallback
  mixes (`STRATA_PREFILL_PTR_SPAN`) are identical too.
- **Speed vs C\*8 (untimed, 2 alternating rounds): 32K 9.48 → 9.21 s (−3.0 %), 112K 31.94 → 30.94 s (−3.1 %).**
  The profile's 10.4 % "copy" share was not all recoverable: the copy had left the weights hot in L2.
- **A regression caught in Phase C:** the first version made prompts 6 % slower. A table of absolute pointers made
  1,152 read-only global loads generic (SASS), in every launch, and my own A/B had only compared on vs off inside the
  patched binary. Fixed and re-measured against C\*8.

**Not built**, with the measured or modeled ceiling: exact speculative sampling (+3.5 % modeled), PDL (≈ 1.8 % of a
window, microbenchmark), dropping the commit → draft-1 sync (≈ 0.5–0.7 %), the draft layer's prompt pass on a second
stream (≤ 6.7 % of a 32K prompt, 2 % at 112K), HC/dense GEMVs toward 80 % of bandwidth (low confidence), and MMQ tile
shapes (ceiling unknown).

**Dropped with measurements:**
- thread-affinity fix: no effect;
- GDN chunked prefill (FlashQLA): BF16 only and not faster;
- coupled drafting: −1.9 % tokens per window;
- `--mtp-window 16384`: prompts −1–3 %, long-context decode risk;
- `--spec-split`: −10 to −26 %;
- every `--spec` / `--spec-min-p` combination screened: none beat 4 / 0.5.
