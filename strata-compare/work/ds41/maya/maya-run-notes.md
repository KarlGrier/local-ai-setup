# Maya v1.1.28 DeepSeek-V4.1 engine in our harness: run notes for the S / M1 / M2 head-to-head

Prepared 10-25 evening, during the measured round. **Code reading only.**
- Maya: `git show` / `git grep` at v1.1.28 (6afa525) in `ext/project-maya`.
- Strata: v0.2.6 (and the v0.2.4 working tree) in `strata-v024`.
- Nothing built, compiled, run or imported. The only Python run was our own venv's (`-I -c "import X"`, `pip list`) and
  `ast.parse` / `bash -n` on the new files.
- Line refs:
  - `model.cu` / `ds4_main` = Maya `src/ds4/ds4_model.cu` / `ds4_main.cpp`.
  - `server.py` / `frontend.py` = Maya `serve/`.
  - `s:` = Strata v0.2.6 `src/dsv41/` or `serve/`.

**Files here (work/ds41/maya/):**

| File | What |
|---|---|
| `maya-score.patch` | Strata's `--score` added to Maya's `ds4_main.cpp` (`patch -p1`; dry-run checked). Its header lists the adaptations. |
| `maya-run-notes.md` | This file. |
| `maya-M1.json`, `maya-M2.json` | Maya server + engine configs for the two arms. The exe, cwd and pack paths are proposals until the build. |
| `maya-tunearm.sh` | tunearm.sh for a Maya server arm (process name, log path, server env, client). |
| `maya-scorearm.sh` | scorearm.sh for the patched `maya-ds4 --score` (process name, Strata-only flags dropped, `unshare -rn`). |
| `maya-netns.sh` | Runs a command in `unshare -rn` with only loopback up. Wrap one arm in it. |
| `maya-speed3.py` | speed3.py plus ENGINE_NAME and an integer `reasoning_effort` 62. Use it for S as well. |
| `maya-ckpt_client.py` | ckpt_client.py with an integer effort 62 (and the notes for Maya: SLOTS=1, one pass a request). |
| `maya-score.py` | skipcheck's per-segment scoring and KL compare for any config file (Maya or Strata). |
| `security-review.md` | **Not mine.** Another agent wrote it in this folder at 22:13. I read it, did not change it, and took two settings from it (`MAYA_UPDATE_CHECK=0` in the server env, `DS4_LANE_CAL=none`). |

**Gaps that matter most (details below):**
1. **Configs:** `--ssd-cache` and `--experts` are errors in Maya (exit 2), and `--dspark auto` means "on". Every Maya config must drop the first two and say `--dspark none`.
2. **Effort:** Maya maps "medium" to 75, Strata to 62. Send a JSON integer **62** to every arm.
3. **Thinking budget:** Maya's default leaves 1024 tokens of max_tokens for the answer, Strata's 512 or a quarter. Run Maya's server with **`STRATA_GLM_THINK_RESERVE=512`** in its own environment. W1/W2 then think up to 2304 and W3 up to 1536 on both.
4. **Leak:** every `STRATA_*` setting in the config or the environment reaches Maya's engine under the same name. Our base config's `STRATA_DS4_PROMPT_SKIP=0` would silently turn M2's skip off; M2 sets `MAYA_DS4_PROMPT_SKIP=1`, which wins.
5. **S uses DSpark:** the round's current best config (`state.json` "cur") has `--dspark on` + `STRATA_DS4_DSPARK_CUM 0.5`, and Maya cannot load a DSpark drafter from our files. The engine comparison needs an **S arm with `--dspark none`** (or S-with-DSpark as a separate reference).
6. **Remaining arithmetic differences in M1:**
   - Maya sets `CUBLAS_WORKSPACE_CONFIG=:4096:8` when unset (ds4_main :1114-1120); Strata does not.
   - Maya runs a side stream for the hc ops (`DS4_HC_STREAM`, on by default, model.cu:1239). Strata has no such stream.
   - Maya's own claimed-exact rewrites have no switch (tiles, FP16 rows, router rows; `DS4_ROUTER_ROWS=0` restores the old router path).
   - Expect M1 ≠ S bitwise. Judge them by the KL references.
