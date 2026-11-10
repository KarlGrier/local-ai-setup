# strata-dsv41 (Strata v0.2.4): speed settings and what they do to the answers

Read-only code survey, 2026-10-24. Nothing was built, started or run on the GPU. Numbers marked "computed" come from the
code's own formulas and our pack's tensor list; numbers marked "measured" come from our own arm logs
(`results/ds41/arm-s70-1023-2340`, `arm-dsp70-1024-0001`). Anything else is reading of the code ("static").

## How to read this

- Engine: `strata-v024/src/dsv41/` at tag v0.2.4. Our binary `engine-v024-ds41/strata-dsv41` is "stock v0.2.4
  (96ca4383)" (its SOURCE file). Line numbers are v0.2.4's. From v0.2.4 to v0.2.4.2 the only change under `src/dsv41`
  is `ds4_gg_cpu.cpp` `min_tokens()` (IQ1_M CPU rows from one token; bit-identical, speed only; on Zen 5 the AVX-512
  rows were already taken from one token, `ds4_gg_cpu.cpp:196`, so no effect on our PC). The server changed two DeepSeek
  defaults in v0.2.4.2 (slots and auto pin on; see 2j).
- Short file names: `model.cu` = `src/dsv41/ds4_model.cu`, `main.cpp` = `ds4_main.cpp`, `model.hpp`, `store.hpp`,
  `pool.hpp`, `os.hpp`, `kernels.cu`, `iq.cu`, `gguf.cu`, `gg_cpu.cpp`, `iq_cpu.cpp`, `engram_io.hpp` (all `ds4_*` in
  `src/dsv41`); `server.py`, `frontend.py`, `dsml.py` = `strata-v024/serve/...`; `template` =
  `strata-v024/serve/fixtures/deepseek41/chat_template.jinja` (the server swaps our pack's template for this one,
  `dsml.py:223,234-243`; our server.out says so).
- "Outputs" column:
  - **no**: speed only, the same bits.
  - **bits**: the numbers can differ in the last bits (other kernel, other summation order, an expert computed on the
    CPU instead of the GPU). Not a quality loss, but greedy answers can flip at near-ties.
  - **LOSSY**: work is dropped or approximated. Never for our runs.
  - **samp**: changes which random draws are used, not the distribution.
  - **content**: changes what the model is asked for or allowed to write (thinking settings).

## What the engine does with our config (log + code)

Config `configs/DS41-v024-s70.json`: `--max-context 32768 --eos 1 --dspark auto --dspark-conf 0.65 --tp 2 --ssd-cache 70`,
env `STRATA_DS4_PROMPT_SKIP=0`, `DS4_STORE_FLOOR_GB=16`.

| What | Result | Evidence |
|---|---|---|
| `--tp 2` | Falls back to 1: the IQ types have 256-value blocks and n_ff 2304 / 2 = 1152 is not a multiple of 256. Two groups of one GPU = a plain layer split | log line 2; `model.cu:1894-1911` |
| Side effects of `--tp 2` anyway | (1) prompt chunk default 8192 instead of 1024 (`own_default` is false because `o.tp > 1`, `model.cu:1968-1969`); (2) decode threads stay off: `par = o.threads \|\| tp > 1` uses the reduced tp (`model.cu:1917`), so decode runs `forward_serial` (one host thread for both GPUs, `model.cu:8336-8389`) | code |
| Layer split | CUDA0 (5080) layers 0-21, CUDA1 (4060 Ti) 22-39 + head; picked by a DP that balances prompt streaming (`model.cu:2103-2149`) | log |
| DSpark | not loaded (`--dspark auto`: experts 132 GB > 1.5 x 23 GB VRAM, `model.cu:1998-2008`) | log |
| VRAM experts | 1156 of 8448 (GPU0) + 201 of 6912 (GPU1) = 1357 of 15360; 14003 (121 GB) on the CPU lane, read in place from the GGUF | log |
| RAM store | 70 GB = 6814 slots of 10.3 MB, policy 0 (LRU), 8 reader threads, O_DIRECT; 6558 = 6814 - (192 + 64) preloaded from the profile | log; `model.cu:4585-4586` |
| CPU lane | 16 threads = 16 physical cores (SMT siblings never used on Linux) | log; `model.cu:116-143, 4626-4655` |
| Lookahead (next-layer prefetch) | off: the store switches it off unless `DS4_AHEAD` is set | `model.cu:4530-4532` |
| Prompt skip | off by our env, and inactive anyway on two GPUs (needs every trunk layer on one GPU) | `model.cu:7880-7885` |
| Layer-major prompt (each expert read once per prompt) | inactive: needs one GPU | `model.cu:7793` |
| Server | engine started at nice +5 (the 9950X3D's Radeon iGPU is in `HIP_IGPU_ARCHS`); slots off, auto pin off (v0.2.4 defaults); thinking capped at max_tokens - reserve | server.out; `server.py:1034-1040, 3287-3301, 3400` |

## Key findings

1. **Uneven layer split: supported only through the environment.** `DS4_SPLIT=a,b` = trunk layers per GPU in device
   order (counts, not first-layer indices). `--layer-split` and the server's `layer_split` are accepted and ignored
   (`main.cpp:1265`). (2a)
2. **No "expert-only helper" GPU and no per-GPU expert budget.** VRAM expert slots live only on the device that owns
   the layer; `--reserve-mib`/`--vram-experts` apply to every card alike. Tensor parallel is impossible for these IQ
   quants. (2b)
3. **On our two GPUs every prompt chunk re-reads the SSD-resident experts.** The layer-major path with its layer cache
   (one read per prompt) needs one GPU. A 20K prompt is 3 chunks of 8192 max (6585 each). Measured disk per prompt:
   P4K (1 chunk) 75-87 GB, P20K (3 chunks) 174-184 GB, which fits this (static attribution). A larger
   `--prefill-chunk` means fewer re-reads but about 215-232 KB of VRAM per chunk token per GPU (computed), taken from
   the VRAM experts. (2c)
4. **The prompt path computes all experts on the GPUs** (CPU-lane experts streamed over PCIe from the store or the
   SSD). There is no CPU/GPU share knob. For 2-2047-token prompts a timing-based cost model picks "flow" (GPU) or
   "windows of 16" (CPU lane computes). (2d)
5. **`--tp 2` vs `--tp 1` differ here only in the default chunk (8192 vs 1024).** `--threads on` (per-GPU decode
   threads) is off in our runs and is an untried lossless knob. (2l)
6. **CPU threads are capped at the physical-core count on Linux (16).** `--cpu-threads` can only lower it. (2e)
7. **I/O is plain `pread`** (no io_uring): one blocking read per expert matrix (2.6-3.4 MB, 4 KiB-aligned O_DIRECT).
   Queue depth = threads: store 8 (`DS4_STORE_THREADS`), prompt flow 8 per GPU (`DS4_READERS`), Engram 16
   (buffered). (2e)
8. **RAM store**: LRU by default; `lfulru` behaves exactly like `lfu`; all slots are sized for the largest expert
   (10.26 MB) while this pack's experts average 8.60 MB, so about 16 % of the 70 GB is padding (computed).
   `DS4_STORE_FLOOR_GB` only stops growth; the store gives memory back only below 4 GB MemAvailable (hard-coded). (2f)
9. **`expert-profile.bin` is rewritten after every request**, prompt routing included. It decides VRAM placement and
   the store preload at the next start. Our pack's file now holds 163.8 M more routing counts than the shipped
   `profile-2.00.bin` (+38 %, computed). **Consecutive A/B arms therefore start from different placements.**
   Restore the file before each arm. (2h, 2i)
10. **Drafting = DSpark only** (DeepSeek's `mtp.*` blocks, from Unsloth's dflash GGUF). There is no prompt-lookup,
    n-gram or suffix drafter, and no nextn layer in the IST-DAS GGUF. "Markov rank 256" is DSpark's bigram bias head.
    The "n-gram" table is Engram (part of the trunk, not a drafter). DSpark costs about 8 GB on GPU0. Measured: VRAM
    trunk experts 1357 -> 381; W1-W3 decode 22.64 -> 20.85 tok/s. (2g)
11. **Run-to-run differences have several sources in the code**: CPU-lane and GPU expert maths differ (ggml Q8_K
    activations per 256 values vs int8 per 32); swaps into VRAM land asynchronously; the profile keeps changing; the
    path pick is timing-based; the sampling counter is not reset per request. No single switch makes outputs repeatable;
    the best combination is in 2i. (2i)
12. **Thinking**: effort words map to the template's "Reasoning Effort: N" line (low 50, medium 62, high 75 = default,
    max 100). The default budget is 32768, but the server caps it at max_tokens - max(512, max_tokens/4). Our 3072-token
    W runs therefore think at most 2304 tokens (matches the logs). (2k)
