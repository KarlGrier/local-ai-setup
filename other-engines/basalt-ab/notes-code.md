# Basalt code notes for the GPU A/B (src = fb0944c7)

Read-only reading of `/home/USER/ai-speed-testing/basalt-ab/src`. Nothing in it was built or run, and nothing was
imported from it. Paths below are relative to `src/`. My own small scripts (run with `python3 -I`) read only the pack
header, the `meta` and `tokenizer/*` sections, and the `data/bench/*.ids` fixtures. The patches below were drafted
on copies in the session scratchpad and checked with `git apply --check`, which changes nothing. `src` is still clean.

GPU facts (`nvidia-smi --query-gpu`, read-only): index 0 = RTX 5080 (01:00.0, cc 12.0, 16303 MiB, 360 W limit).
Index 1 = RTX 4060 Ti (10:00.0, cc 8.9, 160 W).

Pack facts (from its header and `meta`):
- 18 sections. `experts` is 50.29 GB (46.8 GiB). `gguf` is 33.3 GB, and 26.8 GiB of that is `per_layer_token_embd` (IQ4_NL).
- `output.weight` is Q6_K (type 14) [2560, 248320]. `token_embd` is IQ4_XS.
- `meta.sampling` = `{temperature 1.0, top_p 0.95, top_k 20, min_p 0.0, presence_penalty 0.0}`. Nothing else.
- `meta.mtp` = `{expert_format q2_0, draft_vocab true}`.
- The pack's `mtp/dense` has sha256 `dfe18647...` and equals `hf/convert/mtp/rt/dense.bin`. `mtp/draft_vocab` and
  `mtp/dense.index` also equal the hf files.
- The pack's `tokenizer/chat_template.jinja` is byte-identical to `serve/chat_template.jinja`.

---------------------------------------------------------------------------------------------------------------------

## 0. Things that bite (short list)

1. **Set `"gpu": "0"`.** Without it, `nvidia-smi` shows 2 GPUs. The server then adds `--peer-device 1`
   (serve/engine/modelfile.py:120-121), and the engine refuses the cc 8.9 card (src/core/device.cu:97-102).
   `basalt-bench` does the same through NVML (bench_main.cpp:816-817). For the bench, set
   `CUDA_VISIBLE_DEVICES=0 CUDA_DEVICE_ORDER=PCI_BUS_ID`; the bench does not set the order itself.
2. **The engine's built-in defaults are untuned:** 4096 context, fp16 KV, no speculation, `--prefill 0` (prompts
   one token at a time). `prefill`, `max-context`, `kv` and `spec` must be set; set `expert-cache` explicitly too.
   With this pack's profile, `expert-cache 0` already means auto (src/program/generate.cpp:2767).
3. **Prefix reuse is on (`prompt-cache` 6).** A repeated identical prompt is not read again. For prefill timing use
   `"prompt-cache": 0`, which turns off all reuse (generate.cpp:7527), or put a nonce at the start of each prompt.
   Check `timings.cache_n == 0`.
4. **Thinking on with no effort given means xhigh.** The template then adds a "Reasoning effort is set to xhigh..."
   system turn (chat_template.jinja:58-71). Send `"reasoning_effort": "medium"` for our default. Medium adds no
   system line.
5. **Sampler order is penalties → top_k → top_p → min_p → temperature** (sampler.hpp:3). top_p and min_p act on
   un-tempered probabilities. `top_k` 0 or > 64 is treated as 64. If Strata applies temperature first, T ≠ 1 is not
   the same distribution; T 1.0 is unaffected.
6. **`spec 7` means 6 MTP drafts per window.** With suffix drafting on (default `--suffix-draft 3`) the verifier is
   sized 8 and MTP windows are capped at 7 (generate.cpp:1820-1826).
7. **`basalt-bench` uses pre-tokenized fixtures, starts its own engine (no server), and runs to EOS.** It reports the
   mean ± sd over `-r`; it does not pick a best run. The card's "Best measured" is the maintainer's own choice.
8. **Binaries go to `${CMAKE_SOURCE_DIR}/bin` (CMakeLists.txt:398,416), not to the build dir.** A debug build in a
   second build dir of the same `src/` would overwrite `src/bin/basalt`. The debug patch needs its own source copy
   (§6.4).

---------------------------------------------------------------------------------------------------------------------

## 1. Server: start, config, GPU, auth

**Launch.** `bin/basalt serve --config FILE [--python PY] [server args]` (generate.cpp:586-628). It makes `--config`
and `--model` absolute, changes directory to the compiled-in `BASALT_SOURCE_DIR` (CMakeLists.txt:403), and execs
`PY -m serve.server --engine-bin <this binary> ...`. The default PY is `src/.venv/bin/python`, else `python3`, so
pass ours. The server spawns `bin/basalt --serve <engine args>` and talks to it over stdin/stdout
(serve/engine/process.py:171).

```sh
cd /home/USER/ai-speed-testing/basalt-ab
HOME=$PWD/home BASALT_CACHE=$PWD/home/cache PYTHONDONTWRITEBYTECODE=1 \
  src/bin/basalt serve --config $PWD/basalt_config.json --python $PWD/venv/bin/python
# without the C++ launcher (same thing):
cd src && HOME=.. BASALT_CACHE=../home/cache ../venv/bin/python -m serve.server \
  --config ../basalt_config.json --engine-bin $PWD/bin/basalt
```

**Config format** (serve/config.py:70-131): `{"server": {...}, "engine": {...}}`.
- Keys are flag names without dashes; `_` is accepted for `-`. A switch is `true`; `false` omits the flag. A list
  gives a flag several values.
- `model` is resolved relative to the config file.
- Precedence: command line > file > defaults. The engine gets the file's words, then the command line's; the last
  one wins.
- An unknown or misplaced key stops the server. Engine flag names are checked against the strings in the binary
  (config.py:22-29).
- `api-key` in a file is refused (config.py:92-94).

**Minimal `basalt_config.json` for our runs:**

```json
{
  "server": {
    "model": "/home/USER/ai-speed-testing/basalt-ab/models/Qwen3.8-FN-GSQ-RCO-IQ3_S.basalt",
    "gpu": "0",
    "host": "127.0.0.1",
    "port": 8095,
    "vision": "off"
  },
  "engine": {
    "max-context": 40960,
    "kv": "int8",
    "expert-cache": "auto",
    "prefill": "auto",
    "resident-experts": true,
    "vram-reserve-mib": 700,
    "spec": 7,
    "spec-min-p": 0.5
  }
}
```

The same as flags: `--model F --gpu 0 --host 127.0.0.1 --port 8095 --vision off --max-context 40960 --kv int8
--expert-cache auto --prefill auto --resident-experts --vram-reserve-mib 700 --spec 7 --spec-min-p 0.5`.

Optional settings:
- **Prefill arms:** `"prompt-cache": 0`.
- **Server-side sampling defaults** for requests that omit fields: `"temperature": 1.0, "top-p": 0.95, "top-k": 20,
  "min-p": 0.05` in `server` (config.py:353-364).
- **Pinned tiers for identity checks:** `"adapt-swaps": 0, "pcie-frac": 0`.

**Setting by setting:**
- **GPU.** `gpu` lists nvidia-smi numbers. The server sets `CUDA_DEVICE_ORDER=PCI_BUS_ID` and
  `CUDA_VISIBLE_DEVICES=<list>` for the engine (serve/engine/vision.py child_env).
  - With one card listed there is no peer tier.
  - Here `"gpu": "0"` is the 5080.
- **Context.** `max-context` above 32768 turns on elastic KV (docs/running.md):
  - At start each session backs only its first 32768 cells; the rest of that VRAM holds expert-cache slots.
  - A request backs prompt + 16384 cells before its prompt is read, by taking those slots back. Their experts become
    CPU/RAM misses for that request.
  - Log lines: `basalt serve: elastic KV: ...` (generate.cpp:6329, 6346).
  - A short request decodes with the cache a 32K context would have.
- **KV.** `kv` is `fp16` (engine default), `int8`, `q4_0` or `k8v4`. Use the same precision as the Strata arm if
  possible.
