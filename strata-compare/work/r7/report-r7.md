## Round 7 — C\*6 soak and promotion, Strata v0.1.25–v0.1.27 → C\*7, the staging oracle, two conversations at once (2026-09-29 19:55 → 2026-09-30 ~04:30)

**Status: C\*7 is promoted and running on 127.0.0.1:8080** (the launchers' default; engine `engine-cstar7/strata`
sha256 `886b6ab2…`, `configs/Cstar7.json`). The 48-hour passive uptime monitor is watching it.

**What happened, in order:**
1. **C\*6 passed its full 2-hour soak** (333 requests, 0 errors) and was promoted at 22:22. The rollback test passed.
2. **Strata v0.1.25, v0.1.26 and v0.1.27** (v0.1.27 appeared at the first tag check) were reviewed. C\*6's 12 patches
   were ported onto v0.1.27 and the update was measured on its own:
   * prompts **3.6–3.7 % faster** (120K: 36.6 → 35.2 s), from 0.1.25's fused hyper-connection norms;
   * decode **bit-identical**;
   * accuracy **bit-identical**, needles 72/72, the chat-cache round trip exact.
3. The browser test then found **a bug in upstream 0.1.26+**: after a Stop during a long prompt read, the next request
   crashed the engine. I fixed it (patch 0013) and verified the fix. The fixed build passed the 2-hour soak (335
   requests, 0 errors) and was **promoted as C\*7** at 02:40.
4. **Item 1 (engine oracle for next-layer expert staging):** the ~15 % ceiling exists only with the static expert set.
   On your served configuration a perfect predictor saves **0–3 %** by staging, or **8–10 %** by CPU-cache warming,
   and a ~60 %-recall predictor keeps **~2–3 %** (warming) or loses (staging). **Do not build.**
5. **Item 4 (two conversations at once):** **useful only for overlapping tool waits.** That already works through the
   server's queue (+5 % to +46 % total throughput for two web-search agents, no engine change). Engine-level
   concurrency has an ideal ceiling of +28 % total throughput with each conversation ~36 % slower; not worth
   prototyping for single-user chat.

| | C\*6 (round 6) | **C\*7 (now on 8080)** |
|---|---|---|
| base | Strata v0.1.24 + 12 patches | **v0.1.27 + 13 patches** (12 ported + the Stop fix) |
| 32K / 64K / 120K prompt (uncached, served, 4 pairs) | 10.00–10.02 / 19.36–19.43 / 36.55–36.68 s | **9.64–9.66 / 18.65–18.71 / 35.19–35.33 s** |
| decode | 94.1 tok/s (all long requests, T 1.0) | 93.7 tok/s (= ; greedy output bit-identical) |
| accuracy (teacher-forced, 7 texts, one GPU and helper) | – | **bit-identical to C\*6** |
| needles / round trip / browser / fallback | 72/72 · exact · 54/56 · pass | **72/72 · exact · 54/56 · pass** |
| Stop during a long prompt read, then continue | works | works (upstream 0.1.26+ does not; fixed in 0013) |
| 2-hour soak | 333 requests, 0 errors | **335 requests, 0 errors** |

**My mistakes this round (all caught, none affect a result):**
* My soak waiter matched its own command line and sat idle for ~23 minutes.
* The first C\*7 round trip used a config without the static expert set the test needs. It was re-run correctly.
* My own quick reproduction script for the Stop bug did not trigger it (its prompts never took the batched path).
  The evidence is the browser test and round 5's stop120k, which did.
* The first oracle design (greedy decode, the GPU waiting for every staged copy) could not measure staging. It was
  redesigned: fixed text, landed copies only.
* I found a Round 6 mistake: its browser test had set C\*6's shared chat temperature to 0.6. I restored your 1.0
  before any promotion.

**Tag watcher:** read at every step (`logs/r7/tagwatch-reads.log`); v0.1.27 at 19:57, nothing newer since.

### 1. Round 6 wrap-up: the 2-hour soak of C\*6 and the promotion

**Soak** (`work/r6/soak.sh 120`, label SOAK6-0929T1957, 19:57–21:57, C\*6 on 8080 through `switch-model.sh` with the
helper GPU, SearXNG, warm-up; round 5's big-chat traffic at your settings; memory guard and 1 s monitor attached):

| gate item | result |
|---|---|
| requests / errors | **333 requests, 0 errors** (81 returns to a big chat, 43 new chats with a pasted 32K/64K/120K document, 36 web-search chats + 20 web follow-ups, 40 follow-ups, 34 short chats, 29 Stop tests, 21 long-reasoning, 17 regenerates, 12 probes); Stop pressed 137 times |
| engine | no error, stall or watchdog line in this engine's log (only the six "upload no error" start-up lines) |
| server | 70 `fetch_page` refusals (a page outside the allow-list, 0.0 s each), as in rounds 5–6; nothing else |
| memory floors (guard, 0.2 s samples) | 0 samples under the floors; MemAvailable min **25.9 GiB**, 5080 min **476 MiB** free, 4060 Ti min 1,035 MiB free, swap 0 |
| leaks | engine RSS 50.4–60.5 GB, no growth (last 30 min max 58.8 GB) |
| chat cache | this engine's parked total peaked at **10,235 of 16,384 MiB**, never over budget (the summary script's "61,693 MiB" adds up the shared log of every C\*6 server since round 6 and is wrong; recomputed on this engine's part) |
| responsiveness | back to a parked big chat: median 0.83 s (max 4.1 s); to one the cache had dropped: median 10.9 s (read again); fresh 32K probe 9.95–10.03 s from start to end |

**Verdict: pass.** With the soak, no required check of round 6's gate is missing (A/B, accuracy, needles, quality,
web replay, chat-cache round trip, sampler, Stop/overflow/concurrency/idle CPU, launcher fallback, browser test; the
VRAM-grab test cannot run within your 300 MiB floor, as recorded in round 6).