13. **The server sends `repetition/frequency/presence_penalty`, `logit_bias`, `ckpt`, `pipe`, `aux_cpus`, `pcie_frac`
    and `spec_min_p` keys that strata-dsv41 silently ignores.** Its `GEN` parser knows only temperature, top_p, top_k,
    min_p, seed, spec, dspark_conf, pin and dspark_cum (`main.cpp:304-313`).

---

## 1. Settings

### 1.1 Command-line flags (`main.cpp:1200-1274`, defaults `model.hpp:25-61`)

| Flag | Default | What it does | Where | Outputs |
|---|---|---|---|---|
| `--pack DIR` | required | the pack folder (`ds4.txt`, `tensors.txt`, `engram.bin`, `expert-profile.bin`) | main.cpp:1209 | - |
| `--gpus 0,1` | every visible GPU | which CUDA devices, in this order (CUDA_VISIBLE_DEVICES order) | main.cpp:1210-1211; model.cu:1876-1879 | bits (placement) |
| `--max-context N` | 32768 | context; sizes the compressed KV (`cap = ctx/ratio + 1`), score buffers and the indexer slab | main.cpp:1212; model.cu:2039, 2255, 2833 | no |
| `--reserve-mib N` | 600 | VRAM left free on **each** GPU before experts are placed | main.cpp:1213; model.cu:3819-3820 | bits (placement) |
| `--vram-experts F` | 1.0 | share of each GPU's leftover VRAM used for experts (tests) | main.cpp:1214; model.cu:3819-3820 | bits (placement) |
| `--cpu-threads N` | 0 = physical cores | CPU-lane workers; can only lower (min with the core count) | main.cpp:1215; model.cu:4653 | no (rows are per-thread whole, see 2i) |
| `--expert-profile FILE\|none` | `<pack>/expert-profile.bin` | hot-expert counts, read at load and **written back after every request**; `none` = no profile (no preload, VRAM by index) | main.cpp:1216, 1286-1287, 930, 957; model.cu:2537-2546, 8996-9006 | bits (placement) |
| `--ssd-cache GB` | -1 = auto: min(48, MemAvailable - 12), off < 4 | RAM store size (GGUF packs only); 0 = off (CPU lane then reads the mmap/page cache) | main.cpp:1217; model.cu:4457-4469 | no |
| `--ssd-policy lru\|lfu\|lfulru` | lru (0) | store replacement; `lfulru` (2) runs the same code as `lfu` | main.cpp:1218-1221; store.hpp:389-397 | no |
| `--eos ID[,ID]` | 1 | stop tokens | main.cpp:1222 | - |
| `--no-expert-cache` | cache on | no VRAM<->CPU swaps (static placement from the profile; one more VRAM slot per layer) | main.cpp:1223; model.cu:3888-3896, 5968, 5912 | bits (less run-to-run variation) |
| `--dspark on\|off\|none\|auto` | auto | `auto`: load the drafter only if routed experts <= 1.5 x VRAM; `off`: loaded but not used (still takes ~8 GB); `none`: not loaded | main.cpp:1224-1228; model.cu:1998-2009 | samp (on); VRAM |
| `--dspark-conf F` | 0.5 (ours 0.65) | drafts verified while their confidence >= F | main.cpp:1229, 181-183 | samp |
| `--dspark-block N` | 0 = pack's block (5) | at most N drafts a round | main.cpp:1230; model.cu:2010, 6449-6452 | samp |
| `--tp N` | 2 | tensor-parallel width; falls to 1 for our IQ quants. Still sets the chunk default (8192 vs 1024) | main.cpp:1231; model.cu:1894-1911, 1968-1969 | bits |
| `--threads on\|off` | off | a host thread per GPU enqueues its layers (decode via `forward_par`); with tp > 1 always on | main.cpp:1233; model.cu:1917, 8314-8316, 8393-8408 | no (static) |
| `--prefill-chunk N` | -1 = auto (8192 here) | prompt chunk; 0 = windows of 16 only; rounded down to x16, min 256, max 32768 | main.cpp:1232; model.cu:1968-1984, 816 | bits (other chunking) |
| `--mmap-experts on\|off\|auto` | auto | GGUF: off = copy the hottest CPU-lane experts into RAM once (static, no store adaptation); auto/on = read in place | main.cpp:1235-1237; model.cu:4144-4183 | no |
| `--vision on\|off` | on | vision tower if the pack has one (ours has none) | main.cpp:1234 | - |
| `--layer-split X` | - | **ignored** ("this engine balances its own split") | main.cpp:1265 | - |
| `--serve` | - | the server protocol (`GEN`/`STOP`/`QUIT`) | main.cpp:1263, 318-959 | - |
| `--profile-run IDS.json [--window N]` | - | feed segments, no logits, only to build `expert-profile.bin` | main.cpp:1097-1128 | - |
| `--score`, `--spec-eval`, `--ids/--n/--temperature/--seed`, `--dump-logits`, `--pack-info`, `--verbose` | - | tests and diagnostics (`--verbose` also prints path picks and prompt stream stats) | main.cpp:1246-1262 | - |

