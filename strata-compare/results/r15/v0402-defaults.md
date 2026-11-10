# v0.1.40.1 → v0.1.40.2: every default and setup change (Round 15 step 8)

Source: `git diff v0.1.40.1 v0.1.40.2` (242 commits), the `Options` struct and the flag parser (generate.cpp), every
`STRATA_*` name read in src / include / serve / tools (35 new, none removed), serve/server.py, setup. "Here" = this PC:
CUDA, RTX 5080 (sm_120) + RTX 4060 Ti (sm_89), Ryzen 9 9950X3D (AVX2 / AVX-512), Linux, the IQ3_S file, your config
(configs/Cstar14.json). **The release alone with your flags computes what v0.1.40.1 computed: exact7 7/7 identical
(rb-r15-stock = rb-r14-stock), so none of the default changes below changes an output here.**

## Engine options

No existing default changed. New: `--gpu LIST` (selects the visible GPUs without environment variables; we keep
CUDA_VISIBLE_DEVICES) and `--pool-tasks N` (CPU expert tasks per batched phase; 0 = the old policy). Changed semantics,
opt-in: `--expert-cache-per-layer` on a native pack sizes each layer's slots to its own blob (we do not use it).

## New STRATA_* switches that are ON by default here

| switch | what it does when on | how to turn it off | overlaps ours |
|---|---|---|---|
| `STRATA_MMVQ_IL` | **F4** (fork Eddoursul 738e166 + b67a291): 2–4-token dense projections read an interleaved q8_1 copy — IQ4_XS / Q4_K / Q5_K / Q6_K, bitwise native_mmvq's output | `=0` | **our B.3 (same code, same switch name) → B.3 not ported**; measured on vs off in step 8 |
| (#851) AVX2 Q8_K quantizer | the CPU expert pool quantizes the FFN input to Q8_K with AVX2 (native i-quant layers) | `STRATA_NO_Q8K_AVX2` set | **our A.2** (the doorbell writes the Q8_K rows, the pool skips quantizing): A/B in step 8 |
| (d6850f31) IQ3_S / IQ2_S AVX2 decode | the CPU's IQ3_S / IQ2_S unpacking without per-index shift / mask / or | – (always) | – |
| `STRATA_STAGER_SLEEP` | the prompt Stager's waits sleep instead of yield-spinning (Linux default) | `=0` | – |
| `STRATA_PIN_GUARD` | #1250: before page-locking the RAM copy, give back the model files' cached pages; take pages in 1 GiB steps while the available RAM stays above the reserve; page-lock what fits, keep the rest pageable with a warning | `=0` | – |
| `STRATA_PREFILL_STREAM_AHEAD` | prefill streams the next expert group ahead | `=0` | – |
| `STRATA_LAYER_SPLIT_PROBE` | --layer-split auto skips a split whose prompt path cannot start | `=0` | – (no split here) |
| `STRATA_PIPELINE_ADAPT_ASYNC` | with --pipeline-windows (opt-in) | `=0` | – |
| unbuffered-read rule (#1194) | with a RAM budget: unbuffered expert reads only when the file cache cannot hold a 20th of what it would read (>= 1.5 GiB beside the 4 GiB headroom) | `STRATA_UNBUFFERED_LOAD=0 / 1` forces | – (step 4 on the stand-ins) |
| (#789) prefill | routed expert uploads overlap the shared expert | – | – |
| (#1252) DraftPolicy | a lookup window size is measured again when its cost is stale | – | – |

## New, opt-in (off here)

`STRATA_SPEC_PROB` (probabilistic draft acceptance for sampled MTP drafts — rejection sampling with the drafter's q; its
`--spec-min-p` gates on the drawn draft's probability, `STRATA_SPEC_PROB_GATE=top` on q's top; `STRATA_SPEC_PROB_DT`,
`STRATA_SPEC_MIN_TEMP`) — **overlaps our exact sampling: A/B in step 8**; `STRATA_SPEC_GUMBEL` (Gumbel-max coupled
drafts); `STRATA_DF_BRANCH` (mixer graph branches — **overlaps our side mixer: A/B in step 8**), `STRATA_DF_PDL` (sm_90+),
`STRATA_DF_PLE`, `STRATA_DF_QB_Q4`; `STRATA_IO_PREFETCH` (+ `_DEPTH`, `IO_PF_THREADS`, `IO_PF_STAGE`, `IO_PF_AHEAD`) and
`STRATA_IO_STATS` (the file tier's I/O path and counters — step 4); `STRATA_PREFILL_CPU_SHARE`; `STRATA_KV_GROW_HOLD`;
`STRATA_SELECT_SIMT` (below sm_80); debug / test switches (`STRATA_DBG_GDN`, `STRATA_DBG_FORCE_SLOW_LAYER`,
`STRATA_SPEC_DEPTH`, `STRATA_LAYER_SPLIT_GATE`); server timeouts (`STRATA_ENGINE_READY_S`, `STRATA_VISION_READY_S`,
`STRATA_VISION_ENCODE_S`); setup (`STRATA_SKIP_SHA256`, `STRATA_SOURCE`). Build option: `-DSTRATA_Q6K_EXPERTS=ON`.

## Server (serve/server.py) — what can reach your Open WebUI → 8080 path

| change | default | reaches your server? |
|---|---|---|
| #1182 the cancel event is polled every 0.5 s while the engine is quiet: a client that leaves during a long prompt read stops it | on | **yes** — a Stop / closed tab during a long paste (Round 14's Stop-at-120K gate covers the engine side) |
| #1059 a request the engine refuses with ERR is answered at once, not after a 300 s wait for DONE | on | **yes** — e.g. a paste beyond the context |
| #1317 the reads of the engine's READY line (and the image encoder's pipe) time out; STRATA_ENGINE_READY_S overrides | on | **yes** — a hung engine start no longer hangs the server |
| ec7f6a02 a restart clears max_context before the new engine is visible; close() does not join a thread a restart never started | on | yes — the crash-restart path (Round 13's crash test) |
| #351 the endpoints keep reporting the context during an engine restart | on | yes (Open WebUI polls /v1/models) |
| #615 usage and timings across reasoning continuations sum every pass | on | reporting only |
| #893 / #894 chunked request bodies decoded on every route, with a size cap | on | only for chunked clients (Open WebUI sends Content-Length) |
| a782177e GET /metrics in the Prometheus text format (vLLM's names) | only when asked (Accept: text/plain / openmetrics, or ?format=prometheus) | no — our uptime monitor asks without an Accept header and keeps getting the JSON (checked: serve/prometheus.py wants_prometheus) |
| #1031 a POST /settings without "defaults" is a 400 (no longer clears every shared setting); #1035 thinking budget shareable | on | yes if anything posts /settings (our web app does) |
| #956 API keys with spaces / non-ASCII; a blank key refused at start; #569 empty api_key warns | on | no api_key in your config |
| #562 /slots n_prompt_tokens; #1004 /props total_slots; #986 / #987 /props chat_template_caps | on | informational |
| #1175 a tool with non-object parameters → 400; #782 /v1/responses JSON format with tools; #1072 > 64 images | on | tools: yes (web search) — benign |
| #1053 continue a reply that ends inside its thinking; #1172 tool-call recovery; #923 / #924 Codex; R1 pinned prefix | off (opt-in) | – |
| #1080 a --resident-budget-gib above the free RAM warns at start | on | the stand-ins' configs |
