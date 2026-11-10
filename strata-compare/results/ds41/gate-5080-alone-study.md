# DeepSeek V4.1 Flash: "5080 alone" gate, read-only study (2026-11-03)

Read-only. Nothing was built, run, downloaded, changed or posted. GPU use: one `nvidia-smi --query-gpu` (memory and
link fields). Sources: `NOTES.md`, `results/ds41/` (tuning arms, round report, checkpoint, maya-catchup), `configs/DS41-*.json`,
`results/sweep-1103/`, the memory notes, and the daily engine's source tree `strata-v026p343-slotram`.
Source references: `model.cu` = `src/dsv41/ds4_model.cu`, `model.hpp` = `src/dsv41/ds4_model.hpp`,
`main.cpp` = `src/dsv41/ds4_main.cpp`, `rule.hpp` = `src/dsv41/ds4_experts_rule.hpp`. All paths are relative to
`/home/USER/ai-speed-testing/strata-compare/strata-v026p343-slotram/` unless stated. "NOTES n" = line n of
`strata-compare/NOTES.md`.

Arms used below: **A** = daily (4060 Ti first, DS4_SPLIT 8,32), **B** = the 5080 alone (`--tp 1`, no DS4_SPLIT),
**C** = B's placement plus DSpark on the 4060 Ti.

---

## 0. Summary

1. **8/32 was a speed pick between two-card splits (10-24 to 10-26). It was not chosen for memory or 128K fit.** The 5080
   alone was dropped on 10-24 after one screen that was handicapped: v0.2.4, a 1024-token auto chunk for one card, and
   prompt skip off (P4K -44.5 %, P20K -69.5 %). It was not re-tested head-to-head until today's sweep. Today it ran with
   chunk 8192 and skip 1: decode -2 %, P4K +28 %, P20K +2 %.
2. **What A has and B does not:** a 3-pass A/B/A, the 5-check rounding gate against stock, the daily memory check
   (everything up, 16 slots, lowest 15.5 GB), the 97K filled-context check (lowest 18.9 GB), and the conversation-cache
   and follow-up end tests.
   - 128K VRAM fit is not a problem for B. The KV and score buffers are tiny (0.12 GB) and are allocated in full at load,
     and B started at 131072 with 574 MiB free.
   - Vision and concurrency are not in this engine or pack at all.
3. **New risk for B: host RAM on long prompts.** Only a one-device run uses the layer-major prompt path. That path keeps
   every chunk's state in **pinned host RAM, 92,192 B per prompt token**, plus a layer cache.
   - Today's sweep saw +3.8 to +4.2 GB RSS on B's 20-24K prompts, against no rise on A.
   - Projected: ~4.8 GB at 32K, ~7.8 GB at 64K, ~9 GB or more at 97K.
   - The engine stops itself only at **8 GiB MemAvailable** (model.cu:932, 8120). That is below our 12 GB floor, the
     runner's 13 GB DeepSeek relief and the 14 GB daily rule.
   - A never takes this path, so its 97K memory pass does not cover B (section 1.5).
4. **C needs no code, only config:** 4060 Ti first + `DS4_SPLIT=0,40` + `--dspark on` (+ `--dspark-block 1|2`). The
   engine has no draft-device option: the drafter always sits on the first CUDA device. A group with no trunk layers
   has never been run, but the code paths I read skip such a device cleanly (section 2.2).
