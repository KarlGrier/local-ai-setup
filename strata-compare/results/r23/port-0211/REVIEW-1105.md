# v0.2.11 port (r23-port0211): independent semantic review, 2026-11-05

Scope: the 28 local commits on v0.2.10 (`r22-port0210`) and on v0.2.11 (`r23-port0211`). I compared them commit by commit
(`git range-diff`: the patch text is the same in every commit; only the hunk context `main` -> `_main` in server.py, the
app.js conflict and the new test stub differ). For every file both sides touch I read upstream's 0.2.10 -> 0.2.11 diff
around the hunks and the callers, and checked P0211x.json's pins and flags against their read sites in both trees.
Read-only: nothing was edited, built or committed, and no GPU or engine was used. I ran four sets of existing pure CPU tests
with TMPDIR set to `work/r23/scratch-review0211/tmp` and `-B` (both worktrees are still clean): `tools/test_iq_pack.py` on
r23, stock v0.2.11 and r22; the serve node tests with `/home/USER/.unsloth/node/bin/node` (v24.18.0); `node --check app.js`.
I also read the GGUF header with `scratch-review0211/gguftypes.py` and `ggufkv.py`, which are header-only readers.

**Overall:** I found no exactness or speed change on the engine path P0211x runs. Upstream's 0.2.11 engine changes are
startup, layer-split, HIP and PCIe-rule code. On our single-card + helper-cache path, every one of them is held off by
`STRATA_DEFAULTS=026`, `STRATA_SPILL_OFF=1`, `STRATA_MTP_KEEP=1`, the explicit `--prefill auto:16384` /
`--vram-reserve-mib`, or the absence of `--batch` / `--layer-split`. I did find two real problems: a test regression the
gate cannot see, and a gap in the new #3961 safety net that our web-search path opens.

---

## 1. Wrong behaviour

### 1.1 Web search hides v0.2.11's #3961 lost-answer guard (commit 4 `0043e3b7f` × upstream c30aa6475 / a8767488c / 74f390538)
- **Where:** r23 `serve/server.py:6907-7006` `run_with_mcp` (r22 `:6584-6683`, unchanged); the routing is r23 `:8694`
  (r22 `:8351`), `run = run_with_mcp(svc, hub, ...) if extra`; the new guard is r23 `:7245-7255` in `openai_chunks`.
- **What upstream changed:** `openai_chunks` now treats a run that ends without its `("done", ...)` event as an error. It
  prints the lost-answer line, ends the engine through `end_engine_if_unchanged` / `end_for_restart` (r23 `:5472`, `:2984`)
  so the two sides are back in step, and raises `EngineDied`.
- **What our patch makes of it:** every request with the Web search switch on goes through `run_with_mcp`. That
  function always yields its own final done, so the guard never sees a lost inner done:
  - **Round 1:** `done` is still `None`, so `total += done["completion_tokens"]` (`:6943`) raises `TypeError`. No handler
    catches it (the stream handler catches only OSError, EngineDied, QueueWaitExpired, StructuredOutputError and
    ValueError). The stream is cut without `[DONE]`, nothing is logged, and the engine is not restarted.
  - **Round 2 or later:** the previous round's `done` is reused (finish "stop", its tokens counted twice). The client gets
    an empty round as a normal answer, and `answered_done=True` keeps the guard quiet.
- **How the port record reads it:** PORT.md says "run_with_mcp ... one done after the loop on every path ... so the check
  only fires on a real loss". That is true, but it also hides real losses on this path.
- **Severity:** latent. `Service._run` has no return-without-done path today (only exceptions), but #3961 shows upstream
  saw one in the field.
