

## Round 4 — Strata v0.1.15, llama.cpp accuracy reference (2026-09-28)

**Result: C\*4 = Strata v0.1.15 + 6 of C\*3's patches, now on 127.0.0.1:8080** (`./switch-model.sh strata`, default of both
launchers; `STRATA_CONFIG=configs/Cstar3.json` rolls back). It reads prompts **~10 % faster** than C\*3 (120K: 62 s instead
of 68.5 s; 32K: 15.7 s instead of 17.5 s; 1K: 1.1 s instead of 1.4 s), decodes at the same speed, passes the accuracy check,
and found **45 of 45** buried numbers and names at every depth of 32K/64K/120K documents. Against llama.cpp on the same
IQ3_S file, Strata's long-document perplexity is not clearly worse: both engines move by the same amount when only their
own chunk size changes.

**Not done, and why — please read:** items 3 (browser test) and 4 (2-hour soak) did not run, and the deadline was missed.
From 08:57 to 17:10 my session was stalled: the tool-permission check kept returning errors with a growing retry delay,
and nothing ran in those 8 hours (the PC itself stayed on — the system journal shows cron, sysstat and WiFi activity the
whole time; nothing was suspended). When the session resumed at 17:10 I stopped all tests and only did the wrap-up
(clean build, config, 8080, this report). **C\*4 has therefore not had the long soak** — it served ~70 test requests (four
screens incl. 120K prompts, two chat-switch tests, the needle runs) with 0 errors, and the chat-cache code is the same
patch as C\*3's (soaked in round 3), but if anything misbehaves, roll back to C\*3 with the command above.
Also this morning, at 08:32, **my llama.cpp scoring job ran the PC out of RAM** (details under item 2): the kernel killed
only that process, your desktop/Chrome/Open WebUI kept running, ~1.7 GB of other programs' memory was paged to swap.