- **Expert cache.**
  - `expert-cache auto` uses every slot left after weights, sessions and `vram-reserve-mib` (default 700, at least
    256).
  - `resident-experts` keeps the experts no VRAM slot holds in page-locked RAM (cudaHostRegister); details in §3(d).
  - Expected size: 35-47 GiB pinned; this pack's experts total 46.8 GiB.
  - The PLE table (26.8 GiB) is not in RAM. It is read from the SSD with O_DIRECT per token (`--ple-io direct`,
    the default; row cache 1M × 90 B).
  - MemAvailable should stay far above 12 GB with 8080 stopped. The engine's own RAM guard is much lower
    (margin = max(2 GiB, 5% of RAM) ≈ 4.7 GiB, plus 3.5 GiB only when experts stay on the SSD), so our watcher is
    the guard.
  - `"resident-budget-gib": N` caps the RAM copy. The engine refuses a value that would breach its own floor.
- **Speculation.**
  - `spec` N is the verify window: the last accepted token plus N−1 MTP drafts.
  - With `suffix-draft` > 0 (default 3) the engine sets `mtp_max_t = N` and window cap `min(N+2, 8)`
    (generate.cpp:1820-1826).
  - `spec-min-p`: any value > 0 switches on the cumulative draft-length rule; the number itself is never used
    (draft_cum.hpp:31-36 returns `prod acc(p_i) >= th` whenever `th > 0`, and `th` is always ≥ 0.25×scale > 0).
    0 means always draft to the cap. Use 0.5 as their configs do.
- **Relaxed drafting** (engine flag `--relaxed-drafting [P]`): leave it out. The default is 0.0 = exact
  (generate.cpp:469, parse 1446-1455).
  - **Do not send `relaxed_drafting`** in requests. A request value > 0 turns it on even when the engine flag is off
    (process.py:501-506 → `relax=P`, generate.cpp:7257/7286/8210).
  - `"relaxed_drafting": false` forces exact.
- **Vision.** `"vision": "off"` is the default (config.py:320). With off, no `--vision` or `--vision-mmproj` is
  passed and no sidecar starts (modelfile.py:128-136, server.py:95-96). Nothing of the picture reader is loaded.

**API key.** Not needed on 127.0.0.1; it is only required by convention off loopback. The checks without a key:
- **Host** (handler.py:54-68, security.py:127-134): the Host header must be an IP, `localhost` or `*.localhost`.
  `127.0.0.1:8095` passes.
- **Origin on /v1 POST** (handler.py:125-142, security.py:137-152): checked only when an `Origin` header is present.
  Python requests/httpx/openai send none, so they pass.
  - If an Origin is sent, it must be `http(s)://127.0.0.1|localhost[:port]` or equal to the Host. The body must also
    be `Content-Type: application/json`, or the answer is 403/415.

---------------------------------------------------------------------------------------------------------------------

## 2. Request API (`POST /v1/chat/completions`)

**Fields honoured.** The whole request dict is the sampling dict (openai.py:25 → service.run). It is forwarded as
engine keys by process.py:464-507 and parsed in generate.cpp:7244-7289.

| Field | Handling |
| --- | --- |
| `temperature` | > 0 → sampled; 0 → greedy. If absent, the server default applies (pack 1.0). |
| `top_p` | Sent when < 1. |
| `top_k` | Must be a JSON int. Values outside 1..64 become 64. A float such as 20.0 is ignored, and the engine uses its own 20. |
| `min_p` | Sent when 0 < min_p ≤ 1. The pack default is 0, so send 0.05 explicitly. |
| `repetition_penalty`, `frequency_penalty`, `presence_penalty`, `penalty_last_n` | `penalty_last_n` defaults to 64 when any penalty is on. |
| `seed` | Integer > 0. Absent → a per-request time seed (generate.cpp:8195-8196). |
| `logit_bias`, `stop`, `relaxed_drafting`, `response_format` | `response_format` forces exact sampling (handler.py:504-505). |

Omitted fields take the server launch options, then the pack's `meta.sampling` (service.py:570-572).

**Thinking per request** (frontend.py:338-372, 62-76):
- **Off:** `"chat_template_kwargs": {"enable_thinking": false}`, or `"reasoning_effort": "none"` (also `off`,
  `minimal`, `disabled`, `false`). A top-level `enable_thinking` is *not* read on this endpoint.
- **On:** the default. Efforts:
  - `"reasoning_effort": "medium"` adds no system line.
  - `"low"` adds the low line.
  - `"high"`, `"xhigh"`, `"max"` add the xhigh line.
  - No effort at all means the template default xhigh (chat_template.jinja:58-71).
- **Prompt endings** (jinja:176-183): on ends `<|im_start|>assistant\n<think>\n`; off ends
  `<|im_start|>assistant\n<think>\n\n</think>\n\n`.

**`max_tokens`.** Read as `max_completion_tokens` or `max_tokens`. 0, -1 or absent means the rest of the context. A
larger value than the room left gives a 400, unless the server runs with `--fit-max-tokens` (handler.py:508,
service.py:510-524). The count includes thinking tokens.

**Fixed output length.** There is no `ignore_eos` or `min_tokens`.
- The server stops at `<|im_end|>` 248046 or `<|endoftext|>` 248044 (service.py:91-92, 681-689). The engine also
  stops there, because `--serve` forces `stop_eos` (generate.cpp:1777-1782).
- **Workaround:** `"logit_bias": {"248046": -100, "248044": -100}`. A bias of -100 bans the token
  (serve/api/logit_bias.py), so generation runs to `max_tokens`.
  - Cost: every window takes the host-side sampling path (verify.cpp:2973-2981).
  - Relaxed drafting is off for such a request.
  - It is not allowed with `--parallel`.
  - Strata would need the same ban.
- **Other stops still apply:**
  - 256 repeats of one token in a row end the reply as `length` (service.py:31, 693-697; no option).
  - `stop` strings.
- **`<|im_end|>` inside thinking** (if not banned): the server writes `"\n</think>\n\n"` and continues
  (service.py:35, 681-686, 752-759).

**Streaming** (openai.py:13-59, handler.py:518-540). Server-sent events, one `data: {chat.completion.chunk}` per
event:
- The first chunk's delta is `{"role":"assistant","content":""}`.
- Later deltas carry `reasoning_content`, `content` or `tool_calls`.
- `: keep-alive` comments are sent every 10 s of silence.
- The final chunk has `delta {}`, `finish_reason` (`stop`, `length` or `tool_calls`), `usage` (`prompt_tokens`,
  `completion_tokens`, `total_tokens`, `prompt_tokens_details.cached_tokens`) and `timings`. Then `data: [DONE]`.
  No `stream_options` is needed.
- A non-streamed reply carries the same `usage` and `timings` (openai.py:70-99).

**`timings`** (service.py:903-918, llama.cpp names):
- `cache_n`
- `prompt_n` = prompt − cache_n
- `prompt_ms`, `prompt_per_token_ms`, `prompt_per_second`
- `predicted_n`: the server's count, including the EOS token
- `predicted_ms`: the engine's decode ms
- `predicted_per_token_ms`
- `predicted_per_second` = engine generated / decode_ms
- `draft_n` (drafts offered), `draft_n_accepted`

How the engine clocks these:
- `prompt_ms` runs from request start to the end of the prompt read; it includes the refill of lent slots
  (generate.cpp:7448 → 8326).
- The last prompt token is not in `prompt_ms`. It is processed by the first verify window (T=1), which yields
  token 1.
- `decode_ms` runs from before that first window to the end of the loop (generate.cpp:8355 → 8770). So decode tok/s
  **includes the first token** and excludes the prompt.
- There is no TTFT field in the response. The server log line has `first token after X s`.

**Other endpoints** (handler.py:211-297):
- `GET /metrics` (service.py:359-387):
  - `engine`: the engine's INFO facts — `expert_slots`, `expert_cache_mib`, `expert_slots_primary`, `spec`,
    `spec_min_p`, `pool_workers`, `arena_mib`, `vram_free_mib`, `kv`, `context`.
  - `live` state.
  - The last 12 requests, each with `decode_tok_s`, `prompt_ms`, `hit_rate`, `pcie_share`, `drafts_offered` and
    `drafts_accepted`.
  - `hardware`: NVML and psutil readings, sampled every second.