- **Fix (do not apply):** set `done = None` at the top of each `while True:` round in `run_with_mcp`, and after the
  inner `for`, `if done is None: return` (no final done: `openai_chunks`' own #3961 path then runs). That is 2 lines.
- **Test:** a fake `svc.run` that yields events but no done in round 2, with `openai_chunks(..., run=run_with_mcp(...))`
  expected to raise `EngineDied`.

### 1.2 Upstream's new iq_pack tests fail on the port (commit 10 `9d64da88a`, #619)
- **Where:** r23 and r22 `tools/iq_pack.py:445` reads
  `nextn = int(model.files[0].metadata.get("qwen4exp.nextn_predict_layers", 0) or 0)`.
- **What upstream changed:** v0.2.11 added `V31HeaderOnlyLayoutTests` (`tools/test_iq_pack.py:723`), which calls
  `expert_layout` with a `Model.__new__(Model)` that has only `.where`, and no `.files`.
- **Consequence:** `AttributeError`, so the 3 new tests (8 errors counting subtests) fail on r23. They pass on stock
  v0.2.11 (`strata-v0211stock`, run here: OK, skipped=4). The r22 tree does not have these tests.
- **Production:** unaffected. `Model(first)` always sets `files`, and our GGUF has no `nextn_predict_layers` key
  (`block_count = 48`, experts in blk 0-47).
- **Why the gate misses it:** the gate runs only `serve/` tests.
- **Fix:** `files = getattr(model, "files", None)`, then
  `nextn = int(files[0].metadata.get(...) or 0) if files else 0`.
- **Test:** `python -B tools/test_iq_pack.py V31HeaderOnlyLayoutTests`.

## 2. Exactness risk: none found (checked)
- **Pins:** all 45 env keys of P0211x.json have read sites in r23. Their read-site lines are identical in r22 and r23,
  except these:
  - `STRATA_DEFAULTS` gains 11 readers (NV KQ, NV chunk, PCIe rules, stage `late_alloc`, DFlash2 stage term). Each one
    is off under 026.
  - `STRATA_SPILL_OFF` goes from 4 to 13 readers, all `== nullptr` checks, now also covering the layer-split walk.
  - `STRATA_MTP_KEEP` goes from 3 to 5 readers, adding the split DFlash2 drop.
  - The two new PCIe keys and the two server keys.
  - The only env vars new in 0.2.11 are `BLOCKING_CONSOLE, GFX12_RING, NV_CHUNK, NV_KQ_DEFAULT, PCIE_K_RULE,
    PCIE_SHARE_MAX, PF_OWN_PROBE_OFF, SPLIT_EARLY_OFF, STREAM_WRITE_TIMEOUT_S`.
- **PCIe pins are identities:** `pcie_pool_k(r, false)` = 1.85 = 0.2.10's `kPoolFactor`, and `atof("0.60")` clamped =
  0.60 (generate.cpp:2715-2722).
- **NV chunk:** `--prefill auto:16384` sets `prefill_auto_bare=false` (generate.cpp:3559-3560), and 026 returns 0 anyway
  (:3901).
- **NV KQ:** `apply_nv_kq_default` (:3887) runs on our mixed sm_120 + sm_89 cards, but returns nothing under 026.
- **Unpinned 0.2.11 defaults that cannot reach us:** FP16 weight cache (`--batch >= 2` only), `uma_refuse_chunk_if_full`
  (HIP only), the gfx12 ring (HIP only).
- **Q5_0 dot (aa678f10d, iq_kernels.cu:444):** no tensor of ours uses it. The GGUF header has no Q5_0; the experts are
  IQ2_S / IQ3_S / IQ3_XXS / IQ4_XS gate/up and Q2_0 / IQ4_NL down. The MTP `rt/experts.bin` is 2.25 bpw.
- **Serve loop and GEN keys:** the serve decode loop, `verify.cpp`, `mtp.cpp`, `sampler.cu`, `fused_gr.cu`,
  `elementwise.cu`, `moe_fused*.cu` and `expert_source.cpp` are byte-unchanged upstream. The GEN keys the server sends
  are the same set. The `conversations.clear()` / `nan_flush` sites that commit 12 mirrors are the same 2 / 9.
- **Robustness note:** NV_KQ, NV_CHUNK, PCIE_AUTO_SPLIT and late_alloc are held off only by the 026 master switch, while
  the two PCIe keys are pinned explicitly. If 026 is ever dropped, they switch on silently. See 4.6.

## 3. Speed risk
- **3.1 The #3961 restart is a new default with no switch** (server.py:2984 / :5472 / :7252). A lost answer now ends the
  engine. With `--chat-cache 16` / 12 GiB, every parked conversation and the keep=1 session go with it, and the reload
  takes about a minute. The gate only asserts that it never fires. Low risk.
- **3.2 The server pins** keep 0.2.10's behaviour (a client that stops reading holds the turn; a stuck console blocks).
  That is deliberate (OPEN item 1). If they are dropped, `NonBlockingOut` drops the OLDEST text when more than 1 MiB or
  4000 chunks are queued, so the gate's log-line checks (lost line, start lines) become best-effort under bursts.

## 4. Untested (what gap-port0211.sh / port0211_rules.py would not catch)

### 4.1 Web search end to end (commits 4, 5, 14, 15 and model_check's "web search" switch)
No arm sends `strata_web`, calls `GET /web`, or touches SearXNG / Exa / Tavily, so 1.1 is invisible to the gate.

### 4.2 Server-loop outputs vs P028x
- exact7 runs `strata generate --stats` (bringup/lib/run.sh, the CLI path). pf_yardstick runs a bare `--serve` engine
  with its own fixed settings. The screen measures speed only. chatcache_checks compares P with itself.
- So our serve-loop hunks are never output-compared with P028x: keep/tcap, the #652 `emit` commit, chat-cache park and
  unpark, the DRAFT_CUM / COST_GATE / SPEC_EXACT serve branches. They are most of our generate.cpp lines.
- Upstream did not touch that loop, so the risk is low.
- **Cheap test:** greedy `/v1/chat/completions` on B and P with 3-4 fixed prompts (one long enough for an answer_room
  continuation): token ids equal.

### 4.3 C++ parity tests for files our patches modify that build-tests does not build or run
`verify_parity`, `verify_batch_parity`, `sampler_parity`, `gr_parity`, `gr_multi_parity`, `gr_upmix_parity`,
`elementwise_parity`, `q8k_quant_parity`, `native_dense_ple_key_test`, and `prefill_fused_iq_test` without `--v2`.
Upstream did not change these sources, but nothing re-runs them on this port.

### 4.4 Gate scope gaps
- The gate runs only `serve/` tests, so upstream's tools tests (1.2) and `tests/terminal` are not run on our tree.
- The gate skips the 49 node tests. I ran them here with `/home/USER/.unsloth/node/bin/node`. `test_web_start_question`
  passes 5/5, so **the `loadWeb` stub works**. test_web_history, i18n, math, preview, sampling, load_unload, api_key,
  follow and test_speed_average are all OK. `node --check app.js` is OK. **PORT.md open item 2 is closed.**
- **Suggestion:** prepend that node directory to PATH for the gate's servetests.

### 4.5 Other paths no arm exercises
- The sampled path's distribution (Karl's list).
- The side stash (commit 1). It is always off with `--chat-cache` (generate.cpp:16700 `!chat_cache_on`).
- `/v1/responses` and `/v1/messages` with the continuation. #3961's guard exists only in `openai_chunks`.
- A stalled client or console. The pins are checked only for being present.

