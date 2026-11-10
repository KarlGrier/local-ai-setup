# v0.1.41 → v0.1.42: every default and setup change (Round 19, Part B step 2)

Source: `git diff v0.1.41 v0.1.42` (61b3fb5d; 235 commits, 219 without merges; v0.1.41.1 was never released, its fixes are
in v0.1.42), the `Options` struct and the flag parser (generate.cpp), every `STRATA_*` name read in src / include / serve /
tools / setup (458 → 494: 36 new, none removed), serve/server.py. "Here" = this PC: CUDA, RTX 5080 (sm_120) + RTX 4060 Ti
(sm_89) as the helper cache (`--expert-cache-device1 3300`, no layer split, no batch slots, no `--peer-device`), Ryzen 9
9950X3D, Linux, the IQ3_S file with every expert in the RAM arena, your config (C\*16.1's flags: `--pcie-frac 0` explicit,
`STRATA_PREFILL_CPU_SHARE=0`, `STRATA_STAGE_PIN` unset = off).

## Engine options (flags)

No existing flag changed its default. New flags, all off unless given: `--adapt-min-gain` (default 1.5 = the constant it
replaces), `--conversation-cache-min-tokens` (upstream's conversation cache only), `--memory-limit-mib` (a cgroup cap the
engine cannot see), `--aux-cpus` (off), `--batch-mtp` and the batch-window adaptive tier (`--batch` only), the data-parallel
replicas (server option, opt-in).

## Defaults that changed or switches that are ON by default