Unknown flags (e.g. the Qwen engine's `--peer-device`) end the engine with exit 2 (`main.cpp:1269-1273`).

### 1.2 Environment variables of the engine

Every `getenv` in `src/dsv41` (116 reads) plus the two the linked CPU kernels read. "-" in Outputs = not applicable.

#### Placement and memory

| Variable | Default | What it does | Where | Outputs |
|---|---|---|---|---|
| `DS4_SPLIT=a,b,..` | unset (DP split) | trunk layers per GPU group, in order; leftover layers go to the last group; drafter stays on the first | model.cu:2106, 2150-2162 | bits (placement) |
| `DS4_TP_ALIGN` | 128 | alignment n_ff/tp must meet for tensor parallel (the 256-block check stays) | model.cu:1905 | - |
| `DS4_COPY_GB` | unset | static copy of the hottest n GB of CPU-lane experts into RAM | model.cu:4172 | no |
| `DS4_COPY_NUMA` | 2 parts if 2 nodes | NUMA parts of copies (tests) | model.cu:4186 | no |
| `STRATA_DS4_RAM_TIER=1` | 0 | old RAM tier (hottest after VRAM, moved between windows); measured slower upstream | model.cu:1016-1035 | no |
| `STRATA_DS4_LANE_FREE` | 2 | cores left free for the launch thread, only when the lane would take every logical CPU and no `--cpu-threads` (not our case: 16 of 32) | model.cu:4633-4651 | no |
| `DS4_COMMIT_CAP_GB` | unset | Windows commit cap (tests) | model.cu:1083-1091 | - |
| `DS4_CPU_SMT=1` | 0 | Windows only: also SMT siblings | model.cu:117-122 | - |

#### Prompt (prefill) path

| Variable | Default | What it does | Where | Outputs |
|---|---|---|---|---|
| `DS4_CHUNK=N` | unset | chunk size override (tests; min 16) | model.cu:1970-1974 | bits |
| `DS4_CHUNK_MIN=N` | 512, or 2 when every GPU is on the flow (ours) | runs shorter than this go to windows of 16; setting it also disables the path calibration (always flow from N) | model.cu:1972, 2707-2712, 7518 | bits |
| `DS4_WINDOWS=1` | unset | no chunked path at all | model.cu:1922-1924 | bits |
| `DS4_PATH_PICK=0` | on | always the flow (no timing-based flow/windows pick for < 2048 tokens) | model.cu:7517-7520, 7697-7748 | bits (removes a run-to-run source) |
| `DS4_FLOW=0` | on | old streaming: every CPU-lane expert of each layer in batches, not only picked ones | model.cu:2661 | bits |
| `DS4_FLOW_TP=1` | 0 | TP group members on the flow (n/a, no TP) | model.cu:2662-2665 | - |
| `DS4_READERS` | 8 | prompt reader threads per GPU (IoQueue; O_DIRECT reads into pinned staging) | model.cu:2659-2660, 2687, 2692 | no |
| `DS4_RING_MB` | auto: 400 (16 when experts nearly fit VRAM) | VRAM ring the streamed experts land in (and as much pinned staging) | model.cu:2796-2815, 2873-2878 | no |
| `DS4_SPEC_Q` | 0.9 | queue a layer's "likely" experts (P(picked) >= q from the profile) before the layer routes; > 1 = none | model.cu:3228-3278 | bits (stream order, see 2i) |
| `DS4_SPEC_WASTE` | 0.2 | stop early reads for the run once > 20 % went unpicked | model.cu:3250-3256 | bits |
| `DS4_FLOW_PUMP_WAIT=0` | on | keep issuing reads/DMAs while the layer's attention runs | model.cu:7015-7024 | no |
| `DS4_READAHEAD_MB` | 2048 | `fadvise WILLNEED` read-ahead, non-flow path only | model.cu:3062-3099 | no |
| `DS4_LAYER_MAJOR=0` | on (one GPU only) | layer after layer through all chunks, experts read once per run | model.cu:7786-7843 | bits |
| `DS4_LAYER_CACHE_MB` | auto (RAM - 8 GB) | RAM for the layer-major layer cache | model.cu:7815-7820 | no |
| `DS4_LAST_WINDOW=1` | unset | last prompt token in a window of its own (A/B) | main.cpp:773-774, 793-796 | bits |
| `STRATA_DS4_NO_LIGHT=1` | 0 | experts with <= 16 rows in a chunk through the GEMM tiles instead of the int8 "light" kernels | iq.cu:1222-1228 | bits |
| `STRATA_DS4_NO_TC=1` | 0 | no tensor cores in the GGUF expert/prompt kernels (F32 kernel) | gguf.cu:932-955; iq.cu:1083-1091 | bits |
| `DS4_IQ_MAX_SMS`, `DS4_IQ_CTA_PER_SM` | all | grid size of the IQ kernels (benchmarking) | iq.cu:1134-1135 | no |

#### Decode path and CPU lane

| Variable | Default | What it does | Where | Outputs |
|---|---|---|---|---|
| `DS4_SYNC=1` | 0 | synchronous decode (no mailbox to the CPU lane) | model.cu:979, 8161 | no (static) |
| `DS4_ASYNC_T` | 8 | windows up to T tokens use the async mailbox | model.cu:983 | no |
| `DS4_MOE_TOKEN=0` | 1 | T=1 through `win_experts` instead of `moe_gate_up/down` ("the same bits, no faster") | model.cu:980-982 | no |
| `DS4_AHEAD` | 1, but **0 with the store** unless set | 1: guess the next layer's experts on the GPU and read them early (store: low-priority prefetch); 2: also the layer after | model.cu:984-990, 4530-4532, 6136-6169 | no |
| `DS4_AHEAD_EXTRA` | 0 | guesses beyond top-k | model.cu:991, 8763 | no |
| `DS4_AHEAD_ORDER=0` | 1 | compute early-read experts first (slots and sums unchanged) | model.cu:992-993, 6294-6309 | no |
| `DS4_IQ_PF_COLD=1` | prefetch all | without a store: `madvise WILLNEED` only non-resident experts | model.cu:5534-5543 | no |
| `DS4_ATTN_SPLIT=1` | 0 | split-KV decode attention (another summation order, about 4e-7) | kernels.cu:1785-1792, 2016-2019 | bits |
| `DS4_AR_F16=1` | 0 | FP16 all-reduce, groups of > 2 GPUs only | kernels.cu:2155-2162 | lower precision (n/a here) |
| `STRATA_DS4_TQ_WORDS=1` | 0 | trellis expert types only | tq.cu:470-477 | - |

#### RAM store (`--ssd-cache`)

| Variable | Default | What it does | Where | Outputs |
|---|---|---|---|---|
| `DS4_STORE_GB` | the flag | size override | model.cu:4461 | no |
| `DS4_STORE_THREADS` | 8 | O_DIRECT reader threads = concurrent reads | model.cu:4489; store.hpp:95 | no |
| `DS4_STORE_FLOOR_GB` | 8 (ours 16) | no new 64-slot chunk (~0.66 GB) while MemAvailable < chunk + floor; never shrinks | model.cu:4490; store.hpp:465-470 | no |
| `DS4_STORE_POLICY` | `--ssd-policy` | 0 lru, 1 lfu (heat x 0.97 every 240 accesses of the layer), 2 = lfu | model.cu:4491; store.hpp:48, 62-64, 389-397 | no |
| `DS4_STORE_RESERVE` | 192 | slots kept evictable; preload leaves reserve + 64 free | model.cu:4493, 4585 | no |
| `DS4_STORE_PRELOAD=0` | on | do not fill the store from the profile at start | model.cu:4562-4589 | no |
| `DS4_STORE_ZC=1` | 0 | GPU computes store-resident experts over PCIe (zero-copy). **One GPU only**; upstream measured slower; which lane computes an expert depends on timing | model.cu:4495-4499, 4590-4617, 8790-8791 | bits, run-to-run |
| `DS4_STORE_ZC_FRAC` | 50 | share of experts the GPU may take in ZC mode | model.cu:4494 | bits |
| `DS4_STORE_PREGROW` | Linux: on with ZC | commit/register the whole arena at start | store.hpp:97-107 | no |
| `DS4_SETTLE_STORE=0` | 1 | after a chunked prompt, read its hot experts (heat >= 4) into the store (blocking, can evict) | model.cu:5928-5945 | no |

#### GPU expert cache (VRAM <-> CPU lane swaps)

| Variable | Default | What it does | Where | Outputs |
|---|---|---|---|---|
| `DS4_CACHE_MARGIN` / `DS4_CACHE_BONUS` | 1.25 / 1.0 | swap in the hottest CPU-lane pick when heat > coldest VRAM heat x margin + bonus | model.cu:1010-1015, 6060-6073 | bits |
| `DS4_CACHE_DECAY` | 0.9 | heat x decay every 256 tokens | model.cu:1014, 6046-6051 | bits |
| `DS4_CACHE_INFLIGHT` | 8 | swaps in flight (one per layer at a time) | model.cu:1015, 6060 | bits |
| `DS4_CACHE_THREADS` | 1 | threads preparing swaps (each reads the expert with a buffered `pread`) | model.cu:2753, 5853-5856 | bits |
| `DS4_SETTLE_MS` | 6000 | after a chunked prompt, swap rounds for up to this long (inside the prompt's time) | model.cu:5907-5927 | bits |
| `DS4_CHECK_SWAPS=1` | 0 | verify every swap against the file (slow) | model.cu:1120, 5806-5844 | no |

#### Engram (n-gram table, 111 GB IQ4_NL on the SSD)

| Variable | Default | What it does | Where | Outputs |
|---|---|---|---|---|
| `DS4_ENGRAM_THREADS` | min(16, max(4, logical CPUs/2)) = 16 | Engram row reader threads (buffered `pread` on Linux) | model.cu:2461-2463; engram_io.hpp:234-241 | no |
| `DS4_ENGRAM_CACHE_MB` | min(256, max(16, MemAvailable_MB/64)) = 256 | clock-evicted row cache | model.cu:2464-2467; engram_io.hpp:38-60 | no |
| `DS4_EG_DIRECT=1` | 0 | Windows only: unbuffered Engram reads | model.cu:2470-2492 | - |
| `DS4_EG_CHECK` | unset | compare each unbuffered row with a buffered read (Windows path) | engram_io.hpp:215 | - |

#### DSpark drafter

| Variable | Default | What it does | Where | Outputs |
|---|---|---|---|---|
| `DS4_DSPARK_CONF` | 0.5 | read into `conf_threshold` but **never used** (dead); the floor is `--dspark-conf` | model.cu:898 | - |
| `STRATA_DS4_DSPARK_CUM=F` | 0 (off) | also stop drafting when the product of confidences < F | main.cpp:152-162, 181-183 | samp |
| `DS4_DSPARK_MAX=N` | 0 | at most N drafts a round (`--dspark-block` sets it when unset) | model.cu:915, 2010 | samp |
| `DS4_DSPARK_SAMPLE=1` | 0 | sampled requests draw drafts from the drafter's distribution (else its argmax) | model.cu:908-913, 6555-6569 | samp |
| `DS4_DSPARK_QTEMP=f` | 1.0 | those draws at f x temperature | model.cu:914, 6557 | samp |
| `DS4_MK_SPLIT=0` | on | markov steps split over a head group of >= 2 GPUs (n/a: head group of 1) | model.cu:2378-2396 | - |
| `DS4_DSPARK_DUMP`, `DS4_ROUND_LOG` | unset | dumps / acceptance log | model.cu:916; main.cpp:1139 | - |

#### Conversation state (engine side)

| Variable | Default | What it does | Where | Outputs |
|---|---|---|---|---|
| `STRATA_DS4_SLOT_KEEP=1` | off in the engine | set a displaced conversation aside (RAM, then folder) and take it back | main.cpp:331-353 | no (restores exact state) |
| `STRATA_DS4_SLOT_CAP` | 4 | conversations kept in RAM; past that the LRU goes to the folder | main.cpp:350, 497-506 | no |
| `STRATA_DS4_SLOT_MIN` | 1024 | shortest conversation set aside | main.cpp:351, 481 | no |
| `STRATA_DS4_SLOT_DAYS` | 7 | folder entries older than this removed at start | main.cpp:352, 609 | no |
| `STRATA_DS4_SLOT_GB` | 16 (server sets 2) | folder cap, LRU trimmed | main.cpp:353, 419-440 | no |
| `STRATA_DS4_SLOT_DIR` | `<pack>/slots` (server sets `<log dir>/ds4-slots`) | slot folder | main.cpp:577-579 | no |
| `STRATA_DS4_REUSE=0` | 1 | every request reads its whole prompt (A/B, repeatability) | main.cpp:349, 677-680 | bits |

#### LOSSY switches (all off in our config)

| Variable | Default | What it does | Where | Outputs |
|---|---|---|---|---|
| `STRATA_DS4_PROMPT_SKIP` (alias `DS4_YOCO`) | **1** | long prompts (>= 1024 rows before the kept tail): layers 20-39 run only the last (40-20) x 127 + 128 = 2668 rows; 2 = only the last 128 rows; 0 = off. Needs all trunk layers on one GPU | model.cu:7862-7887, 7902-7929 | **LOSSY** (upstream: 99.5 % same top-1) |
| `DS4_YOCO_KEEP=N` | 0 | keep fewer rows in that skip | model.cu:7911-7916 | **LOSSY** |
| `STRATA_DS4_DISK_SKIP_W=w` | 0 (off) | decode/verify: drop a routed expert whose route weight < w x the token's sum and whose pages are not in RAM; no renormalisation | model.cu:1036-1045, 6230-6257 | **LOSSY** (drops experts) |
| `STRATA_DS4_DISK_SKIP_FROM=L` | 0 | ... from layer L on | model.cu:1046-1049 | **LOSSY** |

There is no route bias, no expert-count reduction and no lower-precision expert option in this engine besides these
(the DSpark/`DS4_AR_F16` items above do not apply here).

#### CPU kernel choice (checked bit-identical at run time; speed only)

| Variable | Default | What it does | Where | Outputs |
|---|---|---|---|---|
| `DS4_GG_IQ256` | 2 = from `min_tokens` | Strata's AVX2 multi-token IQ rows vs ggml's dot | gg_cpu.cpp:87-95, 197-212 | no (checked vs ggml once per type: gg_cpu.cpp:96-145) |
| `DS4_GG_IQ512` | rule by CPU family | AVX-512 IQ rows (Zen 5: IQ2_XXS/IQ2_XS always, IQ1_M from 1 token) | gg_cpu.cpp:176-196 | no |
| `DS4_IQ_OWN`, `DS4_IQ_AVX2`, `DS4_IQ_GATHER` | measured | IQ3/IQ2 own rows vs the native lane | iq_cpu.cpp:623-690 | no |
| `DS4_MX_TIER`, `DS4_MX_PF` | measured / 0 | MXFP4 CPU rows (drafter/Unsloth sets; not our IQ experts) | gguf_cpu.cpp:262-327 | no |
| `STRATA_FORCE_AVX2=1`, `STRATA_FORCE_ISA` | unset | linked CPU kernels: pretend no AVX-512 / lower ISA | src/kernels/cpu/expert_layout.cpp:27-44; vendor/exl3_cpu.cpp:1024 | no (static) |
| `STRATA_GLM_EXL3_DECODE` | unset | EXL3 packs only | vendor/exl3.cu:1280 | - |

#### Diagnostics only

`DS4_PROF` (GPU time per stage; model.cu:1142-1145), `DS4_FLOW_STATS` (prompt stream stats: files vs RAM, O_DIRECT vs page cache,
waits; model.cu:8085-8107), `DS4_TRACE` / `DS4_TRACE_AHEAD` (routing traces; model.cu:1153, 6203-6229, 7078-7089),
`DS4_DUMP_H/L/R/Y`, `DS4_PRED_DUMP`, `DS4_XIN_DUMP`, `DS4_XIN_N` (model.cu:1123-1151), `DS4_TOKLOG`, `DS4_NO_EOS`,
`DS4_SCORE_PREFIX` (main.cpp:1427, 1397, 1016), `DS4_GG_VERBOSE`, `DS4_DBG_GG`, `DS4_IQ_VERBOSE`.

Windows or AMD only (no effect here): `DS4_TIMER_MS` (os.hpp:41-51), `DS4_WIN_DIRECT` (os.hpp:80-86), `DS4_WIN_SUBMIT`
(kernels.cu:2129-2138), `DS4_PF_ALL` (os.hpp:376-387), `STRATA_DS4_HIPK`, `HIPK_CFG`, `HIPK_DBG` (ds4_iq_hip*.inc).

### 1.3 Server settings on the DeepSeek path (`serve/server.py`, `frontend.py`, v0.2.4)

| Setting | Default | What it does | Where | Outputs |
|---|---|---|---|---|
| `STRATA_DS4_SLOT_KEEP` (passed to the engine) | **"0" in v0.2.4, "1" in v0.2.4.2** | conversation slots | server.py:3482, 3486-3496 (v0.2.4.2 diff) | no |
| `STRATA_DS4_SLOT_GB` | "2" | folder cap | server.py:3483, 3493 | no |
| `STRATA_DS4_SLOT_DIR` | `<dir of config "log">/ds4-slots` (ours: `logs/ds41/ds4-slots`, never created) | slot folder | server.py:3494-3496 | no |
| `STRATA_DS4_AUTO_PIN` | **off unless "1" in v0.2.4; on unless "0" in v0.2.4.2** | `pin=N` at the end of the leading system messages (a checkpoint other agents behind the same system prompt and tools go back to) | server.py:4921-4943 | no |
| thinking budget | 32768 when neither request nor config sets one; request `reasoning_budget_tokens` / `thinking_budget_tokens`, 0 = none | thinking is closed with a wrap-up text when reached | server.py:204, 4155-4169 | content |
| budget vs max_tokens (#984) | reserve = min(max(512, max/4), max/2) | budget capped at max_tokens - reserve (3072 -> 2304) | server.py:5107-5113 | content |
| small max_tokens (48..1023), no budget | half of max_tokens | DS41 only | server.py:205, 5099-5106 | content |
| reasoning effort | template default "high" (75) | see 2k | frontend.py:138-178; template:22-29, 209 | content |
| sampling defaults | model card T 1.0, top_p 1.0; the config's block wins (ours T 1.0 / 0.95 / 20 / min_p 0.05) | | server.py:8061-8069, 5084-5088 | samp |
| `top_k` | 0 or > 64 sent as 64 | the engine's sampled path keeps at most 64 | server.py:1397-1400 | samp |
| `seed` | only an int > 0 is forwarded; engine default 0 | Philox seed (see 2i) | server.py:1423-1425 | samp |
| penalties, `logit_bias`, `ckpt=0`, `pipe`, `aux_cpus`, `pcie_frac`, `spec_min_p`, `cvec` | - | sent as GEN keys but **ignored by strata-dsv41** | server.py:1408-1462; main.cpp:304-313 | none (no effect) |
| `STRATA_ENGINE_NICE` | 5 on Linux with a Radeon iGPU (ours), else 0 | engine started at nice +N; 0 = off | server.py:1034-1040, 3287-3301, 3400 | no |
| `"layer_split"` | auto | becomes `--layer-split`, which strata-dsv41 ignores | server.py:3010-3043, 3115-3116 | - |
| `engine_ready_s` | 900 (ours 3600) | start timeout | server.py:3043-3053 | - |

---

## 2. Answers

### a. Uneven layer split: **supported (environment variable only)**

- `DS4_SPLIT=a,b` (`model.cu:2150-2162`) gives each GPU group a **count** of trunk layers in device order. Any layers
  left over go to the last group. The DSpark blocks always stay with the first group. Example: `DS4_SPLIT=24,16` puts
  layers 0-23 on CUDA0 (5080) and 24-39 + the head on CUDA1. The head always follows the last layer
  (`model.cu:2167`).
- Setting `DS4_SPLIT` also switches off the automatic split, a dynamic program that minimises the busiest card's
  expert streaming for the prompt pipeline (`model.cu:2103-2149`: "the contiguous split that streams the least into
  its busiest member"). Without chunks it would split by free memory (`model.cu:2084-2102`).
- `--layer-split` is accepted and thrown away (`main.cpp:1265`), so the server's `"layer_split"`
  (`server.py:3010-3043`) has no effect on this engine. Its syntax (first layer of each later GPU) differs from
  `DS4_SPLIT`'s (counts).
- What moves (static): dense weights are about 0.14 GB per layer (log: 3.08 GB / 22 layers, 2.78 GB / 18 + head). VRAM
  experts are placed per group with one uniform fraction for that group's layers (`model.cu:3838-3851`). Moving layers
  therefore mostly moves the same VRAM between layers, and decode should change little. The prompt pipeline balance
  changes more. Not measured.

### b. GPU1 as an expert-only helper card: **not supported.** Per-GPU expert budget: **not supported** (only indirect)

- VRAM expert slots are allocated only on the devices of the layer's own group (`place_experts`,
  `model.cu:3898-3911`), and a layer's experts are read only through that device's table. There is no cross-device
  expert tier and no `--peer-device` here (unknown flags exit, `main.cpp:1269-1273`).
- The only way both cards share a layer is tensor parallel (`tp == number of GPUs` lets unlike cards form one group,
  `model.cu:1925-1931`). It is refused for these quants: the 256-value IQ blocks need `(2304/tp) % 256 == 0`
  (`model.cu:1895-1911`). `DS4_TP_ALIGN` relaxes only the separate 128 alignment.
- Per-GPU expert size: `--reserve-mib` and `--vram-experts` apply to every GPU alike (`model.cu:3819-3820`). Each group
  gets `frac = budget/want` of its own layers' experts (`model.cu:3838-3851`), so the only levers are `DS4_SPLIT` (which
  layers a card owns) and the per-card fixed buffers (prompt chunk, see c).

### c. Prompt chunk size: **supported** (`--prefill-chunk N`; `DS4_CHUNK` for tests)

- Default (`model.cu:1968-1969`): one card without `--tp`/`--threads` -> 1024. Otherwise 8192 (`kVlRows`) when the
  experts are read in place, which a GGUF always is (`model.cu:1950`). Ours: 8192 (log: "prompts in chunks of 8192").
  `--prefill-chunk 0` = windows of 16.
- Limits: rounded down to a multiple of 16, at least 256, at most `kMaxChunk = 4 x 8192 = 32768`
  (`model.cu:816, 1974`). If the buffers do not fit, the engine halves the chunk (down to 256) and then falls back to
  windows (`model.cu:2548-2596`). A prompt is cut into equal chunks: `nc = ceil(n/chunk)`, `per = ceil(n/nc)`
  (`model.cu:7918-7924`). 19,755 tokens -> 3 chunks of 6,585.
- Short prompts: runs under `chunk_min` (2 when every GPU is on the flow, ours) use windows. From 2 to 2047 tokens the
  cost model picks flow or windows (`model.cu:2707-2712, 7697-7748`).
- **Memory per chunk** (computed from `alloc_chunks`, `model.cu:2816-2898`; D 5120, hc 4, ff 2304, index top-k 512,
  candidate top-k 2048):
  - VRAM per chunk token, each GPU: about **215 KB** (h 82 KB, x/acc/y 61 KB, shared-expert FF rows 28 KB, x16 10 KB,
    cand 8 KB, glog 4 KB, the rest small). The GPU with layer 0 and the Engram layers (CUDA0) adds about 17 KB
    (embeddings + Engram rows), about **232 KB** in all.
  - Fixed per GPU: about 0.13 GB of slabs (q/o 256-row slabs, indexer scores, F16 weight scratch), plus the staging
    ring: 400 MB here (`DS4_RING_MB` auto, `model.cu:2799-2815`).
  - At 8192: about 1.76 GB (CUDA1) / 1.90 GB (CUDA0) + about 0.5 GB per card. The engine's own note agrees: going from
    8192 to 16384 "takes ~1.9 GB of VRAM experts" (`model.cu:813-815`).
  - These buffers are allocated **before** the experts (`model.cu:2548` vs `2637`), so every MB comes out of VRAM
    experts.
  - Pinned host RAM per GPU: 2 hand-off slots x chunk x 92 KB = **1.5 GB at 8192** (`model.cu:2792-2794, 2888-2889`),
    plus staging about the ring's size (`model.cu:2686`), plus about 0.4 GB of embedding/Engram staging on CUDA0. That
    is about 4 GB of page-locked RAM the store cannot use (computed).
- **Does each chunk re-read the SSD-resident experts? Yes on our two-GPU setup.**
  - Each (chunk, layer) builds its own stream from that chunk's routing: the "likely" set, then the picked rest
    (`model.cu:3237-3291`).
  - Each item is copied from the RAM store if it is there (`model.cu:3177-3185`). Otherwise it is read O_DIRECT into
    pinned staging (`pool.hpp:207-210`). O_DIRECT bypasses the page cache, so the next chunk reads it again.
  - The layer-major run with its layer cache ("so each is read once a run") needs `devs.size() == 1`
    (`model.cu:7786-7843`, check at 7793).
  - With about 6,600 tokens x 6 picks / 384 experts, about 100 picks per expert per layer, nearly every non-store
    CPU-lane expert is read per chunk (121 GB CPU lane - about 56-59 GB in the store = about 60-65 GB a chunk, static
    estimate).
  - Measured: P4K 75-87 GB, P20K 174-184 GB of disk reads. This fits, but the attribution is not verified (Engram
    reads, the post-prompt store refill and swaps add to it).
- Trade-off (not measured): `--prefill-chunk 20480` would make a 20K prompt one chunk (one read pass instead of 3).
  It costs about 2.6-2.8 GB more VRAM per card (12,288 x 215-232 KB). The 4060 Ti holds only 2.0 GB of experts in all,
  so it would lose them all and probably still not fit. The engine would then halve the chunk back to 10240 (static).
  `--tp 1` (chunk 1024) frees about 1.5 GB per card for experts (+about 350 experts, computed) but makes a 20K prompt
  20 chunks, so about 20 read passes.

### d. Prompt chunks computing SSD/RAM experts on the GPU: **supported, and it is the default.** CPU/GPU share knob for prefill: **not supported**

- The chunked "flow" streams every CPU-lane expert a chunk picks into a VRAM ring and computes it on the GPU. The
  sources are the RAM store (memcpy into pinned staging), the SSD (O_DIRECT into pinned staging), or the page cache.
  The CPU lane does no expert work there (`model.cu:560-566` comment; `flow_push` 3169-3227, `flow_pump` 3336-3436,
  `flow_layer` 3439-3496; Options comment `model.hpp:54-57`).
- The choice is binary per prompt: the flow (all GPU) or windows of 16, where the CPU lane computes its experts. For
  2-2047-token prompts `pick_path` decides from load-time speed probes (DMA, RAM -> staging, disk, CPU lane;
  `calibrate_paths` 7517-7650), page-cache residency samples and running means of past timings (`path_done`
  7771-7785). `DS4_PATH_PICK=0` (or `DS4_CHUNK_MIN`) forces the flow.
- Related: `DS4_FLOW=0` (old batches), `DS4_SPEC_Q`/`DS4_SPEC_WASTE` (early "likely" reads), `DS4_READERS`,
  `DS4_RING_MB`.
- Decode has a GPU-over-PCIe mode for store experts (`DS4_STORE_ZC=1`). It works with one GPU only
  (`model.cu:4498-4499`), was measured slower upstream (`model.cu:4495-4497`), and makes results timing-dependent.

### e. CPU threads and SSD reads

- **CPU workers**: `--cpu-threads N` (`main.cpp:1215`); 0 = the physical cores.
  - How chosen: `node_cores()` reads each NUMA node's `cpulist` and keeps the first logical CPU of each core
    (`model.cu:116-143`), which gives 16 on the 9950X3D.
  - Core 0 runs the decode "service" thread (pinned, `model.cu:2743-2747`). The pool gets the other 15 cores, pinned
    (`model.cu:4640-4655`, `pool.hpp:37-41`). The log's "16 threads" = 15 + 1 (`model.cu:4619-4623`).
  - `--cpu-threads` can only lower the count (`std::min`, `model.cu:4653`). SMT siblings are never used on Linux
    (`DS4_CPU_SMT` is Windows-only, `model.cu:117-122`).
  - Workers spin 20 ms after each batch before sleeping (`Pool(nw, c, 20000)`, `model.cu:4654`; `pool.hpp:96-116`). The
    service thread spins and naps after 2 ms idle (`model.cu:6171-6184`).
- **Reader threads and queue depth** (each thread does one blocking `pread` at a time, so queue depth = threads;
  `pool.hpp:132-235`). There is no upper clamp in the code, only `>= 1`.
  - RAM store (decode misses, preload, post-prompt refill): `DS4_STORE_THREADS`, default 8 (`model.cu:4489`,
    `store.hpp:95`). Guesses wait behind demand reads (`store.hpp:443`, `pool.hpp:161-169`).
  - Prompt flow: `DS4_READERS`, default 8 **per GPU**, so 16 on our box (`model.cu:2659-2660, 2692`).
  - Engram rows: `DS4_ENGRAM_THREADS`, default min(16, max(4, logical/2)) = 16, buffered `pread`
    (`model.cu:2461-2463`).
  - Load time: 12 fixed threads (`model.cu:4012, 4102, 4335`).
- **Read size and alignment**: one job per expert matrix, three per expert (`store.hpp:423-443`; flow
  `model.cu:3367-3395`).
  - Matrix sizes in our pack: IQ1_M 2,580,480 B, IQ2_XXS 3,041,280 B, IQ2_XS 3,409,920 B.
  - O_DIRECT: the offset is rounded down and the end up to 4096 (`os.hpp:98-102`). `pread` is called in pieces of up
    to 1 GiB (`os.hpp:139-151`). A read is buffered when the range is already in the page cache or O_DIRECT fails
    (`pool.hpp:207-214`).
  - No io_uring/libaio anywhere (grep: none). How the kernel splits a 3 MB O_DIRECT read into NVMe commands is up to
    the block layer (not in this code).
- Other read paths:
  - VRAM swaps read the incoming expert with a **buffered** `pread` from the GGUF, even when it sits in the store
    (`read_mx_file`, `model.cu:1737-1743, 5856`; `Pack::read_at` 381-385).
  - Without a store slot, the decode CPU lane reads the mmap (page faults + `madvise WILLNEED`, `os.hpp:310-323`).

### f. RAM store: sizing, policy, floor, fill and adaptation

- **Size**: `--ssd-cache GB` or `DS4_STORE_GB`. Auto (< 0): min(48, MemAvailable - 12 GB), off below 4 GB; 0 = off
  (`model.cu:4457-4469`). Only for GGUF packs with experts in place (`model.cu:4472`).
  - Slot size = the **largest** expert blob + 2 x 8 KiB, rounded to 4 KiB (`store.hpp:79-80`): 10.3 MB here (layer
    39, IQ2_XS). Slots = budget / slot = 6814 (`store.hpp:82`).
  - The arena is reserved once and committed in 64-slot chunks (about 0.66 GB) as slots are first needed
    (`store.hpp:83-86, 465-479`).
  - Computed: this pack's experts are 7.74-10.23 MB, 8.60 MB on average, so about 16 % of each slot (about 11 GB of
    70) holds no data. There is no knob for this.
- **Policy** (log "policy 0" = LRU):
  - 0 `lru`: the score is the last touch.
  - 1 `lfu`: decayed hit count, heat + 1 per access, x 0.97 every 240 accesses of that layer, ties by touch.
  - 2 `lfulru` (`--ssd-policy lfulru`): `score()` only tests `== kLru`, so it is identical to 1 (`main.cpp:1218-1221`;
    `store.hpp:48, 62-64, 389-397`).
  - The victim is the lowest score among slots that are unpinned, ready and not GPU-visible (`store.hpp:481-510`).
- **`DS4_STORE_FLOOR_GB`** (default 8): `grow()` refuses a new chunk while MemAvailable (or the cgroup's room,
  `model.cu:149-188`) < chunk + floor (`store.hpp:470`). It only stops growth.
  - Shrinking is separate and hard-coded: every 16 windows, if MemAvailable < 4 GB, chunks of 0.7 GB are given back
    until about 5 GB is free (`store_watch`, `model.cu:5955-5966`). A floor of 16 does not make the store give memory
    back at 16 GB.
- **Filled at start from `expert-profile.bin`: yes.** `preload_store` (`model.cu:4562-4589`) takes the profile's
  experts that are not in VRAM, ordered by count per byte. It fills up to `slots_max - (DS4_STORE_RESERVE 192 + 64)`
  and waits for the reads. Here that is 6558 experts in 5.5 s.
  - The "50.9 GB" in the log is 6558 x layer 0's blob (7.74 MB, `model.cu:4587-4588`), not the bytes read.
    `DS4_STORE_PRELOAD=0` turns the preload off.
- **Adapts at run time: yes.**
  - Decode: every CPU-lane pick goes through `ensure()` (`StoreHold`, `model.cu:5599-5616`). A hit is pinned and
    touched. A miss is a demand read into a free slot or the policy's victim, and the CPU lane waits for it
    (`store.hpp:145-193, 399-445`).
  - Lookahead guesses only with `DS4_AHEAD` set (`model.cu:6155-6157`), as low-priority reads. They are cancelled
    once the token has passed their layer (`model.cu:6194`, `store.hpp:250-257`).
  - The prompt flow uses store copies but does **not** insert what it reads (`model.cu:3177-3194`). After a chunked
    prompt, `cache_settle` reads the prompt's hot experts (heat >= 4) into the store. This goes through `preload`, can
    evict, and is counted in the prompt's time (`model.cu:5928-5945`; `DS4_SETTLE_STORE=0` turns it off).
- RSS check (measured): engine RSS 60 GB at ready, 71.6 GB peak; lowest MemAvailable 16.0 GB (= our floor).

### g. Drafting

- **DSpark** = the checkpoint's `mtp.*` blocks (`model.hpp:46`).
  - Our pack takes them from Unsloth's `dspark-...-Q8_0.gguf` (architecture `dflash`; `tools/dsv41/pack_gguf.py:661-730`).
  - Geometry (`ds4.txt`): 3 blocks, 128 experts, 3 per token, block size 5, markov rank 256, target layers 37-39.
  - **VRAM**: 7.97 GB of tensors (7.22 GB experts in MXFP4, 0.75 GB dense; computed from `tensors.txt`). All drafter
    experts get VRAM before any trunk expert (`model.cu:3832-3837`), and the blocks sit on the first group (GPU0,
    `model.cu:2088-2092`).
  - Measured (arm dsp70): CUDA0 594 of 8448 in VRAM, 384 of them the drafter's; CUDA1 171. That is 381 trunk experts
    vs 1357 without the drafter. W1-W3 decode 20.85 vs 22.64 tok/s. Drafts kept 64-91 % per round.
  - `--dspark off` still loads it; `none` does not; `auto` skips it when experts > 1.5 x VRAM (`model.cu:1998-2008`;
    `model.hpp:42-46`).
- **Draft and verify rule**:
  - The drafter writes `block` drafts (the token, then noise tokens), each with a sigmoid confidence. The markov bias
    of the previous drafted token is added before each argmax (`model.cu:6457-6602`).
  - A round keeps drafts while confidence >= `--dspark-conf` (and the cumulative product >= `STRATA_DS4_DSPARK_CUM`
    if set), capped by `--dspark-block`/`DS4_DSPARK_MAX` and the room left (`main.cpp:167-204`).
  - Verification runs [token, drafts] as one window (`model.cu:6629-6698`):
    - Greedy: drafts stand while they equal the argmax.
    - Sampled: speculative sampling, keep d with min(1, p(d)/q(d)), q = a point at the drafter's argmax unless
      `DS4_DSPARK_SAMPLE=1`; else draw from the residual. "Every token is still distributed as the model's own draw"
      (`model.hpp:121-127`), but the realised tokens differ from plain decoding with the same seed ("not the plain
      draw's tokens", `sampler.hpp:57-60`).
  - A round that offered no draft skips drafting for the next round (`main.cpp:895-907`). Rejected positions are
    rolled back (`model.cu:6702-6741`).
- **Prompt lookup / n-gram / suffix drafting: not supported** (nothing in `src/dsv41`; the only drafter is
  `Model::draft`).
- **"markov rank 256"**: DSpark's low-rank bigram head, `mtp.2.markov_head.embed/head`, BF16 [129280][256] each,
  66 MB each. `markov_add` adds E[prev] . H to the drafter's logits, and the confidence head reads E too
  (`model.cu:6527-6572`; `kernels.cu:2086-2100`). It is used only by DSpark.
- **"n-gram shard"**: the Engram n-gram memory, part of the trunk itself. Layers 1 and 14 each add 24 hashed n-gram
  rows per token (ngram 4 x 8 heads x 3), from the 111 GB IQ4_NL table (`model.cu:6`; `engram.bin` header DSE1 2
  layers, ngram 4, 8 heads, dim 256). It is model weights, not a drafter. (`pack_gguf.py` calls Unsloth's separate
  Engram file "unsloth's MXFP8 shard".)
- **Native MTP / nextn: not supported beyond DSpark.**
  - The engine reads `mtp.*` only as DSpark blocks.
  - The IST-DAS GGUF has no extra tensors: all 1242 `mtp.*` entries in our `tensors.txt` come from file 5 (the dspark
    GGUF), layers stop at 39, and `pack_gguf.py` stops on any tensor it cannot map (`:584-585`). The pack tool has no
    nextn mapping (grep: none).
  - So there is nothing extra to load. The VRAM cost of drafting at all is DSpark's about 8 GB, above.

### h. Hot-expert profile

- **Format**: raw little-endian `uint32` counts `[layer][expert]` with no header. That is 40 x 384 (61,440 B) or, with
  the drafter loaded, 43 x 384 (66,048 B). Both sizes load (`model.cu:2537-2546`). It is saved with a `.tmp` +
  rename (`model.cu:8996-9006`).
  - A run without the drafter writes only 40 layers and drops the drafter's counts (`prof` sized after
    `n_mtp = 0`, `model.cu:2009, 2537`).
- **How it is built**:
  - The engine counts every routed pick, prompt and decode (`serve_lane` `model.cu:6239`; host path 8887; chunk path
    7090-7099). It writes the file after **every served request** and at exit (`main.cpp:930, 957`).
  - Tool: `strata-dsv41 --pack P --profile-run IDS.json [--window N] [--expert-profile OUT]` (`main.cpp:1097-1128`).
    It feeds each `{"name","ids"}` segment (quant_quality.py's ids format, `main.cpp:972-1004`) from a fresh state,
    with no logits, and saves every 10 segments. `--window` sets the feed size (default 16, so the cost model picks
    the path).
  - `DS4_TRACE=file` records traces (decode: u8 layer, u8 T, T x k int16; chunks: u8 layer|0x80, u16 T, ...;
    `model.cu:6203-6229, 7078-7089`). No tool in `tools/dsv41` turns traces into a profile (grep: none). The shipped
    profiles are `data/dsv41/profile-2.00.bin`/`-2.25.bin`, which setup copies into the pack (`setup.py:8097-8100` at
    v0.2.4.2).
- **How it is used**:
  1. VRAM: per layer, the experts with the highest counts get the slots (ties by index), up to that group's fraction
     (`model.cu:3880-3897`).
  2. The expert cache's starting heat: counts scaled to about 512 per layer (`model.cu:3912-3918`).
  3. RAM store preload: count per byte (`model.cu:4562-4589`).
  4. The flow's "likely" early reads (`model.cu:3245-3262`).
  5. The flow/windows cost model (`model.cu:7654-7665`).
  6. Without a store: load-time read-ahead into the page cache (`model.cu:4049-4069, 4307-4324`).
- **Our pack** (computed now, read-only): the shipped `profile-2.00.bin` totals 426.4 M counts; the pack's
  `expert-profile.bin` (written 10-24 00:23) has 590.2 M (+163.8 M). Every arm so far has added its routing, so each
  start had a different VRAM set and store preload.

### i. Determinism: sources of run-to-run differences, and what can be fixed

The 0.2.4 notes say "small differences in how the numbers are added up decide between them" (`docs/release-notes-0.2.4.md:58`).
Sources found in the code (static unless noted):

1. **CPU lane vs GPU compute an expert differently.**
   - CPU (IQ types): ggml's dot over **Q8_K** activations, one scale per 256 values (`iq_cpu_quant(fm.gu_act, ...)`,
     `model.cu:5553-5562`; `gg_cpu.cpp:2, 64-65`).
   - GPU: int8 with one scale per **32** values (`q8_quant`, `gguf.cu:186-201`; `iq.cu:341-360`).
   - The CPU lane's part is also summed per token on the host and added as one vector (`model.cu:6313-6326`;
     8945-8958). Which experts sit in VRAM therefore changes the bits.