### 1. Update to v0.1.15 and A/B against C\*3
Three releases since v0.1.12, all this morning: **v0.1.13** (prompts ~2× faster on 12 GB cards: chunks up to 8,192 tokens
chosen automatically, llama.cpp's MMQ kernels for the prompt's experts, the next layer's experts streamed during the
current one, the layer-1 n-gram block batched, the next chunk's n-gram rows read ahead; stall reports), **v0.1.14** (IQ-model
stall fix: the PCIe share copied by a GPU kernel; Linux: one pool worker per physical core; setup fixes), **v0.1.15** (all
kernels loaded at start). Diff reviewed as usual → `results/security-review.md` (round-4 addendum): benign, no new network
code or download sources. Built from source in `strata-v0115/` with its own `setup.py` (`--build --kv int8
--experimental-speed-projection off`; nothing downloaded; the model pack it wrote is byte-identical to v0.1.11's).

| C\*3 part | in v0.1.15? | C\*4 |
|---|---|---|
| parallel n-gram reads (patch 0001) | no — still one synchronous read per row | **kept**: without it 32K takes 21.7 s instead of 15.7 s, 1K 1.6–1.8 s instead of 1.1 s |
| batched layer-1 n-gram block (0003), next chunk's rows read ahead (0004) | yes (v0.1.13) | **upstream's** (ours dropped) |
| `--pool-workers 15` (Linux core count) | yes, physical cores (v0.1.14) → 15 workers here | **upstream's default** |
| `--prefill 8192` | `--prefill auto` picks 8,192 here | **upstream's `auto`** |
| chat cache (0002 + 0007), chat list (0008), decode patches (0005, 0006) | no | kept (applied cleanly) |

Two upstream defaults do not suit this PC:
* **v0.1.15 loads every CUDA kernel eagerly, which costs ~300 MiB of VRAM here.** cuBLAS then loads all its kernels when the
  prompt path starts — after the expert cache has already taken the free VRAM — leaving 321 MiB free after load and **220 MiB
  after one request, below your 300 MiB floor** (Chrome open). C\*4 sets `CUDA_MODULE_LOADING=LAZY` (CUDA's default, what C\*3
  ran with): 568 MiB free after load, ~450 at peak. Upstream added eager loading for IQ3_XXS on 12 GB cards; it is not needed here.
* v0.1.14's `--pcie-mode kernel` adds two no-op kernels per layer with `--pcie-frac 0`; measured: no cost
  (114.9 vs 113.0–114.0 tok/s for `dma`), so upstream's default stays.

A/B, alternating C\*3 / R4 (= C\*4) twice, fresh server and cold page cache each time, your sampling from the config
(`work/r4/screen.sh`; decode = 768 tokens after each prompt). Today every arm has ~100 fewer VRAM cache slots than in
round 3, because Chrome is open.

| | C\*3 (2 runs) | C\*4 (2 runs) | change |
|---|---|---|---|
| time to first token, 1K prompt | 1.38 / 1.37 s | **1.13 / 1.14 s** | −18 % |
| 32K prompt | 17.53 / 17.51 s | **15.74 / 15.72 s** | −10 % |
| 64K prompt | 35.17 / 35.19 s | **31.64 / 31.63 s** | −10 % |
| 120K prompt | 68.52 / 68.53 s | **61.95 / 61.88 s** | −9.6 % |
| decode after 32K / 64K / 120K (single sampled runs, ±7 %) | 80.0, 89.0 / 78.6, 75.0 / 85.4, 77.9 | 77.0, 79.5 / 73.5, 78.7 / 85.5, 84.4 | = (noise) |
| decode, all long requests (engine) | 88.8 / 88.3 tok/s | 89.3 / 88.7 tok/s | = |
| long reasoning 8K tokens: math / code | 99.4, 100.6 / 83.4, 81.9 | 100.9, 100.3 / 84.4, 83.3 | = / +1.5 % |
| exact decode profile (greedy windows, repeatable): math / at 32K depth | 111.3, 112.8 / 92.5 tok/s | 114.9, 114.9 / 93.4 tok/s | +2 % / +1 % |
| going back to a 40K chat after a 64K paste elsewhere (switch test) | 0.52 s | 0.53 s | = |
| the 64K paste itself | 35.0 s | 31.5 s | −10 % |
| peak VRAM used (with Chrome) | 15,379 MiB | 15,407 MiB | +28 MiB (~450 MiB free) |
| requests / errors (screens + switch tests) | 0 errors | 0 errors | |

**Accuracy** (teacher-forced NLL, same method as round 3, `results/tf-R4tf-*`): C\*4 − C\*3 = +0.0010 ± 0.0006 (math) and
−0.0024 ± 0.0017 (code + licence text) nats/token — the usual size; on the long texts +0.13 / +0.07 / +0.30 (16K / 24K / 64K),
inside the spread measured below. C\*4 is deterministic (two runs identical). **Criteria met → kept as C\*4.**

### 2. Long-document accuracy against llama.cpp (same IQ3_S file)
**Reference:** signal-3.8-opus's llama.cpp build (6fcaa16, has the sparse-attention prefill fix) run as-is. That build has
no `llama-perplexity`, so I compiled a small scorer in the workspace (`work/r4/llama_tf.cpp`) against *its* `libllama.so` /
`libllama-common.so`, with llama-server's flags for this model (experts in RAM, n-gram table lazy, q8_0 KV, flash attention,
batch/ubatch 4096). It scores exactly the same tokens as Strata's teacher-force mode: the prompt is read, then every token
of the 1,536-token text is scored. Nothing in the signal folder was edited.

| text | llama.cpp | C\*3 | C\*4 | C\*4 − llama.cpp | C\*3 − llama.cpp |
|---|---|---|---|---|---|
| math (short) | 1.3337 | 1.3348 | 1.3362 | +0.0019 ± 0.0007 | +0.0009 ± 0.0006 |
| code + licence (short) | 1.4729 | 1.4749 | 1.4713 | −0.0011 ± 0.0018 | +0.0013 ± 0.0018 |
| long16k (16K prompt) | 14.22 | 17.84 | 20.26 | +0.35 ± 0.03 | +0.23 ± 0.03 |
| long24k | 24.42 | 20.63 | 22.10 | −0.10 ± 0.03 | −0.17 ± 0.03 |
| **long64k (new)** | 22.89 | 21.84 | 29.36 | +0.25 ± 0.03 | −0.05 ± 0.03 |