- `GET /v1/status` (`last_timings`), `/slots`, `/props` (the sampling defaults), `/status`, `/health`,
  `/api/logs?after=ID&limit=N` (server and engine lines), `/v1/models`.
- There is no `/v1/completions`, so raw token-id prompts cannot be sent over HTTP. They can only go through the
  engine protocol (`GEN <max_new> k=v ... id,id,...`).

---------------------------------------------------------------------------------------------------------------------

## 3. Engine log lines (stderr → `$BASALT_CACHE/<first 16 hex of meta sha256>/engine.log`, appended)

The server puts engine stderr in that file (modelfile.py:26-32,126) and tails it into `/api/logs`. Its own `[server]`
lines go to stdout. Format strings below are quoted exactly.

**(a) Experts in VRAM, cache slots**
- `"basalt generate: expert cache auto: %.2f GiB free, %d MiB reserved (+%lld MiB for the draft head, +%lld MiB for what loads after) -> %d slots"` (generate.cpp:3341)
- `"basalt generate: expert cache %lld slots, %.2f GiB of VRAM; policy is"` (3555)
- `"basalt generate: pre-filled %lld of %lld slots from the profile in %.1f s (%.0f MB/s); slot 0 verified"` (3702)
- `"basalt generate: experts live in VRAM %.1f GiB (%.0f%%), peer GPU %.1f GiB (%.0f%%), RAM %.1f GiB%s (%.0f%%), file (SSD) %.1f GiB (%.0f%%); %.1f GiB in all"` (4785)
- `"basalt serve: the prompt path borrows %lld CUDA0 cache slots (%.2f GiB)"` (4979)
- `"basalt serve: %lld MiB of VRAM free with everything loaded"` (5951)
- `"basalt serve: elastic KV: %lld cells backed (+%.0f MiB), the expert cache %lld -> %lld slots, in %.1f ms"` and the
  `%lld -> %lld cells backed` variant (6329, 6346)
- Per request: `"basalt serve: decode expert cache hit rate: %.1f%% (%lld hits / %lld lookups)%s"` (8960)
- Also the stdout line `INFO ... expert_slots=%lld expert_cache_mib=%lld expert_slots_primary=%lld ... spec=%d mtp_max=%d lookup=%d vram_free_mib=%lld ... arena_mib=%lld pool_workers=%d pcie_frac=%.2f spec_min_p=%.2f ...` (5975). The server keeps these as `/metrics` → `engine`.

**(b) Draft acceptance**
- Per request: `"basalt serve: prompt %lld tokens = %lld reused + %s read in %.0f ms (%.1f tok/s), %lld generated in %.0f ms (%.1f tok/s), drafts accepted %lld of %lld, %zu checkpoints%s"` (8941)
- `"basalt serve: suffix drafts: %lld windows, %lld of %lld drafts accepted"` (8992)
- Relaxed only: `"basalt serve: relaxed drafting %.2f: %lld of the %lld accepted drafts were kept by it"` (8948)
- Per window, with `--draft-log FILE` (file, not stderr):
  - `"R temp=%g min_p=%g S=%d"` per request.
  - Then per window `"W %d %d %d %.3f %.3f %.3f"` + ` %.4f` draft probabilities. The fields are T, a (accepted
    drafts, so a+1 tokens emitted), from-suffix, pre ms, verify ms, post ms (generate.cpp:8387, 8670-8673).
- `DONE` on stdout: `DONE <gen> <prompt> <prompt_ms> <decode_ms> <finish> <drafts_accepted> <drafts_offered> <reused> <hits> <lookups> <ram_blobs> <file_blobs> <file_MB> <prompt_read> <offloaded>` (8812-8836).

**(c) Decode and prefill speed**
- The 8941 line above.
- stdout progress `PP <read> <total> <ms> <tok/s>` and `PL ...` (5478, 5492, 7803).
- Server lines:
  - `"[server] done: prompt N tokens (R reused) in X s, P tok/s; M tokens at Z tok/s; first token after T s (finish)"`
    plus `", expert cache X% hit (+Y% of the routed experts over PCIe)"` (service.py:883-900, 835-840).
  - `"[server] reading the prompt: X of Y tokens, P tok/s, N s"` every 5 s (559).
  - With `--request-lines`: `"[server] request prompt %s cached %s output %s prompt_read %.0f ms total %.0f ms prefill %s tok/s decode %s tok/s"` (process.py:67).
- Diagnostics: `--decode-timing` (one line per request), `--profile`, `--wait-stats`.

**(d) Host memory pinned or locked**
- With `--resident-experts` (expert_source.cpp):
  - `"FileExpertSource: copied cache complement through layer %lld/%lld (%.2f GiB, %.0f s)"` (1087)
  - `"FileExpertSource: cache complement: allocation %.1f s, read %.1f s (%.2f GB/s, %.1f%% unbuffered), registration %.1f s"` (1129)
  - `"FileExpertSource: %s cache complement ready: resident %.2f GiB, pinned %.2f GiB in %.0f s%s%s"` (1156). The
    first `%s` is `mapped pinned`, `locked resident` or `pageable resident`. The note is `page-locked and mapped`
    (cudaHostRegister mapped+portable) or `page-locking refused (...); mlock` / `mlock failed (raise ulimit -l)`
    (memory.cpp:91).
  - `"basalt generate: RAM top-up: +%.2f GiB, %lld experts (total %.2f GiB)"` (generate.cpp:6035)
  - `"basalt generate: RAM floor %.1f GiB (%.1f margin + %.1f cache), %.1f GiB experts on SSD, RAM copy <= %.1f of %.1f GiB"` (4682; only when experts stay on the SSD)
  - `"basalt serve: RAM %.2f GiB free, guard %.2f GiB, %.2f GiB kept for serving"` (6046)
- Default arena mode (no `--resident-experts`, no `--mmap-experts`):
  - `"basalt generate: expert arena: %s"` (3258), with the PinnedArena note `cudaHostRegister PORTABLE ok; ...` or
    `cudaHostRegister of the whole arena FAILED (...); N slices pinned (X GiB); ...` (pinned.cu:66-110).
  - `"basalt generate: expert arena: %.2f GiB of VRAM-held experts handed back to the OS"` (4441).
- `"basalt mtp: no pinned RAM left for the draft layer's K/V copy; keeping it in VRAM"` (mtp.cpp:342)

---------------------------------------------------------------------------------------------------------------------

## 4. Pack defaults, relaxed drafting, and lossy or approximate defaults

**Pack defaults.**
- `meta.sampling` holds sampling defaults only. In this pack: temperature 1.0, top_p 0.95, top_k 20, min_p 0.0,
  presence_penalty 0.0. A bad value refuses to start (config.py:233-253).
- The only other recognised sampling key is `experimental_speed_projection`, which switches a control vector per
  request (`cvec=0|1`). It is absent here, and the pack has no vector.
- "It carries no engine flags" (docs/model-file.md:5). No relaxed-drafting default exists in the file.

**Relaxed drafting.**
- **Engine flag:** `--relaxed-drafting [P]` (bare = 0.5) or config `"relaxed-drafting": P|true`. The default is
  `0.0f` = exact (generate.cpp:469).
- **Request:** `relaxed_drafting` (0..1, or false). Only a request that sends it changes it.
- **Where it is not applied:** greedy requests, `logit_bias`, JSON `response_format`, the ppl gate, `--parallel`
  slots, added-token drafts (ids ≥ 248044) and tool calls (generate.cpp:8210-8216, 8476-8494).
- **Off in a default setup:** yes, as long as the config and the client don't set it.

**Lossy or approximate settings** (anything that makes output differ from exact-logit plain sampling):