| change | default | on here? | what it does | off |
|---|---|---|---|---|
| **route tail skip** (b4e3407b, 65268d99) | `STRATA_ROUTE_TAIL_SKIP` unset = **7 on CUDA serve** when not every expert is in VRAM, no `--batch`, no `--peer-device` | **one-GPU configs: yes. Your two-card config: the start-up rule does not test the helper cache, but the dispatch skips nothing while a helper cache is attached** (`d.remote_count == 0` is required, expert_source.cpp L3598) — checked on the served build in step 2 (start-up line, request log, greedy outputs unset vs =0) | a missed expert that every token of a verify window routes at rank ≥ 7 is neither copied nor computed (**changes the output**, upstream: KL ~0.003–0.006; +10–20 % decode on 12–16 GB cards) | `=0` (your rule for every one-GPU config) |
| **PCIe share refined from the CPU pool's speed** (aa7b0cb1) | CUDA, one GPU stage, no `--pcie-frac`: the probed share is re-tuned in the first decode windows | **no** — your configs pass `--pcie-frac 0` (kept, your rule) | – | `STRATA_PCIE_FRAC_DEFAULT=old` or an explicit `--pcie-frac` |
| CPU prompt-read share: not armed when the GPU cache holds every expert (eaaa237e, #1595); a pinned buffer that cannot be had ends the share instead of failing the request (04dbe561) | on where the share is on | no (`STRATA_PREFILL_CPU_SHARE=0` in your config); step 3 tests a fixed 0.4 | – | – |
| PLE row reader: when the default direct reads measure slow at start (cold random-row probe), use mmap (30017336, #1425 #1549 #1629) | on when `--ple-io` is not given | probe runs here (no `--ple-io` in your config); on this NVMe it keeps direct (start-up line checked in step 2) | – | `--ple-io direct` (then only a warning) / `STRATA_PLE_PROBE` |
| lend regions on a layer split: the RAM copy keeps each stage's lend region (aea9dc3e, 51d55a9a, d3fb3e6f) | on | no (no layer split; the one-GPU **budget** branch still turns lend off — #1683) | – | – |
| stage-buffer fences for the lent-slot refills (#1237, 56354964, f71c5307) | on | only with `STRATA_STAGE_PIN=1` (off here) | – | – |
| verify window: the service returns before any CUDA call while nothing has rung (6b392641) | on | yes, timing only | – | – |
| spec windows near the context's end stay inside it (e85567b6) | on | only within 4 tokens of 131,072 | – | – |
| lookup chains: a stale full chain is re-probed when a shorter chain pays (71eaee17, #1252) | on | n-gram lookup drafts only; stock v0.1.42's exact7 = v0.1.41's (Round 18) | – | – |
| Q8_0 dequant coalesced (e910e410) | on | no (Q8_0 files only; the #1682 stand-in in Part A) | – | – |
| request logit biases applied in CUDA sampling (dcc6f756) | on | **yes** when a request sends `logit_bias` (they were ignored before); our exact sampling's verify head takes the request's sampler parameters, so the bias reaches it (probed in step 6) | – | – |
| AVX1 / older-CPU kernels, gfx906 / gfx12 / Arc / SYCL / HIP paths, Windows unbuffered RAM copy (`STRATA_STARTUP_UNBUFFERED`) | – | no (other hardware / OS) | – | – |

## New, opt-in (off here)

`STRATA_PREFILL_HELPER_SOURCE` (the prompt path takes blobs a helper cache holds from that cache: **step 4 tests it**),
`STRATA_ROUTE_PRIOR` (cache-conditioned routing, changes the output), `STRATA_ROUTE_RESIDENT_MTP` (changes the output),
`STRATA_LOOKAHEAD_STATS` (measurement), `STRATA_VERIFY_COMPLEMENT` (a check), `STRATA_SPLIT_MTP_BATCH`,
`STRATA_SPLIT_NEAR_TIE_PCT`, `STRATA_BATCH_YIELD_CHUNKS`, `STRATA_PIPELINE_SPEC_DEPTH` (debug), `STRATA_PF_OCC_W` (experiment
knob), `STRATA_AUX_CPUS` / `STRATA_AUX_STAGER`, `STRATA_MEMORY_LIMIT_MIB`, `STRATA_PF_XMX*` / `STRATA_GFX906_*` /
`STRATA_GFX12_DEFAULTS` / `STRATA_NO_IQ128` / `STRATA_NO_Q8K_AVX1` (other hardware), build and setup names
(`STRATA_ATOMIC_WAIT`, `STRATA_NAT_W12`, `STRATA_NAT_WMMA`, `STRATA_CPUINFO`, `STRATA_EXE`, `STRATA_EXTRA_ARGS`, `STRATA_REPO`,
`STRATA_VCVARS`, `STRATA_SYCL_VERSION`, `STRATA_REPLICA_START`).

## Server (serve/server.py) — what can reach your Open WebUI → 8080 path

| change | default | reaches your server? |
|---|---|---|
| **#1624 (1a62f6df): a tool set that comes back in another order keeps the order first seen**, so the prompt prefix and its cache survive | on | **yes** — a client that reorders its tool list no longer forces a full re-read of the chat |
| **#984 (3d247dd4, bce19db4): a thinking budget is capped at max_tokens less an answer reserve**, so the reply is not cut off while still thinking; the progress line shows the budget | on | **yes** — requests with a thinking budget and a max_tokens |
| **logit bias (dcc6f756)**: `logit_bias` in a request is applied (it was accepted and ignored on CUDA) | on | **yes**, when a client sends it |
| #537 (0d613031): a `</think>` quoted inside the reasoning stays reasoning | on | yes (rare) |
| #1753 (253e09f1): the reasoning loop check also sees a loop written as one long word | on | yes |
| #1619 / #1666 (875d6a92, 14b9dd2e): keep-alives while a request waits for the single turn and while a tool call's held-back argument is generated; a cancelled waiter gives up its place | on | yes (long tool arguments, queued requests) |
| #1620 (8824e217): a request cancelled between two prompt windows keeps the conversation it restored as the live one | on | yes (upstream's path; our chat cache is beside it) |
| #1527 (32a2439d), #1603 (caba015b), #1705 (52f548f4), 2bf1d07c: the request that hit the READY timeout is answered; a parallel request is always running or queued; the watchdog line is found in a long log; context-overflow errors are recognisable | on | yes, robustness |
| HTTP body framing: incomplete chunked bodies refused (d467b3d2, 8c6b1cc5) | on | yes, robustness |
| sampling fields: a wrong type is a 400 that names it (1f6958c1), a numeric string is read (acee40a5); content parts the server does not read are left out with a debug line (5804094b, then 40bdd86d) | on | yes (Open WebUI sends well-formed requests) |
| `repeat_penalty` / `repeat_last_n` accepted under llama.cpp's names (70ac6dd4, #1819) | on | only if a client sends them |
| `reasoning_effort` key in the run config (a6ae2475) | – | no (your effort comes from the shared chat settings) |
| `GET /metrics/prometheus` (95452866), the Monitor's prefill rate, favicon, sparkline scale, compacted stream fragments | on | harmless (127.0.0.1 only) |
| card order within 5 % keeps the config's order (184012ca, #1760); data-parallel replicas (opt-in); `serve/cpu_affinity.py` (a tool); `prevent_sleep` (Windows) | – | no |