(perplexities; differences in nats/token, paired over the same 1,536 tokens; `work/r4/table-tf.md`)

**The long texts are just as sensitive in llama.cpp.** Changing only llama.cpp's ubatch from 4096 to 2048 moves long16k
by **+0.18 nats/token (perplexity 14.2 → 17.0)** and long24k by +0.05, while the short texts do not change at all; the same
kind of "flip" tokens appear (text copied from far back scored ≈ 0 by one run and 8–14 nats by the other). Strata's own
chunk-size change (8,192 → 4,096) moves C\*4's long16k by −0.28, and C\*3's long16k moved from 14.3 (round 3) to 17.8 today
with the same binary, only because ~100 fewer experts fit in VRAM with Chrome open. So a single long text differs by up to
~0.35 nats between any two runs that round differently, in either engine. Strata is lower than llama.cpp on some texts
and higher on others. Averaged over the three long texts: C\*3 +0.00, C\*4 +0.17 nats/token — within this spread, and three
texts are too few to call a 0.1–0.2 offset. **Verdict: not clearly worse, so no fix was attempted.** I built four more long
texts (28K, 40K, 96K and 112K prompts from other documents) to settle a small C\*4 offset, but they did not run (the stall).
The cause of the sensitivity is the model's block-sparse attention: a rounding change can make its top-k block selection
pick a different block for a far-back passage.