7. **SSD bytes:** the per-request SSD GB from `/proc/<pid>/io` is not comparable across engines (Strata's store reads O_DIRECT, Maya page-faults the files). Compare the drive's own counter (`device_read_gb` in disk.jsonl). For decode GB a token, add it to summ.py or read disk.jsonl.
8. **Missing package:** `jsonschema` (+ attrs, referencing, rpds-py, jsonschema-specifications) is not in our venv. Only JSON-schema structured output needs it.
9. **`/v1/responses` on Maya's DeepSeek path** goes through the non-DeepSeek message builder, and a numeric effort gets a 400 there (server.py:3858). Deep research via `/v1/responses` is a "switch" risk; it does not affect the measured arms.

## a. Maya's engine CLI for DeepSeek, and what our harness passes

**How Maya runs it.** One binary, `maya-ds4` (CMake target `maya-ds4` in CMakeLists.txt:471; the build drops it in the
build folder's root). It takes `--pack <model>/maya-ds4`, the folder `tools/ds4/pack_gguf.py --model <dir> --shards ...`
writes (`--out`'s default is `<model>/maya-ds4`). That folder holds `ds4.txt` (the geometry, `format gguf`, `model_dir`),
`engram.bin`, and `tokenizer/`, which is the server's tokenizer plus the chat template (pack_gguf.py:8-14, 347-360, 534-554).
- The engine reads no tokenizer. The server tokenizes and sends ids, as Strata's does.
- Experts per word come from `ds4.txt` `num_experts_per_tok` (model.cu:475). There is no `--experts`.
- Maya writes into the pack folder: `expert-profile.bin` (the default `--expert-profile`), `lane-times.txt` (the PCIe
  lane's calibration, model.cu:9157), and `lt-picks.txt` (AMD only).
- Modes: `--serve` (the server's protocol), `--ids/--n` (CLI decode), `--dump-logits`, `--ppl FILE`, `--encode-image`.
  `--score` comes only with maya-score.patch.

**Flags.** Strata v0.2.6 side: main() :1209-1269. Maya v1.1.28 side: main() :1149-1188. Maya exits 2 on any unknown
option ("unknown option X" + usage).

| Our flag (tune.py / configs / scorearm.sh) | Maya v1.1.28 | Notes |
|---|---|---|
| `--pack DIR` | same | Must be **Maya's own pack** (pack_gguf.py output), not Strata's `pack-ist-das-2.00bpw`. |
| `--max-context N` | same | Default 32768 in both. |
| `--eos 1` | same | `serve`: id list; CLI and `--score`: `atoi`. |
| `--dspark auto` | **parsed, not an error**, but means *on* | Maya: `spec = v != "off"`, `dspark = v != "none"` (main :1159-1163); no "auto". Pass `--dspark none` (the plan: no DSpark; pack_gguf's `--drafter` default `<model>/../dspark/dspark.json` would be taken if present). |
| `--dspark on/off/none`, `--dspark-conf F` | same | |
| `--dspark-block N` | **absent: error (exit 2)** | Not in our configs. |
| `--tp 2` | same | Default 2 in both. GGUF 256-value blocks force 2 -> 1 the same way ("tensor parallel 2 -> 1", model.cu ~2510). |
| `--ssd-cache GB` | **absent: error (exit 2)** | Strata's RAM store (ds4_store.hpp). Maya has none. Drop it (see "Memory" below). |
| `--ssd-policy` | **absent: error** | Not in our configs. |
| `--experts 6` | **absent: error (exit 2)** | Maya always uses the pack's `num_experts_per_tok` (6 for V4.1) and has no "experts per word" start line. Drop it, and drop the v026 pin for Maya configs. |
| `--prefill-chunk 8192` | same flag | Defaults differ. Maya -1 means GGUF in place, so `kVlRows` = 8192 (ds4_kernels.cuh:99). `chunk_default()` only changes it with `DS4_BORROW`, which is off on 2 GPUs (model.cu:3458-3462). Strata v0.2.6 unset gives 4096. Both pinned 8192. |
| `--reserve-mib N` | same | Default 600 in both. |
| `--expert-profile FILE\|none` | same | **Same file format** (uint32 counts [layers(+mtp)][384]; the read is identical, model.cu:3165-3173 vs s:2583-2591), so copies of `profile-2.00.bin` load. Written back after every request in both. Maya also keeps `prof_load` (the frozen-placement ordering fix). |
| `--no-expert-cache` | same | |
| `--verbose` | same | Strata also prints `ds4: build ... (version)`. Maya does not. |
| `--mmap-experts on\|off\|auto` | same flag, **other meaning without a store** | See "Memory" below. |
| `--threads off` | same | Maya sets `prompt_par = true` always (model.cu:2540). Strata: `par \|\| o.tp > 1 \|\| ...`. Both chunked here. |
| `--vision off` | same | |
| `--window 128` | same | Same parse. The default is 16 in both. |
| `--cpu-threads N` | same | Maya: 0 measures its CPU-lane configs at load (`tune_lane`, "the choice changes no output", model.cu:6029-6037) unless `--cpu-threads` or `STRATA_DS4_CPU_LANE=<name>` is given. Strata: physical cores. |
| `--gpus`, `--vram-experts` | same | |
| `--score`, `--score-out` | only with maya-score.patch | |
| `--ids`, `--n`, `--dump-logits`, `--temperature`, `--seed` | same | |
| `--layer-split` | accepted and ignored (both) | Maya's server adds it only when the config has a `gpu` list (server.py:1499-1505). |
| `--version`, `--pack-info`, `--profile-run`, `--spec-eval` | **absent: error** | Maya has `--ppl FILE` instead. |

**Env.** Each name was checked with grep over every v1.1.28 `src/ds4/*` file (getenv literals plus the helpers
`env_f`/`env_tri`/`env_on`/`one_gpu_or`/`ds4_env`), against the same list for Strata v0.2.6 `src/dsv41/*`:
- 165 names in Maya, 121 in Strata;
- full lists in the scratch notes;
- the names are text matches only, so not every one is a setting.

| Our env | Maya v1.1.28 | Notes |
|---|---|---|
| `DS4_SPLIT=10,30` | same | Same parser (model.cu:2762-2774 = s:2196-2208): trunk layers per group, in CUDA device order. |
| `CUDA_VISIBLE_DEVICES` (UUIDs, 4060 Ti first = `GPU-UUID-RTX4060TI...,GPU-UUID-RTX5080...`) | same | The order is the CUDA order. Maya's server sets `CUDA_DEVICE_ORDER=PCI_BUS_ID` + `CUDA_VISIBLE_DEVICES` from a config `gpu` list only. The config's `env` is applied after that and wins (server.py:1508-1526). Use the UUID env, no `gpu` key. |
| `DS4_SETTLE_MS`, `DS4_SETTLE_STORE` | **absent, ignored** | Strata-only (store / settle). |
| `DS4_CACHE_DECAY` | same | Default 0.9 in both (model.cu:1272). |
| `DS4_CHUNK` | same | Overrides the chunk (model.cu:2589 = s:1995). |
| `DS4_LAYER_CACHE_MB` | same | The layer-major path (one GPU only). |
| `DS4_TOKLOG` | **absent, ignored** | No per-token log in Maya. |
| `DS4_PROF` | same name | Maya prints `prof_line` per request in serve mode (ds4_main :1071) and at the CLI decode's end. Strata v0.2.6's extra "ds4 prof CPU lane (IQ rows) per call" line is not in Maya. |
| `DS4_FLOW_STATS` | same | Model.cu:12237 = s:8385. |
| `DS4_SCORE_PREFIX` | **only with maya-score.patch** | Absent at v1.1.28. |
| `STRATA_DS4_PROMPT_SKIP` | **read directly by Maya** | `yoco_mode()`: `DS4_YOCO`, else `STRATA_DS4_PROMPT_SKIP`, else **1** (model.cu:11992-11999; Strata: the same function, s:8165). `MAYA_DS4_PROMPT_SKIP` is copied onto it. |
| `STRATA_DS4_SLOT_KEEP` | **read directly** (engine) | Off unless set to a non-zero value (ds4_main :399-401, the same as Strata). For the server's own default, see section c. |
| `DS4_STORE_FLOOR_GB`, `DS4_STORE_GB`, `DS4_STORE_RESERVE`, `DS4_STORE_THREADS`, `DS4_STORE_ZC` | **absent, ignored** | No store. |
| `DS4_ENGRAM_CACHE_MB`, `DS4_ENGRAM_THREADS` | same | |
| `DS4_NO_EOS`, `DS4_GG_VERBOSE`, `DS4_TOPK`, `DS4_IQ_CTA_PER_SM`, `DS4_PICK`, `DS4_PICK_MIN`, `DS4_MISS_SPLIT`, `DS4_QUANT_SINGLE`, `DS4_QUANT_NODEDUP`, `DS4_WARM`, `DS4_COPY_ALL` | **absent, ignored** | Strata-only. |
| `DS4_CACHE_THREADS` | same name, **default differs** | Maya: 4 with more than 1 GPU (model.cu:3371-3372). Strata: 1 (s:2798). |
| `DS4_RING_MB` | same name, default differs | Maya: 400 fixed (model.cu:3565). Strata: auto 16/400, and our logs show `staging ring: ... -> 400 MB`, so they are equal here. |
| `DS4_AHEAD`, `DS4_AHEAD_EXTRA` | same | Default 1/0 in both. Strata turns the lookahead **off while its store runs** unless `DS4_AHEAD` is set (s:4718). Maya (no store) keeps it on. |
| `DS4_CACHE_MARGIN`, `DS4_CACHE_BONUS`, `DS4_CACHE_INFLIGHT`, `DS4_SPEC_Q`, `DS4_SPEC_WASTE`, `DS4_ASYNC_T`, `DS4_READERS`, `DS4_CHUNK_MIN`, `DS4_COPY_NUMA`, `DS4_LAYER_MAJOR`, `DS4_FLOW`, `STRATA_DS4_NO_LIGHT`, `STRATA_DS4_DSPARK_CUM`, `STRATA_DS4_SLOT_GB`, `STRATA_DS4_DISK_SKIP_W` | same | Same lines and defaults. |
| `DS4_COPY_GB` | same | See "Memory" below. |
| `STRATA_IQ_PREFETCH` | read by Maya's `src/kernels/cpu/iq_avx512.cpp:41` | Not on the ds4 path in Strata. Not used by us now. |

**Memory: the RAM store vs Maya's page cache.**
- `--ssd-cache` is Strata's RAM store (O_DIRECT reads into its own slots), and Maya has no store.
- For a GGUF pack, Maya always reads the CPU-lane experts **in place**: `file_experts = true`, model.cu:2566.
  - At load, the most-routed of them are read ahead into the **page cache**, up to `warm_bytes` = MemAvailable - 8 GB, capped by what VRAM leaves over (model.cu:3189-3206, 5310-5400).
  - The start line says "N CPU-lane experts read ahead (X GB) in Y s".
  - `DS4_WARM_CAP_GB` caps it. Strata sets `warm_bytes = 0` with the store (s:2657).
  - So expect ~70 GB of SSD reads at every Maya start, after dropcache.
- Then `copy_experts()` copies experts into anonymous RAM only as `--mmap-experts` says (model.cu:5411-5450):
  - **auto (default):** copies all of them only if all + 8 GB fit MemAvailable - 8 GB. 121 GB does not fit, so **nothing is copied**: page cache only.
  - **off:** copies the most-routed that fit, which is nearly all free RAM. **Do not use.**
  - **on:** nothing is copied.
  - **`DS4_COPY_GB=n`:** the hottest n GB copied, static. Start without it (the 04:48 page allocation failure was a 66 GB copy plus page-cache reads).
  - Recommendation: pass `--mmap-experts on` explicitly so a start never copies, whatever MemAvailable is.
- The page cache counts in MemAvailable, so the 12 GB guard will not see it. The swap guard might, if the readahead
  pushes idle apps out (system swap growth > 1 GB fails the run).
- `DS4_RAM_TIER` (`STRATA_DS4_RAM_TIER`, both engines, off) stays off.

## b. The two Maya arms: exact settings, names checked at v1.1.28

The full configs are `maya-M1.json` / `maya-M2.json`.

**Common to both:**
- **Args:** `--pack <model>/maya-ds4 --max-context 32768 --eos 1 --dspark none --vision off --tp 2 --prefill-chunk 8192 --mmap-experts on --expert-profile tmp/ds41-profile-arm.bin`.
  - No `--ssd-cache` and no `--experts`: both are errors in Maya.
  - The profile is copied fresh from `profile-2.00.bin` before each run, as tune.py does; same file format.
- **Env:**
  - `CUDA_VISIBLE_DEVICES=GPU-UUID-RTX4060TI...(4060 Ti),GPU-UUID-RTX5080...(5080)` and `DS4_SPLIT=10,30`.
  - `MAYA_DS4_STREAM=0`, `MAYA_DS4_SLOT_KEEP=0`, `DS4_LANE_CAL=none`.
  - `STRATA_SERVER_LOG=0`. This one is for the server.
  - The ship config's `DS4_CACHE_DECAY=0.8` and `DS4_ENGRAM_CACHE_MB=16` (10-24 ship-B). **Update these two to whatever S finally ships.**
  - `DS4_SETTLE_MS=0` and the store settings are Strata-only, so they are left out.
- **Server's own env:** `STRATA_GLM_THINK_RESERVE=512 MAYA_UPDATE_CHECK=0` (maya-tunearm.sh's SERVER_ENV default).
- **Config keys:**
  - `fit_max_tokens: true`, as Strata clamps instead of a 400;
  - `thinking_budget: 32768`;
  - our sampling block;
  - `host 127.0.0.1`;
  - its own `log`.

**M1 = Maya with Strata's arithmetic.** Each name was checked to exist at v1.1.28; the default is what you get when it is unset.

| Setting | Read where | Default | M1 | Your name right? |
|---|---|---|---|---|
| `MAYA_DS4_PROMPT_SKIP=0` | becomes `STRATA_DS4_PROMPT_SKIP` (env_aliases), read in `yoco_mode()` model.cu:11992-11999. `DS4_YOCO` overrides it if set | 1 (mode 1, exact skip). On the 10/30 4060-Ti-first split it **engages** (`yoco_suffix_gpu`: layers 20-39 on the 5080, Engram layers 1/14 < 20) | 0 | yes |
| `DS4_FAT_ROWS=0` | model.cu:3630-3633 | 64 (experts of >= 64 rows as FP16 GEMMs; VRAM experts only since v1.1.27) | 0 = off | yes |
| `DS4_ATTN_MMA=0` | ds4_kernels.cu:3336-3340 | on for sm_80+ (both our cards) | 0 = off | yes |
| `DS4_ATTN_SLAB_MB=8` | model.cu:3517-3521 | auto: the largest 2^k (8..64) whose slab + FP16 scratch fit 3% of the card's free VRAM | 8 | yes |
| `DS4_W16_MB=16` | model.cu:3518-3523 | 2 x the slab | 16 | yes. 16 << 19 = 8 M elements = Strata's fixed `8 << 20` (s:2932), and slab 8 MB = Strata's `8 << 20` / HQ (s:2929): **exactly Strata's sizes** |
| `MAYA_DS4_STREAM=0` | becomes `STRATA_DS4_STREAM`, read by `lane_env()` model.cu:9116-9124. `DS4_STREAM` overrides it | lane allowed for GGUF packs (`lane_alloc` :9156) unless `<pack>/lane-times.txt` says off for that GPU | 0 = off | yes |
| `DS4_IQ_Q8K=0` | ds4_gguf.cu:287-295 | on (Q8_K activations on the GPU like the CPU lane) | 0 = q8_1 per 32, as Strata | yes |

Lossy switches, all unset in M1 and M2:
- `DS4_YOCO_KEEP` (model.cu:12070; 0 = the exact keep);
- `MAYA_DS4_DISK_SKIP_W` → `STRATA_DS4_DISK_SKIP_W` (model.cu:1316; 0 = off; `DISK_SKIP_AUTO` only acts with it);
- `MAYA_DS4_RAM_SKIP_W` → `STRATA_DS4_RAM_SKIP_W` (model.cu:1324; 0 = off);
- `DS4_INDEX_TC` (ds4_kernels.cu:2923; opt-in, off).

**All your names are right.** The only nuance: `DISK_SKIP_W` / `RAM_SKIP_W` exist only under `STRATA_DS4_` / `MAYA_DS4_`, not bare.

Also in M1, and not in your list:
- **`DS4_CACHE_THREADS=1`.** Maya's default is 4 on 2 GPUs (model.cu:3371-3372); Strata's is 1. It moves which experts are in VRAM when, and with Q8K off that changes rounding paths (tune.py's ARITH set lists it). Drop it if M1 should keep Maya's cache threads.

Kept identical by default, so nothing to set:
- `DS4_RING_MB`: 400 in both here.
- `DS4_RECENT`: 0 here (GGUF in place, no landing on 2 GPUs).
- `DS4_BORROW`, the #476 landing (`DS4_LAND`/`DS4_STREAM_ZC`/`DS4_STREAM_WIN`), the decode warm-up (`DS4_WARM_GB`): all one-GPU-only by default.
- `DS4_HELPER`: unset.
- `DS4_Q8_BATCH`: off by default.
- `DS4_LT`: AMD only.
- `DS4_ATTN_V7`: sm_7x only.
- `DS4_ATTN_WMMA`: HIP only.

Not switched, and possibly not bit-neutral:
- `CUBLAS_WORKSPACE_CONFIG` (set by Maya, see top). To remove it from the comparison, give S the same `CUBLAS_WORKSPACE_CONFIG=:4096:8`. Not verified whether it changes any bits here.
- `DS4_HC_STREAM` (side stream).
- Maya's per-host CPU-lane choice (`tune_lane`, model.cu:6029; "changes no output", speed only). Pin `MAYA_DS4_CPU_LANE=cores` for repeatable starts if the first start's line shows it picking something else.

**M2 = Maya's defaults minus anything lossy or nondeterministic.**
- Env: `MAYA_DS4_PROMPT_SKIP=1` (explicit, see the leak below) and `MAYA_DS4_STREAM=0`.
- Everything else at Maya's default: FAT_ROWS 64, ATTN_MMA on, auto slabs (5080 about 16/32, 4060 Ti about 8/16 per the catch-up; computed at load, `--verbose` prints "prompt slabs"), IQ_Q8K on, cache threads 4.
- Chunk 8192 is Maya's own default here (`kVlRows`, ds4_kernels.cuh:99; `chunk_default` only acts with BORROW on 2 GPUs). Passing it costs nothing.

**The leak, answered.** Yes, STRATA_* settings leak into Maya, and in a stronger way than you assumed.
- `env_aliases()` (include/strata/platform/env_alias.hpp; first thing in main) copies every `MAYA_X` onto `STRATA_X`, overwriting it. The server does the same (`tools/maya_names.py` `alias_env`, `env_in` on the config: a config's `MAYA_X` beats its `STRATA_X`).
- The engine code itself reads the **`STRATA_` names**. Only `MAYA_DS4_LANE_FREE` and `MAYA_DS4_TIMER_MS` (Windows) are read under MAYA_.
- So **any `STRATA_X` in the server's environment or the config's `env` applies to Maya's engine directly**. Maya's server passes its whole environment plus the config env to the engine (server.py:1508-1526).

Of our settings, these are the ones Maya would take:
- `STRATA_DS4_PROMPT_SKIP` (base config "0": turns M2's skip off unless `MAYA_DS4_PROMPT_SKIP=1` is set; M1 wants 0 anyway);
- `STRATA_DS4_SLOT_KEEP` (same meaning; off is what we want);
- `STRATA_DS4_DSPARK_CUM` (cur config 0.5; only with DSpark, so inert with `--dspark none`);
- `STRATA_DS4_NO_LIGHT`, `STRATA_DS4_SLOT_GB`, `STRATA_DS4_SLOT_CAP/MIN/DAYS/DIR`, `STRATA_DS4_DISK_SKIP_W/FROM`, `STRATA_DS4_RAM_TIER`, `STRATA_DS4_LANE_FREE` (same meanings as in Strata);
- `STRATA_IQ_PREFETCH` (Maya's `src/kernels/cpu/iq_avx512.cpp`);
- the Maya-only `STRATA_DS4_STREAM`, `STRATA_DS4_RAM_SKIP_W`, `STRATA_DS4_CPU_LANE`, `STRATA_DS4_Q8_BATCH`, `STRATA_DS4_PIN_BY_NEED/PIN_GB`, `STRATA_DS4_TP_GGUF_UNEVEN`, `STRATA_DS4_LT_STORE`, `STRATA_DS4_DRAFT_DEV`, `STRATA_DS4_DISK_SKIP_AUTO/...`, should one ever be set;
- server-side, `STRATA_ENGINE_STALL_S`, `STRATA_SERVER_LOG`, `STRATA_DS4_KEEP_THINKING`, `STRATA_GLM_THINK_RESERVE`, `STRATA_API_KEY` (as `--api-key`'s default).

`STRATA_DS4_AUTO_PIN` (our v026 SERVER_ENV) is unknown to Maya, so it is ignored. Our shell environment has no STRATA_/MAYA_/DS4_ variables (checked), so only the configs and SERVER_ENV matter.

## c. Maya's server for the arms (`serve/server.py --engine strata --config <json>`)

Read by a forked reading pass and spot-checked by hand (the budget formula, `SERVER_ENV`, `apply_server_env`,
`env_in`, the effort tables, the context check, the /v1/responses call).

**Command line.** It is the same as tunearm.sh's: `.venv/bin/python <maya>/serve/server.py --engine strata --config CFG --host 127.0.0.1 --port 8085`.
- `--engine` takes mock or strata; the default is mock (:4337).
- `--host`: argv, else the config's `host`, else 127.0.0.1 (:4383).
- `--port`: argv only, default 8095. The config's `port` is ignored.
- `--tokenizer`: the config's `tokenizer` wins.
- `--fit-max-tokens` exists; there is no `--no-...`.
- Others, unused here: `--gpu`, `--open`, `--idle-unload`, `--api-key`, `--mcp-config`, `--parent-pipe`.
- The server imports its own `tools/strata_tokenizer` and `serve/*` through `sys.path` (ROOT = the tree), so any cwd works.

**Startup.**
- It test-binds the port, loads the tokenizer, and refuses to start if `<tokenizer>/vocab.json` is missing.
- It then starts the engine as `[exe, "--serve", *args]` with the config's `cwd`. The engine's environment is the server's whole environment, plus the config env, plus `lib_dirs` prepended to `LD_LIBRARY_PATH` (:1508-1526).
- It waits for READY with no timeout (`engine_ready_s` is ignored). Only then does it serve, so `/health` refuses connections until the model is loaded. tunearm's 2 s poll loop handles that.
- `STRATA_ENGINE_STALL_S` (default 90) ends an engine that is silent and shows no CPU, disk or GPU work.

**Config keys read:**
- `exe`, `args`, `cwd`, `tokenizer`, `model_name`, `log`, `lib_dirs`, `env`, `sampling`, `host`;
- `fit_max_tokens`, `thinking_budget` (default 32768), `reasoning_effort` (the default for requests that name none);
- `gpu` / `layer_split` (unused: with a `gpu` list the server would set `CUDA_DEVICE_ORDER=PCI_BUS_ID` + `CUDA_VISIBLE_DEVICES` and add `--layer-split`);
- `idle_unload_s`, `api_key`, `cors_origins`, `vision`, `backend`, `mcp_servers`.

Ignored from our Strata configs: `arch`, `port`, `engine_ready_s`, `_comment`.

The config's `env` reaches the **engine only**, except the server's own list `SERVER_ENV` (:4045-4047), which is applied to the server's `os.environ` first (`apply_server_env`):
- `STRATA_ENGINE_STALL_S`, `STRATA_REQUEST_QUIET_S`, `STRATA_DRAIN_S`, `STRATA_HTTP_BACKLOG`;
- `STRATA_MAX_BODY_MIB`, `STRATA_FAIR_SLICE_S`, `STRATA_DS4_KEEP_THINKING`, `STRATA_SERVER_LOG`;
- the responses keys.

`STRATA_GLM_THINK_RESERVE` and `MAYA_UPDATE_CHECK` are **not** on that list. They must be in the server process's own environment: tunearm's `SERVER_ENV`.

**DeepSeek detection, template, tokenizer.**
- Detection is not by `arch`: the server checks whether the tokenizer folder's `chat_template.jinja` contains "｜DSML｜" (frontend.py:55, server.py:4478-4485).
- On DeepSeek, prompts are built by the vendored `serve/ds41_encoding.py` (`encode_messages`), not jinja.
- pack_gguf.py writes `tokenizer/{vocab.json, merges.txt, token_type.json, tokenizer.json (pre deepseek3), chat_template.jinja}` from the GGUF (pack_gguf.py:347-364).
- Not verified: that ds41_encoding gives token-identical prompts to Strata's `serve/fixtures/deepseek41/chat_template.jinja`. maya-ckpt_client's `render_ok` (server prompt_tokens == our local render) checks it on every turn.

**reasoning_effort.**
- Maya, named: low → low, medium → **high**, high → high, xhigh/max → max (frontend.py:121), then 50 / 75 / 100 (ds41_encoding.py:445-479). So "medium" = **75**, and with no effort the default is high = 75.
- Maya, integer: a JSON **integer** 1..100 is used as given (`deepseek_effort_kwargs`, frontend.py:149-156). The string "62" gets a 400.
- Strata's DeepSeek template: medium = 62 (fixtures/deepseek41/chat_template.jinja:23), and integers 1..100 are taken (frontend.py `_NUMERIC_EFFORT` after `set_family("deepseek41")`).
- **Send `"reasoning_effort": 62` (integer) to every arm.** Both then write "Reasoning Effort: 62 (range 1-100, ...)". For Strata this is the same prompt as "medium".
- maya-speed3.py and maya-ckpt_client.py do this. abrun reads `wl["effort"]`, so a workload's `"effort": 62` also works.

**max_tokens and the thinking budget (W1-W3 caps 3072 / 3072 / 2048).**
- Maya, in the engine (#363):
  - The server sends `think_budget=B think_end=<id>` with each GEN (server.py:2596-2601, 797-800). The engine replaces the token after B thinking tokens with `</think>` in the same decode (ds4_main.cpp:1009-1046).
  - B = max(1, min(thinking_budget, max_tokens - max(RESERVE, max_tokens // 4))), with RESERVE = `STRATA_GLM_THINK_RESERVE`, default **1024** (server.py:2598).
  - Default: 3072 → 2048, 2048 → 1024.
  - With **RESERVE=512**: 3072 → **2304**, 2048 → **1536**.
- Strata, in the server (#984):
  - budget = max_tokens - min(max(512, max_tokens // 4), max_tokens // 2) for max_tokens ≥ 1024 (s:5090-5097, 5107-5115): 3072 → **2304**, 2048 → **1536**. Below 1024 it is max_tokens // 2 (s:5099-5106).
  - At the budget the server ends that engine pass. It emits "I have thought about this long enough; time to give my answer.\n</think>\n\n" (s:209-211), counted as output, then starts a **second engine pass** (a short prompt read).
- **Residual differences:**
  - Strata's capped answers carry ~17 inserted tokens and a second prompt read inside the decode window, a slight tok/s distortion. Maya forces one `</think>` token.
  - Both stay at or under max_tokens; finish is length / stop / tool_calls on both.
  - Small caps differ even with RESERVE=512:
    - the 384-token warm-up thinks 1 token on Maya vs 192 on Strata;
    - ckpt_client's 512-cap follow-ups think 1 token on Maya vs 256 on Strata;
    - its 4096 caps are equal (3072).
- Maya ignores a request's `reasoning_budget_tokens` (Strata honours it, s:4155).
- Maya has no `answer_room` switch.

**Sampling.**
- The config `sampling` block is validated at start; top_k must be 1..64 (:4156-4213).
- Request values win over it, as on Strata (:2533-2536).
- Sent to the engine (:795-855): temperature, top_p (if < 1), top_k (0 or > 64 becomes 64), min_p, seed, and the repetition / frequency / presence penalties with penalty_last_n.
- Our 1.0 / 0.95 / 20 / 0.05 pass through unchanged.

**Streaming.**
- `stream_options` is not read by either server.
- Maya always sends `usage` (prompt_tokens, completion_tokens, total_tokens, `prompt_tokens_details.cached_tokens`) plus a llama.cpp-style `timings` object, in the chunk with `finish_reason` (:2764-2782, 2969-2981).
- Deltas use `reasoning_content`, `content` and `tool_calls`. abrun and ckpt_client read all three.
- Thinking off: honoured from `chat_template_kwargs.enable_thinking=false` (frontend.py:447-449). `thinking: {"type": "disabled"}` is read only on /v1/messages. abrun sends both, so this is harmless.
- **Context:** Maya rejects prompt + max_tokens > context - 8 with a 400 unless `fit_max_tokens` (:2335-2346); Strata clamps. Our configs set `"fit_max_tokens": true`. No measured request comes near 32K anyway (P20K ~20K + 8, W3 ~23.5K + 2048).

**Tools in Jan's format.**
- The OpenAI `tools` list goes through ds41_encoding (frontend.py:436). The model's DSML calls are parsed back (frontend.py:684-727, server.py:2538) and stream as `tool_calls` deltas, with finish `tool_calls`.
- Maya's open bug #482 (a call swallowed after a partial closing tag) is not mentioned in the code. The parser holds a partial `<｜DSML｜` until it is complete (:710-719). Not verified whether #482 reproduces.
- `/v1/responses` exists (:3677). Its work path builds the messages with `openai_to_messages(sampling)` **without** `deepseek=` (:3858; the chat path passes it, :2352 / :3887). DeepSeek tool history then takes the generic path, and an integer effort gets a 400. Not verified at runtime.
- `/health` returns 200 (:3555) once the engine is up.

**Engine log lines our harness reads.**
- **Per-request line:** the text is identical in both engines: `maya ds4 serve: prompt N tokens = R reused + X read in Z ms (T tok/s), G generated in M ms (U tok/s); CPU lane P% of the experts` (Maya ds4_main :1063-1070, Strata :920-926).
  - **The LINE regexes in ckpt_client.py / cont_client.py / conv.py need no change.**
  - Maya's "CPU lane %" is per request; Strata's is cumulative. We don't parse it.
  - Maya prints one line a request. Strata prints two when its budget fires (ckpt_client's `budget_hit` is then never true on Maya).
- **Stopped while reading:** neither DeepSeek engine prints the "+ N of M read" form that Strata's server regex allows (s:466-471, #471; another engine's). The DeepSeek engines print "... stopped while reading ..." (Maya :910, Strata :818).
- **Slot lines** (ckpt_client SLOTLINE "ds4 slots|taking a conversation back|going back to token|kept conversation", slot_client's "took back .* from (RAM|the folder)", conv.py's "slot|restor|checkpoint|pin"): the same engine texts (Maya :419/650/656/669 = Strata :367/551/557/570).
  - Maya's **server also copies its own `[maya] ...` lines into the same log** unless `STRATA_SERVER_LOG=0` (:4372-4378), and they repeat slot notes, so SLOTLINE and conv.py would double-count. The M1/M2 configs set it to 0, which needs no regex change. The server's lines then go to tunearm's `server.out` only.
- **summ.py's start-line regexes need no change.**
  - `CUDA(\d) layers \[...\][^:]*: weights ... (\d+) of (\d+) in VRAM...` matches Maya's line (model.cu:5876-5880; its extra " + blocks ..." before the colon falls into `[^:]*`).
  - `(\d+) routed experts on the CPU lane \(([\d.]+) GB` matches (model.cu:5889-5899, the same three forms as Strata's).
- **tune.py's `EXPERTS_LINE`** (`experts per word: (\d+)`): Maya prints no such line, so `tune.run()` would write a GUARD ("failed: experts per word None") for any non-v024 engine. For Maya check `grep -x "num_experts_per_tok 6" <maya pack>/ds4.txt` instead (pack_gguf writes `key value` lines from the GGUF's `expert_used_count`; our Strata pack's ds4.txt has exactly that line).
- **Engine process name:** `maya-ds4`. tunearm's `pgrep -x strata-dsv41` and speed3's `/proc/*/exe` basename must look for it (done in the maya- copies).
- **Log path:** tunearm's fixed `LOGF` has to be the Maya config's `log` (done in maya-tunearm.sh). The engine's stderr is appended there (server.py:4434, StrataEngine(log=...)).
- **Not verified:** Maya's exact startup lines beyond these two regexes. Grep `placement.txt` after the first start.

**Slot keep and pin on Maya.**
- The engine reads `STRATA_DS4_SLOT_KEEP` (unset = off; `MAYA_DS4_SLOT_KEEP` is the same).
- Maya's server sets no default for it (Strata v0.2.4.2+: on) and has no auto pin (our `STRATA_DS4_AUTO_PIN=0` is ignored).
- The engine pins the anchor on every new run of prompts regardless (ds4_main.cpp:927), so run maya-ckpt_client with SLOTS=1 semantics (see its header).
- `STRATA_DS4_KEEP_THINKING` defaults to 0: earlier turns' reasoning is dropped, as in Strata's template.

## d. Python packages: Maya's server on the DeepSeek path vs our venv

How this was checked:
- I listed every module `serve/*.py`, `tools/strata_tokenizer.py`, `tools/maya_names.py` and `tools/gguf_reader.py` (the last two are imported by the first group) import at v1.1.28, and kept the ones not in the standard library.
- Each was imported with our venv's python (`.venv/bin/python -I -c "import X"`, Python 3.12.3, run from the scratch dir). That runs nothing of Maya's.

| Package | Imported at (v1.1.28) | When | Our venv |
|---|---|---|---|
| jinja2 (+ jinja2.sandbox), MarkupSafe | frontend.py:29-30 | startup | 3.1.6 / 3.0.3 ok |
| regex | tools/strata_tokenizer.py:22 | startup | 2026.9.10 ok |
| psutil | server.py:103, telemetry.py:740 | lazy, optional | 7.2.2 ok |
| Pillow, numpy | ds4_vision.py:102-103 | lazy, pictures only (unused with `--vision off`) | 12.3.0 / 2.5.3 ok |
| **jsonschema** | response_schema.py:67-68 | lazy, JSON-schema structured output only | **missing** |
| attrs, referencing, rpds-py, jsonschema-specifications | jsonschema's dependencies | the same | **missing** |
| gguf_reader, maya_names, strata_tokenizer | Maya's own `tools/`, stdlib only | startup | in the tree |

- **To pre-fetch as wheels before the isolated runs:** `jsonschema>=4.18,<5`, `attrs`, `referencing`, `rpds-py` (cp312 manylinux x86_64) and `jsonschema-specifications`.
  - Not needed for the measured arms. Without them, only a request with a JSON schema gets a 400; plain chat and tools work.
  - Needed if `/v1/responses` structured output is part of the "switch" checks.
- Maya's `setup.py`/`maya.py` also pull pyyaml, tqdm, requests, cmake and ninja. None is imported by `serve/`; they are not used.
- `tools/ds4/pack_gguf.py` is stdlib only (catch-up; not rechecked here).

## e. Harness changes for the Maya arms

The existing harness files were not edited. The new copies are in work/ds41/maya/. All are unrun; the shell scripts passed `bash -n` and the Python files `ast.parse`.

1. **`maya-tunearm.sh` (from tune/tunearm.sh).**
   - Changes:
     - The engine's process name comes from `ENGINE_NAME` (default `maya-ds4`). It is used for `eng_pids` (RSS, VmSwap, the kills). The script refuses to start while any `strata-dsv41` or `maya-ds4` runs.
     - `LOGF` = the config's `log`.
     - `DS_SERVER` default = `$MAYA_ROOT/serve/server.py` (`MAYA_ROOT` default `ext/maya-v1.1.28-src`, a proposal).
     - `SERVER_ENV` default = `STRATA_GLM_THINK_RESERVE=512 MAYA_UPDATE_CHECK=0`.
     - The default client is `maya-speed3.py`.
     - The summary grep also keeps "read ahead | read in place | thinking budget | prompt slabs".
   - The rest is unchanged: cool-down, dropcache, the swap and memory guards, the 5080 free-VRAM guard, kcheck, `/health` + port-owner readiness, summ.py, and the nvme flag.
   - **If tune.py drives it,** the `SERVER_ENV` it passes replaces the default, so it must include `STRATA_GLM_THINK_RESERVE=512`. (tune.py's v026 entry passes `STRATA_DS4_AUTO_PIN=0`, which is useless to Maya.)
2. **`maya-scorearm.sh` (from tune/scorearm.sh).**
   - The process name is `maya-ds4`.
   - Strata-only flags are dropped from the config's args if present (`--ssd-cache`, `--ssd-policy`, `--experts`, `--dspark-block`, `--pack-info`, `--version`).
   - The engine runs under `unshare -rn` unless `ISOLATE=0`.
   - Otherwise it is the same: `--dspark none --vision off --threads off --window 128 --max-context 16384 --score ... --score-out OUT/score.tsv`, the same guards, and the same `run.txt`.
   - Its `decode:` mode works, but Maya ignores `DS4_NO_EOS` / `DS4_TOKLOG`.
3. **`maya-score.py`.**
   - It runs skipcheck's 8 x (12,000 + 256) segments, one engine run each, for any config file (Maya via maya-scorearm.sh, Strata via scorearm.sh), and merges them as `skipcheck.score()` does.
   - `compare` calls `skipcheck.compare`.
   - Proposed quality checks, using skipcheck's "vs" rule with rounding references R1 (`--prefill-chunk 4096`) and R2 (`--reserve-mib 2600`) on the base side:
     - M1 vs S, the engine difference;
     - M2 vs M1 with M1's R1/R2, Maya's rounding-level defaults including the split skip.
4. **`maya-speed3.py`.** speed3.py with `ENGINE_NAME` (the `/proc/<pid>/io` target) and an integer `reasoning_effort` 62 on thinking-on requests.
   - **Use it for S too** (`CLIENT='ENGINE_NAME=strata-dsv41 .venv/bin/python work/ds41/maya/maya-speed3.py $URL $OUT 3 3'` with tune/tunearm.sh), so all arms send identical bodies.
5. **`maya-ckpt_client.py`.**
   - It is ckpt_client.py with integer effort 62, applied to the local render as well. It enables the Strata frontend's integer efforts with `use_family("deepseek41")`, because ckpt_client's local Service never calls `set_family`.
   - For Maya: `ENGINE_LOG` = the config's `log`, `SLOTS` = 1 (Maya always pins the anchor), and `budget_hit` never fires.
6. **`maya-netns.sh CMD...`.**
   - It runs `unshare -rn`, then `ip link set lo up`, then CMD. Wrap one whole arm: `bash work/ds41/maya/maya-netns.sh bash work/ds41/maya/maya-tunearm.sh M1-p1 work/ds41/maya/maya-M1.json`.
   - Keep tune.py-level steps (notify-send, `systemctl --user` in `kernel_event`) outside the namespace.
7. **summ.py:**
   - No parsing change needed.
   - For a fair SSD comparison, add the drive counter per generated token:
     - P4K/P20K: `device_read_gb` is already recorded per prompt.
     - W1-W3: add `device_read_gb / completion_tokens` beside `disk_gb_per_token`.
   - Strata's `disk_gb_per_token` (O_DIRECT store reads) and Maya's (page-cache faults and readahead) count different things.
8. **tune.py (not edited).** If the Maya arms go through `run()`:
   - `mkcfg()` cannot build them: BASE carries `--ssd-cache`, `--dspark auto`, `STRATA_DS4_PROMPT_SKIP=0` and `DS4_STORE_FLOOR_GB`. Pass the maya-M*.json files as they are.
   - The `EXPERTS_LINE` check must be skipped for Maya; otherwise every arm gets a "failed: experts per word None" GUARD. Replace it with the `ds4.txt` check.
   - `ENGINES["maya"]` would need `server` = Maya's server.py and `server_env` = `STRATA_GLM_THINK_RESERVE=512 MAYA_UPDATE_CHECK=0`.
   - The simpler route is calling maya-tunearm.sh directly from a small A/B/A driver.
9. **The S arm for the engine comparison:**
   - Use `tune.mkcfg` with the round's final config plus `{"--dspark": "none"}` (and drop `STRATA_DS4_DSPARK_CUM`), on the winning engine. Keep its `--ssd-cache`: that is Strata as it ships.
   - Use maya-speed3.py as the client.
   - Optional for the M1-vs-S arithmetic comparison only: `CUBLAS_WORKSPACE_CONFIG=:4096:8` in S's env.
10. **Pre-run checks (one gap, a few minutes, after the build):**
    - `bash maya-netns.sh nvidia-smi` (CUDA inside the namespace);
    - `bash maya-netns.sh bash bringup/lib/kcheck.sh netns-test` (the watcher check from inside);
    - `bash maya-netns.sh curl -m 2 http://example.com` (must fail);
    - `grep -x "num_experts_per_tok 6" <maya pack>/ds4.txt`;
    - no `work/ds41/maya/maya-M1.shared-settings.json` / `maya-M2.shared-settings.json` exists (server.py:4515-4518 loads `<config minus .json>.shared-settings.json`, "the Chat settings shared with other apps", at start; written only by the dashboard);
    - the new pack's `model_dir` points at the same GGUF folder dropcache.py drops.
11. **Memory and swap:**
    - Every Maya start reads ahead up to MemAvailable - 8 GB (about 70 GB here) of CPU-lane experts into the page cache: "N CPU-lane experts read ahead (X GB) in Y s". Strata's store run reads none (s:2657).
    - That is about 15-20 s of SSD at start, after dropcache. It may push idle pages to swap; the guard fails the run at +1 GB of system swap.
    - `DS4_WARM_CAP_GB=<n>` caps it. One parity option is n = S's store size (70-74), so both start with the same RAM share of hot experts.
    - Keep `--mmap-experts on` (never the copy). `DS4_COPY_GB` stays unset.
