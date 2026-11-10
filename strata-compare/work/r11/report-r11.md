## Round 11 — v0.1.39 adopted, Phase 0 fixes, the CPU path, the GPU critical path, helper balance, prompt chunks / 262K, precision, Signal → C\*13 (2026-10-04 01:30 → 2026-10-05)

Chronological notes: `NOTES.md` ("Round 11"). Phone summary: `results/round11-summary.md`. Build records: `results/r11/builds.md`. Patches: `patches/r11c39/` (C\*13, 37 patches on v0.1.39). PR drafts 41–46 (`pr-drafts/`).

Base: **v0.1.38 + C\*12.1's series (C\*12.1)** from the start; **v0.1.39** was released at 07:34 on 10-04, ported and measured on its own at the end of Phase A (computes exactly what C\*12.1 computes; never slower), and became the base for Phases B–G. All changes are lossless: exact (a), rounding-level (b) with gates, or distribution-preserving (c); Phase E (higher precision) is the one exception.

### Start of round
- **48-hour monitor stopped** after 3 h 22 min: 14 samples, one server segment (C\*12.1), 11 of your requests (one 30,158-token answer at 117 tok/s; an LDR-shaped chat growing to 18K tokens at 110–133 tok/s); MemAvailable 36.1 → 33.4 GiB after them; 5080 480–504 MiB free.
- **Release watcher restarted** (every 40 min). New for this round: the general holdout (`work/r11/holdout11.py`, sha256 frozen) and the LDR-shaped holdout (`prompts/r11/ldr-holdout11.json`, 6 new research topics) were written before Phase A and first run in Phase G.

### Phase 0 — profile, fixes, #567
**Profile of C\*12.1 as served (ms per verify window, quiet desktop):**

| part | LDR | math | code |
|---|---|---|---|
| window | 18.54 | 16.86 | 15.58 |
| GPU: wait for the CPU | 4.08 | 2.94 | 2.84 |
| GPU: hyper-connection reads / GDN / QSA / VRAM experts | 3.03 / 2.65 / 1.95 / 2.39 | 3.02 / 2.63 / 1.71 / 2.52 | 2.76 / 2.50 / 1.61 / 2.08 |
| CPU pool: gate/up / middle quantization / down (Q2_0 + IQ4_NL) | 3.24 / 0.04 / 2.12 (0.28 + 1.84) | 2.52 / 0.03 / 1.66 | 2.22 / 0.03 / 1.44 |
| host: input quantization / plan + dispatch / helper launch / wait for the helper | 0.29 / 0.15 / 0.45 / 0.63 | 0.28 / 0.14 / 0.42 / 0.68 | 0.22 / 0.12 / 0.41 / 0.82 |
| draft round | 1.80 | 1.49 | 1.29 |

