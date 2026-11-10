# Qwen port to Strata v0.2.11 (branch r23-port0211, worktree strata-r23p0211) - log, 2026-11-05

Karl 11-05: "Next port, onto v0.2.11 ... Purpose: a smaller jump when upstream adds Qwen4." Inputs: results/PORT-V0210-PLAN.md
(incl. "Next port's list - additions"), results/r22/port-0211-review.md, branch r22-port0210 (fdd2fffa8, untouched).
**Nothing pushed, installed or switched; no GPU and no engine was run.** P028x stays served. The served tree
(strata-r22p028x), every existing worktree and every existing config are untouched.

- Branch **`r23-port0211` = v0.2.11 (c3b3f5035) + our 28 commits, head `d797db9f6`** (tree df1ae8b7d3c9), in the new
  worktree `strata-r23p0211` (`git worktree add ... -b r23-port0211 v0.2.11`).
- Each commit keeps its r22-port0210 message (with its "ported to v0.2.10" line) plus one line `ported to v0.2.11: ...`.
  Author and committer KarlGrier (noreply); no Co-Authored-By or session trailer.
- Method: `git cherry-pick --no-commit` of `v0.2.10..r22-port0210` in order (3-way merges), every result checked by
  comparing the commit's changed lines with r22-port0210's (scripts in `work/r23/scratch-port0211/`: `pick.sh`,
  `commit.sh`, `dd.sh`). rerere is on in the shared repo; the app.js resolution is recorded there.
- Series check: the same 45 files as v0.2.10..r22-port0210 plus one (upstream's new `serve/test_web_start_question.py`,
  1 line); the changed lines are identical in every file except `serve/web/app.js` (the conflict) and that test.

## What conflicted

| file | our commit (r22-port0210 -> r23-port0211) | upstream commit | how resolved |
|---|---|---|---|
| `serve/web/app.js`, `start()` | #4 Web search switch (86570881b -> 0043e3b7f) | faf3db296 (#4221, in merge 50c2db690): `/?q=` only fills the box and focuses it, never sends | upstream's block, with our `.then(loadWeb)` added to its `loadHealth().then(loadMcp)` chain. The auto-send our old line carried was v0.2.10's code, not ours, so both behaviours stay: the Web search switch loads at start, and `/?q=` is never sent. None of our configs or scripts use `/?q=` (grep) |
| `serve/test_web_start_question.py` (new upstream test, no textual conflict) | #4 (same commit) | faf3db296 | the test runs the real `start()` under node on a fake page that defines `loadHealth` / `loadMcp` only; with our `.then(loadWeb)` start() would throw (ReferenceError) and the test would fail. Added one stub line `async function loadWeb() { await fetch("web"); }` (a GET, no key, as the page's own). Found by reading; **node is not installed here, so this test (and every other node test) is skipped - the stub is unexecuted** |

That is the review's forecast (1 textual conflict of the 10 files both sides changed). The other 27 commits applied clean;
16 of them 3-way-merged files upstream also changed (1-3, 11-13, 16-17, 20, 23-27: generate.cpp, server.py, frontend.py,
test_server.py, test_tool_corpus.py, CMakeLists.txt, qsa_prompt_attn.{hpp,cu}, prefill.cpp), each with its changed lines
identical to r22-port0210's. Semantic reads of those merges:
- **server.py / #3961.** v0.2.11's `openai_chunks` turns a run without its done event into an error and may end the
  engine. Both our run paths end every admitted run with exactly one done: `Service.run` (continuation fix) and
  `run_with_mcp` (the Web search hub uses it unchanged: one `("done", ...)` after the loop on every path, cancel and the
  round limit included). So the check only fires on a real loss. The gate checks it live (`lost_answers`).
- **frontend.py.** 3bbf0f399's `_close_verdict` "hold" (#4701) merged next to our think-fence hold; the server tests and
  the gate's `fence4` cover the pair.
- **generate.cpp.** Upstream's hunks are start-up / PCIe-rule / layer-split spill-walk code (all but the PCIe rule behind
  `multi_gpu`); ours are the serve / CLI decode loops and the patch guards. The guards still run before any of our
  switches is read.

## The list's items (PORT-V0210-PLAN.md "Next port's list")