**Promotion (22:22):** `run-strata.sh` and `switch-model.sh` now default to `configs/Cstar6.json` (round 6's prepared
`work/r6/*.new`; the old copies are in `work/r7/*.before-c6-promotion`). **Rollback test: pass** — 8080 went to C\*5
(engine `3ee92c9a…`, answered "17×3 = 51" in 18 s) and back to the default C\*6 (engine `a56a444b…`, both GPUs, "51",
19 s).

**Two things I fixed on the way:**
* **Round 6's rollback test would not have switched anything.** `switch-model.sh strata` keeps whatever Strata is
  running and does not compare configs, so `STRATA_CONFIG=configs/Cstar5.json ./switch-model.sh strata` with C\*6
  running just reports "already serving". The round-7 copy (`work/r7/rollback_test.sh`) stops 8080 before each switch.
  Keep this in mind for manual rollbacks too: **stop first** (`STRATA_PORT=8080 ./run-strata.sh stop`).
* **Round 6's browser test had changed your chat settings for C\*6.** It starts from a fresh browser profile (the
  page's default temperature 0.6) and clicks Apply with "use for other apps too" on, which wrote 0.6 into
  `configs/Cstar6.shared-settings.json` (15:43:43). Every round-6 client sent its own temperature, so no round-6 number
  changed, but a promoted C\*6 would have served other apps at 0.6. I restored your file (temperature 1.0, top_p 0.95,
  top_k 20, effort high) before the promotion; the promoted server announces "other apps use the Chat settings:
  temperature=1.0". Browser tests now run on a copy of the config (`configs/BR7.json`).

### 2. Item 0 — Strata v0.1.25, v0.1.26, v0.1.27: review, port, measurement on its own, C\*7

v0.1.24 → v0.1.27 is 35 commits (72 files, +6,877 / −369 lines). The tag watcher found **v0.1.27** (22:58 CEST, 15:58
here) at its first check of this round, so it is included. What matters for this PC and config:

| release | change | on our config (IQ3_S, KV streaming `--kv-resident 32768`, helper GPU, Linux, RTX 5080) |
|---|---|---|
| 0.1.25 | prompt path: the per-layer expert **grouping tables in mapped pinned memory** instead of `cudaMemcpyAsync` behind the expert stream (+3.9 % at 32K, +4.5 % at 128K upstream; bit-identical; `STRATA_GROUP_COPY=1` = old) | **applies** |
| 0.1.25 | prompt path: **fused hyper-connection kernels** F-1 (the read without its FP32 copy) and F-2 (a half's write fused with the next half's norm), bit-identical, +4.0 % / +3.3 % upstream; `STRATA_GR_UNFUSED=1` = old | **applies** |
| 0.1.25 | `--kv k8v4` (INT8 K + Q4_0 V) | skipped as you asked (refused with `--kv-resident`) |
| 0.1.25 | AMD HIP backend (gfx1100), Turing (RTX 20) port, hipBLASLt tables | not our hardware; the Turing port touches our v5 kernel's file (below) |
| 0.1.26 | **E-9: the draft layer's prompt pass in batches** (0.9 → 0.07 s of a 32K prompt upstream; `STRATA_MTP_BATCH=0` = old) | **skipped on our config** — confirmed in the code (below) |
| 0.1.26 | low-RAM mode (`--mmap-experts` with native packs) | skipped as you asked |
| 0.1.26 | request-sized prompt chunks (`request_chunk`, lend checks) | applies (small prompts; no effect on ≥ 8K chunks) |
| 0.1.27 | **draft vocabulary with all Chinese/Japanese/Korean tokens** (40,525 → 106,299 ids; upstream: CJK answers +15–38 % decode, English −1–2 %) | installed only by `setup.py` (which we do not run): measured separately |
| 0.1.27 | server: only template-written image markers are images (#150); a config's `env` reaches the engine | applies (harmless for us) |
| 0.1.27 | PLE reader error paths (cancel queued reads on a failed read) | applies (robustness only) |

**Porting the promoted build's 12 patches** (branch `r7-port`, `patches/r7/`): 11 applied unchanged. Patch 0009 (our
"GR v5" multi-token hyper-connection read, decode) conflicted with upstream's Turing change in the same function
(`fused_gr_read_multi`: upstream now cuts a window into slices when a card's shared-memory opt-in is too small). Merged:
our v5 path stays the default and falls back to upstream's chunked kernel on a card that cannot hold the window (our
cards: capacity 9 tokens ≥ 8); `STRATA_GR_OLD=1` still selects upstream's kernels.

**"Fused hyper-connection kernels" vs our v5 kernels: they do not overlap in code.** Upstream's F-1/F-2 are in the
*prompt* path (`src/prefill/`); our v5 is the *decode* verify window's read (`src/kernels/cuda/fused_gr.cu`). The decode
path already had F-2's idea (the previous half's write is applied inside the next read). So "combine" = keep both; each
is measured on its own path with its switch (results below).

**E-9 is skipped with KV streaming — confirmed in the code.** `Prefill::draft_kv` returns false (→ the old per-token
`MtpDrafter::prefill`) when the drafter's K/V state is not fully resident (`st.kv_mode != 0`); with `--kv-resident` the
drafter keeps its K/V as a ring over a host copy (`kv_mode` 2, `mtp.cpp`), which is also what the chat cache parks.
So on our config every prompt, at any length, takes the old pass. Its measured share of prompt time is below (the
ceiling for extending E-9 to the ring: backlog, not built).