2. **The VRAM set changes over time and with timing.**
   - Swaps are prepared on a cache thread (buffered SSD read + copy) and switched in "between windows" whenever they
     are ready (`cache_loop` `model.cu:5762-5848`; `cache_tick_swaps` 5967-6045). Which token first sees an expert in
     VRAM depends on I/O timing.
   - `cache_settle` adds up to 6 s of swaps after each chunked prompt (`model.cu:5911-5949`).
3. **The profile file changes after every request** (h), so VRAM placement at the next start differs. Within a run
   the counts also change the flow's "likely" set and its virtual-slot order (`model.cu:3237-3275`). That changes the
   order streamed experts are added into the chunk's sum (`run_set`: "each added into acc in pick order",
   `model.cu:3498-3567`).
4. **Prompt path choice is timing-based** for 2-2047-token prompts (`pick_path`, `model.cu:7697-7748`, with measured
   speeds and residency samples). The flow (FP16-reconstructed weights + cuBLAS tensor-op GEMMs, `model.cu:2900-2919`)
   and windows of 16 (GEMV kernels + CPU lane) do different arithmetic.
5. **Prompt vs decode numerics differ**, so a context that is re-read (no reuse, a restore, a different chunking)
   gives other bits than one that was reused in place.
6. **Sampling counter.**
   - Philox on (seed, counter) (`sampler.hpp:28-29`). The engine's `counter` starts at 0 **once per engine process**
     and keeps counting across requests (`main.cpp:327, 842, 899`; `round()` 193, 202).
   - The same request with the same seed gets different draws unless the engine was restarted and served the same
     sequence before it.
   - Seed: a request's `seed` (int > 0) is forwarded (`server.py:1423-1425`) and parsed (`main.cpp:309`). Otherwise 0
     (`main.cpp:210`). Sampling is always seeded.
