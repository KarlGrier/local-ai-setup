# strata-dsv41 (Strata v0.2.4): every setting, and the carry-overs from P021m

Read-only code survey, 2026-10-24 (afternoon). Nothing was built, started or run on a GPU. Line numbers are v0.2.4's
(96ca4383, our binary `engine-v024-ds41/strata-dsv41`; v0.2.4 -> v0.2.4.2 changes only `ds4_gg_cpu.cpp` under `src/dsv41`
and two server defaults, see Part B.2). Companion of `engine-options.md` (same short file names: `main.cpp` =
`strata-v024/src/dsv41/ds4_main.cpp`, `model.cu`, `model.hpp`, `store.hpp`, `iq.cu`, `gguf.cu`, `gg_cpu.cpp`,
`kernels.cu`, `os.hpp` = `ds4_*` in `src/dsv41`; `server.py`, `frontend.py`, `responses.py` = `strata-v024/serve/...`;
`kcpu/` = `strata-v024/src/kernels/cpu/`).

How the list was made: every `getenv` / `env_f` / `env_num` in `src/dsv41` (116 reads), every flag in `main.cpp`'s parser
(1209-1273), the getenv reads of the linked CPU-kernel library that the DeepSeek CPU lane actually calls, every env /
config key the v0.2.4 server reads or sets on the DeepSeek path, and a cross-check against the strings in our binary
(`strings engine-v024-ds41/strata-dsv41`). No `MAYA_*` variable is read anywhere (one comment, `model.cu:7864`).

**Exactness column**
- **exact**: the same bits (speed or memory only).
- **rounding**: bits can differ - placement (VRAM vs CPU lane), stream / summation order, chunking, re-read vs reused
  state. Judge by our rounding rule, not bitwise.
- **samp**: sampling stays distribution-exact, but the realised tokens differ from plain decoding (DSpark).
- **content**: changes what the model is asked or allowed to write (budgets, effort).
- **LOSSY**: work dropped or approximated.
- **diag**: diagnostics / tests only.
- **n/a**: not active on our PC or pack.

