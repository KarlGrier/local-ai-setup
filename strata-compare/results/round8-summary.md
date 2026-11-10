# Round 8 — summary (kept current after every phase)

**Now (10:27): Round 8 is done. C\*10 is on 8080** (Strata v0.1.31 + our patches + upstream PR245; engine
`f3ff83cd…`, `configs/Cstar10.json`), with a fresh 48-hour passive uptime monitor.
- **vs C\*7 at the start of the round:** decode ≈ 110 tok/s vs 93.7 (+18 %); long-paste TTFT −4 %.
- **Correctness:** every change is bit-exact on fixed-computation tests; needles 72/72; soaks 0 errors.
- **Your decisions:** 16 chat slots (instant return to up to 16 chats vs up to ~4 GB more RAM with big pastes), and
  whether to send PR drafts 30/31 upstream.
- **Details:** REPORT.md "Round 8" (five-line summary at its end).
**Promoted build (on 8080):** C\*10, promoted 10:26 (engine `f3ff83cd…`); before it C\*9, promoted 06:37 (engine `a7efa8fe…`, `configs/Cstar9.json`); before it C\*8, promoted 20:21 (engine `381892ab…`, `configs/Cstar8.json`). Rollback to C\*9: `STRATA_PORT=8080
./run-strata.sh stop && STRATA_CONFIG=configs/Cstar9.json ./switch-model.sh strata`.

## Start of round (15:06)
- **Round 8a never ran**, so Phase 0 runs: update C\*7 (v0.1.27 + 13 patches) to **v0.1.30** (covers v0.1.28–v0.1.30).
- **The 48-hour uptime monitor was stopped at 15:06 after 10.9 h.** What it recorded:
  - one server and engine process the whole time: no restart, no error, health "ok" in all 45 samples;
  - **529 of your requests** (07:00–14:54, mostly Local Deep Research): 518 stop, 9 length, 1 cancel, 1 disconnect;
  - **time split: 94 % decode, 6 % prompt reading** (6.46 h vs 0.43 h);
    - so decode speed matters far more than prompt speed for how you use it;
  - decode: median 110 tok/s on 329 answers of 768+ tokens (range 81–140);
  - prompts: median 4,029 tokens; only 78 of 529 reused cached tokens;
    - 213 prompts had < 2K new tokens (median 0.70–1.02 s to first token);
  - memory: MemAvailable 24.7–36.3 GiB; 5080 476–490 MiB free; engine RSS 51.7–60.2 GB with no upward drift; swap 0.
- Tag watcher (tags + branches, every 40 min): newest release **v0.1.30**; branches `main`, `rc/0.1.30`.

## Phase 0 — update to v0.1.30
**Port:** v0.1.30 + C\*7's patches 0001–0012 (branch `r8-port`, engine `e9ab833b…`).
- 0013 (our Stop fix) is **not** ported: v0.1.28 fixes the same bug its own way. The stop120k and browser tests decide.
- Four merges were needed. One was a real bug the compiler caught: upstream's new conversation cache added a local
  variable `parked` that hid our chat cache's store of the same name. Ours is renamed.
- v0.1.28 now reserves the draft head's VRAM (+86 MiB), which would cost 47 cache slots. `--vram-reserve-mib 713`
  (instead of 800) gives exactly C\*7's 4,560 slots and 490 MiB free.
- **Pinning:** our Linux fix works on the new base. With the helper GPU the whole expert arena is registered:
  - the log says "cudaHostRegister PORTABLE ok" (with the cap it says "limited to 8 GiB");
  - every expert the prompt path streams goes by DMA (32K: 89,692 of 89,692; 112K: 313,922 of 313,922), which only
    works from registered memory; with the 8 GiB cap (Round 6) only 15,120 of 88,032 went by DMA;
  - the process's VmPin counter can't show it (it reads 0 for C\*7 too: the NVIDIA driver's pins aren't counted there).

**Greedy output is bit-identical to C\*7** (math, code, helper and one GPU, 1,024 tokens each; same speed per window).
- My first pairs looked different. The cause was my method: the CLI sized the port's cache 1–2 slots differently, so
  the pairs weren't fixed-cache. With a truly fixed cache, the outputs match bit for bit.

**Accuracy is bit-identical to C\*7:** teacher-forced over the 7 texts (short and 16K–64K long), one GPU and with the
helper, all 1,536 NLL values match on every text.