7. **DSpark** (when loaded) changes the realised samples (g). `DS4_STORE_ZC`, `DS4_ATTN_SPLIT` and `DS4_AR_F16` are
   other opt-in sources (all off here).

Not sources:
- CPU multithreading: each job computes whole 64-row output blocks and per-token sums run in slot order
  (`model.cu:5470-5516, 5563-5596, 6313-6326`). The CPU row variants are checked bit-identical to ggml at run time
  (`gg_cpu.cpp:87-145`).
- Store vs mmap: the same bytes ("byte for byte", `model.cu:4496-4497`).
- SSD read completion order: flow batch bounds are "fixed by the stream alone ... the same on every run whatever the
  reads' timing" (`model.cu:3453-3456`).
- Engram rows: the file's bytes either way (`engram_io.hpp:9-10`).
- GPU atomics: only integer counters and histograms (`kernels.cu:679, 1502`; vendor exl3 "last block" counters).
  Each work item is computed by one block in fixed order (`iq.cu:937-939`).
- cuBLAS: run-to-run reproducible on the same GPU model and toolkit (general NVIDIA documentation, not checked here).
  Each layer always runs on the same card.

**Most repeatable setup** (static; no single switch gives repeatable outputs):
- Temperature 0 (greedy) or a fixed `seed` with a fresh engine per run.
- `--no-expert-cache` (no swaps; costs adaptation).
- Restore a pristine `expert-profile.bin` before every start.
- `DS4_PATH_PICK=0` (always the flow).
- `DS4_SPEC_Q=2` (no profile-dependent "likely" set; changes prompt speed).
- `STRATA_DS4_REUSE=0` (every prompt read whole).
- DSpark not loaded; `DS4_STORE_ZC`/`DS4_ATTN_SPLIT` unset.

