## Round 5 — update to v0.1.24 (+ dual-GPU test), correctness, web search, failure modes, quality, soak (2026-09-28 22:57 → 2026-09-29 11:50)

**Result (status 11:50, 2026-09-29): C\*5 = Strata v0.1.24 + 9 patches is on 8080.**

| | C\*4 (round 4) | **C\*5** | llama.cpp, same file |
|---|---|---|---|
| 32K / 64K / 120K prompt | 15.7 / 31.6 / 61.8 s | **10.0 / 19.4 / 36.6 s** | 34–44 / 70–81 / 135–152 s |
| decode, long requests | ~90 tok/s (24.2 ms per verify window) | **~94–95 tok/s (22.4 ms)** | ~34 tok/s |

**Speed**
* **Prompt reading is ~40 % faster** than C\*4 (120K: 36.6 s instead of 61.8 s). The gain comes from upstream: v0.1.22
  and v0.1.24.
* **Decode is ~5–8 % faster:** v0.1.23's batched verify window, plus our v5 hyper-connection kernels (−5 % time per
  window).

**Quality and correctness**
* **Blind-graded quality equals llama.cpp's** on the same file: 90.5 vs 90.3 of 100.
* **Harder needle set:** 72/72 on every build.
* **Long-text accuracy** is level with llama.cpp.
* **The chat cache round-trips bit-exact.**
* **Sampling is unbiased** and uses the exact speculative accept rule.

**Fixes and new features**
* **New: a Web search switch** in the chat page (local SearXNG, read-only tools, cited answers).
* **Fixed:**
  * Stop during a long prompt read now takes effect at once.
  * Two tabs no longer lose each other's chats.
  * A crash when another program takes VRAM after start is avoided by a warm-up prompt.

**Testing**
* **2-hour soak:** 330 requests, 0 errors.

**Two GPUs**
* **Dual GPU (4060 Ti) was tested on v0.1.21/0.1.22 and loses on this PC:** the layer split does not fit on an 8 GB
  card, and the helper cache is 4–5 % slower to decode and 22–25 % slower to read prompts. **No Cstar5-dual.**

**Skipped**
* **Uptime (Phase 7)** was skipped as you asked, and the headless-browser test was not repeated on v0.1.24. Both are
  listed for Round 6 at the end.

**Rollback:** `STRATA_CONFIG=configs/Cstar4.json ./switch-model.sh strata`.

### 0. What changed on the PC before this round (found, not changed by me)
* **The RTX 4060 Ti 8 GB is installed** (GPU 1, bus 10:00.0) and **the desktop now runs on it** (Xorg + gnome-shell are on
  the 4060 Ti; the 5080 carries only a 4 MiB Xorg context). So the 5080 is free for the model: C\*4 now caches **4,560
  experts** instead of 4,337 (round 4, with Chrome on the same card) — about 5 % more, for free.
* **PCIe under load** (pinned 2 GiB copies, `work/r5/pcie/pciebw`): **RTX 5080 Gen5 x16, 57.8 GB/s** host→device — it did
  **not** drop below x16, so there is no prompt-reading cost to measure. **RTX 4060 Ti: Gen4 x4 (card max x8), 6.4 GB/s** —
  its slot is a x4 (chipset-type) slot. If you ever move it to the second CPU-attached x16 slot, most AM5 boards then
  split the CPU lanes x8/x8 and the 5080 would drop to x8. That cost can only be measured after such a move: run
  `work/r5/pcie/pciebw` and `work/r5/screen.sh` again. There is no reason to move it, since the helper mode loses anyway (§1b).
* **RAM bandwidth** (`tools/membw`, `results/r5/membw-r5.txt`): 77.9 GB/s on 16 threads over both CCDs (round 1: 76.5),
  79.8 GB/s on 4+4 threads (78.0), 63.4 GB/s from one CCD (63.4). **+1.8–2.4 % on the both-CCD cases, one CCD identical** —
  if you changed the RAM speed, the change is within ~2 %; all earlier numbers (~77 GB/s) remain comparable.
* The PC rebooted three times in the evening (19:16, 19:34, 22:46). The overnight script from round 4 was never started.
* **Your chat settings changed after round 4:** in your 18:24 session you set the chat page's shared settings to
  temperature 1.5 and then **1.0** ("Use for other apps too"; `configs/Cstar4.shared-settings.json`, 18:29). Round 5
  therefore uses **temperature 1.0, top_p 0.95, top_k 20, min_p 0.05** wherever "my settings" matters (sampling test,
  quality, needles, web search, soak), sent explicitly to both engines. Speed screens keep the configs' 0.6, as rounds 2–4.
  C\*5 keeps your shared-settings file unchanged.

### 0b. Second GPU: nothing changes for the existing setups
* **signal-next now spreads over both cards and does not start:** llama.cpp (no device list in its profile) put layers on
  both GPUs and then failed: `failed to allocate CUDA1 buffer of size 7966228608` (its 4096-token compute buffer on the
  8 GB card). **Fixed in `switch-model.sh` only** (the signal folder is untouched): it starts signal-next with
  `CUDA_VISIBLE_DEVICES=<5080 UUID>`. Verified: CUDA0 only, 14,020 MiB as before, test completion 0.8 s.
* **Strata is pinned to the 5080 by UUID** in every Strata config I use (`env.CUDA_VISIBLE_DEVICES =
  GPU-UUID-RTX5080`), and `run-strata.sh` checks the free VRAM of that card. (Strata would have
  picked the 5080 anyway — CUDA numbers the fastest card first — but pinning makes it independent of the order.)
* **Dual-GPU Strata arrived during the night (v0.1.21, 23:33) — tested, and it does not win on this PC; not adopted.**
  See §1b.

### 1. Update to v0.1.20
Five releases since v0.1.15, all on 2026-09-28 (notes: `work/r5/release-notes.txt`; diff reviewed: engine, server,
web app, setup, tools):
* **v0.1.16** the GSQ-RCO Coder (pruned model), model files in a shared `Strata-data` folder, MIT licence;
* **v0.1.17** **sampler order = llama.cpp's** (penalties once, then top_k → top_p → min_p → temperature; before: min_p
  *before* top_p and the penalties applied a second time after the temperature), `/v1/messages?beta=true` + late system
  messages (Claude Code), `--gpu N` / `"gpu"` config key, `tools/needle_bench.py`;
* **v0.1.18** releases published with their engine, a sampler guard;
* **v0.1.19** **penalties applied to every drafted token** (they were mostly not applied), the CLI (`strata generate`)
  samples again (our earlier `--stats` profiles were greedy), top_k 0/>64 → 64, `--calibrate`, **MCP tools in the web
  chat** (`serve/mcp.py`), the expert cache retries smaller when its allocation fails;
* **v0.1.20** a pinned conversation checkpoint at the end of a ≥2,048-token system prompt (new chats of the same client
  reuse it), per-request expert-cache hit rate, a PCIe-bandwidth probe (only when `--pcie-frac` is not set — ours is 0).