**Sampling is much faster (v0.1.29's sampler, #197).** On the same sampled text, every sampler variant picks exactly
the same tokens (checked on math and code, 2 runs each). What changes is the time per verify round:
| | C\*7 | port, old sampler (switch) | port, one-block | **port, default (split)** |
|---|---|---|---|---|
| math, ms per round | 34.31 / 34.33 | 34.47 / 34.36 | 32.75 / 32.79 | **31.93 / 32.18** |
| code, ms per round | 22.34 / 22.38 | 22.48 / 22.33 | 20.80 / 20.71 | **19.80 / 19.79** |
- That is **2.4–2.6 ms saved per round at top-k 20**: +7 % tok/s on math, **+12.8 % on code** in these runs.
- These are exact-mode runs (static expert set). **Served, first A/B pair at your settings: decode 95.5 → 106.1 tok/s
  (+11 %)**, ms per verify round 21.54 → 18.87 at equal tokens per round, long reasoning math 105.9 → 116.4 and code
  88.2 → 100.2 tok/s.

**Served A/B, all 4 alternating pairs (your settings; `results/r8/ab-c7-r8.md`):**
| | C\*7 (4 runs) | **v0.1.30 port (4 runs)** | change |
|---|---|---|---|
| decode, all 768+-token answers | 92.3–95.5 (mean 93.7) tok/s | **105.2–106.1 (mean 105.8)** | **+13 %**, no overlap |
| ms per verify round (same ~2.0 tokens/round) | 20.7–21.5 | 18.4–19.0 | −2.4 ms |
| long reasoning math / code | 104.3 / 86.7 tok/s | 116.6 / 98.9 | +12 % / +14 % |
| 32K / 64K / 120K prompt | 9.64–9.68 / 18.64–18.70 / 35.16–35.31 s | 9.51–9.54 / 18.38–18.42 / 34.75–34.78 s | −1.2…−1.4 % |
| 1K prompt | 0.96–0.98 s | 0.98–1.01 s | +3 % (the new 1,024-token path; see short prompts below) |
| memory | 15,418 MiB, ≥ 27.3 GB free RAM | same | = |

**Prompts (cold, CLI):** 32K 9.59/9.64 → 9.47/9.50 s (−1.3 %); 112K 32.30 → 31.94/31.92 s (−1.1 %).

**Short prompts (v0.1.30 streams all experts from 1,024-token chunks):**
- Output is identical at 1,100 / 1,536 / 2,000 / 3,000 / 4,000 tokens (new rule, old rule and C\*7 all agree).
- Speed, served with warm-up, 2 fresh servers per arm (engine prompt time):
| prompt (tokens read) | C\*7 | port, old rule (2,048) | **port, new rule (1,024)** |
|---|---|---|---|
| 1,066 | 844 ms | 838 ms | 892 ms (**+6 % slower**) |
| 1,578 | 1,017 ms | 1,011 ms | **909 ms (−10 %)** |
| 2,042 | 1,219 ms | 1,208 ms | **957 ms (−21 %)** |
| 3,041 / 4,042 | 1,211 / 1,459 ms | 1,203 / 1,446 ms | 1,197 / 1,446 ms (=) |
| tool result appended, 1,853 | 1,151 ms | 1,147 ms | **1,051 ms (−8.5 %)** |
| short follow-ups (60–145 tokens) | 334–443 ms | same | same |
- The break-even on this PC is about 1.25K tokens. A threshold of ~1,280 would keep the gains and drop the slowdown,
  with the same output. That is a small Phase A config screen; C\*8 keeps upstream's default for now.

**Conversation cache: upstream's new one (#189) vs ours**, same binary, KV streaming + helper GPU, 3 runs each:
| | ours | upstream #189 |
|---|---|---|
| back to a parked chat | 0.36–0.75 s | 0.36–0.78 s (=) |
| first request of the other chat (short / reasoning / 64K paste) | **0.51–0.52 / 0.57–0.58 / 18.29–18.31 s** | 0.67–0.69 / 0.63–0.64 / 18.39–18.45 s |
| engine RAM (peak RSS / lowest MemAvailable) | **53.8–54.7 / 31.3–32.3 GB** | 57.3–58.4 / 27.4–28.6 GB |
| park → resume, resume + edit | exact | exact |
- **Decision: keep ours.** Upstream's snapshots the old chat before every switch and every edit or regenerate,
  2–3× slower per park, and holds ~3.5 GB more RAM, which matters against your 20 GB floor.
- The reasons are written up for upstream in `pr-drafts/27-conversation-cache-vs-chat-cache.md`.

**Gates on the candidate (C\*8 = v0.1.30 + patches/r8/0001–0012, clean build `381892ab…`, tree = the tested port):**
| gate | result |
|---|---|
| accuracy (teacher-forced, 7 texts, one GPU + helper) | **bit-identical to C\*7** |
| harder needle set (32K / 64K / 120K) | **72/72** |
| chat-cache round trip (park/resume, resume + edit) | **exact** |
| stop120k (Stop during a 120K read, then continue) | **7/7** on upstream's fix alone → our patch 0013 dropped |
| browser test (on a config copy) | **52/56**: 2 known non-bugs + 2 web checks blocked externally* |
| launcher fallback (4060 Ti short of memory) | pass |
| **2-hour soak** | **pass: 351 requests, 0 errors**, 137 Stops; RAM never below 25.0 GB free, no growth; 32K probe 9.43–9.53 s all through |
| web replay (saved search results, no live search) | 4/4 answers checked, cited |
| **promotion + rollback test** | **pass** (8080 → C\*7 → back to C\*8, both answered) |
\* SearXNG returns 0 results right now (brave and google: "Suspended: too many requests"), so the model had nothing to
cite. The web mechanics all passed, and the replay with saved results passed; I'll re-run the live check when SearXNG
recovers.

## Phase A — feasibility (done 00:50)
**Where decode time goes (A.1, trace at your settings):** a decode round is 21.8 ms: verify window 19.9 ms (91 %),
commit 0.6 ms, drafting 1.35 ms. Inside the window the GPU works 75 % of the time and waits for the CPU experts 18 %.
- Biggest GPU items per window: the GPU's own expert kernels ~6.0 ms (30 %), dense projections 3.2 ms, hyper-connection
  kernels 2.75 ms. The new sampler costs only 33 µs.
- Roofline (measured ceiling 913 GB/s): dense projections reach 62 % of it, hyper-connections 48 %, the head 75 %, and
  the experts' down kernel only ~22 % (an estimate).

**Prompt (A.2, 32K / 112K):** GDN mixer 25 % (the recurrence alone 7.6 %), expert GEMMs 22 %, expert group copies 15 %,
QSA 15–19 %, hyper-connections 9 %, the draft layer's pass 0.69 s (6.7 % of a 32K prompt, 2 % at 112K). Prompts are only
6 % of your time, though.

**Thread affinity (A.3):** 6 threads inherited the host's single-core pin, but they're idle here. The adaptive cache's
helper thread and the chat cache's copy threads also inherit it; a small A/B is running.

**Speculation (A.4, oracle on 9,000 drafted positions at your settings):**
- The oracle predicts today's acceptance correctly (0.735 predicted vs 0.737 observed).
- **Correction (22:40):** my first window-length model assumed draft 1 is always proposed, but the engine applies the
  draft floor to draft 1 too. Corrected:
  - Raising the floor is worth **at most +1–2 %**, not the +4–5.5 % I wrote earlier. The corrected model tracks the
    screens to within 2–3 %.
  - Exact speculative sampling is worth **+3.5 %** vs today (≈ +2 % over the best setting), not ~+6 %. That's far
    below the 8 % bar, so it goes to the backlog.
- Upstream's coupled drafting: −1.9 % tokens per window here, no gain.
- At 64K–120K the drafter's 32K window keeps acceptance at the short-context level, so sparse attention has nothing to
  recover.

**GDN chunked prefill (A.5): dropped.** FlashQLA only runs in BF16 (~1,600× less accurate than today's FP32), needed two
workarounds to run on the 5080 at all, and with layout conversion it isn't faster than Strata's own kernel
(6.0 vs 5.4 ms per layer-chunk).

**Upstream PR245 (GPU expert kernels):** bit-identical on both cards; −6 to −8 % per decode round in exact mode. A
served A/B is running.

**Programmatic dependent launch:** ~0.14 µs saved per kernel boundary ≈ 1.8 % of a window, for an invasive change.

**Upstream PR245 served A/B: +4.5 % decode** (bit-identical output). Thread-affinity fix: no effect, dropped.
Smaller draft window (16K): prompts up to 3 % faster, long-context decode risk; dropped.

**New prompt find:** 10 % of long-prompt GPU time is a plain per-expert copy into the MMQ group buffer. The experts can
be DMA'd straight into place instead: same bytes, same math. That's about −1 s on a 32K paste and −3.7 s at 112K.

**Config screens (A.6):**
- **Draft length / floor:** 37 decode screens; nothing beats today's spec 4 / floor 0.5 beyond noise (best +0.9 %).
  No change.
- **Chat-cache slots: 16 instead of 6, same 16 GiB.** With 16 chats of normal size, going back to one takes 0.22 s
  instead of 3.6 s. But with big pasted chats the cache then fills its whole 16 GiB, and the needle test hit the
  20 GB memory floor (C\*8 with 6 slots: 23.7 GB). → **Not adopted; your call** (it costs up to ~4 GB more RAM in
  heavy-paste use).
- **Stream threshold 1,280:** no net effect. No change.

**Decision point (ranked):** (1) PR245 +4.5 % decode, (2) prompt copy removal (−3 % prompt time), (3) 16 chat slots (later reverted: memory).
Everything else goes to the backlog with numbers (exact speculative sampling +3.5 % modeled, draft-layer prompt pass
≤ 6.7 % of a 32K prompt, PDL ~1.8 %, one sync ~0.6 %).

## Phase B — build
1. **Upstream PR245 (GPU expert kernels): +4.5 % decode**, output bit-identical (kernel parity on both cards, engine
   output, served A/B). Ready.
2. **Prompt experts read in place (no copy into the MMQ group buffer): −3.0 % / −3.1 % prompt time** at 32K / 112K
   vs C\*8 (9.48 → 9.21 s; 31.9 → 30.9 s), output bit-identical. Phase C's first check caught my first version
   making prompts **6 % slower**: the kernel edit had turned 1,152 cached weight loads into uncached ones, and my own
   A/B had only compared the change on vs off inside the patched binary. Fixed (the loads are back, verified in the
   compiled code), then re-measured directly against C\*8.

Not built (below the bar, numbers in the ranking): exact speculative sampling (+3.5 % modeled), PDL (~1.8 %),
dropping one sync (~0.6 %), the draft layer's prompt pass on a second stream (≤ 6.7 % of a 32K prompt).
Dropped with measurements: thread-affinity fix (no effect), GDN chunked prefill (BF16 only, not faster), coupled
drafting (−1.9 %), a smaller draft window, `--spec-split`.

## Phase C — integrate and verify (done 06:37)
**C\*9 = C\*8 + PR245 + prompt copy removal (C\*8's settings), promoted 06:37.**
- **A/B vs C\*8:** decode +4.4 % (full screens) / +4.0 % (decode screens); TTFT 32K / 64K / 120K −2.8 / −2.9 / −3.0 %.
- **Fresh holdout:** decode +4.8 %, 28K-document TTFT −2.8 %, total request time −4.5 %.
- **Gates:** bit-identical output; teacher-forced NLL identical (adaptive tier off); round trip exact; needles 72/72;
  Stop 7/7; browser 54/56 (known non-bugs; live web search passes again); fallback ok; PR245 kernels clean under
  race / memory / init checks on both cards.
- **Soak:** 361 requests, 0 errors, MemAvailable ≥ 25 GB.
- **Rollback test:** passed.
- **Caught and fixed on the way:** my prompt change first made prompts 6 % slower (fixed); 16 chat slots hit the memory
  floor (reverted).
- **Open point:** a rare, rounding-level difference from the adaptive tier's timing (explained in REPORT).
Tables: results/r8/phaseC-ab.md. Rollback: `STRATA_PORT=8080 ./run-strata.sh stop && STRATA_CONFIG=configs/Cstar8.json ./switch-model.sh strata`.
C\*9 = C\*8 + both Phase B changes (16 chat slots tried, reverted), clean-clone build; bit-identity vs C\*8 (greedy and sampled,
2K–112K prompts); teacher-forced NLL; chat-cache round trip; needles; Stop at 120K; alternating A/B (full screens +
decode screens); then a fresh holdout, browser test, 2-hour soak, rollback test, promotion.

## Phase D — Strata v0.1.31 (done 10:26)
- **Release:** v0.1.31 came out during Phase C. It was ported (our GR v5 merged into upstream's new hyper-connection
  code; our pin patch dropped since upstream now pins on Linux).
- **Measured on its own:** bit-identical, but **6–9 % slower decode per round** without PR245. Upstream's own expert
  speed-up does nothing here, so PR245 was transplanted onto v0.1.31.
- **C\*10 = v0.1.31 + patches + PR245:**
  - Same speed as C\*9 (A/B and holdout), output bit-identical.
  - TF 14/14, round trip exact, needles 72/72, Stop 7/7.
  - Browser test: web mechanics pass; live answers blocked by SearXNG again, and the web replay passes 4/4.
  - Fallback ok; soak 373 requests, 0 errors; rollback test passed. **Promoted 10:26.**
- **Found on the way:** a bug in our launcher since Round 6, where a helper-GPU start could end silently. Fixed.