Even then, the counts' effect on placement only stops at the next start, so restart and restore between runs.

**For our A/B arms**: restore the profile before each arm; otherwise later arms start with a placement trained on
earlier arms' prompts.

### j. Conversation cache

- **In place (always on)**: if a prompt continues what the state holds, only the new tokens are read
  (`main.cpp:681-703`).
  - If it diverges, the engine goes back to the latest checkpoint at or before the divergence (`main.cpp:704-720`;
    `model.cu:4713-4779`). Checkpoint 0 = end of the last prompt, 1 = the token before it, 2 = the anchor
    (`m.pin()`), 3 = the `pin=N` prefix (`main.cpp:777-835`; `model.cu:953-964`).
  - Checkpoints keep only the window rings and the compressors' partial groups. The compressed KV and index keys are
    indexed by position and stay on the GPUs (caches 0.03 GB in our log). So a follow-up turn **does reuse the
    previous turn's state** without re-reading.
  - With thinking and no tools the template drops earlier reasoning (`drop_thinking` default true, off when tools are
    present; template:17, 166-169). The re-rendered history then diverges at the last answer, and the engine resumes
    from checkpoint 0 or 1. Measured: "2446 tokens = 2429 reused + 17 read".
  - `STRATA_DS4_REUSE=0` turns all reuse off (`main.cpp:677-680`).