**Practical check** (`work/r4/needle.py`): 5 facts (a device's 6-digit calibration code + who signed it) inserted as short
files at ~2/25/50/75/98 % depth of the 32K/64K/120K documents, fresh facts and jittered depths for each of 3 runs; asked
all 10 back in one question; your sampling, xhigh. **C\*4: 45/45 codes and 45/45 names**, every depth, every size (TTFT
15.6 / 31.6 / 62.0 s; it thinks only ~500–1,100 characters). The same run on llama.cpp did not happen (the stall).

**Incident (my mistake).** The first llama.cpp scoring run used round 1's `--load-mode none` (as in `scripts/server-B.sh`).
On the newer 6fcaa16 build this pins all 48 GB of experts *and* the scorer held ~40 GB more (a parameter default that
differs from llama-server — `--parallel` — was part of it). **At 08:32 the kernel's OOM killer killed that process**; it was the
only process killed (kernel log checked; gnome-shell, Chrome and Open WebUI kept their pids). The queue then started two
more llama.cpp jobs, which I killed myself within 22 s. About 1.7 GB of other programs' memory went to swap; it pages back
as used (SwapFree 31.4 of 32 GB now). The runs that worked used `--load-mode mmap --parallel 1` under a memory guard
(`work/r4/memguard.sh`: stops the process if MemAvailable < 20 GB or swap grows > 1 GB); MemAvailable then stayed ≥ 86 GB.

### 3. Chat page in a real browser — not run
Prepared, not executed: `work/r4/browser_test.py` drives headless Chrome over the DevTools protocol. It uses your installed Chrome binary
directly (not through flatpak, so it never touches `~/.var/app/com.google.Chrome`), with HOME, caches and a fresh profile in
`tmp/r4/chrome-*`, `--disable-gpu`, DevTools on 127.0.0.1. A launch test worked (HeadlessChrome 154). The test covers the drawer
(High / 0.60 / 0.95 / 20 / empty max tokens), chat list and switching, New chat keeping the old one, delete + Undo,
attach + reload + ask again, Stop, and a two-tab case. The QuickJS logic test (round 3) passes 15/15 on C\*4's page.
**Suspected bug (by reading, not confirmed):** with the page open in two tabs, each tab writes back its own copy of the chat
list, so a chat started in one tab can vanish from the list when the other tab saves (its messages stay in storage).
A fix is ready in branch `r4-web` (`strata-r4-web/`: the list is re-read from storage before every change and refreshed on
the browser's `storage` event). It is not in C\*4 because the test that would confirm the bug did not run. Until then, use the
page in one tab.

### 4. Long soak — not run
`work/r4/chatsoak4.py bigsoak` (10–12 chats of 32K–120K pasted documents so the 6-chat / 16 GiB cache overflows constantly,
returns to old chats, Stop, regenerate, long reasoning, a 32K speed probe every 10 min) and `work/r4/soak_summary4.py`
(parked-total vs the budget from the engine log, MemAvailable floor, probes over time) are ready. One thing to watch when it
runs: in the switch tests MemAvailable was 28–30 GB at 56–58 GB engine RSS, so a full 16 GiB chat cache would bring it
near your 20 GB floor. If it goes below, lower `--chat-cache-mib` to 12288 in `configs/Cstar4.json`.

### 5. Hyper-connection kernels (done early, while the GPU queue ran)
* v4 — same arithmetic, bit-identical (unit test T = 1..8): **slower**. With a cold L2, `down` 24.2 → 33.0 µs, because
  without shared-memory staging each chunk's activations come from L2 on the critical path. Rejected.
* **v5 — `down` split over the rows' length** (164 blocks, one staged quarter each; the 4 partial sums added in a fixed
  order, so deterministic but not bit-identical), `norm` keeps its values in registers: one GR read 39.9 → 32.4 µs (T = 1),
  52.1 → 41.2 µs (T = 4), per kernel down 24.2 → 15.9, norm 7.9 → 5.5, up 16.6 → 17.9 µs. **Engine: decode +2.3 %** (exact
  profiles, 2 pairs: 117.5 / 116.4 vs 114.9 / 113.8 tok/s). Accuracy: C\*4 → C\*4+v5 = +0.0010 (math) / −0.0014 (code+licence),
  long texts −0.12 / +0.06 / −0.13 — within spread. Max rounding difference vs the old kernels 1.2e-4 relative.
* **`--spec-split` re-tested with v5:** 105.9 / 105.1 vs 115.4 / 115.4 tok/s (−8.5 %) at short context; at 32K depth one run
  +3 % but with more tokens per window by chance (time per window still longer) → **stays off**.
* v5 is **not in C\*4**: it had no sampled screen and no soak. To try it: `STRATA_CONFIG=configs/R4-gr.json` (dev build
  `strata-r4-gr/build/strata`, branch `r4-gr`; `STRATA_GR_OLD=1` switches back to the old kernels in the same binary).

### Files and state
* `configs/Cstar4.json` (+ `Cstar4.shared-settings.json`) — the default of `run-strata.sh` and `switch-model.sh`;
  `configs/Cstar3.json`, `engine-cstar3/`, `strata-cstar3/` unchanged for rollback (originals of both launchers in `work/r4/*.orig`).
* `engine-cstar4/strata` (sha256 `74963744…`), built by `work/r4/build-cstar4.sh` from a clean clone of v0.1.15 +
  `patches/r4/0001-0006`; tree identical to the tested branch `r4-port`; `strata-cstar4/` = that checkout (server + page).
* Scripts and data: `work/r4/` (screen, queue, TF, llama scorer, needle, browser test, soak client, kernels test),
  `results/tf-R4tf-*` / `results/tf-L6*` (NLL), `results/needle.jsonl`, `results/runs.jsonl` (configs `R4-*`, `P-*`, `G*`, `S-*`),
  logs `logs/r4/`, notebook `NOTES.md` ("ROUND 4").
* **Machine state:** C\*4 on 127.0.0.1:8080 (test completion 0.7 s; engine RSS 48.8 GB, VRAM free 503 MiB, MemAvailable
  39.6 GB). No other model server, test, queue or monitor of mine running. Outside the workspace: this morning I removed
  2 CUDA JIT-cache entries that round 3's unit tests had written into `~/.nv/ComputeCache` (a round-3 slip); a typo created
  and I at once removed an empty `/tmp/null`; the swap use from the OOM incident above. All round-4 caches (pip, CUDA, XDG,
  Chrome) went to `tmp/r4/`.