**All four code items are already in v0.2.11** (`git merge-base --is-ancestor`), so they arrive with the base; **no extra
commit was needed or added**. Each was checked to have survived the merge:

| item | in v0.2.11 | check |
|---|---|---|
| Serve fix #3961: c30aa6475 + a8767488c + 74f390538 | yes | `openai_chunks` `answered_done` + `EngineDied`, `StrataEngine.end_for_restart`, `Service.end_engine_if_unchanged`, `died_note` at the five handlers are all in the merged server.py; upstream's 10 `OpenAIChunksTerminal` tests pass (verbose run, `scratch-port0211/servefix-v.txt`) |
| Q5_0 expert dot aa678f10d | yes | iq_kernels.cu is not in our 28; the fixed dot is at iq_kernels.cu:438-470. GPU parity runs in the gate (INFO; our IQ3_S file has no Q5_0 tensor) |
| Picture-format whitelist 8181522f1 | yes | `PICTURE_FORMATS` at both `Image.open` sites of server.py's vision path and in ds_pictures.py; our patches add no other `Image.open`. Its tests pass (test_ds_pictures, test_exif_orientation incl. the JPEG 2000 refusal). `.venv` already has Pillow 13.0.0 (gap-decpath step 1b, Karl 11-05) |
| app.js conflict | - | resolved above |

**The pins and keys** (as the v0.2.10 port did them: in the config, `configs/P0211x.json`, made by
`work/r23/scratch-port0211/make_configs0211.py` from P0210x.json, which was not edited):
- the 14 pins of P0210x + `STRATA_PCIE_SHARE_MAX=0.60`, `STRATA_PCIE_K_RULE=0` (engine; both are the 026 values already:
  `pcie_share_ceiling` / `pcie_k_rule_default` return 0.60 / off under `qwen_defaults_026()`, and `atof("0.60")` is the
  0.60 constant, so the pins are identities) + `STRATA_STREAM_WRITE_TIMEOUT_S=0`, `STRATA_BLOCKING_CONSOLE=1` (server
  process, **OPEN**, below);
- `"drafting": "mtp"` and `"user_args": ["--kv-resident", "32768"]`, as P0210x;
- exe `engine-r23p0211/strata`, server `strata-r23p0211/serve/server.py`, log `logs/engine-P0211x.log`; everything else
  as P0210x (port 8081, fallback Cstar18-single).
- **Why the server pins sit in the config's env:** both of our launchers start server.py with the config's env as its own
  environment (run-strata.sh `do_start`: `env "${envs[@]}" $PY $SERVER`; bringup/lib/srv.sh: `env $ENVS ...`), and
  server.py reads both from `os.environ` (:322 at import, :9901 in `main`). The review's note ("the launcher's
  environment, not the config env") holds for server.py itself, but our launchers make the config env the launcher env.
  `child_env` also hands them to the engine, which has no read site for either. No launcher was edited.
- Not added (optional no-ops for us, review section 0): `STRATA_NV_CHUNK=0`, `STRATA_NV_KQ_DEFAULT=0`.
- Test configs (new): `P0211x-h` (no pictures, no fallback), `P0211x-h-off` (our six switches and `--chat-cache` off),
  `s0211-h` (stock v0.2.11 with -off's args and env), `P0211x-h-nov2`, `P0211x-RTpin-vision`.

## Build and tests

`work/r23/build-port0211.sh engine|tests|stock` = build-port0210.sh's flags (Release, CUDA 13.3 V13.3.73, arch "89;120",
the shared llama.cpp checkout at the pinned ggml 3cf03257f - v0.2.11 pins the same one as v0.2.10, 8-row windows), each
under `work/r23/nogap-run.sh` (nice 19, frozen while a gap is open), chained by `scratch-port0211/build-retry.sh`.
- **Memory beside a serving 8080.** With P028x and a research run on 8080, MemAvailable sits at ~21.5-25 GB, close to
  the research queue's 20 GB relief restart. build_memguard.sh (pause < 24, resume > 32, stop < 14 GB) was written for
  builds with Strata stopped: its resume point never comes here and its stop is below the relief restart. So the build
  has its own guard: ninja paused (no new jobs) < 23 GB, resumed > 23.5 GB; the running compilers frozen < 22 GB, thawed
  > 22.75 GB; the build stopped < 21 GB (1 GB above the relief restart), then continued (RESUME=1, ninja redoes every
  unfinished step) once MemAvailable is back above 23.5 GB. 2 jobs. Log: `logs/r23/build-port0211-memguard.log`.
  (A first attempt with 8 jobs was stopped by hand after the commit-4 test fix; a second, with build_memguard's 24 GB
  pause, stalled.)