### 4.6 BASE_ABSENT lacks the log lines of 0.2.11's master-switch-held defaults
Add `"NVIDIA: --prefill auto may take chunks up to"` and `"reads its prompt on llama.cpp's MMQ kernels"`
(port0211_rules.py:114). Then a lost 026 shows at the start check, not only in exact7.

### 4.7 The fallback path is never exercised
In run-strata.sh `helper_check` (:63-80, `CFG=$fb` at :78), a short 4060 Ti swaps the whole config to
`Cstar18-single.json`: the v0.1.44 engine and the strata-cstar18 server. A "P0211x" start then runs neither v0.2.11 nor
our 28 (carried over from P0210x). **Suggestion:** a P0211x single-card fallback config.

## 5. Check (3): the server pins reach server.py, except in the fallback
- **How they get there:** `run-strata.sh:139` (`env "${envs[@]}" $PY $SERVER`) and `bringup/lib/srv.sh:25` (`env $ENVS`
  around guard.py and server.py). switch-model.sh, strata-ensure.sh and the research runner (through strata-ensure) all
  go through run-strata.sh.
- **Where server.py reads them:** `STREAM_WRITE_TIMEOUT_S` at import (server.py:322; 0 skips `settimeout` at :8590), and
  `STRATA_BLOCKING_CONSOLE == "1"` in the `main()` wrapper (:9901). The `__main__` block calls `main()`, not `_main()`.
- **Gate check:** envcheck verifies them in the engine's parent process.
- **Exception:** the 4.7 fallback, which starts another server.
- **Harmless details:**
  - srv.sh's unquoted `$ENVS` is fine because no value has a space.
  - `child_env` also hands both keys to the engine, which has no read site for either.

## 6. Check (1): the app.js merge and the test stub are correct
- r23 `serve/web/app.js:1616` reads `loadHealth().then(loadMcp).then(loadWeb);` (r22 `:1610` also auto-sent `/?q=`).
- `loadWeb` (:702) catches its own errors, so the chain cannot reject.
- The stub (test_web_start_question.py:60) is needed: the harness extracts only `start()`, and the real `loadWeb` calls
  `renderWeb()` on DOM nodes the fake page does not have.

## 7. Cosmetic
- **The stub's key handling:** the real `loadWeb` sends `headers()` (`Authorization` when a key is saved), the stub
  sends none. That matches upstream's own `loadMcp` stub, so the test's "nothing went out with the saved key" never
  covers either GET. PORT.md describes the stub as "(a GET, no key ...)"; the file says "(a GET, as the page's own)".
- **CMakeLists.txt:2506-2513:** our `prefill_fused_v2_test` sits above the "MoE input quantized per token" comment.
  Upstream's new `prefill_mmq_v31_test` now separates that comment from its test (upstream's misplacement, not ours).
- **Broadened meanings:** `STRATA_SPILL_OFF` and `STRATA_MTP_KEEP` now also switch off layer-split steps. The pins still
  mean "off", with no effect on one card.
- **Activity lease (#4463):** each server start creates `<state_base>/runtime/.activity.lock` outside the workspace.
  `STRATA_RUNTIME_DIR` is not set in our configs. The fd is non-inheritable and the lock is `LOCK_NB`.