| # | Setting | Default | Switch |
|---|---|---|---|
| 1 | **Two-stage Q6_K verify head** (§6). Tail logits approximate; top-64 exact unless the copy errs by more than the margin, or the 65,536-row rescore cap overflows. | always on for this pack | none (patch §6.4 `--exp exact_head=1`) |
| 2 | **int8 copies of the hyper-connection matrices** in decode (BF16 in the pack; fp16 scale per 32) — docs/precision/index.md:20-22,49 | always | none |
| 3 | **Prefill numerics ≠ decode.** fp16/BF16 GEMMs, BF16 router input, int8 FP16-MMA prompt attention for int8 KV, chunked GDN on BF16/TF32 tensor cores. The CPU computes 0.6 of the streamed experts with Q8_K/256 activations. (precision/index.md:110-162) | `--prefill auto`, `--prefill-cpu-share 0.6` | `--prefill 0` (very slow), `--prefill-cpu-share 0` |
| 4 | **CPU expert tier** rounds differently (Q8_K/256 vs q8_1/32). The adaptive tier moves experts between windows, so results are not bitwise reproducible run to run. | `adapt-every 4`, `adapt-swaps 96`, `pcie-frac 0.55` | `--adapt-swaps 0 --peer-adapt-swaps 0 --pcie-frac 0` |
| 5 | KV quantization | fp16 (we choose int8) | `--kv` |
| 6 | Sampler truncation: `top_k` ≤ 64 always (0 or > 64 → 64); chain order penalties→top_k→top_p→min_p→temp | fixed | none |
| 7 | Server: 256-repeat stop; `</think>` injection on an early `<|im_end|>`; xhigh effort line when no effort is given | on | send `reasoning_effort`; logit_bias ban |
| 8 | Draft-side approximations (2-bit draft head, fp16 draft attention, draft vocab subset, suffix drafts): speed only, never output | on | — |
| 9 | Relaxed drafting | off | §above |
| 10 | Unseeded requests get a time seed (output random per request; distribution exact) | — | `seed` |

Window-width note: docs/precision/index.md:56 says verify kernels are not batch-invariant across widths. Yet
features.md:266-306 measured bit-identical logits at T 1/3/7 on their builds. Either way that is rounding level,
not bias.

---------------------------------------------------------------------------------------------------------------------

## 5. Speculative sampling exactness

**How it decides.** It is not the q-based min(1, p/q) code. Each verify row t of a window at `pos0` is sampled by
the target's own full chain: `sample_tokens_probe` with `sp.counter = pos0`, then `philox_uniform(seed, counter + t)`.
- Code: verify.cpp:2796-2806 and 2973-2981; sampler.cu:979-1031 (`sampled_tail_pair`). The draw is
  sampler.cu:1023, or :425 in the warp variant.
- Acceptance: `while (a < T - 1 && window[a + 1] == outv[a]) ++a;` (generate.cpp:8495; also 9334 in the CLI loop).
  Tokens `outv[0..a]` are emitted. The row after the last accepted draft emits the target's own draw.
- In words: keep the draft x iff it equals the target's own sample at that row. So p(accept) = p(x). On rejection
  the emitted token is the target sample conditioned on ≠ x, i.e. ∝ max(0, p − δ_x).
- **This is exactly standard speculative sampling for a deterministic (argmax) drafter**, where q is a point mass.
  The draw depends only on (seed, position), so the text with a given seed is token-identical to `--spec 0`
  (coupled_draft.hpp:3-7, verify.cpp:2965-2968). Docs measured 275/275 prompts identical (features.md:266-288).
- `--coupled-draft` (off) samples drafts with the same uniform; acceptance is still exact-match, so still exact
  (coupled_draft.hpp:8-12).

**What p is.** The final distribution after penalties → top_k → top_p → min_p → temperature, plus `logit_bias`. It
is the same sampler code as non-spec decoding. Greedy uses the captured argmax (verify.cpp:2214-2218).

**No shortcuts in exact mode.** There is no greedy-accept, no threshold accept, and no q in the decision. The only
alternate rule is relaxed drafting (off).

**`--spec-min-p` gating** (generate.cpp:8398-8404, draft_cum.hpp:24-76).
- Before the window, T is set from `dprob`: the drafter's own probabilities of its argmax drafts. The rule keeps
  draft j while `prod_{i<=j} acc(dprob_i) >= th`. `acc` is a fixed bin table. `th` starts at 0.35×scale and adapts
  down to 0.25×scale from observed acceptance (`DraftCumAdapt::observe`). The scale is 1.0-1.5, set from the pack's
  CPU-served bytes per slot (generate.cpp:4779).
- Only how many drafts are proposed changes. The emitted token at each position is the target's Philox draw at that
  position whatever T is. Adapting `th` from past acceptance changes only future window lengths.
- **No bias** (at most rounding-level effects if logits differ across window widths).
- Unlike our upstream STRATA_SPEC_PROB issue, nothing here gates on the drawn token's q.

---------------------------------------------------------------------------------------------------------------------

## 6. Two-stage output head (Q6_K head; `q6k_vhead`)

### 6.1 How it works

**Where it is selected** (verify.cpp:2196-2206, inside the captured window graph). If head type 14, `vhead_scratch_`
is allocated and `q6k_vhead_supported(2560, 248320, T)` holds (n_in 2560, n_out % 16 == 0, ≤ 2^18, T 1..8:
q6k_head.cu:755-757), it runs `q6k_vhead(proxy, weights, xq_, head_logits_, ...)`. Otherwise it runs
`q6k_head_mmvq` (exact). Batch windows use the same `record_window` (verify.cpp:3221).

**The 2-bit copy** (`vproxy`) is packed once at load (native_head.cpp:91-104), 199 MB, before the cache is sized.
- Every 32 weights get 4 levels and an fp16 scale (the head_proxy fit, scale raised by sqrt(|w|²/⟨w,ŵ⟩)).
- Kernel: `q6k_vproxy_pack_kernel`, q6k_head.cu:370-399.

**Stage 1** (`q6k_vscore_kernel`, q6k_head.cu:404-546) scores *all* 248,320 rows from the copy on int8 mma, against
the same q8_1 codes the exact kernel reads, and writes the approximate logits to `y`.
- Each persistent block adds its per-column maximum to a 1024-bin histogram: `VHIST=1024`, `VBIN=8` bins per logit,
  centred on 0, so ±64 logits (q6k_head.cu:346-351).
- The last block finds, per column, the bin holding the **64th largest block maximum** (`VKEEP=64`). The threshold is
  `thr = (bin - 512)/8 - VDELTA`, with **`VDELTA = 4.0` logits** (line 540). Fewer than 64 maxima, or bin 0, means
  thr = −inf (rescore all).
- The 64th largest block maximum is ≤ the 64th largest row, so this bound is conservative.
- The grid is fixed per device (`vscore_grid`, line 622), so the rows that are exact do not depend on T.

**Stage 2a** (`q6k_vselect_kernel`, 547-586) lists every (row, column) with approx ≥ thr. The list holds at most
**`VCAP = 65536` entries per call, summed over all T columns**. Extra entries are silently dropped (line 581) and keep
approximate logits. Their docs give per-column means of 1.1-2.0K rescored rows and p99 up to 12.8K (struct). So 7-8
columns can, rarely, hit the cap.

**Stage 2b** (`q6k_vrescore_kernel`, 588-620) overwrites the listed rows with exact Q6_K logits (`q6k_row_one`).
These are the same bits as `q6k_head_mmvq`; q6k_vhead_parity.cpp:245 checks `memcmp`. All other rows keep their
approximate logits (rms ≈ 0.7 logit).

**No switch, flag or env var turns it off.** It is off only if the vproxy `cudaMalloc` fails (native_head.cpp:95-102)
or the shape is unsupported. Patch §6.4 adds `--exp exact_head=1`.

### 6.2 What the sampler normalizes over

**Sampled path:** `sample_tokens_probe` on `head_logits_` (verify.cpp:2801-2806/2973-2981).
- `sampler_sort_kernel` builds the top-k list (k = request top_k ≤ 64) from the two-stage array.
- Then `sampled_tail_pair` (sampler.cu:979-1031) works only on that list:
  - top_p: `e1 = exp(x - x0)`, normalized by the sum over the k list only, cut at the cumulative top_p.
  - min_p: `x < x0 + log(min_p)` relative to the list max.
  - temperature: softmax over the `n_keep` survivors.
  - draw: `philox_uniform`.
- **The approximate tail never enters the sampled distribution.** It matters only through (i) a true top-k row that
  was not rescored (its logit is then the approximate one, usually too low, so it drops out of the list), or (ii)
  the VCAP overflow.

**Greedy:** argmax over the whole mixed array (exact unless the same failure happens).

**Scoring:** the full-softmax KLD gate scores the approximate tail; that is the +0.0017 KLD in features.md:239-251.