No new network code in the engine; the server's new network code is the MCP client (only for servers listed in the
config — none here). **One hazard, so I did not run v0.1.20's `setup.py`:** its new `data_folder()` *moves* the model
files of every folder named `strata*` next to it and one level up (all my worktrees, `strata-v0115/`, which C\*4's
config uses, …) into `Strata-data` and rewrites their configs, and writes `~/.config/strata/settings.json`. I built
with CMake exactly as `setup.py` does and reused the pack/MTP files (their format is unchanged). Issue draft:
`pr-drafts/11-setup-data-folder.md`.

**Port** (branch `r5-port`, `patches/r5/`): all six C\*4 patches still apply (one conflict: the side-stash hook next to
upstream's new root checkpoint and hit-rate fields). Nothing of ours is duplicated upstream any more: n-gram reads (0001)
are still one synchronous read per row upstream; chat cache (0005) and chat list (0006) have no upstream equivalent
(0.1.20's root checkpoint is a different, complementary thing); the decode patches (0003/0004) are untouched upstream.
**One interplay fix (patch 0007):** when the chat cache parks a conversation for a new chat, it used to take *every*
checkpoint with it and read the new chat from token 0 — which would throw away 0.1.20's shared-system-prompt checkpoint;
now the checkpoint the new request resumes from stays with the session (parking only copies). The web app merged
cleanly: the chat list saves upstream's tool cards with each chat (QuickJS test 15/15).

**A/B against C\*4** (two alternating pairs, fresh server and cold page cache each, `work/r5/screen.sh` = round 4's
screen + the chat-switch test; the configs' sampling 0.6/0.95/20/0.05; both on the now desktop-free 5080):

| | C\*4 (2 runs) | v0.1.20 port (2 runs) |
|---|---|---|
| time to first token, 68–87-token prompts (median of 5) | 0.48 / 0.48 s | 0.48 / 0.47 s |
| 1K prompt | 1.10 / 1.10 s | 1.10 / 1.09 s |
| 32K prompt | 15.70 / 15.69 s | 15.70 / 15.70 s |
| 64K prompt | 31.56 / 31.57 s | 31.59 / 31.59 s |
| 120K prompt | 61.80 / 61.82 s | 61.88 / 61.86 s |
| decode, all 768+-token requests (engine) | 91.5 / 90.2 tok/s | 91.1 / 89.3 tok/s |
| ms per verify round (tokens per round) | 24.34 (2.23) / 24.10 (2.17) | 24.37 (2.22) / 23.66 (2.11) |
| long reasoning 8K: math / code | 100.6, 102.0 / 86.6, 82.4 | 102.2, 99.9 / 83.8, 84.6 |
| back to a 40K chat after a 64K paste elsewhere (switch test) | 0.71 / 0.51 s | 0.71 / 0.68 s |
| peak VRAM used / min MemAvailable | 15,428 MiB / 29.4 GB | 15,428 MiB / 29.3 GB |
| request errors (screens + switch tests) | 0 | 0 |

Prompt reading is identical to 0.1 %; decode is equal within the sampling noise (the per-round time is the same or
lower; tokens per round differ by draw luck). **The v0.1.20 port became the base** (later v0.1.21, then v0.1.22, §1c) — same speed,
and it brings upstream's sampler-order and penalty fixes (your sampling now follows llama.cpp's chain exactly).
**Accuracy** (teacher-forced NLL, the round-3/4 method, 7 texts incl. two new long ones, `results/tf-R5tf-*`): the v0.1.20
port and C\*4 give **bit-identical** scores on every text (upstream changed the sampler, not the forward pass) — no
accuracy question. See §5 for the comparison with llama.cpp.
**`--calibrate`** (upstream's `tools/calibrate.py`, run on its own — not through `setup.py`): it measures greedy 128-token
decodes of three short prompts and compares against the *product default* (PCIe share 0.55). Here: share 0.00 90.8,
**0.20 93.0**, 0.35 91.4, 0.55 82.3, 0.75 76.9 tok/s; draft floor 0.5 best (= ours); 15 pool workers best (= ours). Its
result — `--pcie-frac 0.2` — beats the product default (91.2 vs 82.3 in its confirmation) but **not our 0**: exact greedy
profiles 116.9/113.4 vs 112.3/114.6 tok/s at 1K (same time per window at equal window size), and a full sampled screen
with 0.2 gave 89.5 tok/s over all long requests vs 91.1/89.3 for ours, identical ms per verify round (23.71 vs 23.66 at
2.12 vs 2.11 tokens), identical prompt reading. **Not adopted** (the rule: only if it beats ours).
**VRAM floor and eager loading.** With the desktop on the 4060 Ti, the 5080 holds only Strata (plus Xorg's 4 MiB):
**569 MiB free after load, 454 MiB at the end of every screen** (peak) with the LAZY override — above your 300 MiB
floor even if a Chrome GPU process ever landed on the 5080 (it renders on the 4060 Ti now; the uptime log records
every other process on the 5080). **The eager-loading issue is unchanged in v0.1.20:** without the override it caches 24
fewer experts and leaves **321 MiB after load and 208 MiB after one 32K request** (cuBLAS still loads all its kernels
*after* the cache is sized) → C\*5 keeps `CUDA_MODULE_LOADING=LAZY`. Issue draft: `pr-drafts/12-eager-vram.md`.


### 1b. Two GPUs (v0.1.21 and v0.1.22): tested, slower here, no Cstar5-dual

**The cards and links (under load, `results/r5/pcie-links.txt`).** RTX 5080: **PCIe Gen5 x16**, 57.8 GB/s host→GPU
and 58.0 GB/s back, the same as before, so the second card cost the 5080 nothing and there is no reason to move it.
RTX 4060 Ti 8 GB: **Gen4 x4**, 6.4 / 6.8 GB/s (the slot's limit). The desktop now runs on the 4060 Ti, which leaves the
whole 5080 to Strata: 4,560 cached experts instead of 4,337 in round 4.

v0.1.21 (23:33, "one model across two or three GPUs") brought two ways to use a second card. I built a multi-arch
engine (sm_89 + sm_120) with our patches and tested both, then tested again on v0.1.22, which improved multi-GPU:

**Layer split (`"gpu": [0, 1]`, `--layer-split auto`): does not start on this pair.** Each card needs its own copy
of the dense weights (1.5 + 2.0 GB), its share of the session (the KV for its layers stays resident; v0.1.22 can stream
it), the head and the MTP layer. That leaves the 4060 Ti **1.35 GiB (v0.1.21) / 2.50 GiB (v0.1.22) and 0 experts**.
Strata's own planner predicts **~38–39 ms per decode window vs ~24 ms on the 5080 alone** (the 4060 Ti takes 0.84 ms per
layer vs 0.33 ms) and then exits with "layer split, CUDA1 expert cache: no room". With an 8 GB second card the split
cannot help, whatever the settings.

**Helper cache (`--expert-cache-device1 3300`): works, but slower.** The 5080 runs exactly as before; the 4060 Ti holds
3,300 more experts (6.2 GiB, 1.1 GiB left free) and computes them itself. Full screens, fresh server each:

| | 5080 alone (v0.1.22) | + 4060 Ti helper (v0.1.22) | + 4060 Ti helper (v0.1.21) |
|---|---|---|---|
| experts in VRAM | 4,560 (18.6 % of 24,576) | **7,902** (32 %) = 4,602 on the 5080 + 3,300 | 7,902 |
| decode lookups served from VRAM (30 requests, pooled) | 75.7 % | 80.9 % on the 5080 + 5.4 % on the 4060 Ti = **86.4 %** | 80.3 + 5.6 = 85.9 % |
| decode, all long requests | **90.3 tok/s** | 86.4 tok/s (−4 %) | 86.6 (v0.1.21 single: 91.4) |
| ms per verify window (tokens per window) | **23.66** (2.14) | 24.85 (2.15) | 25.05 (2.17) |
| time to first token: 1K / 32K / 64K / 120K | **1.00 / 10.4 / 21.1 / 42.7 s** | 1.55 / 13.0 / 26.2 / 52.2 s (+22–25 %) | 1.68 / 19.5 / 39.1 / 75.7 s |
| long reasoning 8K, math / code | 102.9 / 82.9 tok/s | 98.8 / 78.3 | 95.1 / 82.8 |
| switch test (chat cache) | 0 errors | 0 errors, back to a 40K chat in 0.5 s | 0 errors |
| accuracy, forced 1,536 tokens after a 6K / 40K chat | – | helper − single −0.0002 ± 0.0009 / −0.0019 ± 0.0009 nats/token (v0.1.21) | |

Why the helper card loses:
* The 4060 Ti can only get the experts that did not fit on the 5080, the least-used ones. They answer just 5.4 % of
  lookups.
* Each window still has to wait for the slower card over its x4 link: the verify window gets 1.2 ms longer (24.85 vs
  23.66 ms), which outweighs the extra hits.
* Prompts get slower because, with a helper card, the engine pins only 8 GiB of the expert arena ("mlock failed (raise
  ulimit -l); cudaHostRegister limited to 8 GiB"), so most of the prompt path's expert copies come from pageable
  memory. Raising `ulimit -l` would be a system change, so I did not try it.

On v0.1.22 the helper's prompt penalty is about the same (+22–25 %, was +24 %), on a much faster baseline (its 120K is
52 s vs 76 s on v0.1.21). It is still slower than the 5080 alone on every measure.

**Decision: no Cstar5-dual.** No dual-GPU setup beat the single-GPU best, so there is nothing to switch to. The
soak was not run on a dual setup, because it failed the screens first. The configs to repeat the test are
`configs/R5c-helper.json` and `configs/R5c-split.json`. A card with more VRAM, or an x8/x16 slot for the helper,
would change the picture for the helper mode, not for the split.

### 1c. v0.1.22 (released 04:41): folded in (the C\*5 base until v0.1.24, §1d)

v0.1.22 made prompts faster:
* the prompt's sparse attention runs on tensor cores (FP32-level accuracy; `STRATA_PROMPT_ATTN_OLD=1` gives byte-identical
  0.1.21);
* **n-gram rows are read by a thread pool on Linux too** (`STRATA_IO_THREADS`, default 16). This is what our patch 0001
  did, so **0001 is dropped** and C\*5 sets `STRATA_IO_THREADS=64`, our old value;
* prompt kernels without host waits.

It also brought multi-GPU fixes and a constant-time streaming detokenizer in the server (it had cost 4 ms per token
after 16K tokens). Diff reviewed: server, app and telemetry changes are benign; `setup.py` and the tools make no new
network calls. The other 9 patches applied with one conflict (0003 vs upstream's opt-in device-plan path: kept both);
`patches/r5/` is now this 10-patch series.

| | C\*5 on v0.1.21 (2 runs) | **v0.1.22 port (2 runs)** |
|---|---|---|
| time to first token, 68–87-token prompts | 0.48 / 0.47 s | 0.47 / 0.49 s |
| 1K prompt | 1.09 / 1.10 s | 1.00 / 0.98 s |
| 32K prompt | 15.70 / 15.70 s | **10.41 / 10.39 s** |
| 64K prompt | 31.56 / 31.60 s | **21.10 / 21.08 s** |
| 120K prompt | 61.88 / 61.88 s | **42.67 / 42.71 s (−31 %)** |
| decode, all long requests (engine) | 91.4 / 89.7 tok/s | 90.3 / 89.7 tok/s |
| ms per verify window (tokens per window) | 24.24 (2.21) / 23.92 (2.14) | 23.66 (2.14) / 24.02 (2.15) |
| long reasoning math / code | 100.5, 98.6 / 84.9, 83.5 | 102.9, 101.0 / 82.9, 83.9 |
| switch test | 0 errors | 0 errors (back to A 0.74 s) |
| peak VRAM | 15,428 MiB | 15,428 MiB |

Checks on v0.1.22:
* **Accuracy:** teacher-forced math 0.2902 (before 0.2910), corpus 0.3870 (0.3884). On the five long texts it is now
  slightly *better* than llama.cpp (clipped, §5), where the older port was slightly worse. The new prompt attention
  rounds differently.
* **Chat-cache round trip:** exact again (§2a).
* **Layer split:** re-tested (§1b).

(The v0.1.22 series is kept in `patches/r5-v0122/`, and its build script in `work/r5/build-cstar5-v0122.sh`.)

### 1d. v0.1.23 and v0.1.24 (released 06:50 and 07:07): folded in, **v0.1.24 is the C\*5 base**

*(Your 07:55 message. My tag watcher had seen both at 07:27, but a sorting bug made it list ~20 old tags as "new" in
the same check and I missed the real ones; fixed. Notes: `work/r5/release-notes-0123-0124.txt`.)*

**v0.1.23**
* **#109 batches the verify window's per-token kernels:** router, norms, RoPE, shared-expert cast, gate and combine,
  bit-identical.
* **It contains both of our verify patches:**
  * only the CPU's expert rows are copied back over PCIe (our `0002`, draft 05);
  * the router and indexer q/k projections run as one multi-token GEMV (our `0003`, the one you called 0006).

  **Upstream's versions are kept, ours dropped.** With `--pcie-frac 0` (ours) the window also skips the PCIe wait.
* Also: llama.cpp-style endpoints (`/models`, `/props`, `/slots`, `/v1/status`, `timings`, `cached_tokens`), image
  requests honour sampling, 8 GB cards start, the page uses relative links (#82), `--dump-routing` under `--serve`
  (#118).

**v0.1.24**
* The QSA block-selection scores run on tensor cores (3xTF32), with the top-k in registers: the same selection, and
  scores differ in the last bits.

**The port:** our 8 remaining patches (side-stash, chat cache, chat list, shared-prefix checkpoint, web search, date,
Stop, two tabs) applied to v0.1.23 with three small conflicts, all kept on both sides:
* the side-stash hook next to the new decode timing;
* the page's relative links: our buttons and the web-status fetch were made relative too;
* the Stop fix next to #75's image sampling.

They then applied to v0.1.24 cleanly. Upstream's own server tests pass on the patched server (65 OK, 3 skipped).

| (fresh server, cold cache; 3 × v0.1.22 port, 2 × each new) | v0.1.22 port | v0.1.23 port | **v0.1.24 port** |
|---|---|---|---|
| 1K prompt / 68–87-token prompts | 0.98–1.00 / 0.47–0.49 s | 0.98–0.99 / 0.46–0.47 s | 0.98 / 0.46–0.48 s |
| 32K prompt | 10.38–10.41 s | 10.37–10.38 s | **10.05–10.09 s (−3 %)** |
| 64K prompt | 21.05–21.10 s | 21.02–21.07 s | **19.41–19.44 s (−8 %)** |
| 120K prompt | 42.67–42.71 s | 42.57–42.62 s | **36.67 s (−14 %)** |
| decode, all long requests (sampled; depends on draws) | 90.3 / 89.7 / 90.3 tok/s | 89.2 / 92.0 | 94.4 / 92.1 |
| ms per verify window (tokens per window) | 23.66–24.02 (2.14–2.17) | 23.10 (2.06) / 23.45 (2.16) | 23.63 (2.23) / 23.56 (2.17) |
| **exact decode, greedy math 1,024 tokens** (same acceptance) | 116.3 / 116.1 tok/s, GPU wait 11.2 ms | **120.0 / 120.7, GPU wait 10.5 ms (+3.4 %)** | 120.5 (= v0.1.23) |
| switch test / peak VRAM | 0 errors / 15,428 MiB | 0 / 15,416 | 0 / 15,416 |

**The checks you asked for before adopting v0.1.24:**
* **Harder needle set** (12 documents × 6 questions, 32K/64K/120K): **72/72**, as v0.1.22 and llama.cpp. First token
  at 120K after 37 s (v0.1.22 43 s, llama.cpp 140 s).
* **Long-text accuracy** (teacher-forced, clipped at 5 nats, vs llama.cpp on the same file): long16k +0.064,
  long24k −0.135, long28k −0.016, long40k −0.055, long64k +0.118, **mean −0.005** (v0.1.22 −0.052, v0.1.20/21 +0.023).
  Short texts unchanged. Against v0.1.24 with the old selection switched on, the new selection moves the long texts
  by −0.012 … +0.118 (57–90 of 1,536 tokens flip by more than 1 nat). That is the same size as other last-bit changes:
  v0.1.22's attention kernel moved them by −0.01 … −0.11, and llama.cpp's own batch size (2048 vs 4096) moves
  long16k by +0.09. **Still level with llama.cpp.**
* **v0.1.23's numbers equal v0.1.22's.** v0.1.24 with the old selection (= v0.1.23 arithmetic) reproduces the v0.1.22
  port **bit for bit on 6 of the 7 texts**, so upstream's batching gives exactly the numbers our patches gave. The
  exception is the 1,536-token corpus text (6-token windows), where from token 469 on 103 tokens differ by more than
  0.01 nats (mean −0.0005). That is rounding-level, and I noted it for Round 6.
* **Chat-cache round trip on v0.1.24:** exact again (0 changed tokens, all 1,536 NLLs identical, drafter identical,
  state identical after park → resume and after resume + edit).

**`--dump-routing` under `--serve` (#118), for Round 6:** it now records the speculative path. The hook sits in the
verify-window dispatch and writes one record per verify row. That includes rows of drafts that are then rejected
and verified again in the next window, so some positions are counted twice. Weights are unit (written as zeros),
decode only (no prompt path), flushed at every request. Usable for routed-frequency profiles, not as an exact
per-token trace.

### 2. Correctness
**a) The chat cache round-trips exactly.** Method (`work/r5/roundtrip.py`, `rt_compare.py`): a measurement-only build
(`r5-meas`: an engine key that teacher-forces fixed tokens through the normal serve path and logs, per token, the NLL
and the argmax, plus the drafter's guesses after every window; server fields to send those tokens) with
`--adapt-swaps 0` and the engine's own `STATE_HASH` fingerprint of the whole session after each request. A chat is built
turn by turn as a client sends it (fixed assistant texts), then the **same 1,536 tokens** (a sampled continuation of that
chat) are forced three ways, each against a fresh server that reads exactly the same tokens from the same checkpoint:

| chat | comparison | tokens with a different argmax | NLL identical | drafter guesses different | session state (hash) |
|---|---|---|---|---|---|
| 5.8K tokens | direct vs direct (the residual of a static expert set) | 0 | 1,536 of 1,536 | 0 of 385 windows | identical |
| 5.8K | parked behind a 64K paste in chat C + a short chat B, then resumed, vs direct | **0** | **1,536 of 1,536** | **0 of 385** | identical (GDN, PLE, tails, indexer rows, KV, drafter ring) |
| 5.8K | resumed, then turn 2 edited, vs the same edit read directly | **0** | **1,536 of 1,536** | **0 of 385** | identical |
| 39.7K | direct vs direct | 0 | 1,536 | 0 of 385 | identical |
| 39.7K | parked → resumed vs direct | **0** | **1,536** | **0 of 385** | identical |
| 39.7K | resumed + edit vs the edit read directly | **0** | **1,536** | **0 of 385** | identical except drafter-ring cells outside its window* |

The residual of a static expert set is exactly 0 here (teacher forcing is deterministic), and every parked state — the
drafter ring, the indexer's pooled rows and block positions, the KV host copies — comes back bit for bit. (*The only
hash differences are cells past the end of the conversation, which nothing reads, and in the 40K edit case drafter-ring
cells the drafter never looks at: its guesses match in all 385 windows.) Nothing needed fixing. **Repeated on v0.1.22 and on the final v0.1.24 base** (5.8K chat, 1,536 forced tokens each):
parked→resumed and resumed+edit again 0 changed tokens, all 1,536 NLLs identical, drafter guesses identical, state
identical.
**b) Sampling follows the distribution: no sampler bias.**

*Method* (`work/r5/sampling_probe.py`):
* **Prompts:** the three near-tie prompts from `results/tie_probe_B_C0.md` (arith, code, science), each placed so the
  tie token is either the first token of a verify window (**j0**: plain sampling, no drafts) or the 4th token of a window
  reached through three accepted drafts (**j3**: tests the speculative accept rule).
* **Samples:** 1,000 each through the server, at T 0.6 (the configs' default) and at T 1.0 (your setting), with the full
  chain (top_p 0.95, top_k 20, min_p 0.05). 9,000 requests in all.
* **Reference:** llama.cpp's probabilities for the same token ids from the same IQ3_S file, put through the same
  sampler chain.
* **Second reference:** Strata's *own* probabilities for each candidate, measured by forcing each of llama.cpp's top-30
  candidates three times. This separates the sampler from the logits.

| case | on the tie path (expected) | vs llama.cpp: χ² (dof), p | vs Strata's own probabilities: p |
|---|---|---|---|
| arith j3, T 0.6 / j0 T 1.0 / j3 T 1.0 | 954 (947) / 1000 / 871 (850) | 0.02 (1) p 0.90 / 0.00 p 0.98 / 0.53 p 0.47 | 0.34 / 0.56 / 0.23 |
| code j3, T 0.6 / T 1.0 | 125 (137) / 128 (120) | 2.49 (4) p 0.65 / 1.25 p 0.87 | 0.99 / 0.85 |
| code j0, T 1.0 | 1000 | 25.8 (8) **p 0.001** (' enough' 296 vs 253, ' complete' 237 vs 269) | 0.013 |
| science j3, T 0.6 / T 1.0 | 782 (811) / 573 (588) | 14.3 (3) **p 0.003** / 6.73 p 0.08 | 0.82 / 0.028 |
| science j0, T 1.0 | 1000 | 19.2 (3) **p < 0.001** (',' 433 vs 378, '.' 110 vs 146) | 0.036 |

No sample ever fell outside the allowed set (top-k / top-p / min-p).

*The deviations from llama.cpp are not a sampler bias.* They appear as much in the j0 cases, where no speculation is
involved, as in the j3 cases. They disappear against Strata's own probabilities. The remaining p = 0.01–0.04 are within
what the reference's own uncertainty explains: Strata's probabilities move ±0.02 between repeats because of adaptive
expert placement, which inflates χ² by about 1.5×.

What differs is **Strata's logits at a near-tie**: at the science tie Strata gives ',' 0.402 and ';' 0.397, llama.cpp
0.369 and 0.417. That is a log-odds difference of 0.13 nats, rounding-level (GPU vs CPU expert arithmetic). The
teacher-forced scores (§5) show it does not add up to an accuracy difference.

*The accept rule (read in the verify code) is the exact standard speculative rule:*
* Each verify row samples its own token with the full chain from its own logits, using Philox(seed, position).
* The server loop accepts drafts while the drafted token equals the row's sample, and emits the first mismatch as the
  target's own draw.
* The MTP drafter proposes its argmax (`sp.greedy = true`), so its proposal is a point mass. With a point-mass proposal,
  sample-and-match is exactly "accept d with probability p(d); on rejection, draw from p without d", the standard
  accept/resample rule.
* Each position uses one uniform; a rejected row's draw never decides a kept token.

Nothing to fix.

**c) The old "GPU hit path is NOT CORRECT" warning is gone — question closed.** It is printed by v0.1.6 and v0.1.7 only;
upstream removed it in **v0.1.8** (commit f81df95, issue #23: "the warning outlived the fault") and prints instead that
the GPU rounds differently from the CPU (its own teacher-forced check: 95–98 % same top-1, perplexity on − off
= −0.005 ± 0.005 nats). None of C\*–C\*5's logs contain it. Independent evidence here: the round-trip test above
(bit-exact), and the teacher-forced scores against llama.cpp on the same file (§5: short texts within +0.001–0.003
nats; llama.cpp computes the experts on the CPU, Strata mostly from its GPU cache).

### 3. Web search in the chat page
**How to use it.** In the chat page, click **Web search** (the globe button next to the settings button, under the
message box). It turns green when on and stays on for later messages until you click it again. With it on, the model decides by
itself when to search; each search and each page it opens appears as a small card in its answer (click a card to see
the query or URL and exactly what the model read), and the answer cites the URLs it used. **Stop** works during a
search or a page download. The switch only appears when the running config has web search (C\*5 has) and the local
search service answers; `./switch-model.sh strata` (and `run-strata.sh`) start that service automatically and stop it
with Strata. By hand: `websearch/searxng.sh start|stop|status` (127.0.0.1:8888 only). Switching web search on or off in
the middle of a chat makes the next message read that chat again once (the tool descriptions sit at the start of the
prompt); with the chat cache, switching back finds the other version parked.

**What was built.** Upstream's v0.1.19 MCP support already contains a server-side tool loop (tool cards in the page,
Stop cancels a running call, a round limit) — I plugged a built-in, per-request "hub" into it, so the loop is
upstream's: `serve/websearch.py` (standard library only) with two tools, `web_search` (titles, URLs, snippets from
SearXNG's JSON API) and `fetch_page` (the page's readable text: scripts, styles, navigation, menus and cookie banners
dropped, the article part preferred, trimmed to 12,000 characters, `start=` to read further), and the switch in the
page. Patches `patches/r5/0005` + `0006` (date, `www.`); PR draft `pr-drafts/13-web-search.md`.

**Search backend:** SearXNG from source (git 12f8b65) in its own venv in the workspace (`websearch/`), no Docker, no
sudo, served by granian on **127.0.0.1:8888**, rate limiter and Valkey off (single user), JSON output on. DuckDuckGo
is switched off (it answers this address with a CAPTCHA) and two Tor-only engines are inactive; Brave and Google (CSE)
answer.

**Reliability over the round:**
* **Searches through SearXNG:** 16 of 16 in the scripted tests (median 0.96 s, max 2.2 s) and **295 of 295** in the
  soak's 48 web chats. Another 26 were cut short by Stop, and none failed. DuckDuckGo stays off because it answers this
  address with a CAPTCHA.
* **Page downloads fail more often:** 22 of 31 succeeded in the tests, 24 of 96 in the soak. The soak does not log the
  reasons. In the tests they were sites refusing automated clients (HTTP 403), dead links (404), and the allow-list
  refusing URLs the model had not seen in a search result. The model then answered from other results or said it
  could not open the page.
* **No API key is needed for searching.** If the free engines ever start refusing, the simplest replacement is a Brave
  Search API key: SearXNG's `braveapi` engine takes it as `api_key` in `websearch/settings.yml`.

**Safety rules the tools follow.** They only send GET requests — the search query to SearXNG, and page downloads;
nothing is written, nothing is started, no cookies or credentials are sent, and only text comes back (PDFs/images are
refused). Page text reaches the model inside the tool result, marked as untrusted data. `fetch_page` opens only public
http/https addresses (it refuses 127.0.0.1, your LAN, link-local etc., connects to the exact address it checked so a
DNS trick cannot redirect it, and checks every redirect), and **only URLs that appeared in this chat's search results or
in your own messages** — so text on a web page cannot get the model to send your conversation to an address of its
choosing. The one remaining channel is a search query itself (it goes to the search engines). MCP servers stay off
(no `mcp_servers` in the config), so no tool can run commands.

**Tests** (`work/r5/webtest.py`: requests exactly like the page's with the switch on, your settings; results
`results/r5/webtest.jsonl`; engine = the v0.1.21 port, the base at the time; the web-search code is unchanged since):

| question | time | tool calls | result |
|---|---|---|---|
| latest stable Linux kernel and its date | 18–19 s | 2 searches, 2–3 pages (kernel.org, endoflife.date) | "7.2.8, released 2026-09-25" — correct (kernel.org's table), sources cited |
| two main world headlines today | 25 s → 40 s | 11 (4 searches, 7 pages; AP refused bots: HTTP 403) | first run: **the model assumed the date was July 28** and reported July news → fixed by giving it today's date in the tool description; second run: two stories of Sep 28–29 with 6 sources |
| newest Python 3 release and a notable change | 23–26 s | 2 searches, 3–4 pages (python.org, docs) | "3.14.7, released Aug 5 2026", change cited from docs.python.org |
| follow-up in the kernel chat ("is it LTS?") | 4 s | 0 | correct (the LTS trees listed), from the earlier tool results |
| Stop while a tool call runs | – | – | the answer stops at once; the next request 1.0–1.1 s |
| **guard:** "open iana.org's about page directly" (no URL given) | 12 s | 3 × fetch_page, all refused | the model tried `https://www.iana.org/about` and two variants; all refused ("only URLs from this chat's search results or your messages"); it said so honestly |

Two fixes came out of the first run and are in C\*5: **today's date in the search tool's description** (the model
cannot know it), and `www.` treated as the same site as the bare host (the first run refused `https://kernel.org/`
because the result said `www.kernel.org`). The allow-list is deliberately strict: a page the model merely knows (a
homepage) is opened only after a search returns it or you paste it — in practice it searches first. A follow-up after a
web-search answer reads the tool results again once (~4K tokens, ~2 s: the template drops the earlier turn's reasoning,
as after any answer). The switch was also tested in the real page, in headless Chrome (§4, browser test): shown, on,
three tool cards, cited answer, cards kept after a reload, follow-up, Stop during a tool call, off.

### 4. Failure modes and the browser
Scripts: `work/r5/failures.py` (API-level, like the page) and `work/r5/browser_test.py` (your installed Chrome run headless
from a fresh profile in `tmp/r5/`, driven over DevTools on 127.0.0.1). Run on the v0.1.21 port; the server-side fixes
carried over to v0.1.22 unchanged, and the VRAM test was repeated on v0.1.22 (below).

| failure mode | result |
|---|---|
| **Stop during a prompt read** (120K paste, Stop at 20 s, next request, back to a parked chat) | **bug found and fixed.** Stop reached the engine 2–3 prompt chunks late (the server only noticed the closed connection when a write failed, and it writes once per ~4 s chunk; the second write is usually the first to fail): the 120K read went on until 30.5 s, a 32K paste stopped 6 s in was read to the end (15.6 s). The next request (0.74 s) and going back to the parked chat (0.38 s, 5,629 tokens reused) were fine. Fix: the server now watches the connection while it streams and sends STOP the moment you press Stop (only for the running request). **After the fix: the server is idle 3.0 s after Stop** (was 11.0 s; the read stops within the chunk in progress), next request 0.73 s, back to the parked chat 0.38 s. |
| **Context overflow** — a chat longer than the context | clean **HTTP 400 in 0.2 s** ("prompt (134078 tokens) leaves no room to answer in the context (131072); requests are never truncated"), streamed or not; the page shows it as an error message; the next request is normal |
| — an uncapped reasoning answer that reaches the ceiling (127K prompt) | ends cleanly with **finish "length"** after 3,812 tokens (59 s), no hang; next request normal |
| **Two requests at once** (a second while the first streams; two at the same moment) | both complete; the second waits in the server's queue (status: busy, queued 1) |
| **The page open in two tabs** | sending from both at once works (queued); **the chat-list bug is confirmed** (a chat started in tab 2 vanished from the list when tab 1 saved) → **fixed** (round 4's prepared fix, applied: the list is re-read before every change and on the browser's storage event). After the fix both tabs keep each other's chats (browser test). |
| **VRAM taken after start** | **weakness found and fixed.** With the model loaded (fresh start), a second program took all but ~30 MiB of the 5080's free VRAM, then a 120K paste: the engine stopped mid-request (`out of memory` while loading the prompt path's matrix kernels / allocating their GPU memory pool — both happen on the first long prompt; that is also why free VRAM always drops by ~116 MiB after the first request). The server handled it cleanly (an error message, "the next request restarts it"; the restart took 13 s and answered), but it broke the request. Upstream's EAGER kernel loading does not help (tested: the memory pool is still allocated late). **Fix: a warm-up at start** — `run-strata.sh` sends one ~9K-token prompt right after loading (≈4 s), so kernels and pool are in place before anything else can take the VRAM. With it, the same test **completes the 120K prompt normally with only 32 MiB VRAM free** (65 s), and the next request answers in 1.1 s. | |
| **Idle CPU** | the engine uses **0.08 % of one core** while idle (60 s, 91 threads, the busiest 0.03 %) — no pool worker spins; the server 0.75 % |
| **Browser test** (drawer, chat list, switching, New chat, delete + Undo, attach + reload, Stop, two tabs, web search) | **54 of 56 checks pass** on the final code (`results/r5/browser-test-b3.json`, screenshots `logs/r5/browser/`): the drawer (High / 0.60 / 0.95 / 20 / empty max tokens, "use for other apps too" on), chat list, switching, New chat keeps the old one, delete + Undo (also across a reload), attach a file → reload → the model still sees it (the history reused from the cache), Stop during an answer (0.00 s) and **during a 32K prompt read (server idle 2.0 s later)**, two tabs (list kept; both sending at once), and the web-search switch (shown, on, three tool cards, cited answer, cards survive a reload, follow-up, Stop during a tool call, off). The two non-passes are not bugs: a 110-token chat is not kept in the chat cache (under 512 tokens re-reading costs 0.4 s, by design), and the browser's automatic request for `/favicon.ico` gets a 404. |

**Re-checked on the final C\*5 build (v0.1.24 + patches, 09:33–09:45; `logs/r5/batch.log` FAIL9–FAIL12):**
* **VRAM taken after start:**
  * Without the warm-up, the 120K prompt still aborts the engine. v0.1.24 fails in ggml's memory pool (`cudaMalloc`
    in `ggml_cuda_host.cu:62`); v0.1.21 failed at `cudaFuncSetAttribute`. The server recovers cleanly and the next
    request answers in 13 s.
  * With the launcher's warm-up, the same 120K prompt completes with 32 MiB free (39 s), next request 1.2 s.
  * So the warm-up stays, and PR draft 15 still applies.
* **Stop during a 120K read:** closed at 20.2 s, and the engine stopped the read at 20.7 s ("cancelled"). The server was
  idle 1.0 s after Stop, the next request answered in 0.73 s, and going back to the parked chat took 0.36 s.
* **Overflow:** HTTP 400 in 0.3 s, streamed or not. An uncapped answer at 127K ends at the ceiling with "length"
  (52 s).
* **Two requests at once:** both complete (the second queued).
* **Idle CPU:** engine 0.08 % of one core.

### 5. Quality and long documents
All on the same IQ3_S file, your chat settings sent explicitly to both engines (temperature 1.0, top_p 0.95, top_k 20,
min_p 0.05; each server's default reasoning), Strata = the v0.1.22 port (the base at the time; the needles and the
long-text scores were repeated on v0.1.24 and with v5, §1d/§6), llama.cpp = 6fcaa16 with the memory guard. `~/ai-speed-testing/my_tasks/` does not exist, so the set is the five prompts of `eval_prompts/`.

**Quality, graded blind** (5 prompts × 3 sampled runs per engine, 32,768-token cap). `work/r5/quality_blind.py export`
put the 30 final answers under random labels A–F per prompt (`results/r5/blind/`), with the key in a separate file
(`results/r5/blind-key.json`) that I did not open until all 30 scores were written. Each answer was scored out of 20
with `GRADING_KEY.md`, final answers only. Per-answer reasons: `results/r5/blind-grading-notes.txt`; scores:
`results/r5/blind-scores.json`.

| prompt (out of 20) | Strata: mean (runs) | llama.cpp: mean (runs) |
|---|---|---|
| 01 security incident | 19.3 (19, 19.5, 19.5) | 19.0 (18.5, 20, 18.5) |
| 02 network troubleshooting | 13.3 (20, 20, **0**) | 13.0 (**0**, 20, 19) |
| 03 CCNA tutor | 19.3 (19, 20, 19) | 19.5 (19, 20, 19.5) |
| 04 local AI performance | 19.3 (20, 18.5, 19.5) | 19.7 (20, 19.5, 19.5) |
| 05 patch policy | 19.2 (19, 19.5, 19) | 19.2 (19, 19.5, 19) |
| **total out of 100, mean ± sd over the 3 runs** | **90.5 ± 12.6** (76, 97, 98.5) | **90.3 ± 12.0** (76.5, 97, 97.5) |
| the 14 answers that finished, mean ± sd per answer | 19.39 ± 0.49 | 19.36 ± 0.53 |

**Same quality.** Each engine lost one prompt-02 answer because the reasoning ran into the 32,768-token cap before
any answer (scored 0). That happens at temperature 1.0 on this prompt with either engine, and it is the whole of the
large spread. The finished answers differ only in small things: a quiz whose answers are all "B", a /26 block listed
as 192–223, an ACL sequence number in the wrong place, the actual-task time for one configuration left out, evidence
imaging placed before killing the live VPN session. These appear on both sides.

Same work, different wait: the 15 answers took **68 min on Strata vs 167 min on llama.cpp** (mean 22.6K vs 22.7K
generated tokens; 82.7 vs 34.3 tok/s at temperature 1.0).

**Accuracy on long texts** (teacher-forced, from the existing `.nll` files; `results/r5/nll-clipped-table.md`). The plain
mean NLL on the long texts is dominated by a few "flip" tokens, copied text scored ~0 by one run and 8–14 nats by
another. So I also report the NLL clipped at 5 nats and the top-1 agreement. C\*5 (v0.1.22 port) minus llama.cpp,
clipped, paired over the same tokens:

| text | long16k | long24k | long28k | long40k | long64k | mean |
|---|---|---|---|---|---|---|
| C\*5 (v0.1.22) − llama.cpp | −0.054 ± 0.014 | −0.123 ± 0.018 | −0.044 ± 0.016 | −0.109 ± 0.019 | +0.071 ± 0.014 | **−0.052** |
| C\*4 / v0.1.20–21 port − llama.cpp | +0.019 | −0.013 | +0.050 | −0.022 | +0.080 | +0.023 |
| top-1, C\*5 vs llama.cpp | 0.613 / 0.598 | 0.547 / 0.516 | 0.666 / 0.658 | 0.495 / 0.473 | 0.494 / 0.505 | |

Short texts: math +0.002, corpus +0.001 (clipped, vs llama.cpp). Strata is not worse than llama.cpp on long documents,
and v0.1.22's tensor-core prompt attention did not hurt.

**Harder needle set** (`work/r5/needle2.py`: 12 documents × 6 questions per engine at 32K/64K/120K, 4 runs each, depths
spread 7–94 %). The questions: a 3-hop chain (device → technician → lab → door code), a 2-hop chain, two
"one-digit twin" questions (the document holds near-duplicate serials that differ in one digit), and two "which of these
two sentences/lines is in the document" questions where the wrong one differs by one digit.

| question | L5 32k | L5 64k | L5 120k | S5 32k | S5 64k | S5 120k | L5 all | S5 all |
|---|---|---|---|---|---|---|---|---|
| 1. 3-hop (device → technician → lab → door code) | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | **12/12** | **12/12** |
| 2. 2-hop (project → budget holder → extension) | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | **12/12** | **12/12** |
| 3. one-digit twin: serial of a unit | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | **12/12** | **12/12** |
| 4. one-digit twin: unit of a serial | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | **12/12** | **12/12** |
| 5. which sentence is in it (memo, one digit changed) | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | **12/12** | **12/12** |
| 6. which line is in it (corpus line, one digit changed) | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | **12/12** | **12/12** |
| all six | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | **72/72** | **72/72** |
| time to first token (mean) | 37 s | 72 s | 140 s | 10 s | 21 s | 43 s |  |  |

**Both engines 72/72**, no cut or failed answers. Strata reached the answer 3.3–3.6× sooner.


### 6. Speed extras and soak
**Hyper-connection kernels v5 (round 4: +2.3 % decode, left out of C\*4 for lack of a sampled screen and a soak):
now in C\*5 (patch 0009).**

| | exact greedy profile (math, 1,024 tokens) | sampled screens: time per verify window | sampled: all long requests |
|---|---|---|---|
| v0.1.22 port / + v5 | 116.3 / 117.8–118.3 tok/s; GPU wait 11.2 → 10.1–10.3 ms | 23.66–24.02 → 23.14 / 23.54 ms | 89.7–90.3 → 93.3 / 93.2 tok/s (+3.4 %) |
| **v0.1.24 port / + v5** | 115.7 → 120.4 / 122.7 tok/s (+4 %, same acceptance group); GPU wait 10.3–10.5 → 9.5–9.6 ms | **23.54–23.63 → 22.41 / 22.34 ms (−5 %)** | 92.1–94.4 → 95.0 / 94.3 (v5 runs drew lower acceptance) |

The gain survives upstream's #109 batching, which also sped up the same part of the window.
* **Accuracy on v0.1.24** (teacher-forced, clipped): short texts −0.001 / +0.0005 nats; long texts −0.121 … +0.013
  (mean −0.034); vs llama.cpp mean −0.039.
* **Needle set:** 72/72.
* **Prompts:** unchanged.
* **Switch tests:** 0 errors.
* **Soak:** passed (below).
* **Rollback:** `STRATA_GR_OLD=1` in the config's `env` switches back to the old kernels in the same binary.

The v5 `down` kernel adds its 4 partial sums in a fixed order: deterministic, but not bit-identical to the old kernel
(max 1.2e-4 relative). I made its shared-memory setup per device, like upstream's, so a layer split would also work.

**How long decode needs to reach speed after a fresh start** (`work/r5/steady.py`: fresh server without the warm-up,
the 6,144-token math prompt three times):
* The runs averaged **107.7 / 109.6 / 108.7 tok/s**, so the first run is only 1–2 % slower.
* Only its first 256-token block is clearly low: 97 tok/s vs ~112 later (about 100 windows).
* Block-to-block noise is ±10 %, so there is no sharper point to name.

The start-up profile fills the expert cache before the first request, and the adaptive tier only fine-tunes it.

**2-hour big-chat soak on the final build** (port 8080 as you use it: `./switch-model.sh strata`, warm-up, SearXNG,
your settings temperature 1.0):

**330 requests in 2.00 h (09:46–11:46), 0 errors.**
* **Traffic:** 43 new chats with a pasted 32K/64K/120K document, 80 returns to an earlier big chat, 55 web-search chats
  and follow-ups, 40 follow-ups, 33 short chats, 21 long-reasoning requests, 17 regenerates, and Stop pressed 136
  times.
* **Back to a big chat that was still parked** (57 times, 33K–124K tokens): median 0.83 s, max 4.2 s.
* **Back to one the chat cache had dropped** (23 times, it holds 6 chats / 16 GiB): median 10.9 s, max 37 s, i.e. read
  again.
* **New chat with a pasted document:** 32K ~10 s when read fresh, 64K 19.2 s, 120K 34.2 s.
* **Probe every 10 min** (a fresh 32K read + 512 tokens): 9.95–10.0 s to the first token, decode 80–94 tok/s (your
  temperature 1.0). It showed no drift over the two hours.
* **Memory:** MemAvailable never below 26.0 GB, so `--chat-cache-mib` stays at 16,384 (your rule was to lower it below
  20 GB). Engine RSS 50–60 GB, no swap, VRAM 15,388–15,410 MiB used. The chat cache's peak was 10.5 of 16 GiB, never over
  budget.
* **Engine log:** no error lines. The 6 matches are the start-up "no error" lines.

v5 thereby passed its soak.



### 7. Uptime
**Skipped on your instruction (10:20):** the uptime watch runs after Round 6, on the final build. The script is ready:
`work/r5/uptime.py --until HH:MM` probes 127.0.0.1:8080 every 15 minutes (a small request, plus a search through
SearXNG). Each probe logs RSS, open files, log sizes, first-token latency after idle, idle CPU, VRAM, MemAvailable, new
error lines and other processes on the 5080 to `logs/r5/uptime.csv`.

### Not done / open for Round 6
* **Uptime run** (Phase 7), as above.
* **Headless-browser test on the v0.1.24 build.** It last ran on the v0.1.21 port (54/56 passed). On the final build I
  checked the page files over HTTP (all load with 0.1.23's relative links; our icons are there; `/web` reports SearXNG
  reachable) and ran the page logic test (15/15), but not the full Chrome test with the drawer, tabs, Stop and web
  cards. Run `work/r5/browser_test.py --tag b4` first.
* **v0.1.23's batched verify window is not bit-identical in one case:** the corpus text, with 6-token windows. 103 of
  1,536 tokens differ by more than 0.01 nats, mean −0.0005, so it is harmless. Find which batched kernel it is, then
  report it upstream (PR draft item 20).
* **`--dump-routing` (#118):** usable for routing-frequency profiles, with caveats. It counts rows of rejected drafts,
  and a re-verified position is counted twice. Its weights are unit, and it records decode only. A Round-6 profile
  should record the accepted positions only.
* **Still open upstream** (drafts written, nothing posted):
  * EAGER loading costs ~250 MiB VRAM (draft 12).
  * The first long prompt allocates GPU memory mid-request (draft 15; our warm-up covers it).
  * setup.py moves the model files of `strata*` folders (draft 11).
  * No min-p in the page's settings (draft 08).
* **Dual GPU, if ever revisited:**
  * The helper mode's 8 GiB pinned-memory limit ("mlock failed, raise ulimit -l") would need a system change (limits),
    so I did not try it.
  * A second card with more VRAM, or an x8/x16 slot, would be needed for the helper mode to have a chance.
  * The layer split cannot work with an 8 GB second card.



### Files, state, rollback
**Running now:** Strata C\*5 on http://127.0.0.1:8080 (started with `./switch-model.sh strata`), and SearXNG on
127.0.0.1:8888, which the launcher starts and stops with Strata. Restarted clean at 11:48 after the soak (warm-up 3.5 s,
test answer 0.5 s, 500 MiB VRAM free, 37 GB MemAvailable). No test scripts, probes, queues, tag watcher or monitors of
mine are running.

| what | where |
|---|---|
| C\*5 config (the default for `./switch-model.sh strata` and `./run-strata.sh`) | `configs/Cstar5.json` (+ `configs/Cstar5.shared-settings.json`) |
| C\*5 engine / server + web app | `engine-cstar5/strata` (v0.1.24 + `patches/r5/0001–0009`, sha256 `3ee92c9a…`, source tree identical to the tested branch) / `strata-cstar5/serve/` |
| rebuild C\*5 from scratch | `work/r5/build-cstar5.sh` (clean clone of `strata/`, checkout v0.1.24, `git am patches/r5/0*.patch`, build); older series in `patches/r5-v0122/` (+ `work/r5/build-cstar5-v0122.sh`) and `patches/r5-v0121/` |
| web search service | `websearch/` — `searxng.sh start`, `stop`, `status`, `settings.yml`, the SearXNG source and its venv |
| warm-up at start (keeps a long first prompt safe) | `scripts/strata-warmup.py` (called by `run-strata.sh`) |
| second-GPU pinning | every Strata config sets `CUDA_VISIBLE_DEVICES` to the 5080's UUID; `switch-model.sh` pins signal-next the same way (override with `STRATA_GPU_UUID=…`) |
| earlier launchers / configs | `work/r5/switch-model.sh.orig`, `work/r5/run-strata.sh.orig` (and `.before-pgrepfix`), `work/r5/configs-orig/`, `work/r5/Cstar5.json.v0122` |
| launcher fix (11:45) | `run-strata.sh` now counts only real model servers as "another server is running" (it had matched a monitoring tool whose command line named `strata --serve`) |
| switch back to the old hyper-connection kernels | add `"STRATA_GR_OLD": "1"` to `env` in `configs/Cstar5.json` |
| round-5 results and logs | `results/r5/`, `logs/r5/`, day log in `NOTES.md` ("ROUND 5") |
| PR drafts | `pr-drafts/` (items 11–20 are new; items 1, 5 and 9 are now fixed upstream; `pr-drafts/patches-r5/` is the v0.1.24 series) |

**Rollback to round 4's C\*4** (v0.1.15, no web search): `STRATA_CONFIG=configs/Cstar4.json ./switch-model.sh strata`.
C\*4 is kept as it was, apart from the 5080 pin.