| build | result |
|---|---|
| `engine-r23p0211/strata` (tests OFF, `strata-r23p0211/build`) | **built 13:36**, sha256 `29a9f7886aca...`; SOURCE "v0.2.11 + 28 commits (branch r23-port0211 d797db9f6...), tree df1ae8b7d3c9; nvcc 13.3.r13.3/compiler.38244171_0; jobs 2"; configure log: verify windows hold up to 8 rows. The same 27 warning kinds as the v0.2.10 port's build (none new; mostly nvcc #128-D "loop is not reachable") |
| `strata-r23p0211/build-tests` (tests ON) | **built 13:54**: patch_guard_test, cost_gate_test, draft_cum_test, spec_prob_test, gated_proposal_test, spec_verify_parity, spec_proposal_parity, prefill_fused_iq_test, native_expert_parity; 8-row windows |
| `engine-v0211stock` (detached worktree `strata-v0211stock` at v0.2.11, made by the script; the gate's release reference) | **not finished**: 109 of 170 steps when a gap opened (14:15, the series' next gap). It continues on its own: a detached `nogap-run.sh` (pid 1563763, log `scratch-port0211/build.log`) waits while the gap is open, then resumes it (RESUME=1) under the same guard. The gate refuses until engine-v0211stock/SOURCE + SHA256 exist |

**Unit tests run now (CPU only, under nogap-run, `CUDA_VISIBLE_DEVICES` empty):**
- patch_guard_test (GGUF + MTP) rc 0 "0 failures"; cost_gate_test rc 0; draft_cum_test rc 0; spec_prob_test rc 0 "72 cases,
  0 failed"; gated_proposal_test rc 0 (266 checks) - `scratch-port0211/cputests/`.