### 6.3 Exact Q6_K head kernel in the tree

`basalt::kernels::q6k_head_mmvq(weights, x_q8_1, y, 2560, n_vocab, ncols<=8, stream)` (q6k_head.hpp:12-14,
q6k_head.cu `launch_nc`). It is bitwise native_mmvq type 14 and is the fallback the head already uses. The patch
reuses it with `native_quantize_q8_1` on `head_mixed_`, which is the head's own input, quantized by the same kernel.

### 6.4 Debug patch: HEADCHECK + exact-head switch

**What it does.** With `--exp headcheck=1`, after every solo verify window has finished on the GPU (verify.cpp
`run()`, right after the layer-split early return), the patch:
1. recomputes the exact Q6_K logits for the window's T rows into its own buffers;
2. copies both arrays to pinned host memory;
3. per row:
   - finds the exact top-20 and the two-stage top-20 (logit desc, id asc — the sampler's order);
   - treats rows whose two-stage logit has the exact logit's bits as "exactly rescored";
   - counts:
     - **rows**
     - **exact top-20 not all exactly rescored**
     - **two-stage top-20 ids or order differ**, and separately **as a set**
     - **argmax differs**
     - **max |two-stage − exact| over the exact top-20**
     - the rescored rows per column (mean, max)
     - windows at the 65,536-row cap.

**When it prints.** It writes `HEADCHECK request: ...` and `HEADCHECK total: ...` to stderr after each request's
`basalt serve: prompt ...` line. With `--exp headcheck_every=N` it also writes `HEADCHECK running: ...` every N rows.
`--exp exact_head=1` skips the two-stage head everywhere (the exact-head arm); HEADCHECK is then inactive.

**What it changes.** It only reads and adds a sync, so outputs are unchanged. Decode slows (≈14 MB D2H plus ≈1 ms of
host work per row). Rows past a rejected draft are included; they are real head evaluations. The counts cover verify
windows only; the first window after a prompt is included.

**Config:** `"engine": {"exp": "headcheck=1,headcheck_every=2000"}`. Exact arm: `"exp": "exact_head=1"`.
`basalt-bench` passes `--exp headcheck=1` through.

```diff
--- a/src/core/verify.cpp
+++ b/src/core/verify.cpp
@@ -68,6 +68,156 @@
 
 namespace basalt::core {
 
+// ---- HEADCHECK (debug builds only).  `--exp headcheck=1` runs the plain exact Q6_K head (q6k_head_mmvq) beside the
+// two-stage head (q6k_vhead) at every verify row and compares them on the host; `--exp headcheck_every=N` also prints
+// the running counts every N rows.  `--exp exact_head=1` skips the two-stage head: the exact Q6_K head runs instead.
+namespace {
+constexpr int kHcTop = 20;                 // the exact top-k the check follows
+constexpr long long kHcListCap = 65536;    // q6k_head.cu's VCAP: rows one q6k_vhead call rescores, all columns
+
+struct HcCount {
+    long long rows = 0, windows = 0, outside = 0, list_differs = 0, set_differs = 0, argmax_differs = 0;
+    long long cap_windows = 0, rescored_max = 0;
+    double rescored_sum = 0.0, max_abs = 0.0;
+};
+
+struct HeadCheck {
+    bool on = false;
+    long long every = 0, since = 0;
+    uint8_t* d_xq = nullptr;
+    float* d_exact = nullptr;
+    float* h_two = nullptr;
+    float* h_exact = nullptr;
+    HcCount req, total;
+};
+
+HeadCheck& headcheck() {
+    static HeadCheck h = [] {
+        HeadCheck c;
+        c.on = exp_flag("headcheck", 0) != 0;
+        c.every = (long long) exp_flag("headcheck_every", 0);
+        return c;
+    }();
+    return h;
+}
+
+bool exact_head_forced() {
+    static const bool on = exp_flag("exact_head", 0) != 0;
+    return on;
+}
+
+// the first kHcTop rows of x by (logit desc, id asc), best first
+void hc_top(const float* x, int n, int* out) {
+    auto better = [x](int a, int b) { return x[a] > x[b] || (x[a] == x[b] && a < b); };
+    int h[kHcTop];
+    int m = 0;
+    for (int i = 0; i < n; ++i) {
+        if (m < kHcTop) { h[m++] = i; std::push_heap(h, h + m, better); continue; }
+        if (!better(i, h[0])) continue;   // h[0] is the worst kept row
+        std::pop_heap(h, h + m, better);
+        h[m - 1] = i;
+        std::push_heap(h, h + m, better);
+    }
+    std::sort(h, h + m, better);
+    for (int i = 0; i < kHcTop; ++i) out[i] = i < m ? h[i] : -1;
+}
+
+void hc_print(const char* tag, const HcCount& c) {
+    std::fprintf(stderr,
+                 "HEADCHECK %s: rows %lld (%lld windows); exact top%d not all exactly rescored %lld; two-stage top%d "
+                 "differs (ids or order) %lld, as a set %lld; argmax differs %lld; max |two-stage - exact| over the "
+                 "exact top%d %.6g; rescored rows per column mean %.0f max %lld; windows at the %lld-row cap %lld\n",
+                 tag, c.rows, c.windows, kHcTop, c.outside, kHcTop, c.list_differs, c.set_differs, c.argmax_differs,
+                 kHcTop, c.max_abs, c.rows ? c.rescored_sum / (double) c.rows : 0.0, c.rescored_max, kHcListCap,
+                 c.cap_windows);
+    std::fflush(stderr);
+}
+
+// One verify window: the exact Q6_K logits of head_mixed's T rows against the two-stage logits the window wrote.
+void headcheck_window(const void* weights, const float* mixed, const float* two_d, int n_in, int n_vocab, int T,
+                      cudaStream_t s) {
+    HeadCheck& h = headcheck();
+    constexpr int kMaxT = basalt::kernels::kVerifyMaxT;
+    if (T < 1 || T > kMaxT) return;
+    const size_t floats = (size_t) kMaxT * (size_t) n_vocab;
+    if (h.d_exact == nullptr) {
+        if (cudaMalloc((void**) &h.d_xq, basalt::kernels::native_q8_1_bytes(n_in, kMaxT)) != cudaSuccess ||
+            cudaMalloc((void**) &h.d_exact, floats * sizeof(float)) != cudaSuccess ||
+            cudaMallocHost((void**) &h.h_two, floats * sizeof(float)) != cudaSuccess ||
+            cudaMallocHost((void**) &h.h_exact, floats * sizeof(float)) != cudaSuccess) {
+            std::fprintf(stderr, "HEADCHECK: buffers not allocated (%s): check off\n",
+                         cudaGetErrorString(cudaGetLastError()));
+            h.d_exact = nullptr;
+            h.on = false;
+            return;
+        }
+    }
+    // the head's own input, quantized by the same kernel, through the plain Q6_K head
+    basalt::kernels::native_quantize_q8_1(mixed, h.d_xq, n_in, T, s);
+    basalt::kernels::q6k_head_mmvq(weights, h.d_xq, h.d_exact, n_in, n_vocab, T, s);
+    const size_t bytes = (size_t) T * (size_t) n_vocab * sizeof(float);
+    cudaMemcpyAsync(h.h_exact, h.d_exact, bytes, cudaMemcpyDeviceToHost, s);
+    cudaMemcpyAsync(h.h_two, two_d, bytes, cudaMemcpyDeviceToHost, s);
+    if (cudaStreamSynchronize(s) != cudaSuccess) {
+        std::fprintf(stderr, "HEADCHECK: %s: check off\n", cudaGetErrorString(cudaGetLastError()));
+        h.on = false;
+        return;
+    }
+    long long win_rescored = 0;
+    for (int t = 0; t < T; ++t) {
+        const float* ex = h.h_exact + (size_t) t * (size_t) n_vocab;
+        const float* tw = h.h_two + (size_t) t * (size_t) n_vocab;
+        int te[kHcTop], tt[kHcTop];
+        hc_top(ex, n_vocab, te);
+        hc_top(tw, n_vocab, tt);
+        long long resc = 0;   // rows whose two-stage logit has the exact logit's bits: the rescored rows
+        for (int r = 0; r < n_vocab; ++r) resc += std::memcmp(ex + r, tw + r, sizeof(float)) == 0;
+        win_rescored += resc;
+        bool outside = false, list = false;
+        double mx = 0.0;
+        for (int i = 0; i < kHcTop; ++i) {
+            outside = outside || std::memcmp(ex + te[i], tw + te[i], sizeof(float)) != 0;
+            mx = std::max(mx, (double) std::fabs(tw[te[i]] - ex[te[i]]));
+            list = list || te[i] != tt[i];
+        }
+        int a[kHcTop], b[kHcTop];
+        std::copy(te, te + kHcTop, a);
+        std::copy(tt, tt + kHcTop, b);
+        std::sort(a, a + kHcTop);
+        std::sort(b, b + kHcTop);
+        const bool set = !std::equal(a, a + kHcTop, b);
+        for (HcCount* c : {&h.req, &h.total}) {
+            ++c->rows;
+            c->outside += outside;
+            c->list_differs += list;
+            c->set_differs += set;
+            c->argmax_differs += te[0] != tt[0];
+            c->max_abs = std::max(c->max_abs, mx);
+            c->rescored_sum += (double) resc;
+            c->rescored_max = std::max(c->rescored_max, resc);
+        }
+    }
+    for (HcCount* c : {&h.req, &h.total}) {
+        ++c->windows;
+        c->cap_windows += win_rescored >= kHcListCap;
+    }
+    if (h.every > 0 && (h.since += T) >= h.every) {
+        h.since = 0;
+        hc_print("running", h.req);
+    }
+}
+}  // namespace
+
+// The end of a request (generate.cpp): this request's counts, then the process total.
+void headcheck_report() {
+    HeadCheck& h = headcheck();
+    if (!h.on || h.req.rows == 0) return;
+    hc_print("request", h.req);
+    hc_print("total", h.total);
+    h.req = HcCount{};
+    h.since = 0;
+}
+
 // The CPU tier's cache warm-up.  After layer l's doorbell the parked pool workers score layer l + 1's router on layer
 // l's FFN input (the ring's q8_1 rows; the router in int8 with one scale per 32 values, as the peer's warm-up has it:
 // a prediction only), take every token's top k, rank the predicted experts only the CPU holds by their summed weight,
@@ -2197,7 +2347,8 @@
                 native_quantize_q8_1(head_mixed_, xq_, (int) N, T, cs);
                 if (head_->type() == 13 && q5k_head_supported((int) N, T))   // the same bits, one wave
                     q5k_head_mmvq(head_->weights(), xq_, head_logits_, (int) N, (int) n_vocab_, T, cs);
-                else if (head_->type() == 14 && vhead_scratch_ != nullptr && q6k_vhead_supported((int) N, (int) n_vocab_, T))
+                else if (head_->type() == 14 && vhead_scratch_ != nullptr && !exact_head_forced() &&
+                         q6k_vhead_supported((int) N, (int) n_vocab_, T))
                     q6k_vhead(head_->vproxy(), head_->weights(), xq_, head_logits_, (int) N, (int) n_vocab_, T,
                               vhead_scratch_, cs);
                 else if (head_->type() == 14 && q6k_head_supported((int) N, T))
@@ -2970,6 +3121,11 @@
         ++windows;
         return next_ == nullptr || next_->run(T, tokens, pos0, pool, next_user_, out, err);
     }
+    // HEADCHECK (debug): this window's two-stage head against the plain exact Q6_K head (reads only, same stream)
+    if (headcheck().on && head_ != nullptr && head_->loaded() && head_->type() == 14 && vhead_scratch_ != nullptr &&
+        !exact_head_forced() && q6k_vhead_supported((int) g.n_embd, (int) n_vocab_, T) &&
+        q6k_head_supported((int) g.n_embd, T))
+        headcheck_window(head_->weights(), head_mixed_, head_logits_, (int) g.n_embd, (int) n_vocab_, T, cs_);
     if (head_sampling_ && (sampled || hist_d_ != nullptr || biased) && !early_sample) {
         SamplerParams sp = sampling_;
         sp.counter = (uint64_t) pos0;
--- a/src/program/generate.cpp
+++ b/src/program/generate.cpp
@@ -107,6 +107,8 @@
 #include <set>
 #include <vector>
 
+namespace basalt::core { void headcheck_report(); }   // HEADCHECK (debug): src/core/verify.cpp
+
 namespace {
 // One unit of background work at a time, on a persistent worker thread (starting a thread per job costs more than
 // the job's wake-up).  `join` waits for the job in flight.
@@ -8944,6 +8946,7 @@
                          prompt_ms > 0 ? 1000.0 * read_n / prompt_ms : 0.0, (long long) produced_n, decode_ms,
                          decode_ms > 0 ? 1000.0 * produced_n / decode_ms : 0.0, (long long) draft_accepted,
                          (long long) draft_offered, checks.size(), cancelled ? " (cancelled)" : "");
+            basalt::core::headcheck_report();
             if (relax_on)
                 std::fprintf(stderr, "basalt serve: relaxed drafting %.2f: %lld of the %lld accepted drafts were kept by it\n",
                              (double) req_relax, (long long) relaxed_kept, (long long) draft_accepted);
```

**Why it is safe.**
- It needs only headers verify.cpp already includes: `diag.hpp` (`exp_flag`), `native_mmvq.hpp`, `q6k_head.hpp`,
  `verify_kernels.hpp` (`kVerifyMaxT = 8`), `<algorithm>`, `<cstring>` and `<cmath>`.
- `-Werror` is off by default (CMakeLists.txt:17).
- The check runs after `cudaStreamSynchronize(cs_)` in `run()`. `head_logits_` and `head_mixed_` are not written
  again until the next window. The sampled path only reads them.
- The "rescored" test (equal bits) is the same test the kernel's own parity test uses. If exact and rescored bits
  ever differ, the "not all exactly rescored" count goes to about 100% while `max |two-stage - exact|` stays tiny.
  That pattern means "bits differ", not "rows missed".

**Build without touching `src/`.** The binaries land in the *source* dir's `bin/`.

```sh
cd /home/USER/ai-speed-testing/basalt-ab
git clone -q --no-checkout src src-headcheck && git -C src-headcheck checkout -q fb0944c7
# save the diff above as patches/headcheck.diff (and §7's ppl_top.diff if wanted), then:
git -C src-headcheck apply ../patches/headcheck.diff
# build exactly as scripts/build.sh does, with src -> src-headcheck (the memguard pattern basalt-ab/src* covers it)
```

The result is `src-headcheck/bin/basalt`. `basalt serve` from that binary runs the server from `src-headcheck`
(baked-in `BASALT_SOURCE_DIR`).

---------------------------------------------------------------------------------------------------------------------

## 7. Logit dumps

**No working facility.**
- `--dump-logits PATH` / `--logits-stride` exist and open the file (generate.cpp:4087-4110), but nothing ever writes
  a row. The only other use is the `fclose` at 9442. It is a dead option in this checkout.
- `--exp concur9_logit_hash=1` prints only `LH -1 <pos> <fnv1a>` per accepted row (stderr; generate.cpp:8508). That is good for
  Basalt-vs-Basalt identity, not for comparing values.
- `--exp spec_log=1 --draft-log F` writes `F.tk`: the target's top 8 *final* probabilities for sampled,
  non-suffix accepted rows only. It is not teacher-forced and not raw logits.

**The teacher-forced path that exists: the quality gate.** Code: include/basalt/program/ppl_gate.hpp,
generate.cpp:7258-7260/7287/7315-7326/8496-8507.
- Engine flags `--ppl-base BASE.kld --ppl-out ROWS.tsv`.
- A request `GEN <n_ctx-1-n_ctx/2> ppl=K ppl_t=T <ids>`. The ids must be chunk K's first `n_ctx/2+1` tokens.
- The rest of the chunk is forced through verify windows of T tokens: temperature 0, every token committed, no
  drafter or suffix use. T is clamped to the engine's window size; `--spec 0` gives T=1.
- Every row from position `n_ctx/2` to `n_ctx-2` is scored against the base. One line per row:
  `chunk pos target nll nll_base kld same_top top top_base dlogp`.
- `BASE` is llama.cpp's `--kl-divergence-base` format:
  - header `"_logits_"`, u32 n_ctx, i32 n_vocab (248320), i32 n_chunk;
  - then `n_chunk*n_ctx` int32 tokens;
  - then per chunk `n_ctx-1-n_ctx/2` rows of `(f32 scale, f32 min, n_vocab u16 padded to even)`.
- `basalt-bench --quality N --kld-base BASE --logs DIR` drives the same thing. It sets `--spec 5 --spec-min-p 0.7`,
  adaptation off and `--resident-experts`, and leaves `DIR/rows.tsv`.

**To get top-64 logits on fixed positions:**
1. Apply this small patch, which adds `--exp ppl_top=K`. It writes `ROWS.tsv.top` with one line per scored row:
   `chunk pos target lse id:logit ×K` (raw logits, best first).
2. Feed a synthetic base built from our own tokens. Its log-probs are dummies, so `kld` and `nll_base` are
   meaningless, but `nll`, `top` and the `.top` file are real.

Layout constraint: a chunk is n_ctx tokens. The prompt is the first `n_ctx/2+1`; the scored rows predict the last
`n_ctx/2-1` tokens. So a prompt of P tokens needs a forced continuation of P−2 tokens; pad or trim the continuation
to fit. Combine with `--exp exact_head=1` for exact Q6_K logits, or leave it out to see the two-stage logits Basalt
really samples from.

```diff
--- a/include/basalt/program/ppl_gate.hpp
+++ b/include/basalt/program/ppl_gate.hpp
@@ -6,6 +6,7 @@
 // A serve request with `ppl=K` reads chunk K's first half as its prompt and then teacher-forces the rest through
 // the verify windows; every scored row is compared with the base row here and written as one line to
 // --ppl-out: chunk pos target nll nll_base kld same_top top top_base dlogp_top_base.
+#include "basalt/core/diag.hpp"
 #include "basalt/platform/file.hpp"
 
 #include <algorithm>
@@ -68,6 +69,7 @@
     bool finish(std::string& err) {
         const bool ok = wait(err);
         std::fflush(out_);
+        if (top_ != nullptr) std::fflush(top_);
         basalt::platform::advise_dontneed(fd_, 0, 0);   // the rows this chunk read need not stay cached
         return ok;
     }
@@ -100,8 +102,12 @@
             std::fprintf(stderr, "basalt ppl: cannot write %s\n", out);
             close_fd();
         }
+        // --exp ppl_top=K (debug): each scored row's K largest raw logits, to --ppl-out's path + ".top"
+        top_k_ = (int) basalt::core::exp_flag("ppl_top", 0);
+        if (out_ != nullptr && top_k_ > 0) top_ = basalt::platform::open_file_utf8(paths().second + ".top", "ab");
     }
     ~PplGate() {
+        if (top_ != nullptr) std::fclose(top_);
         if (out_ != nullptr) std::fclose(out_);
         close_fd();
     }
@@ -141,6 +147,18 @@
         for (int64_t i = 0; i < V; ++i) sum += std::exp(lg[(size_t) i] - maxv);
         const float lse = maxv + (float) std::log(sum);
         const int32_t tgt = tok_[(size_t) pos + 1];
+        if (top_ != nullptr) {   // chunk pos target lse, then id:logit for the K largest raw logits, best first (ties: lower id)
+            const int k = (int) std::min<int64_t>(top_k_, V);
+            std::vector<int32_t> ord((size_t) V);
+            for (int64_t i = 0; i < V; ++i) ord[(size_t) i] = (int32_t) i;
+            std::partial_sort(ord.begin(), ord.begin() + k, ord.end(), [&](int32_t a, int32_t b) {
+                return lg[(size_t) a] > lg[(size_t) b] || (lg[(size_t) a] == lg[(size_t) b] && a < b);
+            });
+            std::fprintf(top_, "%d\t%lld\t%d\t%.9g", chunk_, (long long) pos, tgt, (double) lse);
+            for (int i = 0; i < k; ++i)
+                std::fprintf(top_, "\t%d:%.9g", ord[(size_t) i], (double) lg[(size_t) ord[(size_t) i]]);
+            std::fputc('\n', top_);
+        }
         const double nll = lse - lg[(size_t) tgt];
         const double nll_base = -(scale * b[tgt] + min_lp);
         double kld = 0.0;
@@ -159,6 +177,8 @@
 
     int fd_ = -1;
     std::FILE* out_ = nullptr;
+    std::FILE* top_ = nullptr;   // --exp ppl_top=K
+    int top_k_ = 0;
     int64_t n_ctx_ = 0, n_vocab_ = 0, n_chunk_ = 0, row_u16_ = 0;
     int chunk_ = -1;
     std::vector<int32_t> tok_;
```

Synthetic base writer (our own script, nothing from the tree):

```python
# make_base.py CHUNKS.json OUT.kld   (CHUNKS.json: [[n_ctx ids], ...], all the same length)
import json, math, struct, sys
chunks = json.load(open(sys.argv[1])); V = 248320; n = len(chunks[0])
assert all(len(c) == n for c in chunks)
rows, row_u16 = n - 1 - n // 2, 2 * ((V + 1) // 2) + 4
with open(sys.argv[2], 'wb') as f:
    f.write(b'_logits_' + struct.pack('<Iii', n, V, len(chunks)))
    for c in chunks: f.write(struct.pack(f'<{n}i', *c))
    row = struct.pack('<ff', 0.0, -math.log(V)) + bytes(2 * (row_u16 - 4))   # a uniform dummy row
    for _ in range(len(chunks) * rows): f.write(row)
```

Each row is ≈0.5 MB, so a 1024-token chunk is about 254 MB.

Running it:
1. Start the engine: `HOME=... BASALT_CACHE=... CUDA_VISIBLE_DEVICES=0 CUDA_DEVICE_ORDER=PCI_BUS_ID
   src-headcheck/bin/basalt --serve --model PACK --ppl-base B.kld --ppl-out R.tsv --exp ppl_top=64[,exact_head=1]
   --expert-cache auto --prefill auto --kv int8 --resident-experts --max-context <n_ctx+64> --spec 0
   --adapt-swaps 0 --pcie-frac 0`.
2. Wait for `READY` on stdout.
3. Write `GEN <n_ctx-1-n_ctx/2> ppl=0 ppl_t=1 <first n_ctx/2+1 ids of chunk 0, comma separated>`.
4. Read until `DONE`, then send `QUIT`.

The same protocol is in docs/precision/builds.md:189-201.

---------------------------------------------------------------------------------------------------------------------

## 8. basalt-bench (src/program/bench_main.cpp)

**It starts its own engine** (`<engine> --serve <args>`, lines 216-240) and talks to it over GEN/DONE. There is no
server, chat template or tokenizer: the fixtures are pre-tokenized ids from `data/bench/*.ids` (`--fixtures DIR`,
default `src/data/bench`).

**Usage:** `basalt-bench --model PACK [-t conv,struct,prose] [-p 16384,...] [-r N] [--spec N] [--spec-min-p P]
[-o md|json] [--logs DIR] [--power-label W] [--no-windows] [--set "F V ..."] [any other --engine-flag [value]]
[-- engine args]` (usage at 351-405, parse 506-575).
- Built in (830-832, 856-866): `--spec 0` unless given; `--spec-min-p 0.5` when spec ≥ 2; `--max-context` sized to the
  fixtures (max(4096, ids + max_new + 16); about 8306 for struct, about 16.7K with `-p 16384`).
- `--peer-device 1` is added when more than one GPU is visible (816-817).
- **It does not add** `--expert-cache`, `--prefill`, `--kv` or `--resident-experts`. Their speed runs used
  `--spec 7 --spec-min-p 0.5 --kv int8 --vram-reserve-mib 500 --resident-experts [--peer-exclusive]`
  (features.md:360-362). The pack's profile makes the expert cache auto anyway.
- **GPU selection:** none of its own. Use `CUDA_VISIBLE_DEVICES=0 CUDA_DEVICE_ORDER=PCI_BUS_ID`. Power and clocks
  come from NVML device 0, which is the 5080 here (`nvidia-smi -i 0` fallback, 1079-1081). Pass
  `--power-label 360`.
- A calibration run like theirs, on our card:

  ```sh
  CUDA_VISIBLE_DEVICES=0 CUDA_DEVICE_ORDER=PCI_BUS_ID HOME=.../home BASALT_CACHE=.../home/cache \
    src/bin/basalt-bench --model models/Qwen3.8-FN-GSQ-RCO-IQ3_S.basalt -t conv,struct,prose -r 3 \
    --spec 7 --spec-min-p 0.5 --kv int8 --vram-reserve-mib 500 --resident-experts --expert-cache auto \
    --prefill auto --power-label 360 -o json --logs logs/bench-r1
  ```

**What it prints.** A markdown table `| test | t/s | accept % | draft len |` with mean ± sd over `-r` (1134-1175),
or JSON (1176-1290) with per-run `tok_s`, `tokens`, `decode_ms`, `drafted`, `accepted`, `acceptance_pct`,
`tokens_per_pass`, `mean_draft_len`, window stats from its own `--draft-log`, `verify_ms_by_t`, clocks and `checksum_ok` (struct).
- **tok/s** = `generated / decode_ms` from the engine's DONE line (697). `generated` counts every emitted token:
  accepted drafts, the per-window target token, the first token and the EOS token.
  `decode_ms` runs from before the first window (which reads the last prompt token) to the end; prefill is
  excluded.
- **accept %** = accepted / offered.
- **draft len** = offered / windows.

**"Best of several runs".** Not in the bench: it gives the mean ± sd, and with `-r` > 1 the first, cold repetition is
included. The card's "Best measured" is the maintainer's choice. The precision docs' own A/Bs took "three rounds
interleaved, the cold repetition dropped".

**Fixture definitions** (591-600, 621-626), run in the fixed order conv → struct → prose in one engine session. The
order matters because the suffix draft policy and the adaptive expert tier carry over between requests.

| fixture | ids | max_new | sampling keys sent |
|---|---|---|---|
| conv | 38 | 1200 | `temperature=0.6 top_p=0.95 top_k=20` |
| struct | 98 | 8192 | `top_p=0.95 top_k=20` (no temperature → greedy) |
| prose | 19 | 1200 | `temperature=0.6 top_p=0.95 top_k=20` |

- No min_p, no penalties, no seed (each run gets a fresh time seed).
- The engine stops at EOS (`--serve` forces `stop_eos`), so conv and prose lengths vary from run to run (≤ 1200).
- Struct is expected at 7230 tokens; otherwise "note: struct produced N tokens".
- No warm-up request.

**Exact prompt texts** (decoded from `data/bench/*.ids` with the pack's own vocab). There is no system message.
Thinking is off: rendered with `enable_thinking=False`, generation prompt added.

```
conv   (38 ids)  '<|im_start|>user\nExplain how a B-tree differs from an LSM tree, with a worked example of each. About 600 words.<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
prose  (19 ids)  '<|im_start|>user\nWrite an essay on the Odyssey.<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
struct (98 ids)  '<|im_start|>user\nOutput a JSON array of 200 objects, no prose, no fence. Keys in order: "id" (1..200), "name" ("item_"+id), "category" (cycle alpha,beta,gamma,delta), "value" (id*7), "active" (true if id even), "tags" (["t1","t2"]). Start with [ end with ].<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
prefill: line0 '<|im_start|>user\nDocument:\n' + 4 random ids (1000..150000) + body (16647 ids of /etc/services text, cut or repeated to the depth) + '\n\nIn one sentence, what is this document?<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
```

Special ids: `<|im_start|>` 248045, `<|im_end|>` 248046, `<|endoftext|>` 248044, `<think>` 248068,
`</think>` 248069. The ids end `248068,271,248069,271`.

**Reproducing on Strata through the OpenAI API.**
- Request: `messages=[{"role":"user","content":<text between "user\n" and "<|im_end|>">}]`, thinking off
  (`chat_template_kwargs.enable_thinking=false`), no system message.
- Check `usage.prompt_tokens` is 38, 19 and 98; better still, compare the ids if Strata can tokenize.
- Sampling as in the table above (top_k 20, top_p 0.95, min_p 0, no penalties; struct temperature 0); `max_tokens`
  1200, 8192, 1200; stop at EOS.
- For Basalt itself over HTTP, the same messages with `"chat_template_kwargs": {"enable_thinking": false}`
  reproduce these ids (template identical; no effort line when thinking is off).
- Compare decode-only tok/s with the first token included. That is Basalt `timings.predicted_per_second`; make
  Strata's number the same definition.

---------------------------------------------------------------------------------------------------------------------

## 9. Other things for a fair speed comparison

**Hardware gap.** Their table is a 400 W RTX 5090 plus a 5060 Ti peer tier (experts and prompt rows on the second
card). Ours is the 5080 alone at 360 W, and Basalt cannot use the 4060 Ti (cc 8.9). The bench warns if the power
limit changes during a run (989-991).

**CPU.**
- Pool workers default to every physical core except the host's (pool.cpp:69-80); that is 15 on the 9950X3D.
- They are pinned one per physical core (`--pool-affinity all`).
- The host loop is pinned to core 0 and busy-spins `_mm_pause` while waiting on the GPU (verify.cpp run()).
- So decode keeps all 16 cores busy, and background jobs compete.
- Prefill also uses the pool (`--prefill-cpu-share 0.6`).
- `--pool-workers N` and `--pool-affinity auto|p-cores` exist.

**Startup cost.** It reads about 47 GiB of experts unbuffered (O_DIRECT) into the pinned RAM copy at start. Expect
minutes; the server waits up to 900 s for READY (process.py:46).

**PLE table.** 26.8 GiB, read per token from the SSD with O_DIRECT (`--ple-io direct`, 256 in flight, 90 MB row
cache). Decode speed depends on the disk and on concurrent disk load. `--ple-io mmap` uses the page cache;
`--ple-io ram` locks 26.8 GiB, which together with the expert copy would breach our 12 GB floor — don't use it.

**Warm-up and adaptation.**
- The adaptive tier swaps up to 96 experts every 4 windows (decay 0.93). Early requests run before residency has
  adapted.
- The prompt path lends cache slots and refills them after each long prompt.
- Elastic KV moves slots for prompts longer than 16K.
- Do one or two warm-up requests per arm, and alternate arms (ABBA).

**Suffix (prompt-lookup) drafting.** On by default (`--suffix-draft 3`; windows up to 8). It helps repeats such as
JSON, code and quoted text. Turn it off with `"suffix-draft": 0` if Strata has no equivalent, or keep it on as part
of "the engine".

**Prefix reuse.** `prompt-cache` 6, `prompt-cache-every` 16384 and `prompt-cache-root` 2048 save checkpoints in RAM,
about 118 MB each. See §0.3 for prefill arms.

**Server overhead.** A telemetry thread samples NVML and psutil every second (serve/util/telemetry.py:236-249). The
engine sets its own `oom_score_adj` to 1000 (platform/system.cpp:116-117), so it is the preferred OOM victim.

**Files written outside basalt-ab.**
- `$BASALT_CACHE/<hash>/` (tokenizer, engine.log; plus vision files only if vision is on), else `~/.cache/basalt`.
- `basalt-bench` uses `/tmp/basalt-bench-<pid>/` (engine.log, draft.log, rows.tsv) and removes it at exit, unless
  `--logs DIR`. `/tmp` is hard-coded on Linux; TMPDIR is ignored (platform/file.cpp:228-230).
- Vision modes use `tempfile.mkdtemp("basalt-vision-")`; not with vision off.
- Python writes `__pycache__` into `src/serve` and `src/tools` unless `PYTHONDONTWRITEBYTECODE=1`.
- `--draft-log`, `--expert-profile-save` and `--ppl-out` write only where told.
- Nothing goes to `~/.config`, and nothing reaches the network at serve time; the only outbound path is an image
  URL in a request.

**Spec semantics vs Strata.**
- Basalt `--spec 7` = 6 MTP drafts per window (7 with a suffix window). Make the Strata arm propose the same number
  of drafts.
- Basalt drafts are the draft head's argmax; `--coupled-draft` is off.

**Tool-call and stop behaviour** may differ in the server: the 256-repeat stop and the `</think>` injection.
Thinking-on arms should send `reasoning_effort` explicitly on both engines.
