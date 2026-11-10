# v0.1.40.2 → v0.1.41: every default and setup change (Round 16 step 1)

Source: `git diff v0.1.40.2 v0.1.41` (151 commits, v0.1.40.3 and v0.1.40.4 included), the `Options` struct and the flag
parser (generate.cpp), every `STRATA_*` name read in src / include / serve / tools / setup (423 → 458: 35 new, none
removed), serve/server.py, serve/frontend.py, serve/web/app.js. "Here" = this PC: CUDA, RTX 5080 (sm_120) + RTX 4060 Ti
(sm_89) as the helper cache (`--expert-cache-device1 3300`, no layer split, no batch slots), Ryzen 9 9950X3D, Linux, the
IQ3_S file, your config (configs/Cstar15.json).

**The release alone with your flags (run r16):** exact7 3/7 identical to v0.1.40.2's stock (the three long prompts equal,
the four short ones differ) and it does **not** repeat itself (two identical runs: 3/7). Both come from the CPU prompt-read
share below. With `STRATA_PREFILL_CPU_SHARE=0` (run r16z): see the gate section of REPORT.md "Round 16".

## Engine options

No existing default changed (the `Options` struct differs by two new fields: `--batch-groups auto` for a layer split with
`--batch`, not used here).

## Defaults that changed or switches that are ON by default