5. **C's side effects:**
   - With two cards visible, the one-device paths switch off. There is no layer-major prompt path (P20K drive reads go
     back to A's ~115 GB) and no mid-layer Stop.
   - The drafter card still allocates full prompt-chunk buffers (~1-2 GB).
   - The 8 GB Q8_0 drafter then does not fit: an estimated ~245 of 384 drafter experts get VRAM. A ~4.9 GB Q2_K/Q4_K
     drafter fits.
6. **The hand-off is small.** Per round the 4060 Ti's x4 link carries the 3 hidden-state taps (60 KiB per kept token),
   5 embedding rows (50 KiB) and the drafter's output (100 KiB), about **0.28 MB at draft 1 and 0.34 MB at draft 2**,
   roughly 0.1 ms.
   - The real cost is the drafter's own pass. It always runs a block of 5 positions through 3 blocks, reading
     ~0.8-1.4 GB on the 4060 Ti (~3.5-6 ms), in series with the 5080.
   - Then comes the verify window on the 5080, which reads the union of its tokens' experts.
   - Break-even: the 2-token window may cost at most ~1.84x a token's expert time (draft 1), and the 3-token window at
     most ~2.7x (draft 2).
   - Earlier DSpark arms: -7.9 % (drafter on the 5080) and +3.0 % screen / -3.3 % confirm (drafter on the 4060 Ti with
     10 trunk layers there). Expect level to a modest gain; only the gate can tell.
7. **Exactness.** DSpark's verification is exact speculative sampling: argmax drafts, so q is a point mass; a draft is
   kept with probability min(1, p/q); a rejected one is redrawn from the residual, with separate Philox keys. The
   confidence gate depends only on the accepted prefix, so it adds no bias.
   - **But `--score` never drafts**, so the KL gate cannot see DSpark.
   - C also needs a greedy identity run (`--spec-eval`, placement frozen) and a sampled distribution test. The engine has
     no harness for the second one.
8. **Files.**
   - The Q8_0 drafter is 7,976,914,240 B (sha256 6ba6ac1b...927a): Q8_0 dense, MXFP4 experts, BF16 markov head. The daily
     pack lists it as file 5 and the engine opens it at load, so it must stay where it is.
   - A Q2_K / Q4_K drafter is supported in principle: device kernels for Q2_K-Q4_K experts; Q4_K/Q5_K/Q6_K/Q8_0/BF16 for
     dense; **no Q2_K or Q3_K dense**. It goes into a **new** pack via `pack_gguf.py --dspark-gguf`, and its GGUF header
     has to be checked first.
9. **One lossy one-GPU default:** `--experts auto` picks 5 experts on ≤16 GiB of cards, and the 5080 has 15.92 GiB.
   The sweep configs pin `--experts 6`; keep it. The auto chunk would be 4096 on the 5080 alone; pin 8192. Nothing like
   Qwen's tail skip switches on with one GPU (section 3.1).

---

## 1. Why the earlier round picked 8/32

### 1.1 Timeline

| When | What | Result | Source |
|---|---|---|---|
| 10-24 16:14-17:51 | split group (v0.2.4, skip 0, 32K): 5080-first 26/28/30 layers vs 4060 Ti-first ("rev") 22-30 layers on the 5080 | r30 (4060 Ti first, 10/30) best: decode +11.4 %, P4K +22.2 %, P20K +45.4 % vs the auto split | `results/ds41/tuning/tune-summary-1024.txt:44-63` |
| 10-24 18:13 | gpus group: **one5080** (5080 alone, "layer-major prompt path, auto chunk 1024; layer cache capped at 4 GB") | **clearly worse**: decode -1.3 %, P4K -44.5 % (120.3), P20K -69.5 % (143.2); P20K drive 95.9 GB vs 204 GB | `tune-summary-1024.txt:66-69`; NOTES 8431-8433 |
| 10-25 12:04-13:24 | confirm runs | r30 KEPT vs 5080-first; s30f (5080 first 30/10) not kept | `tune-summary-1024.txt:260-265` |
| 10-26 03:06 | end test **one5080-flow** (v0.2.6 stock, chunk 8192, skip **0**, layer cache 4 GB) | P4K 298.1, P20K 403.7, 20K stream 64.8-97.3 GB (ship config B at the time: ~308 / ~515) | `tuning/one5080-flow-1026-0306/summary.txt`; NOTES 8664 |
| 10-26 | prompt skip on the 5080 alone (KL) | PASS (mean 0.00085, p90 0.00164); PASS again under the 10-26 rules | NOTES 8674, 9154; `round-report-1026.md:44` |
| 10-26 ~09:50 | Karl's re-rank after #343: the 4060 Ti streams 76 GB per 20K prompt over its x4 link and waits 9.4 s of 38 s, so give it fewer layers | split_step screens 10/30 vs 8/32 | NOTES 8889-8899; `maya-catchup.md` "Re-rank after #343" |
| 10-26 15:35 | **8/32 KEPT**: A/B/A 3 passes vs 10/30 | decode +2.1 / +1.5 %, P4K +7.8 / +6.9 %, P20K +16.2 / +16.6 %; drive bytes unchanged ("the gain is the 4060 Ti's share") | NOTES 9033-9045 |
| 10-26 16:28-16:45 | rounding gate, final config (#343 + 8/32) vs stock | top-1 FAIL by one, then PASS under Karl's spread-based rule + NLL check | NOTES 9084-9117 |
| 10-26 15:57 / 16:44 | daily memory check (68 GB store, everything up, 16 slots ~31K) / conversation cache + follow-ups | lowest 15.5 GB; both end tests PASS | NOTES 9047-9049, 9127-9135 |
| 10-26 19:28-20:09 | context cost at 32K / 64K / 128K (A, 3 passes) | decode 28.34 / 28.47 / 28.27, P4K ~350, P20K ~699 (no context cost) | `tuning/ctx-{32k,64k,128k}-1026-*/summary.txt` |
| 10-27 01:36 | 97K filled context on A, everything up | 96,917 tokens in 102.3 s (947 tok/s); decode at that length 21.0; lowest 18.9 GB ("store not full yet") | NOTES 9319-9322; `tuning/long100k-1027-0136/` |
| 10-27 02:13 | daily -> 128K, slot RAM cap 1.7 GiB | | NOTES 9352-9357 |
| 11-03 06:40-07:16 | sweep (1 pass, 128K, daily settings): A on-v10 vs B off-v10 | A 28.8 / 342 / 701, P20K drive 115 GB; B 28.2 / 438 / 714, drive 64 GB | `results/sweep-1103/sweep.md`; NOTES 9571-9572 |

**Why 8/32:** it came from two speed steps between two-card layouts. First 4060 Ti first + 10/30 against 5080-first
splits (10-24/25), then 8/32 against 10/30 on the #343 config (10-26). The goal was to cut what the 4060 Ti streams over
its PCIe 4.0 x4 link on long prompts. Every daily check after it (rounding gate, memory, 128K, end tests) ran on 8/32
because it was already the final config. **None of those checks compared it with the 5080 alone.**

### 1.2 Why the 10-24 "5080 alone" verdict does not stand

- **Chunk.** The one5080 arm let the single-card default choose the chunk (1024 under v0.2.4's rule). Every two-card arm
  ran 8192. Under v0.2.6 the auto chunk is 4096 on the 5080 alone: `rule.hpp:41-49`, because the card has less than
  16 GiB (16,303 MiB = 15.92 GiB).
- **Prompt skip.** It was off in every 10-24/26 arm (STRATA_DS4_PROMPT_SKIP=0). Today it is on (skip 1, in the daily
  config): layers 21-39 run only the last 2,668 rows of a long prompt. This is the gap between one5080-flow's P20K 404
  and today's 714.
- **Layer cache.** It was capped at 4 GB in both old arms (DS4_LAYER_CACHE_MB=4096). Today it was left to the engine.
- **Engine.** v0.2.4 (10-24) and v0.2.6 stock (10-26) against today's v026p343-slotram.

`maya-catchup.md` (row 4, the helper GPU) already said "Zero-code first: 5080 alone on v0.2.6 with --prefill-chunk
4096/8192". Today's sweep is that check, at one pass.

### 1.3 Today's numbers next to A's 3-pass reference

| | decode | P4K | P20K | P20K drive | VRAM experts | ready RSS / MemAvailable | lowest MemAvailable (no daily services) |
|---|---|---|---|---|---|---|---|
| A 3-pass, 128K (ctx-128k-1026-2009) | 28.27 (spread 0.57 %) | 350.1 (4.1 %) | 699.0 (1.0 %) | 113-114 GB | 451 + 857 | - | 19.4 GB |
| A sweep on-v10 (1 pass) | 28.81 | 341.6 | 701.3 | 115.1 GB | 451 + 857 | 59.1 GB / 27.0 GB | 17.9 GB |
| B sweep off-v10 (1 pass) | 28.21 | 438.0 | 714.3 | 64.1 GB | 711 | 56.4 GB / 29.5 GB | **16.8 GB** |

Also from the engine logs (`sweep-ds-{on,off}-v10-*/engine-run.log`):
- **Short prompts** (123-143 tokens) read at 35-37 tok/s on A (3.3-4.0 s) and 44-49 tok/s on B (2.6-3.3 s).
- **W3's 23.5K prompt** read at 756 tok/s on A and 787 on B.

B's decode is level with A (-0.2 % against the 3-pass A, within noise). B's prompts are better at 4K, short and 20K+,
with half the drive reads at 20K.

### 1.4 Coverage: what the 8/32 choice covered and what today's sweep did not

| Item | Covered for A (8/32) | Covered for B (5080 alone) | Notes |
|---|---|---|---|
| Speed noise (3 passes) | A/B/A 10-26, ctx arms | no (1 pass) | gate item |
| Rounding gate vs stock (5 checks) | PASS 10-26 (NOTES 9114) | only the prompt-skip check on v0.2.6 stock (NOTES 8674/9154) | B's placement differs: rounding-level, but must be gated. Score with a ≥2-chunk prefix (the final gate's 12,000 tokens = 2 chunks at 8192) so B's layer-major path is inside the check |
| **128K fit (VRAM)** | yes | **yes, at load**: `--max-context 131072`, caches 0.12 GB, 574 MiB free; peak 15,438 MiB used at 20-24K | KV + score buffers are allocated whole at the full context (model.cu:2300-2360; `rule.hpp:35`). Not context-dependent later |
| Memory headroom, daily (everything up, 16 slots) | lowest 15.5 GB (68 GB store) | no | B idles ~2.5-2.7 GB lower in RAM (one CUDA context, no x4 bounce buffers): likely better at short prompts |
| **Long prompts 32K-128K: memory** | 97K: lowest 18.9 GB | **no; this is B's main risk** | section 1.5 |
| Long prompts: speed | 97K at 947 tok/s, decode 21.0 at that length | no | |
| Engram | nothing device-specific was tested | same | Engram rows are read on the host (16 MB row cache); layers 1 and 14 are on the 5080 in B. The #343 skip rule's "no Engram layer from the skip layer on" (model.cu:8190-8196) holds in all arms |
| Vision / pictures | n/a | n/a | the pack has no `vision.*` tensors (0 in tensors.txt); v0.2.6 answers "this engine has no vision tower" (main.cpp:671); `docs/DEEPSEEK41.md:89` |
| Slot keep (cap 16, RAM cap 1.7 GiB) | end tests PASS | no | slot logic is in main.cpp and does not depend on the device. A and B share a slot identity (model.cu:5318-5337: mtp count, geometry, pack files), so their slots can be swapped; **C's identity differs** (mtp=3) |
| Concurrency | n/a | n/a | one request at a time; `--parallel` is ignored (`docs/DEEPSEEK41.md:89`) |
| Quality (hard set, graded set) | on A | no | the rounding gate stands in for it |

### 1.5 The long-prompt memory risk on B (not in any earlier test)

- **The path.** `lm_begin()` (model.cu:8092-8143) runs a prompt layer-major only when `devs.size() == 1` and the prompt
  has ≥ 2 chunks (more than 8,192 tokens). So it runs on B and never on A or C (model.cu:8094).
- **The cost.** It allocates the chunk states for the whole prompt with `cudaHostAlloc`, pinned:
  `run.T.size() x chunk_hand_bytes()`. `chunk_hand_bytes` = chunk x (hc·dim·4 + 32 + index_topk·4 + cand_topk·4)
  = 8192 x 92,192 B = 755 MB per 8K chunk (model.cu:2880-2882). It also allocates a layer cache: the largest layer's
  non-store CPU-lane experts.
- **Measured today** on B (`sweep-ds-off-v10-1103-0707/monitor.tsv`):
  - P20K at 07:09:28-40: RSS 60.7 -> 64.8 GB, MemAvailable 25.3 -> 21.4.
  - W3's 23,552-token prompt at 07:14:14-38: RSS 65.3 -> 69.5 GB, MemAvailable 21.0 -> 16.8, back to 20.8 afterwards.
  - A at the same steps: no such jump (`sweep-ds-on-v10-1103-0640/monitor.tsv` 06:47:08-33, 18.7 flat).
- **The engine's own limit** (model.cu:8117-8121): it takes the layer-major path while
  MemAvailable > **kRamMargin (8 GiB, model.cu:932)** + the states + one expert.
  - With `DS4_LAYER_CACHE_MB` set, it **skips that check entirely**: the states are allocated whatever RAM is left. The
    10-24/26 one-GPU arms set it to 4096. Do not use it as a "cap".

| prompt | chunks (8192) | pinned states | + layer cache (measured ~1.5-2 GB at 20K) | projected B dip vs A |
|---|---|---|---|---|
| ≤ 8,192 | 1 | none (no layer-major) | - | none |
| 20-24K | 3 | 2.27 GB | ~1.5-2 GB | **+3.8-4.2 GB (measured)** |
| 32K | 4 | 3.02 GB | ~2 GB | ~5 GB |
| 64K | 8 | 6.04 GB | ~2 GB | ~8 GB |
| 97K | 12 | 9.06 GB | what is left above 8 GiB | ~9 GB or more |
| ~128K | 16 | 12.08 GB | - | only if MemAvailable > ~20.7 GB, else the engine falls back to per-chunk streaming (no extra RAM, A-like drive reads) |

- **Against our rules.** Take daily use with everything up and a full store. A sat at 15.5 GB (daily-68); B starts
  ~2.5 GB higher. A 32K prompt would then dip to ~13 GB, under the 14 GB daily rule. 64K to ~10 GB, under the 12 GB
  floor and the 13 GB relief that restarts 8080. 97K to ~9 GB.
  - These are projections (±2 GB). The page cache and the store's fill level move them.
- **Pinned memory.** The 9-12 GB of states is pinned, on top of the RAM store's 68 GB. The memory note's stressapptest
  condition (> 60 GiB locked) is already met (PASS 10-10). Still check the kernel log after each long run.
- **Options:**
  - **(a)** `DS4_LAYER_MAJOR=0`: zero code. Prompts over 8K stream per chunk like A, so B's 20K drive saving goes. P4K
    and short prompts keep B's gain. Price it as its own arm.
  - **(b)** A smaller `--ssd-cache` for B, e.g. 60-62 GB: zero code, costs decode, measure it.
  - **(c)** A one-line build change: make lm_begin's margin our floor (kRamMargin 8 -> ~16 GiB, or a new env read only at
    model.cu:8120). The layer-major and per-chunk paths have to pass a rounding check against each other.
  - **(d)** A cgroup MemoryMax on the engine: `ram_avail()` reads the tightest cgroup v2 limit (model.cu:149-161). Not
    recommended: OOM-kill risk.

---

## 2. DSpark on the 4060 Ti, model on the 5080 alone

### 2.1 What DSpark is in this engine

- DSpark is DeepSeek's DSparkBlock: the pack's `mtp.0-2` blocks, the only drafter in this engine (no prompt lookup, no
  nextn layer; NOTES 8411). Geometry is in `models/.../pack-ist-das-2.00bpw/ds4.txt`: block size 5, noise token 128799,
  markov rank 256, 128 experts, 3 per token, target layers 37/38/39. `n_mtp = ratios.size() - nl = 3`
  (model.cu:400-433).
- In the pack its tensors come from file 5, `dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf` (`tensors.txt` lines 6+,
  1,242 `mtp.*` entries).
  - Q8_0 dense: 46 tensors, 0.600 GB.
  - MXFP4 routed experts: 1,152 tensors, 7.219 GB; 384 experts at 18.8 MB each.
  - BF16 markov embed/head: 2 tensors, 0.132 GB.
  - F32: 42 tensors, 0.020 GB.
  - Total 7.972 GB.
- Modes (main.cpp:1230-1235; model.hpp:42-51; model.cu:2023-2034):
  - `--dspark auto` loads it only if the trunk's routed experts are ≤ 1.5x the GPUs' free VRAM. Here 132 GB > 1.5 x 16
    (or 23) GB, so it is **never** loaded; the message is the "3.3x a token's bytes" line.
  - `on` forces it. `off` loads it but does not use it. `none` does not load it.
- Knobs:
  - `--dspark-conf F`: the per-draft confidence floor. The daily config uses 0.65; the engine default is 0.5.
  - `--dspark-block N`: at most N drafts a round; it only truncates (model.cu:2035, 6727-6730).
  - `STRATA_DS4_DSPARK_CUM`: the product-of-confidences cut (main.cpp:152-162).
  - `DS4_DSPARK_MAX`, plus test-only `DS4_DSPARK_SAMPLE` / `QTEMP` / `DUMP` (model.cu:901-919).
  - A request can also send `spec=0|1` (main.cpp:211, 310).
- After a round whose drafts were all under the floor, the next round skips the drafter (the "cool" flag,
  main.cpp:897-912).

### 2.2 Placement: no draft-device option; the drafter takes the first CUDA device

- The split puts the drafter's blocks first in its order, so they always land in group 0, the first device of
  `CUDA_VISIBLE_DEVICES` (model.cu:2133-2147). `DS4_SPLIT=a,b` assigns only trunk layers: "the drafter stays with the
  first" (model.cu:2195-2206).
- `d_dev = L[nl].dev` is the drafter's card and `head_dev = L[nl-1].dev` the head's card (model.cu:2212-2213).
- On `d_dev`: the drafter's dense weights, its experts and `main_proj` / `main_norm` (model.cu:3796-3800).
- On the head's group: the drafter's final norm, the confidence head and the markov embed/head (~132 MB, F16)
  (model.cu:3750-3794).
- **Recipe for C, no code change:** `CUDA_VISIBLE_DEVICES` = 4060 Ti, then 5080 (as in daily); `DS4_SPLIT=0,40`;
  `--dspark on`; `--dspark-block 1` or `2`; `--experts 6`; `--prefill-chunk 8192`. Keep `--tp 2` or use `--tp 1`.
  - Either works: tp drops to 1 in both (the experts' 256-value blocks do not split n_ff 2304, model.cu:1901-1916), so
    decode runs on one host thread in A, B and C (`par = threads || tp>1`, model.cu:1924).
  - Prompt chunks stay on with `o.tp > 1` or an explicit `--prefill-chunk` (model.cu:1929-1931).
  - Expected start lines: `CUDA0 layers [40, 42]: ... (N of 384 in VRAM)` and `CUDA1 layers [0, 39] + head`, and no
    "DSpark not loaded".
- **Untested shape: a group with no trunk layers.** The auto DP split always gives each group ≥ 1 layer
  (model.cu:2148-2193); only `DS4_SPLIT` can make an empty one. What I checked:
  - The window path embeds on `L[0].dev` and hands off only on a device change (forward_serial, model.cu:8650-8705).
  - The per-device runner skips devices without layers (`mi < 0 -> continue`) and returns true for a device outside
    the head group (run_dev, model.cu:8741-8796).
  - The prompt chunk runner guards an empty layer list (model.cu:7603-7641, `if (!c.fl_layers.empty())`).
  - The yoco/skip rule sees every trunk layer on one device, so the skip applies (model.cu:8176-8199).
  - The KV sources are all local.
  - **Conclusion:** no code change is visible as needed, but a start + greedy smoke test comes first.
- **Side effects of a second visible device** (none of these depend on the drafter):
  - `lm_begin()` refuses (`devs.size() != 1`, model.cu:8094), so there is **no layer-major prompt reuse**. P20K drive
    reads go back to A's ~115 GB, and C's speed on prompts over 8K must be measured. On the other hand, C has no 9-12 GB
    transient (section 1.5).
  - `halt_now()` (Stop inside a chunked prompt, after the current layer) is one-device only (model.cu:843). With two
    devices a Stop ends at the next chunk boundary.
  - `alloc_chunks()` allocates a full set of 8192-row prompt buffers on **every** device, the drafter card too
    (model.cu:2914-2985; only the staging ring is skipped on a card without trunk layers). The engine budgets
    1.1 GiB for these (model.cu:2159); my type-by-type sum is ~1.9 GB.
- **Optional code changes** (not needed for a first C screen):
  - **(i) Layer-major with a drafter card:** in lm_begin, replace `devs.size() != 1` / `chunks[0]` with "the device that
    holds every trunk layer". About 10-30 lines, model.cu:8092-8143; the LM taps code at 7557-7566 already serves the
    drafter. Needs a rounding check against B.
  - **(ii) No chunk buffers on a card without trunk layers:** ~5-10 lines in alloc_chunks. Gives ~1-2 GB more drafter VRAM.
  - **(iii) A drafter block of k+1 instead of 5 for draft k:** ~2 lines in `draft_()` (model.cu:6735-6745). Cuts the
    drafter's expert reads ~3-5x. It changes the drafts, because the block attends to itself, but not the exactness;
    acceptance must be re-measured.

### 2.3 VRAM on the 4060 Ti (estimates, to be read from the start line)

- **Evidence.** dspark4060 (10-25, 4060 Ti first, 10/30, Q8_0 drafter): `CUDA0 layers [0, 42]: weights 2.04 GB, experts
  2.65 GB (140 of 4224 in VRAM), 598 MiB free` (`tuning/dspark4060-1025-0239/engine-start.log`). All 140 are drafter
  experts (2.65 GB / 18.8 MB): **244 of 384 drafter experts ran on the CPU lane** and the 4060 Ti kept no trunk experts.
  The drafter's experts take VRAM before any trunk expert (model.cu:3939-3944). The RAM store excludes the drafter's
  layers (model.cu:4643), so spilled drafter experts are read from the file and page cache.
- **Drafter-only 4060 Ti (C):** about 8.59 GB total, minus ~2.7 GB of context, chunk buffers and scratch, minus the
  0.63 GB reserve, minus the drafter's dense, leaves ~4.6-4.9 GB for drafter experts.
  - **Q8_0 file** (7.22 GB of experts): ~245 of 384 (~64 %) in VRAM; the rest on the CPU lane, on every draft round.
  - **~4.9 GB Q2_K/Q4_K file**: Q2_K experts are 11.6 MB each (3 x 3.87 MB), 384 x 11.6 = 4.46 GB; Q4_K dense ~0.3 GB.
    **About all 384 fit**, with ~0.3-0.5 GB to spare.
  - With change (ii), the Q8_0 file gets ~345 of 384.
- **The 5080 in C** loses ~0.15-0.2 GB against B to the head-side drafter pieces (markov 2 x 66 MB, confidence head,
  logits/ints) and the trunk's rollback rings: ~690-700 VRAM experts instead of 711.

### 2.4 What the drafter needs from the target, and the bytes over the x4 link

The drafter needs **hidden states, not only tokens.**

- **Taps.** `tap()` (model.cu:8578-8590) takes the mean over the 4 hc streams of the residual entering layers 37, 38 and
  39, for every position the trunk keeps. These are 3 x 5120 floats = 61,440 B per token, copied from the 5080 to
  pinned host memory (`h_taps`).
- **Seeding.** `seed_drafter()` (model.cu:6659-6713) uploads the kept rows to the drafter's card and runs `main_proj`
  (Q8_0 5120x15360, 83.6 MB), then each block's `wkv` / norm / rope into its 128-token window ring. It runs:
  - after every plain step: 1 row (forward's `seed_rows=-1`, model.cu:8645);
  - after every verify: m+1 rows, the accepted drafts plus one (model.cu:6966-6967);
  - at each prompt's end: the last ≤128 rows (model.cu:8438-8440, `tap_cap` 128).
- **The draft** (`draft_()`, model.cu:6735-6870):
  - Upload of the token y + 4 noise tokens: 5 embedding rows, BF16, from a pinned host table.
  - The 3 blocks on the 4060 Ti.
  - The hidden rows (5 x 5120 floats) out to a pinned bounce buffer and in to the 5080. Peer-to-peer copies would take
    ~1.7 ms each through the driver, so the engine avoids them (model.cu:481-482).
  - On the 5080: the drafter's final norm, **the trunk's head** (Q5_K, 455 MB read once for 5 rows), the markov bias
    5 times in sequence (66 MB F16 each) and the confidence head.
  - The draft ids and confidences come back to the host.

| transfer per round | where | bytes | draft 1 | draft 2 |
|---|---|---|---|---|
| embedding rows (always 5) | host -> 4060 Ti | 5 x 5120 x 2 | 51.2 KB | 51.2 KB |
| drafter output rows | 4060 Ti -> host -> 5080 | 5 x 5120 x 4 | 102.4 KB | 102.4 KB |
| taps of the verify window | 5080 -> host (x16) | (k+1) x 61,440 | (122.9 KB) | (184.3 KB) |
| seed rows | host -> 4060 Ti | (m+1) x 61,440, m ≤ k | ≤ 122.9 KB | ≤ 184.3 KB |
| **over the x4 link** | | | **≤ 0.28 MB** | **≤ 0.34 MB** |
| plain step (no draft) | host -> 4060 Ti, async | 61,440 | 61 KB | 61 KB |
| prompt end (once) | host -> 4060 Ti | 128 x 61,440 | 7.9 MB (~1.2 ms) | |

- **Link speed.** At the engine's own measured 6.4 GB/s (its DMA probe, model.cu:7808-7822, matches the x4 link),
  0.28-0.34 MB is ~45-55 µs, plus ~4 small transfers (typically ~10-20 µs each for pinned copies; not measured here):
  **~0.1-0.15 ms per round, under 0.5 % of a 35 ms token.**
- **Drafter compute** on the 4060 Ti (~288 GB/s), per round, serial with the 5080, because the next draft needs this
  verify's taps:
  - Dense: 3 x ~179 MB, plus `main_proj` 84 MB.
  - Experts: ≤ 5 rows x 3 picks x 3 blocks = 45 picks, ≤ 846 MB (MXFP4).
  - **Q8_0 file:** ≤ 1.4 GB per round, about 5-6 ms, plus whatever runs on the CPU lane when ~1/3 of its experts spill.
  - **Q2_K/Q4_K file:** ≤ ~0.85 GB per round, about 3-3.5 ms.
  - Head + markov on the 5080: ~0.9 ms.
  - `--dspark-block 1/2` does **not** shrink this: `draft_()` always runs the pack's block of 5 (`T = g.d_block`, model.cu:6738; the drafts are only cut afterwards, 6727-6730).

### 2.5 The verify round on the target ("3.3x a token's bytes")

- `verify()` (model.cu:6902-6977) feeds [y, drafts] as one window of T = k+1 rows through all 40 layers. Each routed
  expert the window picks is read or streamed once and applied to its rows (`kSlots = kWin x kPicks`, model.cu:5345).
  So the window costs the **union** of its tokens' experts.
- On B, with 711 of 15,360 experts in VRAM, the per-token cost is mostly expert traffic: RAM store to GPU over x16, the
  CPU lane, drive misses (0.07-0.08 GB a token).
- The "3.3x" comes from the engine's own comment (model.hpp:42-44; model.cu:2030-2031): upstream's measurement, not
  ours, and it does not say for which window size.
- **Model:** a token on B is t ≈ 35.5 ms = f (dense + head + attention, T-independent, ~6-7 ms) + e (experts, ~29 ms).
  The 10-25 W runs (`dspark4060-1025-0239/engine-run.log`) give the acceptance: position 1 kept 81 % of the times it is
  reached, position 2 88 % (1,301 of 1,676 drafts). Tokens per drafted round are 1.81 at draft 1 and 2.52 at draft 2.
  With a ~4.5 ms draft round (the Q2K file), the window's union factor u must stay under:
  - **draft 1:** u(2) ≤ (1.81 x 35.5 - 11) / 29 ≈ **1.84** (~1.70 with an ~8 ms Q8_0 round);
  - **draft 2:** u(3) ≤ (2.52 x 35.5 - 11) / 29 ≈ **2.7** (~2.6).
  - If tokens share 20-30 % of their cold experts, C gains ~+10-20 %. If they barely overlap, C is level to -3 %.
- **What we measured before:**
  - 10-23 dsp70: DSpark on the 5080, stealing ~976 trunk VRAM experts: decode **-7.9 %** (NOTES 8401).
  - 10-25 dspark4060: 4060 Ti, 10/30, drafter mostly on the CPU lane, no trunk VRAM experts left on the 4060 Ti:
    screen **+3.0 %**, confirm **-3.3 %**, not kept (`tune-summary-1024.txt:203, 224, 292-294`).
  - Neither arm had the setup C has: the trunk keeps its VRAM experts and the drafter is fully resident.
- **Expectation:** level to a modest gain on decode. Prompts are unaffected by DSpark, but C loses B's layer-major path.

### 2.6 Exactness of DSpark here

- **The verify rule** (model.cu:6902-6960; `include/strata/dsv41/sampler.hpp:51-75`;
  `src/dsv41/vendor/sampler.cu:470-508`):
  - Without `DS4_DSPARK_SAMPLE` the drafts are the drafter's argmax, so q is a point mass at d.
  - Row i keeps d with probability p(d), where p is the request's full chain: top_k, top_p, min_p, temperature. A draft
    outside the cut has p = 0 and is never kept.
  - Otherwise row i draws from the residual max(0, p - q), renormalised (d excluded). After k accepted drafts the bonus
    token is a plain draw at `counter + n`.
  - Accept and residual use separate Philox keys (`kSpecAcceptKey` / `kSpecResidKey`), and the counter advances by
    accepted + 1 (main.cpp:193).
  - **This is distribution-exact speculative sampling.** The 10-23 code check said the same (memory note ds41-flash-plan).
- **Gating adds no bias.** `confidence_kernel` (`src/dsv41/ds4_kernels.cu:1305-1315`) scores draft t from the drafter's
  hidden row t and the markov embedding of token t-1, which is y or the previous draft. Whether draft t is verified
  therefore depends only on the prefix already accepted. The cumulative cut is the same. This stays true even with
  `DS4_DSPARK_SAMPLE=1`.
  - This is unlike the Qwen SPEC_PROB case, which gated on the drawn token's own q.
- **Caveats:**
  - The realised tokens differ from plain decoding with the same seed ("not the plain draw's tokens", sampler.hpp:57-60).
    The comparison has to be in distribution.
  - `--score` (main.cpp:1012-1060) only calls `feed()`, so **the teacher-forced KL gate never exercises DSpark.** For C
    it covers the placement only (trunk on the 5080, a second card visible, no layer-major path).
  - DSpark itself needs:
    - **(1) a greedy identity run:** `--spec-eval IDS.json --n N` (main.cpp:1136-1190) with the drafter, against
      `--dspark none`, placement frozen with `--no-expert-cache`. Greedy speculative decoding must give the same tokens.
    - **(2) a sampled distribution test:** many seeds at fixed prefixes, per-position token histograms with DSpark on
      against off (chi²), like the Qwen B.2 check. **The engine has no harness for this; one has to be written.**
  - Drafted rounds use the window path (T ≤ 16) where plain decode uses T = 1. The engine states that a window's entry
    gets the token path's bits (`src/dsv41/ds4_gguf.cuh:13-14`; `model.hpp:6-8`). The usual placement rounding (VRAM
    against CPU lane) applies as in any arm.

### 2.7 DSpark files on disk; loading a "DSpark-draft-Q2K-Q4K"

**On disk** (one copy; `find` over `ai-speed-testing` and the HF cache):
- `strata-compare/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf`:
  7,976,914,240 B (7.43 GiB), dated 10-27 13:08.
- It was restored after the 10-27 deletion by `work/cleanup-1027/restore-dspark.sh`: unsloth/DeepSeek-V4.1-Flash-1017-GGUF,
  sha256 `6ba6ac1b331c540691a209e7fc97dec2a24e295acb1e755c84c7d24a4373927a`.
- **Keep it:** the daily pack's `tensors.txt` lists it as file 5 and the engine opens every listed file at load, even
  with `--dspark auto` (NOTES 9485-9488).

**How the engine reads a drafter:** only through a pack. `tools/dsv41/pack_gguf.py --dspark-gguf FILE`
(pack_gguf.py:417-418, 675-745) maps the GGUF's `blk.N.*` to `mtp.N.*`. The head tensors map as:

| GGUF tensor | pack tensor |
|---|---|
| `fc` | `mtp.0.main_proj` |
| `enc.output_norm` | `mtp.0.main_norm` |
| `output_norm` | `mtp.2.norm` |
| `conf_proj` | `confidence_head.proj` |
| `markov_w1` | `markov_head.embed` |
| `markov_w2` | `markov_head.head` |

The new file then becomes another file entry in **that pack's** `tensors.txt`; nothing is copied.

| Requirement | Where | Note for a Q2K/Q4K file |
|---|---|---|
| `general.architecture` = `dflash`; `dflash.block_count`; geometry keys block_size / expert_count / expert_used_count / target_layers (or the flags `--dspark-noise-token 128799`, `--dspark-markov-rank 256`) | pack_gguf.py:685-703 | another tool's quant may lack the keys |
| every tensor name maps, every ggml type is in `TYPES` (F32, F16, BF16, Q8_0, MXFP4, Q2_K-Q6_K, IQ*) | pack_gguf.py:37-49, 711-743 | stops on anything else |
| experts: MXFP4, or one low-bit type for gate and up (down may differ); **MXFP4 and low-bit types do not mix** in a layer | model.cu:1676-1680; `ds4_iq.cuh:3-5`; `ds4_iq.cu:1333-1343` | Q2_K / Q3_K / Q4_K have GPU kernels; CPU lane too (`ds4_gg_cpu.cpp:40`) |
| dense matrices: BF16, Q8_0, Q4_K, Q5_K, Q6_K only | model.cu:1405-1410, 1471-1473 | **Q2_K or Q3_K dense would fail at load** ("not an EXL3 matrix in the pack") |
| router / norms / confidence head: F32, F16, BF16 or Q8_0 | `f32()`, model.cu:1553-1580 | a K-quant router would fail |
| markov head: BF16 embed + F16 or BF16 head, exactly vocab x 256 | model.cu:3781-3790 | |

- **Where the ~4.9 GB comes from (my reading):** 384 Q2_K experts (4.46 GB) + Q4_K dense (~0.3 GB) + the BF16 markov
  head (0.13 GB) gives ~4.9 GB, which matches the name. The repo's own `drafter_pack.py --requant NAME --experts Q2_K
  --dense Q4_K` builds the same kind of file from DeepSeek's checkpoint shards (drafter_pack.py:80-150), but we do not
  have those shards.
- **Pack hygiene:**
  - Build a **new pack folder** for C. Never touch `pack-ist-das-2.00bpw`.
  - Pass `--dspark-gguf` explicitly: with no flag pack_gguf.py takes the **first `dspark-*.gguf` in the model folder**
    (pack_gguf.py:678-679).
  - Use the setup recipe's other flags (`--engram`, `--engram-meta`; no `--skip-tensors` / `--dense-override`,
    `docs/DEEPSEEK41.md:48-50`).
- **Check the header before packing:** read the GGUF header read-only (`tools/gguf_reader.py` or `pack_gguf.py`'s own
  `Gguf`): arch, keys, every tensor name, type and shape against the table above.

---

## 3. Other things the gate must handle

### 3.1 One-GPU defaults in this engine (the tail-skip question)

| Default | One GPU (B) | A | Lossy? | Gate action |
|---|---|---|---|---|
| `--experts auto` -> 5 if the cards' total ≤ 16 GiB (`rule.hpp:14-26`; model.cu:2048-2059) | **5** (5080 = 16,303 MiB = 15.92 GiB) | 6 (24 GiB) | **yes** (10-26: 5 vs 6 KL FAIL, NOTES 8675-8676) | pin `--experts 6`; check "experts per word: 6 (full quality)" (present in the sweep's B log) |
| `--prefill-chunk` auto (`rule.hpp:41-49`) | 4096 | 8192 (via `--tp 2`) | rounding only (upstream KL flat across chunks) | pin 8192 |
| `STRATA_DS4_PROMPT_SKIP` default 1 (model.cu:8168-8174) | active (stock one-GPU path) | active (#343 split path) | rounding-level by our check (PASS on the 5080 alone) | keep 1; it is in the gate |
| layer-major prompt (`DS4_LAYER_MAJOR`, on) | **on** | off | rounding-level (another order of the same sums) | B's KL prefix must be ≥ 2 chunks; memory (1.5) |
| `DS4_STORE_ZC` (GPU from the store over PCIe) | allowed (model.cu:4668) | n/a | timing-dependent, opt-in, off | leave unset |
| `STRATA_DS4_DISK_SKIP_W` | opt-in, off (model.cu:1040-1052) | same | lossy if set | leave unset |
| `DS4_YOCO_KEEP` / skip mode 2 | opt-in | same | lossy | leave unset |
| `--dspark auto` | not loaded | not loaded | - | B: as is; C: `on` |

There is no tail-skip-style lossy default that switches on with one GPU, provided `--experts 6` stays pinned. The
server adds only the slot defaults (`strata-v026/serve/server.py:3482-3498`).

### 3.2 Memory floor and relief

- **The thresholds:** the 12 GB floor everywhere; the runner's relief restart under 13 GB when DeepSeek is on 8080
  (memory note memavailable-floor; the model id must keep "deepseek"); the daily rule ≥ 14 GB with everything up;
  `DS4_STORE_FLOOR_GB=14` only stops store growth, and the store gives memory back only under 4 GB.
- **B with short prompts:** better than A, ~2.5 GB more MemAvailable.
- **B with prompts over 8K:** section 1.5. The gate needs B's long-prompt runs at ~32K, ~64K and ~97K (and one near
  128K) **with everything up and a full store**, as daily-68 / long100k did: lowest MemAvailable, swap rule, kcheck.
  - If B trips 14/13/12, price options (a) to (c) of section 1.5.
  - **Do not set `DS4_LAYER_CACHE_MB`**: it skips the RAM check.
- **C:** host memory like A, because there is no layer-major path.
- **`need_ram_mib` 81305** (A's use + 12 GB) still fits B at start. B's real peak is set by the long-prompt runs.

### 3.3 VRAM: `--vram-experts`, reserve, 128K on the 5080 alone

- **Measured (sweep B):**
  - `--vram-experts 1.0`: 711 experts, 574 MiB free after load (default reserve 600 MiB), peak 15,438 MiB used
    (~496 MiB free) during the 20-24K prompts. That is above our 300 MiB VRAM guard.
  - 0.75: 521 experts, decode 27.4. 0.5: 335 experts, decode 25.4. Keep 1.0.
- **Do not lower `--reserve-mib`:** 400 and 300 tripped the 300 MiB guard on 10-24 (`tune-summary-1024.txt:84-85,
  103-104`).
- **128K costs nothing extra on the GPU later.** KV (4 sources), the score and bm buffers, the chunk scores
  (`AI x (ctx+64)`) and the attention scratch are allocated at load for the full `--max-context` (model.cu:2300-2360,
  2930-2950). A's 32K/64K/128K arms show the same VRAM and the same decode. Check B's peak VRAM in the ~97K run anyway.
- **C's 5080:** ~0.15-0.2 GB less for experts (2.3). C's 4060 Ti: section 2.3.

### 3.4 Launcher and harness details

- **`need_vram_mib`:** run-strata.sh checks it against the **first** card of `CUDA_VISIBLE_DEVICES`
  (`strata-compare/run-strata.sh:87-112`).
  - B: the first card is the 5080, and 7000 MiB would let it start on a half-full card. Use ~15,400.
  - C: the first card is the 4060 Ti, and the 5080's free memory is not checked at all.
- **Profiles:** every arm needs its own copy of the same seed profile (memory note ds41-profile-writeback). With the
  drafter loaded, the engine writes a 43 x 384 profile (66,048 B instead of 61,440; engine-options.md 2h). Never point
  C at `logs/ds41/daily-profile.bin`.
- **Slot folder:**
  - Give each arm its own `STRATA_DS4_SLOT_DIR`, or slot keep 0 for the speed arms.
  - The sweep configs shared the daily folder `logs/ds41/ds4-slots`: both use the log's parent. The first arm (on-v10)
    **removed 8 slots at start** ("not this model's or incomplete"; the cleanup also removes slots older than 7 days,
    main.cpp:600-640).
  - **C's identity differs** (mtp=3, another pack's files; model.cu:5318-5337). A C run in the daily folder would delete
    every daily conversation as foreign.
- **Pack:** C needs its own pack folder (2.7). A and B use the daily pack unchanged.
- **Harness hygiene:** hold `tmp/gpu-test.lock`. Start servers with `8>&- 9>&-`. Keep pgrep/pkill patterns off launch
  lines. Drop the model files from the page cache before each arm (work/ds41/tune/dropcache.py), as the sweep did.

### 3.5 Suggested gate order (for Karl's decision; nothing scheduled)

1. **No GPU:** check the Q2K/Q4K header against 2.7; build C's pack folder (CPU, header-only).
2. **Short GPU smoke:**
   - C starts with the expected placement lines (2.2, 2.3).
   - `--spec-eval` greedy identity: DSpark against `--dspark none`, `--no-expert-cache`, a few prompts.
   - Write and run the sampled distribution test (2.6).
3. **Speed, 3 passes each, 128K, same seed profile, own slot folders:** A, B, C-draft1, C-draft2 (W1-W3, P4K, P20K).
   Add a B0 arm (`DS4_LAYER_MAJOR=0`) only if step 4 fails.
4. **Memory, everything up, full store:** B (and C) at ~32K / 64K / 97K / near 128K: lowest MemAvailable against
   14 / 13 / 12, swap rule, kcheck, VRAM peak.
5. **Rounding gate** (the 10-26 five checks, ≥ 2-chunk prefix): B against A's base and references; C's placement the
   same way. DSpark itself is covered by step 2.
6. **End tests on the winner:** conversation cache + follow-up re-reads (after.py daily_tests). Then Karl decides; the
   daily config is unchanged until then.