**"Our launcher"** = `configs/DS41-v024-s70.json` plus what `strata-v024/serve/server.py` adds. Confirmed from
`results/ds41/arm-s70-1023-2340/engine-start.log`: the server adds no engine argument (the "engine started" line is exactly
the config's args + `--serve`). It adds this environment for the engine (`server.py:3499-3532`):
- `STRATA_DS4_SLOT_KEEP=0`, `STRATA_DS4_SLOT_GB=2`, `STRATA_DS4_SLOT_DIR=logs/ds41/ds4-slots` (`server.py:3482-3496`,
  3513-3514).
- `LD_LIBRARY_PATH` from `lib_dirs`.
- nice +5, because the 9950X3D's Radeon iGPU is in `HIP_IGPU_ARCHS` (`server.py:1034-1040`, 3287-3301).

The server also applies thinking budget 32768 with the #984 cap, effort default "high" (75), and the config's sampling
block (details in section 6).

## 1. Command-line flags (`main.cpp:1200-1273`; defaults `model.hpp:25-61`)

| Setting | Default | Our launcher | Exactness | Covered by the round? | Speed? | file:line |
|---|---|---|---|---|---|---|
| `--pack DIR` | required | pack-ist-das-2.00bpw | n/a | - | no | main.cpp:1209 |
| `--gpus 0,1` | every visible GPU, CUDA order | not set; `CUDA_VISIBLE_DEVICES` = 5080, 4060 Ti (UUIDs) | rounding (placement) | yes: card order (r22-r30) | yes | main.cpp:1210-1211; model.cu:1876-1879 |
| `--max-context N` | 32768 | 32768 | rounding (VRAM left for experts) | no | small (VRAM) | main.cpp:1212; model.cu:2039, 2255, 2833 |
| `--reserve-mib N` | 600 (each GPU) | 600 | rounding (placement) | yes: 400, 300 | yes | main.cpp:1213; model.hpp:29; model.cu:3815-3821 |
| `--vram-experts F` | 1.0 | 1.0 | rounding | no | can only lower | main.cpp:1214; model.cu:3819-3820 |
| `--cpu-threads N` | 0 = physical cores (16) | 0 | exact | yes: 14 / 12 / 8 | yes | main.cpp:1215; model.cu:4653 |
| `--expert-profile F\|none` | `<pack>/expert-profile.bin`, written back after every request | pack's file (the round: `tmp/ds41-profile-arm.bin`, restored per run) | rounding (placement, preload, likely-set) | yes: custom profile (B.8) | yes | main.cpp:1216, 1286-1287, 930, 957 |
| `--ssd-cache GB` (10^9) | auto: min(48, MemAvailable - 12), off < 4 | 70 | exact | yes: 74 | yes | main.cpp:1217; model.cu:4457-4469 |
| `--ssd-policy lru\|lfu\|lfulru` | lru | lru | exact | yes: lfu (lfulru = lfu) | yes | main.cpp:1218-1221; store.hpp:389-397 |
| `--eos ID` | 1 | 1 | n/a | - | no | main.cpp:1222 |
| `--no-expert-cache` | cache on | on | rounding | methodology (frozen run) | yes | main.cpp:1223; model.cu:3888-3896 |
| `--dspark on\|off\|none\|auto` | auto | auto -> not loaded (132 GB experts > 1.5 x 23 GB) | samp | extra screen `dspark4060` (on, 4060 first) | yes | main.cpp:1224-1228; model.cu:1998-2009 |
| `--dspark-conf F` | 0.5 | 0.65 (inert: DSpark not loaded) | samp | no | with DSpark only | main.cpp:1229, 181 |
| `--dspark-block N` | 0 = pack's 5 | 0 | samp | no | with DSpark only | main.cpp:1230; model.cu:2010 |
| `--tp N` | 2 | 2 (falls back to 1; only effect: chunk default 8192) | rounding (chunking) | yes (chunk screens; one5080 sets 1) | yes | main.cpp:1231; model.cu:1894-1911, 1968-1969 |
| `--prefill-chunk N` | -1 = auto (8192 here) | auto | rounding (chunking) | yes: 4096 / 2048 / 1024 | yes | main.cpp:1232; model.cu:1968-1984 |
| `--threads on\|off` | off | off | exact (static reading) | yes: `thr` | yes | main.cpp:1233; model.cu:1917, 8393-8481 |
| `--vision on\|off` | on (our pack has no tower) | default | n/a | - | no | main.cpp:1234 |
| `--mmap-experts on\|off\|auto` | auto (read in place) | auto | exact | **no** | maybe (see 7) | main.cpp:1235-1237; model.cu:4152-4183 |
| `--layer-split X` | accepted, ignored | not sent (no `"gpu"` list in the config) | n/a | - | no | main.cpp:1265 |
| `--serve` | - | server adds | - | - | - | main.cpp:1263, 1296 |
| `--images --encode-image --dump-image --size` | vision tests | - | diag | - | no | main.cpp:1238-1241 |
| `--temperature --seed --ids --n --window --dump-logits --score --score-out --profile-run --spec-eval --pack-info --version --help` | CLI tests, profile build | - | diag | `--score` in the teacher-forced test | no | main.cpp:1246-1266 |
| `--verbose` | off | off | diag | methodology | no | main.cpp:1248 |

Any other flag ends the engine with exit 2 (`main.cpp:1267-1273`). The server can add such flags: see 6.

## 2. Engine environment, `DS4_*` (`src/dsv41`)

| Setting | Default | Our launcher | Exactness | Covered by the round? | Speed? | file:line |
|---|---|---|---|---|---|---|
| **Placement and memory** | | | | | | |
| `DS4_SPLIT=a,b` | unset (DP split) | unset (log: 22 / 18 + head) | rounding | yes: s26f-s30f, r22-r30 | yes | model.cu:2106, 2150-2162 |
| `DS4_TP_ALIGN` | 128 | unset | n/a (TP impossible for IQ) | no | no | model.cu:1905 |
| `DS4_COPY_GB=n` (10^9) | unset: no static copy | unset | exact | **no** | maybe (huge pages, see 7) | model.cu:4172 |
| `DS4_COPY_NUMA` | 2 parts if 2 NUMA nodes (1 here) | unset | exact | `numa2`: **a no-op alone** (acts only on copies; see 9) | no | model.cu:4183-4187 |
| `DS4_LAYER_CACHE_MB` | auto RAM - 8 GB (one GPU only) | unset | exact | yes: one5080 at 4096 | one GPU | model.cu:7815-7820 |
| `DS4_LAYER_MAJOR=0` | on (one GPU only) | unset | rounding | implied by one5080 | one GPU | model.cu:7786-7843 (7792) |
| `DS4_COMMIT_CAP_GB` | unset | unset | n/a (Windows commit) | - | no | model.cu:1083-1091 |
| **Prompt (prefill)** | | | | | | |
| `DS4_CHUNK=N` | unset | unset | rounding | tests | test | model.cu:1970-1974 |
| `DS4_CHUNK_MIN=N` | 512, or 2 when every GPU is on the flow (ours) | unset (2) | rounding | yes: 64 | yes | model.cu:1972, 2707-2712, 7518 |
| `DS4_WINDOWS=1` | unset | unset | rounding | no | slower | model.cu:1922-1924 |
| `DS4_PATH_PICK=0` | on (timing-based flow / windows pick, 2-2047 tokens) | unset | rounding | partly (`DS4_CHUNK_MIN=64` also ends the calibration) | short prompts | model.cu:7517-7520, 7697-7748 |
| `DS4_FLOW=0` | on (new flow) | unset | rounding | no | old path | model.cu:2661 |
| `DS4_FLOW_TP=1` | 0 | unset | n/a | - | no | model.cu:2662-2665 |
| `DS4_READERS` | 8 per GPU | unset | exact | yes: 16 / 32 | yes | model.cu:2659-2660 |
| `DS4_RING_MB` | auto 400 | unset | rounding (VRAM experts) | yes: 128 / 64 | yes | model.cu:2796-2815, 2874 |
| `DS4_SPEC_Q` | 0.9 | unset | rounding (stream order) | yes: 1.0 only | yes | model.cu:3228-3278 |
| `DS4_SPEC_WASTE` | 0.2 | unset | rounding | **no** | prompt | model.cu:3250-3256 |
| `DS4_FLOW_PUMP_WAIT=0` | on (pumps during attention) | unset | exact | no | =0 is the old, slower way | model.cu:7015-7024 |
| `DS4_READAHEAD_MB` | 2048 | unset | exact | no | non-flow path without a store only | model.cu:3062-3099 |
| `DS4_LAST_WINDOW=1` | unset | unset | rounding | no | A/B only | main.cpp:773-774 |
| `DS4_IQ_MAX_SMS`, `DS4_IQ_CTA_PER_SM` | all SMs, kernel's own | unset | exact (static) | **no** | maybe (IQ kernel grid) | iq.cu:1134-1135 |
| **Decode and CPU lane** | | | | | | |
| `DS4_SYNC=1` | 0 | unset | exact | no | slower | model.cu:979 |
| `DS4_ASYNC_T` | 8 | unset | exact (static) | **no** | 9-16-token windows | model.cu:983, 6473, 8161 |
| `DS4_MOE_TOKEN=0` | 1 | unset | exact ("same bits, no faster") | no | no | model.cu:980-982 |
| `DS4_AHEAD` | 1, but **0 with the store** unless set | unset (= 0) | exact | yes: 1 / 2 | yes | model.cu:990, 4530-4532 |
| `DS4_AHEAD_EXTRA` | 0 | unset | exact | yes: -2 | yes | model.cu:991 |
| `DS4_AHEAD_ORDER=0` | 1 | unset | exact | **no** | only with AHEAD | model.cu:992-993 |
| `DS4_IQ_PF_COLD=1` | prefetch all | unset | exact | no | without a store only | model.cu:5534-5543 |
| `DS4_ATTN_SPLIT=1` | 0 | unset | rounding (other summation order) | no | maybe (long-context decode) | kernels.cu:1785-1794 |
| `DS4_AR_F16=1` | 0 | unset | lower precision; n/a (TP groups > 2 GPUs only) | no | n/a | kernels.cu:2155-2162 |
| **RAM store** | | | | | | |
| `DS4_STORE_GB` | the flag | unset | exact | via `--ssd-cache` | yes | model.cu:4461 |
| `DS4_STORE_THREADS` | 8 | unset | exact | yes: 16 / 24 / 32 | yes | model.cu:4489 |
| `DS4_STORE_FLOOR_GB` | 8 | 16 | exact | yes: 15.5 with s74 (**15.5 acts as 15**, see 9) | memory | model.cu:4490; store.hpp:465-470 |
| `DS4_STORE_POLICY` | `--ssd-policy` | unset | exact | via `--ssd-policy lfu` | yes | model.cu:4491 |
| `DS4_STORE_RESERVE` | 192 slots | unset | exact | **no** | first requests (preload size) | model.cu:4493, 4585 |
| `DS4_STORE_PRELOAD=0` | on | unset | exact | no | =0 slower start | model.cu:4562-4589 |
| `DS4_STORE_ZC=1` | 0 | unset | rounding, timing-dependent | no | one GPU only | model.cu:4495-4499 |
| `DS4_STORE_ZC_FRAC` | 50 | unset | with ZC only | no | - | model.cu:4494 |
| `DS4_STORE_PREGROW` | Linux: only with ZC's GPU mapping | unset | exact | no | **no-op without ZC** | store.hpp:97-107 |
| `DS4_SETTLE_STORE=0` | 1 | unset | exact | yes: 0 | yes | model.cu:5928-5945 |
| **GPU expert cache (VRAM <-> CPU lane swaps)** | | | | | | |
| `DS4_CACHE_MARGIN` | 1.25 | unset | rounding | yes: 1.1 | yes | model.cu:1013, 6060-6073 |
| `DS4_CACHE_BONUS` | 1.0 | unset | rounding | **no** | yes | model.cu:1013 |
| `DS4_CACHE_DECAY` | 0.9 every 256 tokens | unset | rounding | **no** | yes | model.cu:1014, 6046-6051 |
| `DS4_CACHE_INFLIGHT` | 8 | unset | rounding | yes: 4 | yes | model.cu:1015 |
| `DS4_CACHE_THREADS` | 1 | unset | rounding | yes: 2 / 4 | yes | model.cu:2753 |
| `DS4_SETTLE_MS` | 6000 | unset | rounding | yes: 0 | yes | model.cu:5907-5927 |
| `DS4_CHECK_SWAPS=1` | 0 | unset | diag (slow) | - | no | model.cu:1120 |
| **Engram** | | | | | | |
| `DS4_ENGRAM_THREADS` | min(16, max(4, logical/2)) = 16 | unset | exact | yes: extra screen `engram64t` (64) | yes | model.cu:2461-2463 |
| `DS4_ENGRAM_CACHE_MB` | min(256, max(16, MemAvailable_MB/64)) | unset | exact | yes: 16 / 4096 | yes | model.cu:2464-2467 |
| `DS4_EG_CHECK` | unset | unset | diag | - | no | engram_io.hpp:215 |
| **DSpark (only when loaded; not loaded here)** | | | | | | |
| `DS4_DSPARK_CONF` | read, **never used** | unset | n/a | - | no | model.cu:898 |
| `DS4_DSPARK_MAX=N` | 0 (`--dspark-block` sets it) | unset | samp | no | with DSpark | model.cu:915, 2010 |
| `DS4_DSPARK_SAMPLE=1` | 0 | unset | samp | no | with DSpark | model.cu:908-913 |
| `DS4_DSPARK_QTEMP=f` | 1.0 | unset | samp | no | with DSpark | model.cu:914 |
| `DS4_MK_SPLIT=0` | on (head group >= 2 GPUs) | unset | n/a (head group of 1) | - | no | model.cu:2378-2396 |
| **LOSSY switches** | | | | | | |
| `DS4_YOCO` (test alias of the prompt skip; **wins over** `STRATA_DS4_PROMPT_SKIP`) | unset | unset | LOSSY | config check | one GPU | model.cu:7867-7873 |
| `DS4_YOCO_KEEP=N` | 0 | unset | LOSSY | config check | one GPU | model.cu:7911-7916 |
| **CPU kernel choice (bit-identical, checked at run time)** | | | | | | |
| `DS4_GG_IQ512` | rule: Zen 5 = AVX-512 rows for IQ2 always, IQ1_M from 1 token | unset | exact | no | already the fast choice here | gg_cpu.cpp:176-196 |
| `DS4_GG_IQ256` | 2 = from `min_tokens` | unset | exact | no | n/a (512 rows win on Zen 5) | gg_cpu.cpp:197-212 |
| `DS4_MX_TIER`, `DS4_MX_PF` | measured / 0 | unset | exact | no | MXFP4 rows only (drafter) | gguf_cpu.cpp:262-327 |
| **Diagnostics** | | | | | | |
| `DS4_PROF` | off | off | diag (adds event syncs) | methodology | slows | model.cu:1142-1145 |
| `DS4_FLOW_STATS` | off | off | diag | methodology | no | model.cu:8085-8107 |
| `DS4_TOKLOG` | off | off | diag, **CLI decode only**: prints nothing under `--serve` (see 9) | methodology | no | main.cpp:1427 (CLI path; serve returns at 1296) |
| `DS4_TRACE`, `DS4_TRACE_AHEAD`, `DS4_DUMP_H/L/R/Y`, `DS4_PRED_DUMP`, `DS4_XIN_DUMP`, `DS4_XIN_N`, `DS4_DSPARK_DUMP` | off | off | diag | no | no | model.cu:1123-1153, 6203-6229, 916 |
| `DS4_NO_EOS`, `DS4_ROUND_LOG`, `DS4_SCORE_PREFIX` | off | off | diag (CLI / `--spec-eval` / `--score` only) | `DS4_SCORE_PREFIX` in the skip test | no | main.cpp:1397, 1139, 1016 |
| `DS4_GG_VERBOSE`, `DS4_DBG_GG` | off | off | diag | no | no | gg_cpu.cpp:139, 46 |

## 3. Engine environment, `STRATA_DS4_*`

| Setting | Default | Our launcher | Exactness | Covered by the round? | Speed? | file:line |
|---|---|---|---|---|---|---|
| `STRATA_DS4_PROMPT_SKIP` | **1 = ON (LOSSY)**: long prompts run layers 20-39 on the last 2668 rows only; needs every trunk layer on one GPU | **0** (config) | LOSSY | config check; teacher-forced `skipcheck` test (one GPU) | one GPU | model.cu:7862-7887, 7902-7929 |
| `STRATA_DS4_DISK_SKIP_W=w` | 0 (off) | unset | LOSSY (drops experts) | config check | yes, LOSSY | model.cu:1036-1045, 6230-6257 |
| `STRATA_DS4_DISK_SKIP_FROM=L` | 0 | unset | LOSSY | config check | - | model.cu:1046-1049 |
| `STRATA_DS4_REUSE=0` | 1 (reuse in place) | unset (1) | rounding (re-read vs reused) | test reference | =0 much slower | main.cpp:349, 677-680 |
| `STRATA_DS4_SLOT_KEEP` | engine: off; **server v0.2.4 sets "0"**, v0.2.4.2 sets "1" | 0 | exact (state restored whole) | conv test (conv1-3) | interleaved conversations | main.cpp:347-348; server.py:3482, 3492 |
| `STRATA_DS4_SLOT_CAP` | 4 RAM slots | 4 | exact | **no** | interleaving | main.cpp:350, 497-506 |
| `STRATA_DS4_SLOT_MIN` | 1024 tokens | 1024 | exact | **no** | interleaving | main.cpp:351, 481 |
| `STRATA_DS4_SLOT_DAYS` | 7 | 7 | exact | no | no | main.cpp:352, 609 |
| `STRATA_DS4_SLOT_GB` | engine 16; **server sets 2** | 2 | exact | conv test (1) | interleaving | main.cpp:353, 419-440; server.py:3483, 3493 |
| `STRATA_DS4_SLOT_DIR` | `<pack>/slots`; server: `<dir of "log">/ds4-slots` | `logs/ds41/ds4-slots` (created only with slots on) | exact | conv test | no | main.cpp:577-579; server.py:3494-3496 |
| `STRATA_DS4_DSPARK_CUM=F` | 0 (off) | unset | samp | no | with DSpark (see B.6) | main.cpp:152-162, 179-183 |
| `STRATA_DS4_RAM_TIER=1` | 0 | unset | exact | no | upstream measured slower | model.cu:1016-1035 |
| `STRATA_DS4_LANE_FREE` | 2 (only if the lane would take every logical CPU) | unset | exact | no | n/a here | model.cu:4633-4651 |
| `STRATA_DS4_NO_LIGHT=1` | 0 | unset | rounding | **no** | maybe (prompt kernels) | iq.cu:1222-1228 |
| `STRATA_DS4_NO_TC=1` | 0 | unset | rounding | no | slower (F32 kernel) | gguf.cu:932-955; iq.cu:1083-1091 |
| `STRATA_DS4_TQ_WORDS=1` | 0 | unset | n/a (trellis experts only) | - | no | tq.cu:470-477 |

## 4. Other `STRATA_*` read by code the DeepSeek CPU lane calls (`kcpu/`, linked library)

`gg_cpu.cpp` calls `iq512x_rows` / `iq256x_rows` and `cpu_avx512_ok` (`gg_cpu.cpp:15-17`, 135-136, 182-222). On the
9950X3D every IQ type takes the AVX-512 rows.

| Setting | Default | Our launcher | Exactness | Covered? | Speed? | file:line |
|---|---|---|---|---|---|---|
| `STRATA_IQ_PREFETCH=bytes` | 2048 (0 = off) | unset | exact (prefetch hints) | **no** | **yes, CPU-lane decode** | kcpu/iq_avx512.cpp:41-45 (used 325-328, 389-391, 463-465, inside the DeepSeek exact rows 305-600); kcpu/iq_avx2.cpp:184-190 |
| `STRATA_FORCE_AVX2=1`, `STRATA_FORCE_ISA=avx2\|avx\|sse` | unset | unset | exact | no | slower | kcpu/expert_layout.cpp:27-44 -> gg_cpu.cpp:182 |
| `STRATA_IQ256_GATHER`, `STRATA_NO_AVXVNNI` | auto | unset | exact | no | n/a (AVX2 rows only) | kcpu/expert_layout.cpp:210-216, 261-263; kcpu/iq_avx2.cpp:492-495 |
| `STRATA_IQ_GATHER` | off | unset | exact | no | n/a (not in the DeepSeek rows) | kcpu/iq_avx512.cpp:37-38 |

Linked into the binary but **not on the DeepSeek path**: `STRATA_CPU_YMM`, `STRATA_IQ_MT_MIN`, `STRATA_IQ3S_MT1`,
`STRATA_NO_IQ512/256/128`, `STRATA_KQ256`, `STRATA_CPU_IQ_ALL_EXACT1`, `STRATA_NO_Q8K_AVX1/2`, `STRATA_NO_IQ4NL`,
`STRATA_NO_NVFP4_512/256`, `STRATA_NVFP4_PREFETCH`, `STRATA_Q2_BITPLANE`, `STRATA_ACT_DUMP*` (Qwen / GLM native lane;
`ds4_iq_cpu.cpp:9-10` `#undef STRATA_NATIVE_EXPERTS`). Also `STRATA_NO_TQ_KERNELS` and `STRATA_TQ_ISA` (trellis
experts only), and `STRATA_GLM_EXL3_DECODE` (EXL3 packs, vendor/exl3.cu:1280).

## 5. Compiled out, dead, or not in our binary

- **`DS4_IQ_OWN`, `DS4_IQ_AVX2`, `DS4_IQ_GATHER`, `DS4_IQ_VERBOSE`: compiled out.** `ds4_iq_cpu.cpp:9` undefines
  `STRATA_NATIVE_EXPERTS`, so lines 48-757 are not built, and the names are missing from the binary's strings.
  `engine-options.md` lists them as live; they do nothing.
- `DS4_DSPARK_CONF`: read, never used (`model.cu:898`).
- `DS4_STORE_STAGE`: only in a comment (`model.cu:1054`), never read.
- Windows / AMD only, not in our binary: `DS4_TIMER_MS`, `DS4_WIN_DIRECT`, `DS4_WIN_SUBMIT`, `DS4_PF_ALL`,
  `DS4_CPU_SMT`, `DS4_EG_DIRECT`, `STRATA_DS4_HIPK`, `HIPK_CFG`, `HIPK_DBG`.

## 6. Server (v0.2.4) on the DeepSeek path: environment, config keys, GEN keys

| Setting | Default | Our launcher | Exactness | Covered? | Speed? | file:line |
|---|---|---|---|---|---|---|
| `STRATA_DS4_AUTO_PIN` | v0.2.4: off unless "1"; v0.2.4.2: on unless "0" | off | exact | conv test - **but see 9** | agents sharing a system prompt | server.py:4921-4943 (reads the **server's own** `os.environ`, 4935) |
| `STRATA_ENGINE_NICE=N` | 5 with a Radeon iGPU (ours), else 0 | nice +5 | exact | **no** | under CPU load | server.py:1034-1040, 3287-3301 (engine env or `os.environ`) |
| `CUDA_VISIBLE_DEVICES` / `CUDA_DEVICE_ORDER` | config `env`; a `"gpu"` list adds PCI order | UUIDs, 5080 first | rounding | yes (order) | yes | server.py:3504-3512 |
| `"sampling"` block | model card T 1.0, top_p 1.0 (server.py:8061-8069) | T 1.0, top_p 0.95, top_k 20, min_p 0.05 | samp | fixed | no | server.py:5084-5088, 7902-7962 |
| `top_k` sent | 0 or > 64 sent as 64 | 20 | samp | - | no | server.py:1397-1400 |
| `seed` | only an int > 0 is sent; engine default 0 | none | samp | - | no | server.py:1423-1425; main.cpp:309 |
| `"reasoning_effort"` (config) / `<config>.shared-settings.json` | none: template default "high" = 75 | **none** (no shared-settings file for this config) | content | - | yes (thinking length) | server.py:8482-8488, 8598-8606; frontend.py:140-151 |
| `"reasoning_budget_tokens"` | **DS41 default 32768** when neither request nor config sets one | unset -> 32768 | content | - | yes | server.py:204, 4155-4169, 8566-8574 |
| #984 cap | budget capped at max_tokens - min(max(512, max/4), max/2) | on | content | - | yes | server.py:206, 5107-5113 |
| `"answer_room"` | on (`false` turns it off) | on; for DeepSeek the 32768 budget + #984 already gives the same cap | content | - | yes | server.py:8461, 5089-5106 |
| DS41 small cap | 48 <= max_tokens < 1024 with no budget: half | inactive (the budget is always set) | content | - | - | server.py:205, 5099-5106 |
| `repeat_stop_tokens` | 256 (one token 256 times ends the reply) | 256 | content (guard) | - | no | server.py:202, 8565 |
| `reasoning_loop_recovery`, `reasoning_close_retry`, `tool_call_recovery` | off | off | content | - | no | server.py:8462, 8556-8583 |
| `"fit_max_tokens"` | on | on | content | - | no | server.py:8442 |
| `"engine_ready_s"` / `"engine_silence_s"` / `STRATA_ENGINE_STALL_S` | 900 / 300 / 90 | 3600 / 300 / 90 | - | - | no | server.py:3043-3053, 2999-3007, 315 |
| `"codex_thread_titles"` | off | off | content | - | yes (Codex title turns skip the engine) | server.py:8490, 7222-7227; responses.py:302-354 |
| `"layer_split"` | auto -> `--layer-split`, ignored by the engine | not sent | n/a | - | no | server.py:3010-3043, 3113-3114 |
| `"vision"` section | absent | absent | - | - | - | **appends `--vision` without a value: the engine exits 2** (server.py:3103-3112; main.cpp:1202-1207, 1234) |
| `"parallel"`, `"pool_cores"`, `"expert_profile_save"`, `"vram_elastic"`, `"drafting"` | absent | absent | - | - | - | **would add `--batch` / `--pool-cores` / `--expert-profile-save` / `--vram-elastic` / drafter flags: unknown, exit 2** (server.py:3087-3097, 3120-3218) |
| `"effort_position": "end"` | start | start | - | - | - | looks for `--tail-role-token` in the binary, does not find it, stays at start (server.py:2974-2996) |
| GEN keys sent but **ignored by strata-dsv41** | penalties (`penalty_repeat/freq/present`, `penalty_last_n`), `ckpt=0` (`"strata_checkpoint": false`), `pcie_frac` / `spec_min_p` / `pipe` / `aux_cpus` (only with `strata_tune`), `img_keys`, `cvec`, logit bias | none of the tune keys sent | none | - | no | server.py:1389-1462; main.cpp:304-313 |
| GEN keys the engine reads | `temperature top_p top_k min_p seed spec dspark_conf pin dspark_cum/spec_cum` | the server sends the sampling keys and `pin` (auto pin / `strata_prefix`); never `spec`, `dspark_conf`, `dspark_cum` | | | | main.cpp:304-313; server.py:1452-1458 |

## 7. Not covered by the round and could plausibly change speed (exact or rounding-level only)

The syntax is ready for `results/ds41/tuning/extra-screens.json`'s `"extra"` group (`tune.py:218-232`, 422):
`[key, {mods}, note]`. All are static picks. Ordered by expected value on our box.

1. **CPU-lane row prefetch distance** (exact; decode, CPU-lane experts). It is a library knob our list missed. The
   upstream comment measured -2-3 % gate/up time from the 2048 default on IQ3_S.
   - `["iqpf0", {"STRATA_IQ_PREFETCH": 0}, "CPU-lane IQ rows: no software prefetch (2048)"]`
   - `["iqpf1k", {"STRATA_IQ_PREFETCH": 1024}, "prefetch distance 1 KB"]`
   - `["iqpf4k", {"STRATA_IQ_PREFETCH": 4096}, "prefetch distance 4 KB"]`
2. **Hot experts on huge pages** (exact; decode). THP on this PC is `madvise` (`/sys/kernel/mm/transparent_hugepage/enabled`).
   - Copies are on huge pages: `os.hpp:401-412` `MADV_HUGEPAGE`.
   - The RAM store's arena is not: `os.hpp:423-437` gives no advice, so it stays on 4 KB pages.
   - A static hot core next to a smaller store could cut TLB misses on the memory-bound rows (static guess).
   - Screen: `["copy8", {"DS4_COPY_GB": 8, "--ssd-cache": 62}, "8 GB of the hottest CPU-lane experts copied (huge pages), store 62"]`.
   - The interplay between the copy and the store is not verified. Check the log line "routed experts on the CPU lane
     (... GB of RAM, N NUMA parts)" and the store size.
   - `DS4_COPY_NUMA=2` only means something together with this screen.
   - Bigger form: `["mmapoff", {"--mmap-experts": "off", "--ssd-cache": 0}, "static copy of all that fits instead of the store"]`.
     Upstream found copies "no faster" (model.cu:4146-4149, 4165-4167).
3. **Expert-cache heat** (rounding; decode). Only the margin is screened.
   - `["decay95", {"DS4_CACHE_DECAY": "0.95"}, "swap heat decays slower (0.9)"]`
   - `["decay8", {"DS4_CACHE_DECAY": "0.8"}, "faster"]`
   - `["bonus0", {"DS4_CACHE_BONUS": "0"}, "swap threshold bonus 0 (1.0)"]`
4. **Short reads through the async mailbox** (exact; the 17-token wrap-up continuation, short prompts in windows of 16).
   - `["async16", {"DS4_ASYNC_T": 16}, "windows up to 16 tokens async (8)"]`.
   - This setting is moot if `--threads on` wins: `par` makes every window async (model.cu:8161).
5. **Prompt early reads, the in-between values** (rounding; prompt). Only `DS4_SPEC_Q=1.0` (off) is screened.
   - `["specq8", {"DS4_SPEC_Q": "0.8"}, "more early reads"]`
   - `["waste4", {"DS4_SPEC_WASTE": "0.4"}, "early reads tolerate more waste (0.2)"]`
   - `["waste1", {"DS4_SPEC_WASTE": "0.1"}, "less"]`
6. **Engine priority** (exact). This only matters under other CPU load: the research runner, LDR, SearXNG.
   - `["nice0", {"STRATA_ENGINE_NICE": 0}, "engine at nice 0 (5)"]`.
   - It reaches the engine through the config env.
   - Screen it with a fixed background load, or not at all.
7. **Store preload size** (exact; the first minutes after a start).
   - `["sres64", {"DS4_STORE_RESERVE": 64}, "preload leaves 128 slots free instead of 256"]`.
8. **Prompt kernel variants** (rounding / exact; prompt).
   - `["nolight", {"STRATA_DS4_NO_LIGHT": 1}, "<=16-row experts through the GEMM tiles"]`
   - `["cta2", {"DS4_IQ_CTA_PER_SM": 2}, "IQ kernel grid 2 CTAs/SM"]`
9. **Context size** (rounding; VRAM for experts). Do not screen it for speed first. Read the engine's VRAM-expert
   count at `--max-context 24576` / `16384`.
   - The KV itself is small: 4 sources at ratio 2/2/2/1, about 0.9 KB a token per device that reads them.
   - Most of the VRAM is the score and indexer buffers (model.cu:2255, 2833).
   - Screen only if it frees more than about 30 experts. It also caps the research prompts.
10. **Only if a screen in its family is promising.**
    - With `DS4_AHEAD`: `["aorder0", {"DS4_AHEAD": 1, "DS4_AHEAD_ORDER": 0}, ...]`.
    - With `dspark4060` (samp): `--dspark-conf` 0.5 / 0.8, `--dspark-block 3`,
      `STRATA_DS4_DSPARK_CUM` 0.5, `DS4_DSPARK_SAMPLE=1`.
11. **Not an engine setting.** `echo always > /sys/kernel/mm/transparent_hugepage/enabled` (root, system-wide) is a test
    of point 2 without the copy. The code idea is `madvise(MADV_HUGEPAGE)` on the store arena in `os::range_commit`
    (exact).

Skipped as clearly slower, no-ops or test-only:
- `DS4_SYNC`, `DS4_WINDOWS`, `DS4_FLOW=0`, `DS4_FLOW_PUMP_WAIT=0`, `DS4_MOE_TOKEN=0`, `STRATA_DS4_NO_TC`,
  `STRATA_FORCE_*`.
- `DS4_STORE_PRELOAD=0`, `DS4_STORE_PREGROW`, `DS4_READAHEAD_MB`, `DS4_IQ_PF_COLD`, `STRATA_DS4_RAM_TIER`,
  `DS4_GG_IQ*`, `--vram-experts`.

Slots (`STRATA_DS4_SLOT_*`, auto pin) change speed only for interleaved conversations. They are a test, not a screen
(B.2).

## 8. Non-exact settings: confirm off

| Setting | Default | Our config | Server | Kind | Note |
|---|---|---|---|---|---|
| `STRATA_DS4_PROMPT_SKIP` | **1 (ON)** | **0** | not set | LOSSY | **The one lossy default that is ON.** Inactive on two GPUs anyway (needs every trunk layer on one GPU, model.cu:7875-7887). It would act in a one-GPU config without the 0. |
| `DS4_YOCO` | unset | unset | not set | LOSSY | Takes precedence over `STRATA_DS4_PROMPT_SKIP` (model.cu:7868-7871). Check the shell environment too. |
| `DS4_YOCO_KEEP` | 0 | unset | not set | LOSSY | only with the skip |
| `STRATA_DS4_DISK_SKIP_W` / `_FROM` | 0 | unset | not set | LOSSY | drops experts, no renormalisation |
| `DS4_AR_F16` | 0 | unset | not set | lower precision | TP groups of > 2 GPUs only (n/a) |
| `DS4_STORE_ZC` (+ `_ZC_FRAC`) | 0 | unset | not set | rounding, timing-dependent | one GPU only |
| `DS4_ATTN_SPLIT` | 0 | unset | not set | rounding | split-KV decode attention |
| `STRATA_DS4_TQ_WORDS` | 0 | unset | not set | n/a | trellis packs |
| DSpark (`--dspark on`, `--dspark-conf/-block`, `DS4_DSPARK_MAX/SAMPLE/QTEMP`, `STRATA_DS4_DSPARK_CUM`) | auto | auto (not loaded here) | never sends `spec`/`dspark_*` | samp | distribution-exact; realised tokens differ; verify windows round differently from single steps |
| `STRATA_DS4_REUSE` | 1 | unset | not set | rounding | reuse (decoded state) vs re-read differ in bits; the default is the reference |
| Rounding-level defaults that are ON by design | - | unchanged | - | rounding | Expert-cache swaps landing async (model.cu:5762-6045). `DS4_SETTLE_MS` 6000. The timing-based `DS4_PATH_PICK`. Profile-dependent `DS4_SPEC_Q` 0.9. Profile written back after every request (main.cpp:930). CPU-lane vs GPU numerics. The sampler counter runs per process (main.cpp:327). |
| Thinking budget 32768 + #984 cap + wrap-up text | **ON** | (unset) | applied | content | server.py:204, 211, 4155-4169, 5107-5113; the intended behaviour, same cap formula as P021m's answer_room for max_tokens >= 1024 |
| Effort default "high" (75) | **ON** | none set | template | content | P021m's paths use medium; see B.4 |
| `top_k` 0 / > 64 -> 64 | ON | 20 | applied | samp | n/a for our 20 |
| Penalties, logit bias | sent | - | sent | ignored by the engine | a request asking for them silently gets none |
| `reasoning_loop_recovery`, `reasoning_close_retry`, `tool_call_recovery` | off | off | off | content | opt-in |

Nothing lossy is ON in our launcher. The only non-exact default that is ON in the engine is `STRATA_DS4_PROMPT_SKIP=1`.
Our config turns it off, and it is inert on two GPUs. The server's ON defaults are content-level: the thinking budget
and the effort default.

## 9. Findings while building the table (corrections for the round)

1. **The `numa2` screen measures nothing.** `DS4_COPY_NUMA` is read only inside `copy_experts` after the copy budget
   check (model.cu:4166-4187). With `--mmap-experts auto` and no `DS4_COPY_GB` the budget is 0 and nothing is copied.
   Pair it with `DS4_COPY_GB` or drop it.
2. **`STRATA_DS4_AUTO_PIN=1` in a config's `env` does not reach the server.** The server reads it from its own
   `os.environ` (server.py:4935); the config env goes only to the engine (child_env, server.py:3499-3514).
   - `tunearm.sh:53` (and `speedarm.sh:42`) start the server without exporting the config env.
   - So the round's conv test (tune.py:507) runs **without** the auto pin on the v0.2.4 server.
   - `run-strata.sh` does export the config env (run-strata.sh:114), so a daily launcher through it works.
3. **`DS4_STORE_FLOOR_GB` is whole GiB.** `(size_t)(atof(v)) << 30` truncates (model.cu:4490), so the s74 screen's 15.5
   acts as 15 GiB (16.1 GB), and our 16 is 17.2 GB. `--ssd-cache` is in GB (10^9).
4. **`DS4_TOKLOG` only prints in the CLI decode path** (main.cpp:1427; `--serve` returns at 1296). The profiled
   baseline gets no token-latency line from it.
5. `DS4_IQ_*` are compiled out (section 5), and `DS4_STORE_PREGROW` is a no-op without ZC on Linux.
6. The server's `pcie_frac` reaches the engine only through a `strata_tune` object (server.py:1427-1432). Our configs
   have none, so nothing is sent; the engine would ignore it anyway (B.5).
7. `configs/DS41-v024-s70.json`'s `_comment` says `DS4_STORE_FLOOR_GB=20`; its env says 16 (the env is what runs).
8. `run-strata.sh` falls back to the v0.1.11 server when a config has no `"server"` key (run-strata.sh:38-39). The DS
   configs have none, because the arm scripts pass the server themselves.
9. A `"vision"` section (P021m has one) or any of `parallel` / `pool_cores` / `expert_profile_save` / `vram_elastic` /
   `drafting` in a DS config stops the engine at start (section 6).

---

# Part B. Carry-overs from P021m (Qwen, `configs/P021m.json`, `strata-r22p021m/serve/server.py`)

## B.1 `--reserve-mib`

- **Default 600 MiB, on each GPU alike** (`model.hpp:29`; `main.cpp:1213`).
- Per GPU group, the expert budget is `(cudaMemGetInfo free - reserve_mib << 20) x --vram-experts`, measured at placement
  time (`model.cu:3812-3821`). This happens **after** the dense weights, KV, chunk buffers (about 1.8-1.9 GB per card
  at chunk 8192) and the 400 MB ring are allocated (`model.cu:2548` vs 2637, 2776).
- The drafter's experts come first (none here). The trunk's share is then `frac = budget / want` of each layer's 384
  experts, with the floors filled whole, layer by layer (`model.cu:3832-3864`).
- Each layer with experts on both sides keeps **one VRAM slot spare for swaps**: 40 slots, about 0.34 GB
  (`model.cu:3888-3896`).
- MiB per expert = the layer's blob: 7.74 MB (IQ1_M layers) to 10.23 MB (layer 39), 8.60 MB mean (computed from
  `tensors.txt`, engine-options appendix). So **100 MiB = about 12 experts (10-13.5)**: reserve 600 -> 300 is about
  35-40 more per card.
- **Nothing else is reserved for a display.** The engine has no display logic (grep: none); whatever the desktop holds
  at load is excluded by `cudaMemGetInfo`, and later growth eats into the reserve.
- The server adds a reserve only with a GPU vision encoder (`--vram-reserve-mib 700`, a Qwen flag that would stop
  strata-dsv41; server.py:3109-3111). Since 10-23 the monitor is on the iGPU, so neither card draws a desktop.
- P021m's `--vram-reserve-mib 713` is the Qwen engine's main-card reserve, not the same flag.

## B.2 Slot policy (conversation slots)

**What the knobs do** (`main.cpp:331-353`, 477-576; `ds4_slotmeta.hpp`):
- `STRATA_DS4_SLOT_KEEP=1` turns slots on (any non-zero). The engine default is off. The **v0.2.4 server sets "0"**
  (server.py:3482, 3492); v0.2.4.2 sets "1" (commit baa8f616). A config `env` entry wins over the server's setdefault.
- `STRATA_DS4_SLOT_CAP` (4) is the number of conversations kept in RAM.
- `STRATA_DS4_SLOT_MIN` (1024) is the shortest conversation set aside. **It exists.** It is checked on the displaced
  state's whole length, generated tokens included (main.cpp:480-481).
- `STRATA_DS4_SLOT_GB` caps the folder's `.bin` bytes: engine 16, server 2.
- `STRATA_DS4_SLOT_DAYS` (7): older folder entries are removed at start.
- `STRATA_DS4_SLOT_DIR` sets the folder.
- `STRATA_DS4_AUTO_PIN` is not a slot knob: the server marks the end of the leading system/developer messages as `pin=N`,
  which becomes checkpoint 3 (main.cpp:777, 801). That checkpoint travels with a slot's checkpoints, so a slot can serve
  another agent behind the same system prompt (slotmeta `pick`).
- `STRATA_DS4_REUSE=0` resets the state every request, so nothing is ever saved.

**When something is saved.**
- Only when a request does **not** continue the state in place (main.cpp:700-720). The engine then saves the
  conversation **currently in the model** (`slot_put`), not the new one, before it takes back the best kept one
  (`slot_take`).
- Saved if: slots are on, the state is >= `SLOT_MIN` tokens, it holds no pictures (main.cpp:708; slot_save refuses
  them, model.cu:4815-4817), and it changed since it was last taken back (`slot_held`, model.cu:4803-4806).
- **Tools play no role.** A tool-call conversation is text like any other.
- A continuation miss (B.3) also triggers a save: the overshoot state becomes a junk slot.
- The engine's exit writes the live conversation and every RAM slot to the folder (main.cpp:932-956).

**Eviction order.**
- A new save first drops every older slot whose tokens are a prefix of it (the same conversation, superseded;
  main.cpp:492-494).
- Past `SLOT_CAP` in RAM, the least recently used RAM slot is written to the folder. If under 8 GB is free there, it is
  dropped instead (main.cpp:497-506, 442-449). The `used` clock is set at save and at take-back (main.cpp:495, 562).
- After each write, the folder is trimmed LRU-first to `SLOT_GB`, never the file just written (main.cpp:419-440, 474).
- At start, folder slots come back as file slots, oldest first (main.cpp:596-633).
- A folder slot is still a fast hit: it is read whole from the NVMe.

**Opt-out: none today.**
- The engine's GEN keys are `temperature top_p top_k min_p seed spec dspark_conf pin dspark_cum` (main.cpp:304-313).
- The server already sends `ckpt=0` for `"strata_checkpoint": false` (server.py:1443-1446), and the deep-research
  proxy already sets that field on its one-shot classes, but strata-dsv41 ignores it.
- No header or field changes slot saving. Only the global env knobs do.

**Size** (computed from `slot_bytes`, model.cu:4794-4800, with this pack's geometry):
- About 2.8 MB fixed (40 window rings of 128 x 528 B), plus 0.92 KB a token (4 KV sources at ratio 2/2/2/1, 368 B a
  row), plus up to 4 checkpoints of about 2.9 MB each.
- 6.5K tokens with 3 checkpoints is about 17 MB, which matches the docs (DEEPSEEK41.md:85). A full 32K conversation is
  about 43 MB.
- So 16 RAM slots cost at most about 0.7 GB of engine RSS, and 8 GB of folder holds about 190 full conversations.

**The problem for our traffic.**
- Every displaced conversation of >= 1024 tokens takes a RAM slot as the most recently used. That includes a medium
  one-off (a title call that thinks, a research extract / verify / report call, the `run-strata.sh` warm-up of about
  9.5K tokens).
- So each such one-off pushes the oldest chat to the folder.
- A research run's many distinct long prompts each become a slot. Once the folder passes `SLOT_GB`, the chats, being
  older, are trimmed first.

**Proposal, settings now** (all exact):
- Config `env`:
  - `STRATA_DS4_SLOT_KEEP=1`
  - `STRATA_DS4_SLOT_CAP=16`: about 0.7 GB worst case; it absorbs 12 one-offs between two turns of a chat without a
    chat leaving RAM.
  - `STRATA_DS4_SLOT_GB=8`: chats survive about 190 research-size slots in the folder.
  - `STRATA_DS4_SLOT_MIN=1024`: keep the default. 2048 only if Jan's title calls turn out to be 1-2K-token states, and
    it costs short chats about 10 s each to re-read.
- `STRATA_DS4_AUTO_PIN=1` in the **server's** environment. `run-strata.sh` exports the config env; test scripts must
  `export` it themselves.
- `"codex_thread_titles": true`, so Codex's title turns never reach the engine (responses.py:329-354).
- Skip `run-strata.sh`'s warm-up for DeepSeek. It reads about 9.5K tokens (minutes of disk on DS) and becomes a slot.
  The DS engine allocates its chunk buffers at load, so the OOM reason for the warm-up does not apply.
- Limit: LRU cannot tell a one-off from a chat. These settings only dilute the problem.

**Proposal, a small code change for later** (no output change; it only decides what is kept):
1. **Honour `ckpt=0` in strata-dsv41** (about 10 lines, main.cpp).
   - Parse `ckpt` in `parse_gen`.
   - Mark the live state "one-shot"; a later request that continues it without `ckpt=0` clears the mark.
   - Return early in `slot_put`.
   - Deep-research's one-shot classes then never take a slot. The server side is already there.
2. **Probation for one-request conversations** (an SLRU, about 40 lines).
   - A conversation saved after a single request (never continued in place, never taken back) goes to a probation list
     of `STRATA_DS4_SLOT_PROBATION=2` RAM slots.
   - Probation slots are evicted first and never written to the folder. A take-back promotes one.
   - This catches Jan's title calls and other one-offs with no client help. A new chat's first turn still survives a
     couple of one-offs.
3. **Owner tags, as P021m's a8a5ee60.**
   - The server maps `strata_owner` to `owner=TAG` and `strata_chat_drop` to `chat_drop=TAG` (the proxy already sends
     both).
   - The engine gives tagged conversations their own RAM cap (e.g. `STRATA_DS4_SLOT_CAP_TAGGED=4`), trims tagged ones
     first in the folder, and drops them on `chat_drop`.
   - Research agent loops then keep their slots for interleaving without evicting chats.
   - (A research agent turn should **not** get `ckpt=0`. If it were not saved, an interleaved request would make its
     next turn re-read a 24-33K prompt.)
4. Only if 2 is not done: a server rule that adds `strata_checkpoint: false` to Jan's title-request shape. Take the
   shape from one logged request (message count, roles, max_tokens, tools; format only) before writing the rule.

**How to test** (one gap; extend tune.py's `conv` test, which already slices the engine log):
- Fresh slot folder.
- Config: slots on, the server's env with `STRATA_DS4_AUTO_PIN=1`, `CAP=4` (baseline) and then the proposal.
- Sequence:
  1. Four real chats A-D (prompts/longreason math and code, agentturn A/B, each with a nonce), 2 turns each,
     interleaved, so 4 RAM slots fill.
  2. Six title-shaped one-offs (a short user message plus a "give a 5-word title" instruction, max_tokens 64-256, at
     500 / 1500 / 3000 state tokens).
  3. Three research one-offs (abrun research4 R1-verify20k and R3-extract5k, distinct nonces, `strata_checkpoint`
     false).
  4. One more turn on each of A-D.
- Read from the engine log:
  - `ds4 slots: saved a N-token conversation ...; X in RAM, Y in <dir>`
  - `took back a N-token conversation ... from RAM|the folder (T s); K new tokens to read`
  - `maya ds4 serve: prompt N tokens = X reused + Y read`
- Pass for the target policy: every A-D follow-up is taken back **from RAM** and reads at most the new turn + 64 tokens;
  no `saved` line for a one-off once 1 or 2 is in.
- Report TTFT against the same follow-ups with slots off (conv3).
- Settings-only expectation: at CAP 4 the first medium one-off moves A to the folder (still a hit, from the folder); at
  CAP 16 nothing moves.

## B.3 The continuation fix (P021m a653ae6c) and the DeepSeek path

**What P021m fixed** (`git -C strata-r22p021m show a653ae6c`; server.py +42, generate.cpp +49, test_server.py +85):
1. **One-shot calls with a budget.** Deep-research's extract / verify / report / compact calls (`ckpt=0`) ended with
   `live_ok=false` in the Qwen engine, so answer_room's continuation pass had nothing to resume from (8080 phase 4: 31
   of 32 missed, about 11 s each).
   - Fix: the server sends `keep=1` on every pass of a budget request with ckpt=0 (its own field `_strata_keep_live`).
   - The engine keeps the live session for the server's own next pass only: no checkpoint, never parked
     (generate.cpp:12393).
2. **The STOP race.** The server STOPped at the budget, often mid speculative window, and the session held tokens past
   the wrap-up point (gap 7: 4 of 8 missed).
   - Fix: GEN keys `tcap=N tend=ID`. The engine stops after N tokens unless it handed out `</think>` (id 248069), and
     commits only what it hands out.
   - The server sends the tokens left to the budget while thinking (`_strata_think_cap`). Past a non-clean point the
     next pass extends the session (generate.cpp:12394).
3. **Tool-call turns.** Covered indirectly: at max_tokens 1024 the call is written in the continuation pass. They were
   checked for validity (toolcall_check.py), not for reuse.
   - Note: the cap formula gives 512 of 1024 on both servers: `max - min(max(512, max/4), max/2)`. toolcall_check.py's
     docstring says 768.

**How it was replayed:**
- `work/r22/contarm.sh`: abrun.py `normal` W1 (math proof, cap 3072, so thinking is capped at 2304). 8 reps as sent,
  plus 4 with `--extra '{"strata_checkpoint": false}'`. One engine-log slice each.
- `work/r22/rcont.sh`: abrun.py `research4` R1-verify20k (about 24K tokens, xhigh, cap 4096 -> 3072) x 3 and
  R2-report54k (about 54K, medium) x 2, both with `strata_checkpoint` false.
- `work/r22/toolcall_check.py`: OpenCode A/B, Jan's web_search/fetch_page, research agent 989, each at its own cap and
  at 1024, 3 each.
- Verdict: `work/r22/gap9_verdicts.py cont`. It matches `prompt N tokens = X reused + Y read ..., G generated`. A
  continuation is a prompt within 0-64 of the previous N + G; it is a hit if read <= 64.
- Request format (abrun.py:68-76; toolcall_check.py:59-61):
  - `POST /v1/chat/completions` with `model`, `messages` (a nonce line prepended to the first message), `max_tokens`
  - `"stream": true`, `"stream_options": {"include_usage": true}`
  - `"reasoning_effort"` medium or xhigh
  - T 1.0 / top_p 0.95 / top_k 20 / min_p 0.05
  - optional `tools`; no seed
- Results:
  - Gap 9: W1 12/12 hits against 4/12 before. A hit reads 19 tokens in about 0.1 s; a miss took 0.85-0.93 s.
  - Gap 10: research 3/3 against 0/3, about 5.7 s saved each.

**The DeepSeek path (v0.2.4 server + strata-dsv41).**
- **Server.**
  - Budget = the request's `reasoning_budget_tokens` / `thinking_budget_tokens`, else the config's, else
    **DS41_DEFAULT_BUDGET 32768** (server.py:4155-4169). It is then capped by #984 at max - reserve
    (server.py:5107-5113). So every thinking request below about 43.7K max_tokens can continue, the same as P021m's
    answer_room for max_tokens >= 1024.
  - At `thought >= budget`, at a clean point, the pass breaks (server.py:5340-5343). `gen.close()` sends STOP and drains
    to DONE (5366-5380).
  - Prompt = prompt + seg + `REASONING_WRAP_UP` (17 tokens measured; server.py:211, 5446-5474).
  - A forced call (`tool_choice`) continues with prompt + seg + "\n\n" + its opening (5451-5455).
  - `reasoning_close_retry` (opt-in, off) continues with prompt + seg + `REASONING_CLOSE`.
  - The request holds the engine FIFO across all its passes (server.py:5200-5218), so nothing interleaves.
- **Engine.**
  - There is no `ckpt`, `keep`, `tcap` or `tend` key (main.cpp:304-313). The state always stays in the model after
    DONE, so **P021m's problem 1 cannot happen on DS**.
  - **Problem 2 can.** A STOP is honoured only before the next token is printed (main.cpp:876-912).
    - After a plain step, the last printed token has been fed, so the state is exactly prompt + seg: a hit.
    - After a **DSpark verify round**, the accepted drafts are in the state but not yet printed. The same overshoot
      happens if the server lags behind the engine (a slow stream reader).
    - Then the continuation diverges inside the state (`c < n_state`, main.cpp:700). The engine goes back to
      checkpoint 0, the end of the first pass's prompt (main.cpp:709-719; model.cu:4713-4717), and **re-reads the whole
      thinking**: 2304 tokens is tens of seconds on DS, against about 4 s for the 17-token hit (the round's
      chunkmin64 note).
    - With slots on, the overshoot state is also saved as a junk slot first (main.cpp:708).
  - With `--dspark auto` (not loaded here) only the lag case remains, and our arms showed hits
    (`2446 tokens = 2429 reused + 17 read`).
- **Reuse counting.**
  - stderr line `maya ds4 serve: prompt N tokens = X reused + Y read in T ms (R tok/s), G generated in ...`
    (main.cpp:921-927). X = `from`: kept in place, restored from a checkpoint, or taken from a slot.
  - `DONE` field 9 = from. The server reports only the first pass's value as `usage.prompt_tokens_details.cached_tokens`
    (server.py:5892, 5685), so use the engine log.
  - `gap9_verdicts.py cont`'s regex matches the DS line unchanged.

**Proposed DS replay test** (a `contarm-ds.sh` modelled on contarm.sh / rcont.sh):
- Setup:
  - The DS server on 8086, started like tunearm.sh with the exported env.
  - `ELOG` = the config's `"log"`; one slice per set.
  - Verdict `gap9_verdicts.py cont`.
  - Everything must fit `--max-context 32768`: R2-report54k and R4-agent33k / the research-989 tool shape do not.
- Requests (Jan-style, format only):
  - `POST /v1/chat/completions`, `"stream": true`, `"stream_options": {"include_usage": true}`
  - `messages` = [optional system (the assistant's instructions), user], with a nonce line in the first message
  - `max_tokens` per shape
  - `"reasoning_effort": "medium"`: Jan's default assistant, DS level 62. `"xhigh"` = Deep think = DS "max" (100),
    frontend.py:140-141.
  - T 1.0, top_p 0.95, top_k 20, min_p 0.05
  - `tools` = Jan's web_search/fetch_page schemas for tool turns; no `tool_choice` except in set 4
  - `"seed"` (int > 0) only in the exactness arms
- Sets:
  1. W1, cap 3072 (budget 2304): x 6 as sent, x 3 with `"strata_checkpoint": false` (ignored by DS; shows there is no
     difference).
  2. Tool turns at cap 1024 (budget 512, so the call comes in the continuation): toolcall_check.py shapes opencode-A,
     opencode-B and jan, x 2 each.
  3. Research: R1-verify20k (xhigh, cap 4096 -> 3072) x 2 and R3-extract5k (medium, cap 2048 -> 1536) x 2, with
     `strata_checkpoint` false.
  4. One forced call: the jan shape with `"tool_choice": {"type": "function", "function": {"name": "web_search"}}`,
     cap 1024 (the "opens" path).
  5. Optional: the same with DSpark forced on (the `dspark4060` config). Expect misses, which is the case for a tcap
     port.
- Measures:
  - (a) Hits: read <= 64, 17 for the wrap-up. Pass = all hits in sets 1-4.
  - (b) The continuation's prompt ms, hit vs miss.
  - (c) With slots on, no `ds4 slots: saved a` line between the two passes of one request.
  - (d) Exactness, arms A (default) vs B (`STRATA_DS4_REUSE=0`):
    - Each arm is a fresh engine with the restored profile and the repeatability setup (`--no-expert-cache`,
      `DS4_PATH_PICK=0`, for this check only).
    - The same seed. The replayed request is **each engine's first request**, because the Philox counter runs per
      process (main.cpp:327, 842).
    - Expect the first pass to be identical in A and B. The continuation in A extends decoded state, while B re-reads
      it through the prompt path, so the two may part at a near-tie (rounding-level, like the conv test's A7 vs A7
      fresh).
    - Add A again (A vs A') to show the setup is deterministic.
    - Add one greedy (temperature 0) pair to see where they part.

## B.4 Control layer: P021m's keys and behaviour vs the v0.2.4 DeepSeek path

| P021m (key / behaviour) | Exists on the v0.2.4 DS path? | Daily DS config |
|---|---|---|
| `"sampling"` T 1.0 / 0.95 / 20 / min_p 0.05 | yes (config block; merge model card -> config -> shared -> request, server.py:5084-5088) | same block (already in DS41-v024-s70) |
| `P021m.shared-settings.json` = effort medium, T 1.0, top_p 0.95, top_k 20 | yes: `<config>.shared-settings.json` (server.py:8598-8606) | copy it as `configs/<ds-daily>.shared-settings.json` (same 4 keys). DS41-v024-s70 has none, so requests without a level think at "high" (75). Optionally also `"reasoning_effort": "medium"` in the config (server.py:8482-8488) |
| Effort words | **different**: DS low 50 / medium 62 / high 75 (default) / xhigh = max = 100; Qwen high = xhigh (frontend.py:134-151) | nothing to set; Jan's "Deep think" (xhigh) becomes DS max |
| answer_room (on) + #984 | yes, the same formula for max_tokens >= 1024; DS also caps 48-1023 at half and applies 32768 above about 43.7K | default (no key) |
| Continuation fix (keep=1, tcap/tend) | keep=1 not needed (no ckpt handling, the state stays live); **tcap/tend missing** | nothing; port tcap only if DSpark is used |
| `--chat-cache 16 --chat-cache-mib 12288` (parks only checkpointed conversations >= 512 tokens, so ckpt=0 calls never; LRU by count and MiB; generate.cpp:2684-2685, 11893-11957) | as slots: `STRATA_DS4_SLOT_KEEP/CAP/MIN/GB/DIR`, `STRATA_DS4_AUTO_PIN`; **ckpt=0 ignored**, no MiB cap (count + folder GB) | `STRATA_DS4_SLOT_KEEP=1`, `STRATA_DS4_SLOT_CAP=16`, `STRATA_DS4_SLOT_GB=8`, server env `STRATA_DS4_AUTO_PIN=1` (B.2) |
| Owner tags `strata_owner` / `strata_chat_drop` (a8a5ee60, server.py:1423-1430) | **no** (fields ignored, harmless) | code idea B.2 item 3 |
| `"web_search"` (SearXNG 8888, 6 results, 12000 chars, 20 s, 20 rounds; serve/websearch.py; Exa/Tavily fallback) | **no** (no websearch.py in v0.2.4; the key is ignored). The 8080 chat page loses its Web search switch. Jan's own MCP tools are unaffected | keep the key (inert; `run-strata.sh` starts SearXNG for it); port websearch.py later |
| `"mcp": {"max_rounds": 20}` | yes (mcp.py:629-645); inert without `mcp_servers` on both | same |
| `"vision"` (Qwen mmproj, strata-vision) | **must not be copied**: the DS pack has no tower, and the server would append `--vision` without a value, so the engine exits 2 | no `"vision"` key |
| `"fallback"` (`run-strata.sh` helper_check, only with `--expert-cache-device1`) | n/a | omit |
| `"server"`: strata-r22p021m/serve/server.py | must point at **strata-v024/serve/server.py** (run-strata.sh otherwise uses v0.1.11's) | `"server": ".../strata-v024/serve/server.py"` |
| Think-fence rule (845031f5: `</think>` inside a code fence held) | **no** (#2794 not in v0.2.4 or v0.2.4.2) | known difference; port later |
| `env` Qwen knobs (STRATA_SPEC_EXACT, ...) | not read by strata-dsv41 | do not copy; DS env = CUDA_VISIBLE_DEVICES, `STRATA_DS4_PROMPT_SKIP=0`, `DS4_STORE_FLOOR_GB=16`, the slot keys, plus the round's winners |
| Penalties / logit_bias honoured | **ignored** by strata-dsv41 | none |
| Max context 131072 | DS 32768 here (long research prompts do not fit) | per the round |
| `"codex_thread_titles"` | yes (also in P021m's server, unset there) | `true` if Codex uses DS |
| `run-strata.sh` warm-up | would be a 9.5K-token read and a slot | skip for DS |

**Daily DS launcher keys** (on top of the round's winning args):
- Paths: `exe`, `"server"` (strata-v024), `arch: "deepseek41"`, `model_name`, `tokenizer`, `cwd`, `log`, `lib_dirs`.
- `host 127.0.0.1`; port via `STRATA_PORT=8080`; `engine_ready_s 3600`.
- `sampling` {1.0, 0.95, 20, 0.05}, `"reasoning_effort": "medium"`.
- `"mcp": {"max_rounds": 20}`, `"web_search": {...}` (inert), `"codex_thread_titles": true` (optional).
- `env`: `CUDA_VISIBLE_DEVICES`, `STRATA_DS4_PROMPT_SKIP: "0"`, `DS4_STORE_FLOOR_GB: "16"`, `STRATA_DS4_SLOT_KEEP: "1"`,
  `STRATA_DS4_SLOT_CAP: "16"`, `STRATA_DS4_SLOT_GB: "8"`, `STRATA_DS4_AUTO_PIN: "1"` (works through run-strata.sh's
  export).
- Plus `configs/<ds-daily>.shared-settings.json` = {"reasoning_effort": "medium", "temperature": 1.0, "top_p": 0.95,
  "top_k": 20}.
- No `vision`, `fallback`, `parallel`, `pool_cores`, `expert_profile_save`, `vram_elastic`, `drafting`,
  `effort_position`.

## B.5 pcie-frac

**strata-dsv41 does not read it.**
- There is no flag: `--pcie-frac` would end the engine with exit 2 (main.cpp:1267-1273).
- There is no GEN key: `parse_gen` ignores unknown keys (main.cpp:304-313). `grep -i pcie` in `src/dsv41` finds only
  comments and the ZC code.
- The server sends `pcie_frac=` only from a `strata_tune` object (server.py:1427-1432, 7955). Our configs have none, so
  it is not even sent. `engine-options.md`'s "the server sends it" holds only with `strata_tune`.

Nearest equivalents:
- Prompts: the flow already computes **every** CPU-lane expert on the GPU, streamed over PCIe from the store or SSD
  (model.cu:3169-3496). There is no share knob. `DS4_PATH_PICK` / `DS4_CHUNK_MIN` pick flow (100 % GPU) vs windows
  (CPU lane computes) for short prompts. `DS4_READERS`, `DS4_RING_MB` and `DS4_SPEC_Q` shape the PCIe stream.
- Decode: the CPU lane computes all non-VRAM experts. `DS4_STORE_ZC=1` + `DS4_STORE_ZC_FRAC=50` would let the GPU
  compute store-resident experts over PCIe, which is the real analog. It works on one GPU only, upstream measured it
  slower, and it is timing-dependent (model.cu:4494-4499).

## B.6 `STRATA_DS4_DSPARK_CUM`

- What it does: the drafts' cut on the **product** of their confidences (DeepInfer's cumulative rule) (main.cpp:152-162).
  - In each DSpark round, a draft is verified while its own confidence is >= `--dspark-conf` **and** the running
    product of the confidences so far is >= F (main.cpp:179-183).
  - It is an adaptive draft length per round: a window whose later drafts are likely lost is cut short.
- Default **0 = off**.
- Per request through the GEN key `dspark_cum` / `spec_cum` (main.cpp:313). The v0.2.4 server never sends it, so only
  the env applies.
- Upstream note: not measured faster on H100 / the owner's PC; Project Maya runs 0.5 (Radeon 8065S: +6.5 % decode,
  "the same tokens").
- Exactness: **samp.**
  - Greedy: the accepted tokens are the trunk's argmax, but window sizes change the verify rounding.
  - Sampled: speculative sampling stays distribution-exact (model.hpp:121-127), but the realised tokens depend on the
    window sizes (the counter advances by acc + 1 a round, main.cpp:193).
- It only acts when DSpark is loaded, which `--dspark auto` does not do on our box.
- It is the DS counterpart of P021m's `STRATA_DRAFT_CUM=1` (Basalt's per-request adaptive rule). DS's is a fixed
  threshold.