| change | default | on here? | what it does | off |
|---|---|---|---|---|
| **CPU prompt-read share** (162ce64e, f2a3b946, 92bce20e) | `STRATA_PREFILL_CPU_SHARE` unset = `auto` with `STRATA_PREFILL_CPU_SHARE_MAX` = 1024, on CUDA without a layer split, batch slots or HIP | **yes** — your two-card config counts as one GPU here (the rule tests `multi_gpu` = a layer split, not the helper cache); the engine logs "prefill: the CPU share is ON by default for prompt chunks below 1024 tokens" | for a prompt chunk below 1,024 tokens the idle CPU pool computes some of the experts the 5080 would stream; `auto` times the layers with and without the share and keeps sharing only while that is faster (so which layers share depends on timing: outputs differ at rounding level and do not repeat run to run; upstream: mean KL ~0.004) | `=0` (= the 0.1.40.3 bytes) — **step 1 measures it** |
| stage buffers pinned (`STRATA_STAGE_PIN`, 475912c6 / d2e3f1c9) | was on by default on 10-07, **opt-in in v0.1.41** (fb58e0db: IQ3_S decode corrupted after a 4,096-token prompt in upstream's release gate) | no (`STAGE_PIN_DEFAULT 0`); used only by the file tier (experts read from the GGUF), not by IQ3_S here | – | kept off (your rule) |
| stager batched unbuffered reads (`STRATA_STAGER_BATCH`, 0b030b96) | 8 blobs per read for file-backed blobs | only with a file tier (the Q4 check if any expert came from the SSD) | the prompt path's stager reads runs of neighbouring blobs in one direct read | `=1` |
| close the experts.bin view once reads are unbuffered (`STRATA_KEEP_MAPPING`, 0b030b96) | closed | only with unbuffered reads | – | `=1` keeps it |
| stager RAM profile when the GGUF experts are in the page cache (#1353, `STRATA_STAGER_SSD`) | auto (≥ 90 % of a sample resident → RAM profile) | only with a file tier | – | `=1 / =0` force |
| watchdog file-tier tolerance (#1407, `STRATA_WATCHDOG_IO_S`) | 10 × the watchdog limit while the OS is still reading the file tier | only with a file tier | the engine's #29 watchdog waits while reads go on | `=0` |
| HC norm products kept in scratch (ccd657a2) | always | upstream's split norm (STRATA_HC_SPLIT path); our B.1 read replaces that read when on | same roundings (bitwise, by upstream's note) | – |
| q8_1 emit sites clamped (#606 7a0e3023, #1448 e372d4ff) | always | the QFUSE gate-reduce tail, the batched GDN verify store, the S26 swiglu path: a block whose amax overflows stores a finite scale instead of inf/NaN (`!` / id-0 degeneration); finite blocks below 8.3M bit for bit as before | – | – |
| tokenizer piece cache (f346dc6b, 4dc544ed) | always | server-side prompt encoding: repeated pre-tokenizer pieces remembered (a resent 89K-token prompt 0.32 → 0.07 s upstream; same ids) — beside our #567 prompt encoder | – | `PIECE_CACHE_MAX = 0` (code) |
| MMVQ_IL (F4) rows table per architecture (2d6c6ae5) | per-arch hook; **sm_120 and sm_89 keep the shared table = v0.1.40.2's** | unchanged here | – | `STRATA_MMVQ_IL_ROWS` overrides |
| MMVQ_IL opt-in (f7610d2c) and its revert (668072aa), both 10-07 | **net: on, as in v0.1.40.2** | unchanged | – | `STRATA_MMVQ_IL=0` |
| drafter's native router call guarded (6c0fca38, 512 experts / k = 10) | always | this model is 512 / 10: no change | – | – |
| prompt buffers share the embedding storage (199fd1d5, #1454) | the planner keeps counting the shared bytes (`STRATA_EMB_REUSE_ACCOUNT` unset): the auto chunk and the borrowed slots stay 0.1.40.3's | no change of chunk here | – | `=1` uses the saved bytes (other rounding) |
| peer prompt share without P2P (`STRATA_PF_PEER_*`, `STRATA_PEER_NO_P2P`) | on where it applies | only with `--peer-device` (not used here) | – | – |
| Volta / Pascal / AMD / Intel paths (sm_70 table opt-in, #1469 Pascal decode, SYCL, HIP tables) | – | no (other hardware) | – | – |

## New, opt-in (off here)

`STRATA_FS_SLOTS` (+ `_AHEAD`, `_BUDGET`, `_ADMIT`, `_DEPTH`, `_VERIFY`: the Foresight swap space — per-layer VRAM slots refilled
with recently missed experts; off unless `STRATA_FS_SLOTS` > 0), `STRATA_GDN_CHUNKED` (the prompt's DeltaNet recurrence in
32-token chunks, "other bits"), `STRATA_ROUTE_RESIDENT` (+ `_RANKS`: residency-biased routing, **changes the output** — not
lossless), `STRATA_EMB_REUSE_ACCOUNT`, `STRATA_SM70_TABLE`, `STRATA_STAGE_PIN=1`, debug hooks (`STRATA_DBG_FEAT`,
`_FEAT_LAYERS`, `_ROUTE_OVERRIDE`, `_CPU_GATE`, `STRATA_DUMP_FIRST_LOGITS` per request), test knobs (`STRATA_PEER_NO_P2P`,
`STRATA_VERIFY_NO_HOST`, `STRATA_EXP_LAYOUTS`, `STRATA_GR_FAST_BUILD`, `STRATA_SYCL_BIN`).

## Server (serve/server.py, frontend.py, web app) — what can reach your Open WebUI → 8080 path

| change | default | reaches your server? |
|---|---|---|
| **#1317 part 2 (d7932123, 5aee72b1): a frozen engine is ended after 90 s** with no output, no CPU time and no disk I/O (psutil, which the workspace venv has), unless its GPU is busy; the next request starts it again | on (`STRATA_ENGINE_STALL_S`, 0 = off) | **yes** — a hung engine (driver stall, deadlock) no longer holds requests until engine_silence_s |
| **malformed request bodies (039f9e90): a wrongly shaped body gets a 400 (traceback logged), a bad Content-Length a 400, a body over 256 MiB a 413 before it is read** | on (`STRATA_MAX_BODY_MIB`) | **yes** — robustness at the HTTP layer (Open WebUI sends well-formed bodies; a 10 TB Content-Length used to be read until the client gave up) |
| **a tool call written `<function= NAME>` is the call NAME (dd667967)** | on | **yes** — the model's tool calls (your web search; Open WebUI tools) with a space after `=` were not recognised |
| listen backlog 256 (ca001df5, `STRATA_HTTP_BACKLOG`) | on | yes, harmless (30–40 simultaneous clients got resets) |
| #1344 several API keys (comma list or config list) | – | no (no key set) |
| a request with no free slot gives the control lines back (d9621d1e) | on | no — parallel slots only (`parallel: 2` deadlock); your server runs one slot |
| upstream's conversation cache evicts to pass the RAM gate (940011da) | on | no — your server uses our `--chat-cache`, not upstream's `--conversation-cache-mib` |
| card order for an auto layer split (#1352, be8db787, 786b3ca0) | on | no — only for configs with a `"gpu"` list and an auto layer split (yours sets CUDA_VISIBLE_DEVICES with a helper cache). Upstream's own test `test_vision_device` fails on this PC because of it (it expects "0,1" for the two cards; the 5080 is faster so it goes last) |
| vision section without `--vision` (#1322) | on | no |
| web app: an assistant turn with no answer text is sent back in the history (#1392, c13ddd62) | on | the built-in chat page only (merged beside our web-app rows), not Open WebUI |