**Measured on its own (engine level, `strata generate --stats`, same flags as C\*6, cold page cache, guarded;
`results/r7/item0-engine.txt`).** C\*6 = engine-cstar6; R7c = v0.1.27 + the same 12 patches (engine-r7c).

| check | C\*6 | R7c (v0.1.27 port) |
|---|---|---|
| greedy decode, exact (`--adapt-swaps 0 --suffix-draft 0`), math / code, 1,024 tokens | output `8b1157e8` / `0db2777b` | **identical outputs**, same rounds and window sizes |
| ms per verify round, math (2 runs) / code (2 runs) | 32.36, 31.83 / 24.37, 24.31 | 31.88, 31.78 / 24.30, 24.43 (=) |
| 32K prompt, cold, first start (2 runs) | 9.95, 9.93 s | **9.66, 9.61 s (−3.0 %)** |
| 112K prompt (2 runs) | 33.55, 33.61 s | **32.38, 32.37 s (−3.5 %)** |

Where the prompt gain comes from (upstream's own A/B switches, same binary):

| R7c with … | 32K prompt | reading |
|---|---|---|
| (default) | 9.66, 9.61 s | |
| `STRATA_GR_UNFUSED=1` (0.1.25's fused norms off) | 9.95, 9.95 s | = C\*6: **the fused hyper-connection norms are the whole gain** |
| `STRATA_GROUP_COPY=1` (grouping tables copied again) | 9.62, 9.61 s | no effect on this config |
| `STRATA_MTP_BATCH=0` (0.1.26's batched draft pass off) | 9.66, 9.62 s (112K: 32.38 s) | = default: **the batched pass is not used with KV streaming (runtime confirmation)** |

**The old draft-layer prompt pass (the ceiling for extending 0.1.26's batching to KV streaming):** 694 ms at 32K and
697 ms at 112K (it only covers the drafter's window), 7.5 ms for a ~140-token prompt; `STRATA_PREFILL_TIMING` books it as
"after each chunk (the draft layer) 694 ms" of 10.55 s. So **at most 0.69 s per long prompt: 6.6–7.2 % at 32K, 2.2 % at
112K** (upstream's batched pass took 0.9 s → 0.07 s on an RTX 5070). Backlog, not built.

**Our v5 decode kernels vs upstream's on the new base** (`STRATA_GR_OLD=1` = upstream's multi-token read): per generated
token 12.57 vs 12.47 ms (math, +0.8 %) and 13.04 vs 12.49 ms (code, +4.4 %) without v5 → **v5 still helps; kept together
with upstream's fused prompt-path norms** (they do not overlap).

**0.1.27's CJK draft vocabulary** (installed only by `setup.py`; measured with a separate MTP folder of symlinks + the
new file): on English text, compared on the same output trajectory, math 126.8 → 124.2 and 124.5 → 121.8 tok/s
(−2.1 / −2.2 %), code 109.1 → 108.5 / 106.8 (−0.5 / −2.1 %) — upstream's "English −1–2 %" holds here. **The candidate keeps
the English-era vocabulary.** If you chat in Chinese, Japanese or Korean, the new file is worth it (+15–38 % upstream).

**Served A/B, C\*6 vs the port** (`results/r7/ab-c6-c7.md`; round 6's screens, 4 alternating pairs, fresh guarded
server and cold page cache each, your settings T 1.0):

| | C\*6 (4 runs) | **v0.1.27 port (4 runs)** | change |
|---|---|---|---|
| 32K prompt (uncached) | 10.00–10.02 s | **9.64–9.66 s** | **−3.6 %**, no overlap |
| 64K prompt | 19.36–19.43 s | **18.65–18.71 s** | **−3.7 %** |
| 120K prompt | 36.55–36.68 s | **35.19–35.33 s** | **−3.7 %** |
| 1K prompt / short prompts | 0.97–1.00 / 0.45–0.47 s | 0.96–0.97 / 0.45–0.48 s | = |
| decode, all 768+-token requests | 94.8 / 93.4 / 93.8 / 94.5 (94.1) | 93.8 / 95.4 / 93.3 / 92.2 (93.7) | = (sampling noise; greedy is bit-identical) |
| long reasoning 8K math / code | 103.3–105.2 / 86.9–88.5 | 103.1–105.2 / 84.9–90.5 | = |
| VRAM / MemAvailable / RSS | 15,418 MiB / ≥ 29.1 GB / 57.5 GB | same | = |
| correctness (5 prompts) / chat-switch test | all right / 0 errors | all right / 0 errors | = |

**The new base wins** (a reproducible gain beyond the noise, no regression), so it went through your checks:

| check | result |
|---|---|
| accuracy (teacher-forced, 7 texts, one GPU and with the helper) | **bit-identical to C\*6**: 1,536 / 1,536 NLL values equal on every text in both setups (`results/r7/tf-compare.txt`) |
| harder needle set (12 documents × 6 questions, 32K/64K/120K) | **72/72** |
| chat-cache round trip (park / resume / edit, helper on, static expert set) | **exact**: 0 argmax changes, all NLLs identical, drafter 0 of 385, state equal except stale cells |
| headless-Chrome browser test incl. Web search | first run **53/56 — found a real bug** (below); after the fix **54/56** = round 6's two known non-bugs |
| Stop during a 120K read, then the next requests (round 5's stop120k) | unfixed: **fails** (going back to the parked chat errors); fixed: **7/7** |
| launcher fallback (4060 Ti short of memory → 5080 alone) | pass |
| 2-hour soak (the fixed build) | **pass** — below |

**A bug in upstream 0.1.26+, found by the browser test and fixed (patch 0013).** After you press Stop while a long
prompt is being read, the next request whose prompt goes through the batched prompt path — continuing that chat, or
going back to a parked chat — failed with `ERR cancelled`; the engine then exited and the server restarted it (a minute,
and every parked chat was lost). Cause: the serve loop keeps one error string for its whole life, a Stop leaves
"cancelled" in it, and 0.1.26's new draft-layer hook fails a prompt chunk whenever that string is non-empty (0.1.24's
hook ignored it). Fix: the hook gets its own error string (both serve and CLI paths); no arithmetic change — after the fix
greedy output, the 32K prompt time and the teacher-forced NLLs are unchanged. C\*6 does not have the bug (its stop120k:
7/7). Write-up for upstream: `pr-drafts/26-stop-then-next-request.md`.

My mistakes in this item, caught: the first round trip used a config without `--adapt-swaps 0` (the test needs a static
expert set) — invalid, re-run; my own quick reproduction script for the bug did not trigger it (its follow-up prompts
never took the batched path), so the evidence is the browser test and stop120k, which did.

**The 2-hour soak of C\*7** (the fixed build, `work/r7/soak.sh 120`, 00:39–02:39, the same traffic as C\*6's):
* **335 requests, 0 errors**, including 139 Stops, many of them during prompt reads; no request after one failed;
* no engine error or restart; the server logged only 57 `fetch_page` allow-list refusals;
* guard: 0 samples under your floors (MemAvailable min 25.96 GiB, 5080 min 476 MiB free, 4060 Ti min 1,052 MiB);
* engine RSS 50.4–60.6 GB with no growth; chat cache peak 10,282 of 16,384 MiB, never over budget;
* back to a parked big chat: median 0.81 s; fresh 32K probe 9.63–9.85 s throughout (C\*6's soak: 9.95–10.03 s).

**Promotion (02:40):** the launchers now default to `configs/Cstar7.json` (old copies in
`work/r7/*.before-c7-promotion`). Rollback test: 8080 → C\*6 (`a56a444b…`, "51", 20 s) → back to the default C\*7
(`886b6ab2…`, both GPUs, "51", 20 s): pass.

### 3. Item 1 — the engine oracle for next-layer expert staging (measured; no predictor built)

**What was built (measurement only, branch `r7-oracle`, never served).** The promoted build's source plus an
env-gated oracle (`src/core/oracle.cpp`):
* a run **records**, for every verify window and layer, the experts the CPU pool computed;
* a second run **replays** that record as the predictor. As soon as the host has released layer l to the GPU, it copies
  layer l+1's predicted experts into two VRAM staging banks on the copy engine, during the GPU phase that precedes
  layer l+1. The layer's plan then gives each staged expert to the GPU (upstream's existing "PCIe share" groups) if
  its copy has landed; otherwise the CPU computes it as before. The real router still decides.
* The staging VRAM is **charged to the expert cache**: `--vram-reserve-mib 882` instead of 800 for 2 × 16 slots
  (81 MiB), so the 5080 cache holds 4,518 instead of 4,560 experts. The recording for these arms is made at the same
  reserve.
* **Warming** the same way: the CPU threads read exactly the rows each of them will compute into their caches. This
  needs a static task → thread assignment (`STRATA_POOL_STATIC=1`, measured to cost nothing: −0.1 / −0.2 %). It can be
  capped at N experts per layer, with or without the host thread's share.
* **A degraded predictor**: each true expert kept with probability 0.6, plus wrong ones up to precision 0.46. Those are
  round 6's measured figures for the best causal predictor (next layer's router on the pre-MoE residual, K = 10).

**Method, and one thing that did not work as planned.** Your spec was greedy decoding with `--adapt-swaps 0
--suffix-draft 0`. For warming that works: warming does not change arithmetic, so the replay stays aligned (402/402 and
525/525 windows). **For staging it does not work.** A staged expert is computed on the GPU, which rounds differently
from the CPU, so a near-tied router choice flips and the greedy text drifts from its recording within the first window
or two (88 of 18,336 layer calls stayed aligned). The "perfect" predictor then became ~34 % recall. So staging was
measured on a **teacher-forced fixed text** instead: the math text, 1,536 tokens, through the same verify windows,
cache, CPU pool and helper GPU, in windows of 2, 3 and 4 tokens. With the token sequence fixed, the recorded predictor
covered **~98 % of the true CPU experts** (rare near-ties still flip a few ids). Window size 1 cannot be forced this way,
because the engine refuses `--spec 1` with a native pack. Per-window times come from the oracle's own log (graph
launch → the window's GPU work and copies done). Baseline repeats agree within 0.1–0.4 % (per-window sd 0.5–0.7 %).

**Results** (saving in time per window, + = faster; perfect predictor unless noted):

| arm | static tier (your spec): T2 / T3 / T4 | **adaptive tier (what C\*7 serves)**: T2 / T3 / T4 |
|---|---|---|
| CPU experts per window (baseline) | 516 / 669 / 798 | **142 / 214 / 286** |
| baseline window | 24.6 / 30.4 / 36.1 ms | **14.6 / 17.9 / 21.3 ms** |
| **staging ≤ 4 experts per layer** (what fits the ~200 µs GPU phase) | **+15.1 / +12.7 / +11.8 %** | **−0.2 / +1.6 / +2.5 %** |
| staging ≤ 6 | +13.6 / +13.9 / +14.0 % | −0.9 / +1.3 / +2.8 % |
| staging ≤ 8 | +8.2 / +9.8 / +11.1 % | – |
| staging ≤ 16 (landed copies only) | −3.6 / −7.3 / −6.5 % | – |
| staging ≤ 16, the GPU waits for every copy | T4 −34 % | – |
| **warming ≤ 6 experts**, host out | +13.9 / +11.0 / +10.3 % | **+8.1 / +9.9 / +9.4 %** |
| warming all | +1.3 / −4.6 / −7.1 % | – |
| **both: staging ≤ 4 + warming ≤ 4** | **+17.8 / +16.6 / +16.9 %** | +0.1 / +2.9 / +4.2 % |
| **~60 %-recall predictor**, staging ≤ 6 | +2.7 / +3.6 / +4.6 % | **−2.9 / −1.6 / −0.6 %** |
| **~60 %-recall predictor, warming ≤ 6** | +3.7 / +3.3 / +3.6 % | **+1.7 / +2.8 / +2.5 %** |

Greedy decode, static tier (T1–T4 mix, aligned): warming ≤ 6 experts **+10.3 % (math) / +11.7 % (code)**, ≤ 4 +8.0 /
+8.6 %, all −5.2 / +4.6 %; by window size, warming everything helps 1-token windows by 11–12 % and hurts 4-token
windows (math +9.5 % slower).

**The DMA's effect, measured:**
* *Its own bandwidth.* A layer's CPU experts are ~22–29 MB with the static tier. The copy engine moves ~53 GB/s,
  so staging all of them takes ~0.4–0.5 ms, twice the GPU phase. Copies still in flight during the pool phase read
  the same DRAM the CPU pool is reading (~77 GB/s shared), and both slow down. Staging more than fits (16 slots) is
  therefore slower than not staging at all. Making the GPU wait for the copies is far worse (−34 %).
* *On the GPU phase.* With staging ≤ 6 (T4, static tier; GPU stage profile), the GPU's own non-expert stages grow:
  hyper-connection read + router 1.68 → 2.03 ms, output projection 0.69 → 0.83 ms, copy + combine 0.42 → 0.85 ms per
  window. Then there is the added GPU expert work (the staged groups ~1.3 ms). The CPU wait falls 16.3 → 10.3 ms, and
  the net window time falls 36.2 → 31.4 ms.

**Answer to your questions:**
* **Is the measured ceiling at least ~15 %?**
  * Under the conditions you specified (static expert set), yes, just: staging alone 13.6–15.1 % at the best slot count,
    staging + capped warming 16.6–17.8 %.
  * **On the configuration you actually run (adaptive tier), no.** Staging gives 0–3 % per window, and the best oracle
    arm is warming at 8–10 %. The adaptive tier already holds most of the experts that staging would move, and what
    is left on the CPU is mostly hidden behind the GPU.
  * Round 6's 14.7 % was a model that assumed staging was free on the GPU side, and it was measured before the 4060 Ti
    helper, which serves ~5 % of the entries and hides more of the pool.
* **What a ~60 %-recall predictor would realistically keep:**
  * adaptive tier: **+1.7 to +2.8 %** with warming, and **a loss** with staging (−0.6 to −2.9 %; wrong experts cost copy
    bandwidth and GPU time);
  * static tier: +3–5 %.
* **Recommendation: do not build the predictor or staging track.** The best realistic figure on your configuration is
  ~2–3 %, below the noise of a served A/B. If this area is revisited, the target is CPU-cache warming, not PCIe
  staging, and it needs the pool's static task assignment plus a predictor that knows the pool's job order.

### 4. Item 4 — can two conversations run faster together than one after another? (feasibility, ~3 h; no engine change)

Everything ran on the promoted C\*7 (engine untouched: only flags, clients, and for nsys the trace twin of the same
source with the oracle off). Only accepted output tokens are counted; sampling and settings are the same in every
compared pair. **Evidence** (measured) and **estimates** (arithmetic on the evidence) are kept apart.

#### a) Where a decode window's time goes (evidence: nsys, 120 windows, math, greedy)

| | your served flags (adaptive tier, lookup drafts) | exact flags (static tier, `--adapt-swaps 0`) |
|---|---|---|
| window (wall) | **18.7 ms** (T1 13.4 … T4 22.3) | 31.1 ms (T1 19.0 … T4 40.3) |
| GPU working | **14.6 ms (78 %)** | 16.1 ms (52 %) |
| GPU waiting for the CPU (flag wait) | **2.7 ms (15 %)** | 16.8 ms (54 %) |
| gaps (host-only time: commit, drafting) | 0.2 ms | 0.2 ms |
| CPU expert pool per layer / per window | **133 µs / 6.4 ms**; the GPU works through 69 % of it | 404 µs / 19.4 ms; 36 % |

**Estimate — the ideal ceiling for interleaving two independent conversations** (one's GPU work during the other's CPU
phase, nothing else changes): the pair of windows cannot take less than the larger of the two resources' total work.
* Served flags: the GPU is the bottleneck, 2 × 14.6 = 29.2 ms vs 2 × 18.7 = 37.4 ms back to back → **at most +28 % total
  throughput** (1-token windows +22 %, 4-token +31 %). Each conversation would run ~36 % slower than alone.
* Static tier: CPU-bound, 2 × 19.4 = 38.8 vs 62.2 ms → +60 %. That is not the served configuration.

The second conversation's VRAM (its 32K resident K/V cells, recurrent state, window buffers: ~0.5 GiB) would come
out of the 5080's expert cache (~5 % of its experts), which lowers that ceiling a little.

#### b) `--spec-split` at the largest groups it supports (evidence)

8-token windows (4 + 4) and 6-token windows (3 + 3), every window full (`--spec-min-p 0`), math and code, ms per round:

| | static tier (exact, 2 identical repeats) math / code | **adaptive tier (served), 1 run** math / code |
|---|---|---|
| 8 tokens, unsplit | 59.7 / 54.4 | 41.6 / 39.2 |
| **8 tokens, split 4 + 4** | **53.1 (−11 %) / 46.1 (−15 %)** | **39.3 (−5.5 %) / 37.9 (−3.3 %)** |
| two 4-token windows back to back | 74.3 / 62.1 | 48.4 / 46.9 |
| 6 unsplit / split 3 + 3 / two 3-token windows | 48.5 / 42.0 / 62.9 · 42.1 / 34.9 / 54.4 | – |

Unlike rounds 3–4 (split −8.5 %), the split now wins at 8 tokens. v5 shrank the GPU's share, and the split hides the
GPU's wait for the CPU (static: 14.7 → 0.3 ms per round) even though its two groups duplicate experts (23.5 → 31.8
distinct CPU experts per layer). One window of 8 is also much cheaper than two windows of 4 (−14 to −16 %), because
the dense weights are read once.

#### c) One window with tokens of two unrelated conversations (evidence: the fixed `--dump-routing` traces)

Distinct CPU-side experts per layer (the math and code greedy runs, 1,024 accepted tokens each, static placement):

| window | same conversation (mean of the two) | **merged: half from each** | the two halves as separate windows |
|---|---|---|---|
| 4 tokens | 14.5 | **17.0 (+18 %)** | 18.4 (merged −7 %) |
| 8 tokens | 22.3 | **26.1 (+17 %)** | 29.0 (merged −10 %) |

Batching two conversations into one window costs ~17–18 % more CPU expert traffic than a same-conversation window of
the same size, but still saves 7–10 % against processing them in two windows.

#### d) Per-conversation state and one-conversation assumptions (evidence: the code)

See the table below the item (per-conversation state; every server and engine place that assumes one live
conversation; what the chat cache covers; the helper GPU). In short, the engine has one sequence (one SessionState,
one verify window with fixed mapped buffers, one drafter, one pool driver, one stop flag, and one error string —
tonight's Stop bug was exactly that). The chat cache time-multiplexes whole conversations between turns, but never
runs two at once. **The server already frees the engine between tool rounds.**

#### e) Two agents with web search, one after another vs overlapped through the queue (evidence)

`work/r7/agents2.py`: two agents, two turns each (Linux kernel releases; Node.js LTS and Python), web search through
the server's own tools, your settings, fixed seeds, 4,096 tokens max per turn, fresh server per run:

| run | total time | output tokens | total speed | per agent, end to end | first-token latency | tool time |
|---|---|---|---|---|---|---|
| one after another #1 | 80.0 s | 3,510 | 43.9 tok/s | 45.8 / 41.4 tok/s | 0.72–0.97 s | 33.6 s |
| **overlapped #1** | **55.8 s** | 3,561 | **63.9 tok/s (+46 %)** | 35.8 / 34.4 tok/s | 0.83–2.96 s | 31.1 s |
| one after another #2 | 83.5 s | 5,911 | 70.8 tok/s | 75.4 / 68.5 tok/s | 0.82–1.41 s | 14.6 s |
| overlapped #2 | 65.9 s | 4,885 | 74.1 tok/s (+5 %) | 34.0 / 53.3 tok/s | 1.00–3.12 s | 18.8 s |

Peak memory was the same either way (MemAvailable ≥ 34.9 GiB, engine RSS ≤ 51.9 GB, 5080 ≥ 462 MiB free). Every tool
round is its own engine request. In the overlapped runs the chat cache parked and restored the other agent's
conversation in 0–5 ms (≈ 100–230 tokens read again). The live web and sampling made the runs unequal. The gain
follows the tool time there was to hide: run #1 hid ~24 of its ~31 s of searching, and run #2 had little to hide (one
agent's searches returned in ~2 s). Per-agent speed and first-token latency get worse when overlapped: an agent waits
for the other's turn.

#### Recommendation: **useful only for overlapping tool waits**

* Overlapping agents' **tool waits already works today** (+5 % to +46 % total throughput here, no engine change). It
  costs each agent up to ~3 s of first-token latency and lowers its own speed. For agent workloads that is worth using
  (send agents through the same server concurrently); for your single-user chat it changes nothing.
* **Running two sequences in the engine is not worth prototyping for this PC and use:**
  * the measured ideal ceiling is +28 % total throughput on your configuration, with each conversation ~36 % slower;
  * batching into one window saves more GPU (one weight read) but carries 17–18 % more CPU expert traffic per token;
  * both need a second session (VRAM taken from the expert cache), per-sequence windows, drafters, stop and error
    state, and a server that runs two requests at once.
* **Biggest remaining unknown:** whether one host thread and one CPU pool can drive two conversations' windows without
  adding serial host time. Today the doorbell handling, plan, activation quantization and pool are single-threaded
  per window (~0.5 ms per window of serial host work), and the interleave needs the host to service both windows'
  layers in alternation. That, and not the GPU/CPU arithmetic above, decides how much of the +28 % would survive.

#### d) in full — per-conversation state and one-conversation assumptions


Source: `strata-r7` (branch r7-port). Line numbers are in `src/program/generate.cpp` unless a file is named.
Evidence = read in the code; nothing here was measured.

**Per-conversation state (what a second live conversation would need its own copy of)**

| state | where | size / note | chat cache covers it? |
|---|---|---|---|
| QSA K/V, 12 layers (int8) | `SessionState::qsa_states` (session.hpp), with KV streaming: authoritative copy in pinned host RAM, `n_slots` pages in VRAM | ~1 KiB per cell and layer pair (int8) | **yes**: host copies below the longest checkpoint are copied out on park (`park`, ~3727) |
| QSA indexer (pooled rows, dead row, block position, key tail) | `QsaState::idx_pooled / idx_dead / idx_block_pos / idx_tail` | small | **yes**: pooled/dead/bpos on park; the tail inside each checkpoint (`ConvCheckpoint::tails`) |
| GDN recurrent state + conv history, 36 layers | `SessionState::gdn_state` | fixed size per sequence | **yes**: `ConvCheckpoint::gdn` |
| residual `R`, block scratch | `SessionState::block`, `R` | per window, transient | n/a (recomputed) |
| n-gram (PLE) history | `ss.ple_prev[2]`, `ss.ple_hist` (NG_HIST rows) | small | **yes**: `ConvCheckpoint::ple` |
| n-gram prefetch in flight (patch 0012) | `PleTable::Impl::pf_pending / pf_ticket` (ngram.cpp) | ONE pending read | no (it is only a cache warm; a stale one is collected by the next gather) |
| MTP drafter K/V (a ring over a host copy with KV streaming) | `MtpDrafter::st_` (mtp.cpp) | ring = window + 4·max_t + 64 cells | **yes**: its host copy is one of `stash_arrays` (~3625), rebuilt by `mtp.kv_restore` on resume |
| prompt-lookup (suffix) drafter | `SuffixDrafter sfx` (~3597) | ONE instance | rebuilt per request from the prompt ids (`sfx.reset()` + append, ~4353) → effectively per request |
| draft policy (MTP vs lookup windows) | `DraftPolicy policy` (~3598) | process-wide, learned from measured round times | shared on purpose (it is not content) |
| sampler / RNG | `Verifier::sampling_`; draws are Philox(seed, position) (verify.hpp) | stateless per position; the seed is per request (`req_seed` or the clock, ~4264) | n/a |
| penalty history | per request (`set_history`) | – | n/a |
| cancellation | engine: ONE `stop_req` atomic (~3471, "STOP" line ~3507); server: a `cancel` Event per request, `stop_now(cancel)` stops the engine only if that request is the one running | – | n/a |
| the live conversation | `live`, `live_ok`, `checks` (~3271) | the session's own checkpoints | this IS what parks |
| side stash | `SideStash stash` (~3606) | one | separate mechanism (off when the chat cache is on) |

Process-wide and fine to share between conversations: the expert caches (5080 tier, 4060 Ti helper), the adaptive
tier's usage counts, the PLE row cache, the weights, the CPU pool, the draft policy.

**Every place that assumes ONE live conversation**

*Server (`serve/server.py`)*
1. `Service.run` holds `self.fifo` (a `threading.Lock`, ~580) for the whole of ONE model turn (~837): one request in the
   engine at a time; the others wait (`status["queued"]`).
2. The engine protocol is one command at a time over stdin/stdout (`GEN … REUSED … tokens … DONE`); the server drains
   to THIS request's `DONE` while still holding the FIFO (~887).
3. `status` (busy / phase / generated) describes one request.
4. **Tool rounds release the FIFO:** `run_with_mcp` (~978) calls `svc.run` once per model turn and executes the web /
   MCP tool calls *between* turns, outside the FIFO. So while one conversation waits for a web search, another request
   can already use the engine; the chat cache parks the first conversation and brings it back for its next turn.

*Engine (`strata --serve`)*
5. The serve loop reads one line at a time (`while (next_line(line))`, ~3830) and runs a request to its end.
6. ONE `SessionState ss`: one set of QSA/GDN/PLE state = one sequence position space.
7. ONE `Verifier ver`: the window graphs (one per window size T) are captured with fixed-address mapped buffers
   (`h_tok_`, `h_x_`, `h_ids_`, the plan block, flags A/B/M, `h_ymiss_`); one window in flight.
8. ONE `MtpDrafter` with one K/V ring; ONE `SuffixDrafter`.
9. ONE `ExpertDispatch` / `Drive` (job map `job_of`, `jobs_multi`, `act_multi`, the GPU plan sink) and ONE `ExpertPool`
   (a batch at a time, driven by the host thread pinned to core 0).
10. The helper GPU (`RemoteExperts`): one `begin`/`finish` pair per layer, its own staging buffers.
11. The prompt path (`Prefill`): one prompt at a time; with `--prefill auto` it BORROWS expert-cache slots for its
    buffers and refills them after (a second sequence decoding meanwhile would see a smaller cache).
12. `stop_req`: one flag for "the running request"; and the serve loop's error string `err` (generate.cpp:1353), one for
    the whole process and never cleared — tonight's Stop bug (item 0, patch 0013) was exactly this: one request's
    "cancelled" read by the next. Two live conversations would need both per sequence.
13. The chat cache has one live conversation; `park`/`unpark` swap it whole (measured in the soaks: park 1–115 ms,
    restore 14–44 ms for 7K–66K-token conversations; a conversation under 512 tokens is not parked but re-read).

**What the chat cache already gives, and what it does not**

* **Gives:** time-multiplexing at request (turn) granularity — several conversations stay warm in RAM and the engine
  switches between them in tens of milliseconds instead of re-reading them. Combined with (4), two agents that spend
  time in tool calls already overlap: one's tool wait can be filled by the other's generation, at the cost of a
  park/restore per switch.
* **Does not give:** two sequences in flight at once. Interleaving (A's GPU phase during B's CPU phase) or batching
  (A and B in one verify window) needs a second SessionState (+ its VRAM: the QSA slots and the GDN state), a second
  set of window buffers/flags (or a window graph whose rows belong to two sequences with two position sets and two
  K/V pools), per-sequence drafters, a per-sequence stop, and a server that runs two requests at once.

**How the helper GPU would fit**

The 4060 Ti computes ~5 % of the routed entries (its 3,300 cached experts) inside each layer's CPU phase
(`RemoteExperts::begin` before the pool, `finish` after). With two sequences interleaved it would serve both
sequences' CPU phases, so its per-layer work doubles; today it finishes 4–9 µs after the pool, so it stays off the
critical path only while its work stays below the pool's. It holds only experts (no dense weights, no K/V), so it
cannot run a second sequence's GPU phase; in a merged (batched) window it would see the union of both sequences'
experts like the CPU does.

### 5. C\*7 on 8080 and the 48-hour passive uptime monitor

04:09: `./switch-model.sh strata` started the promoted C\*7 on 127.0.0.1:8080 (engine `886b6ab2…` on both GPUs, SearXNG on
8888, a test question answered "51", "other apps use the Chat settings: temperature=1.0"). The **passive uptime
monitor** (`work/r7/uptime_monitor.py`, round 6's, paths in `logs/r7/uptime/`) runs for 48 hours. Every 15 minutes it
reads only `GET /health`, `/status` and `/metrics`, `/proc` and `nvidia-smi`, and never sends a model request or
restarts anything. It records your requests' timings (`requests.csv`), memory, file descriptors, idle CPU and free
VRAM (`samples.csv`), and every restart or identity change (`events.log`). First sample 04:09:37: healthy, MemAvailable
36.2 GiB, 5080 490 MiB free, 4060 Ti 1,052 MiB free. Stop it early with `kill $(cat logs/r7/uptime/monitor.pid)`.

### 6. Files, state, and what is left

| what | where |
|---|---|
| **C\*7** (promoted, the launchers' default) | `configs/Cstar7.json` (+ `Cstar7-single.json` for the 5080 alone; your shared chat settings in `Cstar7.shared-settings.json`), engine `engine-cstar7/strata` (sha256 `886b6ab2…`, sm_89 + sm_120), server/page `strata-cstar7/serve/` |
| rebuild C\*7 from scratch | `work/r7/build-cstar7.sh` (clean clone of v0.1.27 `a790805`, `git am patches/r7/0*.patch`, tree check) |
| patch series | `patches/r7/` (13 = C\*6's 12 ported + 0013 the Stop fix); branch `r7-port` in `strata/` |
| upstream write-up of the Stop bug | `pr-drafts/26-stop-then-next-request.md` |
| rollback | `STRATA_PORT=8080 ./run-strata.sh stop && STRATA_CONFIG=configs/Cstar6.json ./switch-model.sh strata` (stop first: `switch-model.sh` keeps a running Strata whatever the config) |
| launchers before the promotions | `work/r7/*.before-c6-promotion`, `work/r7/*.before-c7-promotion` |
| measurement builds (never served) | `r7-meas` (teacher-forcing/force hooks, `engine-r7m`), `r7-oracle` (the oracle + NVTX + teacher-forcing, `engine-r7o`, `engine-r7o-trace`) |
| results | `results/r7/` (item-0 engine checks, A/B `ab-c6-c7.md`, `tf-compare.txt`, round trip, oracle tables, merged windows, agents), `results/round7-summary.md`, day log `NOTES.md` "ROUND 7" |
| round-7 scripts | `work/r7/` (queue, guard, run/srv/screen/with_server, soak, rollback test, promote-c6/c7, oracle_table, merge_windows, agents2, stop_repro, tagcheck …) |

**Running at the end of the round:** C\*7 on 127.0.0.1:8080 with SearXNG on 8888; the 48-hour passive uptime monitor
(section 7); the tag watcher. Nothing else of mine.

### Round 8 backlog (ranked by expected gain × confidence ÷ cost)

| # | item | expected | first step |
|---|---|---|---|
| 1 | **Batched draft-layer prompt pass with KV streaming** (extend 0.1.26's E-9 to the drafter's ring) | ≤ 0.69 s per long prompt: 6.6–7.2 % at 32K, 2.2 % at 112K (measured ceiling) | write the ring's K/V from the batched pass (the host copy + the ring slots); parity test against the per-token pass |
| 2 | Prompt: MMQ through a pointer table (no per-expert group copy) | ≤ 10 % of prompt GPU time | parity test of one layer |
| 3 | Prompt: underfilled MMQ (21 % of a 32K prompt at ~1.4 TFLOPS) | unknown, possibly large | MMQ tile occupancy per expert size |
| 4 | Deterministic draft-policy switch (upstream suggestion, PR draft 24) | exact A/B tests without `--suffix-draft 0` | – |
| 5 | CPU-cache warming with a predictor | ~2–3 % on the adaptive tier at 60 % recall (measured, item 1); only if a better predictor appears | – |
| 6 | Two conversations at once | see item 4's recommendation | – |
| – | dropped with numbers | next-layer PCIe staging (item 1: 0–3 % perfect, a loss at 60 % recall on the served tier) | – |