- Server suite (`unittest discover`, gap 17's form): **1462 tests, 1 failure = test_hip_ordinal** (the known one: it reads
  this PC's KFD iGPU; also failed on stock 0.2.7 / 0.2.8 / in gap 17), 49 skipped (node) - `scratch-port0211/servetests.txt`.
  The serve fixes' own tests verbose: 43 ran, OK (5 node skips) - `servefix-v.txt`.
- fence4 (the four-backtick think-fence check on the port's parser): PASS.

**GPU tests, skipped now (they run in the gate's gap):** spec_verify_parity, spec_proposal_parity (upstream's sampler
parity), prefill_fused_iq_test --v2 --no-timing (our v2 kernels' bit-identity), native_expert_parity --synthetic on
iq2_s/q5_0, iq3_xxs/q5_0, iq2_s/iq4_nl, iq3_xxs/iq4_nl, iq2_s/q2_0, iq4_xs/iq4_nl (the Q5_0 dot; INFO).

## Unresolved / open

1. **Server pins (Karl):** `STRATA_STREAM_WRITE_TIMEOUT_S=0` and `STRATA_BLOCKING_CONSOLE=1` keep the old behaviour
   (a client that stops reading holds the turn; the server's print blocks). Accept v0.2.11's defaults (60 s write
   timeout, the bounded console queue) as serve fixes instead? Then the two keys leave P0211x*.json and
   `port0211_rules.py` `PINS` / `SERVER_PINS`.
2. **The #4221 node tests are not run here** (no node; 49 node tests skipped in the suite, as in gap 17), so our
   `loadWeb` stub in `test_web_start_question.py` and the app.js resolution are checked by reading only (no JS syntax
   check either). A browser look at the chat page (Web search switch present, `/?q=` fills the box) is the cheap check.
3. **The activity lease (#4463)** comes with v0.2.11's `server.py main`: the server takes a shared lease in Strata's
   runtime folder (`strata_control.runtime`) and never fails on it. It only matters for `strata update`, which we do not
   use; left as upstream wrote it.
4. **Not in the gate (Karl's list):** check (2) in 1-token windows and checks (1) + (2) on the speculative path. They
   need MEASUREMENT twins of this port (the 5 commits of r22-port0210-meas, not ported). v0.2.10 -> v0.2.11 has no diff in
   the sampler, verify, MTP or serve decode loop, but Karl's switch conditions want them before any switch. A trial
   (`git merge-tree`, no ref written): the 5 commits merge onto r23-port0211 without a conflict, and the stock twin's 5
   onto v0.2.11 too (textual only).
7. **engine-v0211stock is still building** (see Build): until it exists the gate refuses at its pre-gap check.
5. Carried from the v0.2.10 port (unchanged): on a HIP build ours and upstream's `serve_stop_bound` both run; gap 17's
   Basalt baseline FAIL (struct decode -2.4 %, blend -2.5 % vs P028x) is unexplained - the gate runs the v0.2.10 port
   beside it on the decode fixtures (INFO) to separate the two ports.
6. The build ran beside a serving 8080 (Karl 11-05's nogap rule), so `build_memguard.sh`'s resume point (32 GB) could
   never come; the build used its own guard (below). Not a numerics question: the flags are build-port0210.sh's.

## The gate: `work/r23/gap-port0211.sh` + `work/r23/port0211_rules.py` (written 11-05, not run)

**Not added to `work/r23/gap-series.sh`; no `.ready` file.** Run as `bash work/r23/gap-port0211.sh` (no arguments, all
paths absolute; snapshot-copy safe). Output: `results/r23/port-0211/gap/` (summary.txt, gates.txt, decision.txt). The
rules (fixed before any run) are the rules file's docstring: gap 17's baseline for v0.2.11, no gated switch (every new
v0.2.11 default is pinned off).

What it measures (arms: B = x28h = P028x, P = P0211x-h, P10 = P0210x-h for INFO):
- **Before the gap** (no GPU, 8080 serving; refusals as the r23 drivers: locks, a foreign model server, 8081, kwatch, a
  missing or unrecorded engine/config, < 20 GB free): build gates (engine SHA = SHA256 file, SOURCE head = worktree head,
  stock = v0.2.11, the 9 test binaries, 8-row windows), the 18 pins + 2 keys, and the CPU tests at nice 19 (ours:
  patch_guard / cost_gate / draft_cum; upstream's spec_prob / gated_proposal; the server suite with
  `KNOWN_SERVE_FAILS` = test_hip_ordinal; fence4). A failure here refuses: the gap is not opened.
- **In the gap:** the GPU unit tests (spec_verify_parity, spec_proposal_parity, prefill_fused_iq_test --v2; Q5_0 parity
  INFO); exact7 at pin 2500 - release first (P-off = stock v0.2.11), P = P028x (if not: stock 0.2.8 vs stock 0.2.11
  decides as in gap 17), repeat, v2 on = off, and P vs gap 17's stored v0.2.10 port (INFO); pf_yardstick long40 with
  kernel_rule2 + kernel_rule3 against gap 8's references, logit files vs x28h / p210 (INFO); the 9-workload screen, 3
  passes in turned order, **g16's rule + Karl 11-03's per-workload no-loss (P vs B)**; Basalt's cold fixtures (M, H:
  decode / 16K / 64K, g16's rule; P10 decode INFO); the served form (chat cache + a picture through PICTURE_FORMATS);
  the live tool-call test B vs P; lossless; **#3961's lost-answer line in no server log of the port**; start lines
  (also absent: the no-drafter retry, the lost-answer line); every arm's env check, now including the engine's parent
  server.py and its server pins; no fatal line; no foreign GPU user before or during an arm (the 11-05 DeepSeek lesson);
  the settled PCIe share per arm-pass (INFO).
- **Many-positions NLL: INFO only** (Karl 11-05, the bound is revoked): one score.py arm on P (only if 9 min fit), then
  after the gap its byte identity with and its compare against the NLL gap's x28h / x28h-unfused / x28h-cpushare.
- Verdict: BASELINE PASS / BORDERLINE (only g16's speed rule borderline) / INCOMPLETE / FAIL. A PASS makes r23-port0211
  the checked base for the next port; nothing switches.

**Time with 8080 down: about 100 min** (deadline 130, `P0211_MAX_MIN`): open + memory ~2, GPU unit tests ~3, exact7 6
sets ~20 (+3 if s028 is needed), pf_yardstick ~9, screen 6 arm-passes ~22, Basalt 21 cold starts ~25, served form +
tool calls ~11, NLL arm ~5 (INFO), lossless / end ~3. Before it, with 8080 serving: ~12 min of CPU tests, then
`port_gap4.sh begin` waits for the running question. After it (CPU, nice 19): the reports and the NLL compare, a few
minutes.

Checks done (no GPU, no engine): `bash -n` on the driver and build script; `py_compile`; `port0211_rules.py selftest`
**0 failures in 23 checks** (gap 17's real screen and Basalt data through the new decide - it reproduces gap 17's verdict,
speed PASS and Basalt FAIL, and gap 17's screen also passes the added per-workload rule; every verdict class; the pins on
the real configs; start lines with an injected #3961 / retry line; `lost`; `e7cmp` on gap 17's stored runs 7/7 and
3/7); `envcheck` run read-only against the live 8080 engine with P028x.json (finds the engine by exe, its parent
server.py, ENV CHECK OK).

## Required before v0.2.11 could replace P028x (Karl 11-05; from the review results/r23/port-0211/REVIEW-1105.md)

No action now - these are switch conditions, added to the port plan. gap-port0211.sh's gate alone does NOT cover them:
1. **Web search end to end** (MCP tool rounds through `run_with_mcp`, incl. a round that ends without its end event -
   the 5f5aebcc2 fix) on P0211x, against P028x on the same prompts.
2. **Served outputs against P028x**: the same requests through the server path (not exact7's command-line path), output
   for output - so our serve-loop changes are compared too.
3. **The C++ parity tests for the files our 28 patches change** (the ~10 that build-tests does not build; list in
   REVIEW-1105.md section 4), built and run.
4. **The lost-answer guard (#3961)**: when it is tested, measure how often it fires on our workload (research runs +
   Jan chat; each firing restarts the engine and, with the chat cache on, drops every parked conversation - ~1 min
   reload), and note whether a small patch to make it switchable is worth carrying.

**Carry into any new port (Karl 11-06):** the model-mismatch guard, `work/ds-launcher/model-guard/apply_guard.py` (three small edits in `serve/server.py`) + the `model_not_running` key in the new config. Inert without the key.

## Gate result (gap 11-07 03:33-05:14) and Karl's decision (11-07)

Verdict (results/r23/port-0211/gap/decision.txt): **BASELINE FAIL, on prompt speed only.**
- **Exactness passed:** exact7 vs P028x 7/7 identical (bit for bit), 0 of 40 first-token logit files differ from gap 16's
  x28h, 27 of 27 kept-row / window-logit files identical, KL checks pass, NLL rule3 PASS.
- **Speed:** screen decode +1.34 % and prompt +0.55 % (PASS), Basalt decode / blend / 16K / 64K all PASS; **the per-workload
  no-loss rule (Karl 11-03) fails: R3-extract5k prompt -1.4 % (noise 0.2 %), R4-agent33k prompt -0.3 % (noise 0.1 %).**

**Karl 11-07:** keep it as a fail for serving; P028x stays served. r23-port0211 passed exactness and failed only on prompt
speed (-1.4 % R3, -0.3 % R4). **It stays the base for the Qwen4 day-one port; the speed fail doesn't block that.**

**After the weekend chain - find the 1.4 %, desk first (Karl 11-07):** read the prompt-path changes between v0.2.8 and
v0.2.11 that affect ~5K prompts (prefill chunking, the 32768 chunk ceiling for a bare `--prefill auto`, MMQ/KQ, the PCIe
share rule and anything else in src/prefill, the prompt kernels and generate.cpp's prompt setup), and any new default our
pins don't cover (compare v0.2.11's defaults under STRATA_DEFAULTS=026 with P0211x's 18 pins + 2 keys). Use a short gap only
to confirm the top candidate (P vs B on R3-extract5k, plus the candidate's switch). **If it's a switch, note the pin for the
Qwen4 port** (here and in results/PORT-V0210-PLAN.md's next-port list).

## The 1.4 % hunt (11-07, desk only; results/r23/port-0211/HUNT-1107.md)

**R3's -1.4 % is a measurement artifact, not the v0.2.11 prompt path.**
- R3's engine prompt time includes our chat cache parking R2's 54K conversation (commit 4036f229f, `park()` at
  generate.cpp:15314-15381; the prompt timer starts before it).
- Gap speed logs (checked by hand, gap/speed/{B,P}{1,2,3}r.englog):

  | arm | park of 54K | R3 read | R3 read minus park |
  |---|---|---|---|
  | B | 104-106 ms | 1391-1394 ms | 1287-1289 ms |
  | P | 125-126 ms | 1413-1417 ms | 1287-1291 ms |

- The park's cost has two levels on every build. Across the stored r22/r23 gap logs: 44 of 119 at 100-114 ms, 75 at
  120-139 ms. B drew the fast level 3/3, P the slow one 3/3. Gap 17's v0.2.10 port showed the same -0.77 %, passed only
  by B's noise.
- R4's -0.3 % is a ~15 ms pause outside the engine's prompt timer that moved from R1 to R4; the sum is unchanged.
- Without the park in the window: R3 -0.04 % (noise 0.27 %), R4 -0.07 % (noise 0.08 %), all 9 workloads pass.

Defaults: every prompt-path default new in v0.2.8 -> v0.2.11 is pinned, held off by 026 or by an argument, or does not
reach our setup. The exception is the dispatch counters (af6ba4c60, STRATA_DISPATCH_STATS=0 turns them off;
negligible cost). **No pin to add for the Qwen4 port.**

Confirm gap (written in HUNT-1107.md, not run; ~25 min with 8080 down; after Phase 5's queue):
- B vs P, each also with `--chat-cache 0`, R2/R3 alternated.
- Pass: P matches B with the cache off, and on engine-minus-park.

For Karl:
- (1) measure the screen's prompt without the park from now on (a rule change);
- (2) whether the 11-07 "fail for serving" stands. It does not block the Qwen4 base either way.

### Karl's decisions on the hunt (11-07)

> "1. Measurement rule: yes, as a dated amendment applying from now on. Per-workload prompt numbers exclude the chat-cache
> save. Time the save as its own line in every screen, and judge it separately against its own noise, taking its
> two-speed pattern into account, so a real regression in saving still shows.
> 2. Port verdict: put the 'fail for serving' on hold. Run the 25-minute confirmation gap (B vs P, each also with the
> chat cache off) after Phase 5's queue. If it confirms the artifact, record the port's baseline check as passed under
> the amended rule. Passing doesn't mean switching: the before-switch requirements in the port plan still apply.
> Optional, desk only: if it's cheap to find, note why the save takes ~105 ms some times and ~130 ms others. Don't spend a
> gap on it."

**Verdict status: ON HOLD** (was "BASELINE FAIL on prompt speed only"). It waits for the confirmation gap after Phase 5's
queue. Implementation of the amendment (rules code, selftests, the gap script): a helper at the desk, reported in
HUNT-1107.md.

### The amendment is implemented (11-07, helper; Claude re-ran its selftests: all 0 failures)

- **Shared code:** work/r22/g17_rules.py (new "11-07 park amendment" section, `park-selftest`). Used by
  port0211_rules.py, basalt_rules.py, ud31_rules.py and the Qwen4 kit's q4_rules.py. Every file was backed up to
  `.before-park-amend`.
- **Scope:** gates that start from 11-07 14:00 on; finished gates give byte-identical outputs.
- **The save line:**
  - each save is divided by the stored median of its level (872 stored saves; only the 1238 MiB size has two levels);
  - FAIL if P's index is above B's by more than the larger pass spread (>= 2 %), or if P has more saves above the stored
    band in >= 2 passes;
  - the fast/slow mix is INFO;
  - a size with no stored band gives NOT DECIDED on a shift.
- **The confirmation gap:** work/r23/gap-confirm0211.sh + confirm0211_rules.py.
  - Written, dry-run checked, not run, no .ready.
  - It refuses while the bench unit is active unless C0211_AFTER_P5=1.
- **The two-level save, a likely cause (unverified):** the ~28 MB K/V save buffers sit just under glibc's dynamic mmap
  threshold. So a save gets either reused heap pages or fresh pages that fault during the copy. The gap samples page
  faults to test this; a fix would be a code change (reuse the buffers), not a pin. HUNT-1107.md section 5.
- **Open for Karl:** the per-workload prompt number is now taken on the engine clock (engine prompt ms minus the save).
  Time outside the engine is INFO per workload; the aggregate g16 rule stays on the client clock minus the save (-1 %).
  On the client clock R4 would still fail (-0.29 %, the ~15 ms pause that moved from R1 to R4). So this choice decides
  whether the port can pass.

### Karl's decisions on the amendment (11-07, recorded before the confirmation gap)

> "Prompt clock: engine clock for the per-workload prompt numbers, as you recommend. The overall screen rule stays on the
> client clock minus the save, at -1%. Add one INFO flag, not a fail: if a workload's outside-engine time is worse in all
> 3 passes by more than its own spread, flag it for review, so a server-side slowdown hitting one workload can't hide
> under the overall rule. Record the amendment as dated before the confirmation gap."
> "Save buffers: if the page-fault count in the confirmation gap supports your theory, put 'reuse the chat-cache save
> buffers' in the backlog for the next config change (exactness check: output unchanged). Low priority."

**The amendment as it stands (dated 2026-11-07, applies from now on, before the confirmation gap):**
1. Per-workload prompt numbers exclude the chat-cache save and are taken on the engine clock.
2. The overall screen rule stays on the client clock minus the save, at -1 %.
3. The save is its own line, judged against its own two-level noise.
4. INFO, never a fail: a workload whose outside-engine time is worse in every pass by more than its own spread is
   flagged for review.

The INFO flag and the dated text are being added to the rules files by the helper (the same backup / mv / selftest
rules).

**After the confirmation gap:** if its page-fault counts support the glibc mmap-threshold theory, add "reuse the
chat-cache save buffers" to results/BACKLOG-1027.md H (next config change, low priority; exactness check: output
unchanged).

## Confirmation gap result (2026-11-09 07:12-07:42, post-Phase-5 chain step 1; 28 min with 8080 down)

Log: results/r23/post-p5-chain.log (and results/r23/port-0211/confirm/). Rules: confirm0211_rules.py, sha 817e4ae8652a.
- (a) prefill with the chat cache off: R3 Poff +0.20 % vs Boff (noise 5.49 %) -> PASS.
- (b) prefill with the chat cache on, minus the save: R3 P -0.05 % vs B (noise 6.54 %) -> PASS.
- (c) the chat-cache save: P -2.2 % vs B on the level-normalized index (noise 11.7 %) -> PASS.
  - The 1238 MiB save's level: B fast 5 / slow 3, P slow 8 of 8. The level mix is INFO.
- (d) the stored 11-07 gate, re-judged under the amendment -> PASS:
  - screen decode P +1.34 %;
  - screen prompt P +0.70 %;
  - no workload slower beyond its noise on the engine clock;
  - save P -0.2 %;
  - INFO: R4-agent33k -0.29 % on the client clock minus the save.

**VERDICT: BASELINE PASS under the 11-07 amended rule** (Karl 11-07: "If it confirms the artifact, record the port's
baseline check as passed under the amended rule. Passing doesn't mean switching: the before-switch requirements in the
port plan still apply."). P028x stays served. The switch conditions ("Required before v0.2.11 could replace P028x")
still apply in full. r23-port0211 stays the base whose resolutions the v0.2.13 port carries over (Karl 11-09).

**Save buffers (Karl 11-07: "if the page-fault count in the confirmation gap supports your theory, put 'reuse the
chat-cache save buffers' in the backlog"): NOT supported, so not added.**
- The engine's minor page faults per start: B1 (slow/fast) 1,872,170, B2 (fast/fast) 1,796,954, B3 (fast/fast)
  1,869,568, B4 (slow/slow) 1,869,572; P1-P4 (all slow) 1,707,581-1,708,324.
- B3 and B4 differ by 4 faults with opposite save levels.
- P, slow on every save, faults ~160K fewer times per start than B.
- The fault count does not follow the save level. Caveat: the sample is the whole start, not each save. A buffer
  backed by transparent huge pages would add only tens of faults, so this cannot rule the theory out; it only does
  not support it. The cause of the two levels stays open (desk only, no gap, as Karl said).