The CPU pool is memory-bound (~74 GB/s over the gate/up rows). **The desktop on the 4060 Ti:** with the screen redrawing (22–34 % of its graphics engine — it followed Chrome's GPU process), the helper's work waits: LDR decode ~103 tok/s vs ~124 quiet, host wait for the helper 2.9 vs 0.6 ms. Every later measurement recorded the desktop load (0.0–0.5 % in all decision runs). Plugging the monitor into the iGPU would remove this cost — your call.

**Fixes transplanted (each behind an old/new switch, each with a test that reproduces the bug):**

| PR | bug reproduced on C\*12.1 / v0.1.39 | after |
|---|---|---|
| #550 | residency-table uploads read stale by GPU kernels: 5080 0.55 % (idle) / 1.55 % (busy) of uploads, **4060 Ti 99.95 %** | 0 / 0 / 0 / 0 (upload 4.5 → 9.1 µs on the 5080, only on swaps) |
| #652 | follow-ups re-read the previous answer: 4/14 + 1/5 (C\*12.1), 2/14 + 1/5 (0.1.39) | 14/14 + 5/5 resumed |
| #454 | `stop` / `stop_sequences` ignored: every case with a stop string leaked | all 9 cases pass, both APIs, streamed or not |
| #700 | prose mentioning `<tool_call>` before a real call → HTTP 400 | parsed, prose kept |
| #567 | the prompt re-encoded from token 0 each request | **0 id differences in 28.5 M tokens**; TTFT of cached turns 31K 0.216 → 0.150 s, 98K 0.372 → 0.146 s |

The bundle costs nothing (v0.1.38: LDR decode +0.1 %, decode +0.1 %; v0.1.39: −0.7 / −0.8 %, within noise). Correction made during the round: the two "Anthropic stop" cases first scored as failures were the test's fixed token threshold not allowing for the default thinking — the engine stops early on both APIs.

### Phase 0.1 — v0.1.39, ported and measured on its own
A large release (381 files): GPU decode work (zero-doorbell graph when all experts are resident, sub-warp expert packing, per-T GR v3 kernels, **the shared expert on its own stream by default**), #578 as `--remote-expert-opt`, #650 (huge pages), **#583 (a new prompt-chunk rule)**, #603, #547's byte count, batch slots, a gfx906 build. None of our Phase 0 fixes. Port: C\*12.1's 19 patches minus two (GR v5 never ran under `STRATA_GR_V3=1`; our shared-expert branch is upstream's default now), conflicts merged by hand (the request loop, our side-mixer branches vs the batch-slot rows, web search vs the new config page, our helper-aware tier (STRATA_ADAPT_HELPER) beside #578's rule).

| check | result |
|---|---|
| exact7 vs C\*12.1 | **7/7 identical** |
| teacher-forced NLL, 18 texts | 17 bit-identical; single-GPU corpus −0.0001 ± 0.0002 from token 1,169 (deterministic) |
| server tests / needles / round trips / Stop at 120K | 200 OK / 36/36 / identical / 7/7 |
| LDR / decode / full screen decode vs C\*12.1 | **+0.8 % / +2.1 % / +3.0 %**; ms per round −2.8 / −0.8 / +0.3 %; TTFT ±0.5 % |
| #583's chunk rule vs the old list | neutral here (same 16,384 chunk; borrows 322 fewer slots) |

**Adopted as the base.** Found on the way: the "repeat 3 times" gate varied on C\*12.1 too — the lookup drafter picks windows from measured round times and the sampled text depends (rounding-level) on the window grouping; pinned windows repeat 3/3 on both builds, so the gate now pins them.

### Phase A — the CPU path
| item | class | result | verdict |
|---|---|---|---|
| **A.2 — the doorbell writes the pool's Q8_K rows** (fork d9ce223's idea, re-implemented bit for bit with ggml) | (a) | parity 0/5,120; exact7 7/7; LDR decode +1.4 % (round −1.0 %), decode +1.8 % (round −1.4 %); fixed computation −1.34 % (v0.1.38) / **−1.80 %** (v0.1.39) | **kept** |
| IQ_GATHER=1 | (a) | LDR +1.3 % but round +1.3 % (tokens per round); fixed pair +0.23 % | dropped |
| IQ_PREFETCH 0 / 1024 / 4096 vs 2048 | (a) | decode −0.0 / −0.3 / −0.2 % | 2048 stays |
| #650 huge pages | (a) | fixed pair +0.01 % (identical outputs) | no effect (0.1.39's default anyway) |
| helper-late launch (my addition from the profile) | (a) | served round −0.3 / −0.4 % (0.1.38), −0.7 / −0.2 % (0.1.39); fixed pair −1.32 % | dropped (noise served) |
| A.3 Q2_0 down rows / A.4 GPU hit plan / A.5 #500 | – | profile: 0.28 ms / not exposed / 0.04 ms | not run |

Tie-breaker lesson: a "fixed computation" pair on the served flags is not fixed (the cache size follows free VRAM, the tier swaps on timing); with exact7's pins it still drifted after a 16K prompt (drafter state after long prompts) — the pinned short-prompt form never drifted and is now the default.