- **Slots (`STRATA_DS4_SLOT_KEEP=1`)**: only when a request does **not** continue the state.
  - The conversation in the model is saved first to a RAM slot (`slot_put`, `main.cpp:478-515`). The slot holds the
    position, tokens, every window ring (DSpark blocks too), partial groups, each source's compressed KV and index
    keys up to pos, and the checkpoints (`model.cu:4781-4800`). Docs: about 17 MB per 6.5K tokens.
  - Then the best kept conversation for the new prompt is loaded (`slot_take`, `main.cpp:521-576`).
  - RAM holds `STRATA_DS4_SLOT_CAP` (4). Past that the LRU goes to the folder as `slot-<ms>-<seq>.bin` + `.meta`,
    written as `.tmp` then renamed, and not written with < 8 GB free (`main.cpp:442-476`).
  - At engine exit every RAM slot is written to the folder (`main.cpp:932-956`). At start the folder is read back;
    foreign, incomplete or > 7-day entries are removed and it is trimmed to `SLOT_GB` (`main.cpp:577-635`).
  - Shorter than 1024 tokens or holding pictures: not saved.
  - **Nothing is written to the folder per turn** in normal turn-taking. The only per-request disk write is
    `expert-profile.bin` (64 KB, `main.cpp:930`).
- **Folder**: engine default `<pack>/slots` (`main.cpp:578-579`). The server sets `<dir of the config's "log">/ds4-slots`
  (`server.py:3494-3496`); for us `logs/ds41/ds4-slots`, which does not exist, so slots were never on.