### Phase B — the GPU critical path (on v0.1.39 + the Phase 0 fixes)
| item | class | gates | served result | verdict |
|---|---|---|---|---|
| **B.1 — fork's HC read** (9ef275e + 803e165 + 8290279 + 3d133ba) | (b) | micro −7.7 / −20 / −19 / −32 % at 1–4 tokens; **first port gave NaN** (0.1.39's batched PLE writes into the read's scratch) → own scratch; then needles 12 × 6/6, TF FP16-distance 0.0419 → 0.0439 / 0.0366 → 0.0322, repeat 3/3 | LDR **+2.3 %** (round −1.2 %), decode **+2.7 %** (−1.9 %) | **kept** |
| **B.2 — split decode attention** (fd23d91) | (b) | needles 12 × 6/6; FP16-distance 0.0419 → 0.0368 / 0.0366 → 0.0374; repeat 3/3 | LDR **+4.3 %** (round −3.7 %); full +2.3 % (−5.9 %); decode after 32K / 64K / 120K **+6.5 / ±0 / +3.5 %** | **kept** |
| **B.3 — interleaved matvec** (738e166 + b67a291's matvec) | (a) | parity bitwise (55 cases × 1–8 columns); the fork's 3090 table replaced by a 5080 table; exact7 7/7 | LDR **+1.0 %** (round −2.5 %), decode **+1.6 %** (−2.3 %) | **kept** |
| B.4 — draft round (22b46b6 front once; d3d48b1's kernels) | (a) as claimed | front part exact 7/7; my port of the kernels part changed drafts (6/7) | LDR +0.4 %, decode +0.5 % | dropped |
| 235784c (one-token window commits itself) | (a) | sits on fork refactors we do not have; ~0.5 % by the fork's numbers | – | not ported |

**Phase B combined vs the same binary all off:** LDR **+9.1 %**, decode screen **+10.6 %** (math +16.2 %), full **+8.2 %**; every round 8–10 % shorter; TTFT unchanged; TF FP16-distance 0.0397 (helper) / 0.0374 (one GPU); needles 24 of 25 runs 6/6 (one sampled 5/6 at T 1.0; re-run 12/12).

### Phase C — helper balance (on the Phase B result)
| item | result | verdict |
|---|---|---|
| C.1 helper slots 1500 / 2400 / 3300 / 3500 (3600 refused: the engine keeps ≥ 512 MiB free) | decode −7.3 / −3.9 / – / +0.8 % vs 3300; helper share 9 / 14 / 18 / 19 %; profile at 3300: pool 5.74 ms, helper wait 0.71, waitCPU 3.64 | **3300 stays** |
| C.2 per-layer helper cap (`STRATA_HELPER_CAP` 2,0.75 / 4,0.75 / 0,1) | −6.6 / −5.9 / −12.5 % | dropped (lengthens the CPU pool) |
| C.3 upstream `--remote-expert-opt` (#578), part by part | **all −17.9 %**, move −19.0 %, avoid −2.8 %, reduce −2.8 % | dropped — **and keep it out of setup (`--no-remote-expert-opt`)** |
| C.4 upstream `--peer-device 1` (default prompt rows / 0) | −14.7 / −14.3 % decode; TTFT +3.6 … +6.8 % | dropped |

### Phase D — prompt chunks and 262K
| item | result | verdict |
|---|---|---|
| #547 | its byte count is in 0.1.39; the rest only matters without an expert source | nothing to port |
| #693 equal chunks (hand port) | fresh prompts: 17,800 tokens **−12.4 %** TTFT, 24,000 −2.4 %, others ±0.6 %; needles 12/12, Stop OK — **but it removes the 16,384 mid-prompt checkpoint: a research follow-up's TTFT 1.67 → 5.24 s** (found in Phase G) | **dropped** (PR draft 42) |
| `--prefill auto:32768` | picks 22,272 (borrows 4,086 slots): 33.5K −7.6 %; on C\*13 the full screen: 64K / 120K −1.2 / −1.1 %, round +1.2 % | not adopted |
| **262K context** (`configs/Cstar13-262k.json`) | #603 in 0.1.39; 4,441 slots (−118), host K/V 3.09 GiB; TTFT 1K–120K ±0.8 %; **200K / 250K prompts 50.8 / 65.4 s** (~3,900 tok/s), decode after 104–118; **needles 8/8 at 200K/250K**; three 190K chats parked at 3.44 GiB each, **restored in 124 ms (TTFT 1.22 s vs 47.7 s)** | works; optional config |

One reliability finding in D.1: with the chat cache full, **CUDA's kernel watchdog killed an engine kernel once** (both GPUs run with the X server's watchdog on); 0.1.39's server restarted the engine by itself (one empty reply, ~12 s, chat cache lost). PR draft 45.

### Phase E — higher precision (each alone; accuracy first)
On the short texts every option stays within ±0.0025 nats of the base (≤ 1.2 se); on long texts the 7-text means move ±0.02 with se 0.02–0.05 (block selections), with two leaning worse: **BF16 embedding +0.083 / +0.103**, **FP8 n-gram table +0.036 / +0.059** (both from the original Qwen checkpoints, while this IQ3_S is the GSQ-RCO variant). Rotated KV, RoPE table, prompt BF16x2: no measurable change (BF16x2 also +10 % TTFT at 120K). Needles 12/12 for all (FP8 11/12, one sampled miss); rotated-KV round trip identical. **None adopted** (your rule: only if accuracy clearly improves); each stays behind its switch.

### Phase F — Signal AP-Q4_K_XL (≤ 3 h, no tuning)
A Q6_K embedding dequantizer (bit-exact vs ggml: 0 of 5,120,000) — **the file now loads** (Round 10 stopped there; PR draft 40 corrected: the embedding is Q6_K, not Q8_0). 56 GiB RAM budget, 32K, the 5080 alone vs IQ3_S as you run it:

| | acceptance | tokens / round | output tokens / answer (all / finished) | decode tok/s | time per finished answer | TTFT 8K / 32K |
|---|---|---|---|---|---|---|
| Signal AP-Q4_K_XL | 0.691 | 2.03 | 2,500 / 223 | **70.5** | 3.9 s | 3.25 / 10.25 s |
| IQ3_S (Phase B build) | 0.687 | 2.04 | 2,529 / 264 | **130.9** | 2.5 s | 2.13 / 7.45 s |

### Phase G — C\*13
**C\*13 = v0.1.39 + `patches/r11c39`** (37 patches: C\*12.1's series ported, the five fixes, A.2, B.1, B.2, B.3), built from a clean clone (engine-cstar13; tree 19b7bffe). Flags = C\*12.1's + `STRATA_ROUTER_Q8K` / `STRATA_GR_FORK` / `STRATA_QSA_SPLIT_ATTN` / `STRATA_MMVQ_IL`.

| gate | result |
|---|---|
| upstream server tests / tokenizer tests | 212 OK (9 skipped) / 11 OK (after fixing #567's test calls to the renamed method) |
| #567 ids | 0 differences in 28,545,945 tokens |
| exact7 vs the Phase B build | 7/7 |
| needles / Stop at 120K / repeat / round trips | 12 × 6/6 / 7/7 / 3/3 / identical |
| #652 / stops / tool tag | 14/14 + 5/5 resumed / all pass / 5/6 (the sixth: two valid tool calls where the test wants one) |
| browser test (a copy of the config, no web search this time) | 41 / 2 — Round 10's two known non-bugs |

**Speed — C\*13 vs C\*12.1 (A B B A, fresh servers, your settings):**

| screen | decode | ms per round | TTFT | total time |
|---|---|---|---|---|
| **fresh LDR-shaped holdout** (first use) | **123.2 → 136.1 tok/s (+10.5 %)**; every request kind +3.4 … +12.4 % | −9.8 % | −0.3 … −0.7 % | **−9.0 %** |
| **fresh general holdout** (first use) | **120.2 → 131.5 (+9.4 %)** | – | document 7.22 → 7.20 s | **−7.9 %** |
| LDR screen | 124.2 → 139.0 (+11.9 %) | −10.4 % | −0.6 … −2.7 % | −9.7 % |
| decode screen | 122.7 → 138.2 (+12.6 %); math +13.0 %, code +13.0 % | −9.2 % | 32K −0.4 % | −8.3 % |
| full screen | 125.5 → 138.3 (+10.2 %) | −10.8 % | 32K / 64K / 120K −0.4 / −0.2 / −0.1 % | −6.7 % |

**Soak, rollback, promotion:**
- **2-hour soak on 8080 (your traffic shape, through switch-model.sh with configs/Cstar13.json): 440 requests, 0 errors**,
  Stop 159×; back to a kept big chat (32K–126K tokens) median **0.74 s** (n = 105; C\*12.1's soak 0.77 s), max 1.45 s;
  re-read after an LRU drop median 5.08 s (n = 10); new 32K / 64K / 120K pastes max 7.79 / 15.56 / 29.89 s (C\*12.1's soak:
  7.85 / 15.63 / 29.94); **MemAvailable min 21.4 GB** (floor 20); engine RSS 50.5–64.6 GB, no growth per 30-minute block;
  32K probe decode 123.7–143.2 tok/s, no trend; no error lines in the engine log; 34 LRU drops (the 12 GiB chat cache
  enforced). (The soak script's "parked total peak 92,201 MiB" sums park lines over the whole shared log without
  subtracting restores — not a real figure; RSS bounds what was parked.)
- **Soaked vs fresh decode screen: 138.2 → 137.5 tok/s (−0.5 %), ms per round −2.0 %** — no slowdown after 2 h.
- **Promoted at 10:36 on 10-05** (`work/r11/promote-c13.sh`): the launchers default to `configs/Cstar13.json` (the old
  ones kept as `work/r11/*.before-c13-promotion`); **real rollback test passed** (8080 → C\*12.1, engine 20266ca9…, both
  GPUs, answered → back to the default C\*13, engine 0839b20b…, both GPUs, answered; 498 MiB free on the 5080).
  Rollback: stop 8080, then `STRATA_CONFIG=configs/Cstar121.json ./switch-model.sh strata`. Optional 262K:
  `STRATA_CONFIG=configs/Cstar13-262k.json ./switch-model.sh strata`.
- **Release check at every phase boundary:** v0.1.38 = newest until 07:34 on 10-04, then v0.1.39 (adopted); no newer
  release through the end of the round (40 tags, 10:14 on 10-05).
- A fresh **48-hour passive monitor** runs (logs/r11/uptime-c13/); the queue runner, the release watcher and the
  desktop-load logger are stopped. **Round 11 ends here.**

**For you (no change made, your call):** (1) keep `--remote-expert-opt` out of any config made with upstream's setup
(`--no-remote-expert-opt`) — it costs ~18 % here; (2) the desktop runs on the 4060 Ti: whenever the screen redraws, the
helper's work waits (LDR decode ~103 vs ~124 tok/s in Phase 0) — the monitor on the motherboard's output would remove that
and the kernel watchdog from the compute GPUs.

### Ranked backlog (lossless only; expected effect on this machine)
| # | item | expected | cost / risk | first step |
|---|---|---|---|---|
| 1 | **The CPU pool** (5.7 ms per LDR window; the GPU waits 3.6 ms for it) — e.g. a faster IQ4_NL down-row path (1.84 ms), fewer bytes per expert row | large if reachable | high | per-format AVX-512 kernel bench at 1 token |
| 2 | **The drafter** (1.1–1.4 ms per round): profile the round graph on 0.1.39 before porting more fork work; find which d3d48b1 part changed drafts | ~1–2 % | medium | nsys of the round graph |
| 3 | #693 done right: equal chunks inside each 16,384 stretch (keeps the checkpoint) | up to −12 % TTFT on fresh 17–25K prompts | low | PR draft 42's suggestion |
| 4 | Why the long-prompt runs drift (drafter state after a long prompt?) — matters only for test repeatability | 0 % | low | hash the drafter's KV after the prompt |
| 5 | A disk tier for dropped chats (design note: results/r11/design-chat-disk-tier.md) | ~30 s → < 1 s for a returning 100K chat | medium; privacy — your decision | – |
| 6 | Bounded device-side spins (the watchdog event, PR draft 45) | reliability | medium | count spin lengths under load |
| 7 | 235784c (a one-token window commits itself) | ~0.5 % | medium (fork refactors) | – |
| 8 | #646 kernel-only bench vs ours on both cards (not reached this round) | – | low | – |