- **Auto pin** (`STRATA_DS4_AUTO_PIN`): the server marks the end of the leading system/developer messages as `pin=N`
  (`server.py:4921-4943`). The engine stops the read there for checkpoint 3 when N >= 256 (`main.cpp:775-801`).
- Defaults: v0.2.4 server = slots off, auto pin off (what we run). v0.2.4.2 = both on (git diff `server.py`
  `DS41_SLOT_KEEP_DEFAULT "1"`; `AUTO_PIN` `!= "0"`).

### k. Thinking on/off, effort and budget (OpenAI-compatible API)

- **Off**:
  - `reasoning_effort` set to none, off, minimal, disabled, "false" or `false`.
  - `chat_template_kwargs: {"enable_thinking": false}`.
  - Anthropic `thinking: {"type": "disabled"}`.
  - (`frontend.py:154-169, 568-578, 657-679`)
  - Other `chat_template_kwargs` keys (`drop_thinking`, `thinking_mode`) are **not** forwarded; only
    `enable_thinking` and `reasoning_effort` are (`frontend.py:573-578`).
- **Effort**: `reasoning_effort` (or Responses `reasoning.effort`, or `chat_template_kwargs.reasoning_effort`) accepts
  low, medium, high, max; xhigh and maximum map to max; or an integer 1-100 (`frontend.py:140-169`).
  - The template turns this into the line "Reasoning Effort: N (range 1-100 ...)" at the top of the system turn with
    `{"low": 50, "medium": 62, "high": 75, "max": 100}`. **Default "high" (75)** when nothing is given
    (template:22-29, 209).
  - The effort only changes prompt text, not a token cap.
  - Anthropic `budget_tokens` maps to low (< 2048), medium (< 8192) or high, and is also a real budget
    (`frontend.py:172-178, 661-671`).
- **Budget**: `reasoning_budget_tokens` (or `thinking_budget_tokens`), else the config's, else **`DS41_DEFAULT_BUDGET`
  = 32768** for DeepSeek; 0 = none (`server.py:204, 4155-4169`).
  - The #984 rule then caps it at `max_tokens - min(max(512, max_tokens/4), max_tokens/2)` (`server.py:5107-5113`):
    384 -> 192, 3072 -> 2304. Our server.out confirms "thinking capped at 192 of max_tokens 384".
  - Without any budget, max_tokens of 48-1023 gives half (`server.py:5099-5106`).
  - When the budget is reached, the server closes the thinking with the wrap-up text "I have thought about this long
    enough; time to give my answer.\n</think>" (`server.py:211, 5453`) as a continuation (log: "+17 read").

### l. Other things that affect decode or prompt speed

- **Decode threading**: `--threads on` makes each GPU's host thread enqueue its own layers, with host-mapped flag
  hand-offs (`model.cu:8393-8481`). In our runs decode is `forward_serial`: one thread, D2H + H2D through pinned
  bounce buffers with an event at the GPU boundary (`model.cu:8350-8368`). Lossless; not measured.
- **CUDA graphs**: none (grep).
- **Batch sizes**: decode is one token a window (T up to 16 only for DSpark verification); prompts use windows of 16
  or chunks; no parallel requests (docs: `--parallel` ignored).
- **Pinned memory**:
  - Pinned (page-locked): the prompt path's hand-off, staging and embedding/Engram buffers (about 4 GB at chunk 8192,
    see c), the decode mailbox, the swap buffers.
  - Not pinned: the store arena (pageable unless ZC), so store experts are memcpy'd into pinned staging before their
    DMA during prompts (`model.cu:3192-3194`).
- **Prefetch/lookahead**: `DS4_AHEAD` (off with the store; upstream measured 4.5 vs 4.7 tok/s on a 5070 PC with a
  3.6 GB/s NVMe and 62 % right guesses, `model.cu:4530-4532`). Our NVMe (Samsung 9100 PRO) is faster, so it is worth an
  A/B. Lossless.
- **GPU expert cache policy**:
  - Heat +1 per pick (prompt and decode), x 0.9 every 256 tokens. A swap happens when the hottest CPU pick > coldest
    VRAM x 1.25 + 1, one per layer in flight, at most 8, one prep thread.
  - The outgoing expert just goes back to the file. The incoming one is read with a buffered `pread`.
  - Each layer keeps one VRAM slot spare for swaps (40 slots, about 0.34 GB; `model.cu:3888-3896`). After each chunked
    prompt up to 6 s of catch-up swaps (`DS4_SETTLE_MS`) plus a blocking store refill (`DS4_SETTLE_STORE`) run before
    the first token. Both are counted in TTFT; untested here.
- **Engram placement**: always read from the GGUF files with buffered `pread` (Linux), so the page cache keeps hot rows
  and competes with the store for RAM. There is a 256 MB row cache. No option puts the table in VRAM or locked RAM
  (`model.cu:2445-2536`). Rows are dequantised on the GPU.
- **VRAM headroom**: `--reserve-mib 600` per card. Each 100 MB is about 11-12 experts (computed). Lower carries OOM
  risk.
- **Prompt staging ring** `DS4_RING_MB` (400 MB per card here): VRAM that could hold about 40 experts per card.
- **Engine priority**: the server starts the engine at nice +5 because of the iGPU (`server.py:3287-3301`). That only
  matters when other CPU load competes. `STRATA_ENGINE_NICE=0` turns it off.
- **Store slot padding** (f) and **profile drift** (h) are structural; there is no knob for the padding.

---

## 3. Lossless A/B candidates (none measured; ordered by expected value for our box)

| # | Change | Expected effect (static) | Risk |
|---|---|---|---|
| 1 | Restore `profile-2.00.bin` (or a frozen copy) into the pack before **every** arm | removes a confound between arms (placement, preload) | none |
| 2 | `--threads on` | decode: per-GPU threads instead of one serial host thread | unknown; lossless |
| 3 | `DS4_AHEAD=1` | decode: next-layer guesses read into the store early on our fast NVMe | wasted reads (upstream slower on a slow SSD) |
| 4 | `DS4_STORE_THREADS=16` | more concurrent O_DIRECT reads for decode misses | none |
| 5 | `DS4_READERS=12-16` | prompt: more concurrent reads per GPU (16-32 in all) | none |
| 6 | `--ssd-policy lfu` | store keeps frequent experts over recent ones | none |
| 7 | `DS4_SETTLE_MS=0` and/or `DS4_SETTLE_STORE=0` | shorter TTFT after long prompts; slower decode right after them? | placement changes bits |
| 8 | `--prefill-chunk 4096` vs 8192 vs 12288 | trades VRAM experts (decode) against re-read passes (long prompts) | 12288 may not fit the 4060 Ti |
| 9 | `--reserve-mib 400` | about 23 more VRAM experts per card | OOM |
| 10 | `DS4_SPLIT=21,19` / `23,17` | prompt pipeline balance; decode probably flat | none |
| 11 | one GPU only (`CUDA_VISIBLE_DEVICES` = the 5080) | layer-major prompt reads each expert once per prompt (default chunk 1024); loses the 4060 Ti's 8 GB | decode likely slower |
| 12 | `STRATA_ENGINE_NICE=0` | only matters under other CPU load | desktop responsiveness |

Diagnostics that cost nothing in answers and would show where time goes: `DS4_FLOW_STATS=1` (per-prompt O_DIRECT vs
page cache vs RAM, reader waits) and `--verbose` (path picks, store and stream lines). `DS4_PROF=1` prints the GPU
time per stage but adds event syncs.

## Appendix: computed numbers

- Expert blob per layer (gate+up+down, `tensors.txt`): IQ1_M-only layers 7.74 MB; mixed 8.20-9.86 MB; layer 39
  (all IQ2_XS) 10.23 MB. Mean 8.60 MB; all routed experts 132.1 GB.
- Store slot 10.26 MB -> 16 % padding on average.
- Chunk buffers: about 215 KB/token (CUDA1), about 232 KB/token (CUDA0) of VRAM, plus about 0.13 GB slabs + ring
  (400 MB). Pinned host: 92 KB/token x 2 slots per GPU, plus staging about the ring.
- DSpark: 7.97 GB (`mtp.*` in `tensors.txt`), experts 7.22 GB.
- Profile: shipped 426,449,520 counts, pack now 590,241,360 (+163,791,840; per-entry difference >= 0 everywhere).
