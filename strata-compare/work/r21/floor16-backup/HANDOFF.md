# HANDOFF — strata-compare, written 2026-10-15 23:29 CDT before an overnight shutdown

Read this file first. When the user says **"continue"**, work through the **MORNING QUEUE** at the bottom, in order.
Project folder: `/home/USER/ai-speed-testing/strata-compare` (it is NOT a git repo; Strata's own clones/worktrees
inside it are). Chronological notes: `NOTES.md` (append to it as you go). Main report: `REPORT.md`.

## STATUS 2026-10-17 (round 21 done; this supersedes "State at shutdown" and the MORNING QUEUE below)

- **The 10-16 morning queue (items 1-8) is finished.** Report: REPORT.md "Round 21" + results/round21-summary.md.
- **8080 = C\*18t** (`configs/Cstar18t.json` = C\*18 + think-fix commit d9e2c3a5, serve tree `strata-r21think/`), the
  switch-model.sh / run-strata.sh default since 10-16 09:55. Rollback: `STRATA_CONFIG=configs/Cstar18.json`.
  Standing guard via `phase_end.sh NAME keep`: GUARD_VRAM_MODE=warn60 + GUARD_FOLLOW_PORT=8080.
- **Sampling (since 10-16 21:53):** every path T 1.0 / top-p 0.95 / top-k 20 / min-p 0.05 (config "sampling" blocks of
  Cstar18t / Cstar18 / Cstar18-single, OpenCode's body; backups work/r21/*.before-sampling). New configs need a copy of
  the base's `.shared-settings.json` and the same "sampling" block; check both `[strata]` start lines before long runs
  (in bringup/out/logs/server_*.log the first one is glued to the config dump's "}" - don't anchor greps with ^).
- **10-17 (user's plans, done 13:4x):** C\*18t on 8080, kwatch running. Suite quick at medium: IQ3_S 94.5, NVFP4 94.3
  (xhigh 90.7 / 86.8), ~1/3 of the time; IQ3_S low 91.4 (below medium in 3 categories) -> **reasoning effort medium is
  the default on every path since 13:24** (work/r21/effort_default.sh; 8080 Chat settings via POST /settings, rollback
  configs' files, OpenCode + variants, Codex, dsh, Jan; backups work/r21/effort-default-backup/; checked with
  client_check.py). The chat page's own drawer level is the user's to switch. Hosted Flash ignores the effort (probe
  $0.04): no hosted medium run. Harness r5/r6 at T 1.0: 4/4 green. REPORT.md / round21-summary.md filled. Q8_0 honesty
  run DROPPED. v0.1.45 NOT ported (port once, to the big release; hourly tag watch work/r21/tagwatch.sh; summary first,
  then wait for the go). Standing rule: no run over ~30 min between 23:00 and 09:00 unless the user says so.
  Harness/suite runs that must compare with older xhigh runs now need the level set explicitly.
- **Settled 10-17 13:4x:** Xorg root config skipped; fit_max_tokens stays off; Q8_0 shards (models/r15/Q8_0) and
  models/fp4local deleted (412 GiB free). Configs on those files (r15-q8-*, r20-q8-*, r21-q8ref, r21-*fp4local*) no
  longer start; the yardstick needs the Q8_0 again for a new reference. Keep bringup/out/r15q8 (r15q4 links to it).
- **10-17 14:05-16:0x, the user's three usability fixes (NOTES 14:0x-14:5x; configs/usability/README.md "Strata on
  demand"):** chat page tool rounds 20 (`web_search.max_rounds` is the key that counts; `mcp.max_rounds` 20 too) in
  Cstar18t / Cstar18 / Cstar18-single. Jan assistant **"Deep think"** (xhigh, same sampling; default assistant stays
  medium). Launchers jan-strata / opencode-strata / codex-strata / dsh-strata call `bin/strata-ensure.sh`: start C\*18t
  on demand (own systemd scope, phase_end.sh "ondemand" keep), wait <= 3 min, refuse with a notification while a test
  holds a lock. **Measurement scripts hold `tmp/gpu-test.lock`** (with_server.sh takes it shared; new measurement
  scripts that start servers some other way must take it too) and set STRATA_NO_AUTOSTART=1 for client runs.
  systemd user service `strata-idle-stop.service` stops 8080 after `minutes` (configs/usability/strata-idle-stop.conf,
  45; 0 = off) - it will also stop a server you started by hand for a test unless a lock is held. Cold start icon ->
  first answer 18.6 s. Jan checked live 19:19 (Jan assistant -> medium, Deep think -> xhigh, None -> no level =
  medium); Jan's picker keeps the last-used assistant for new chats. Request monitor off again (19:21).
- **10-17 evening, deep research round (~/ai/deep-research, its NOTES.md / README.md "Research from Jan"):** Jan queues
  LDR deep research through an MCP server; `deep-research-runner.service` runs the jobs; strata-proxy (8090) holds
  research calls while a test holds tmp/gpu-test.lock or tmp/suite/heavy.lock (test scripts then run
  `bringup/lib/research_wait.sh`; with_server.sh does), at night, when paused, or for 5 min after another client used
  Strata. **The runner may restart 8080** (same config) to empty Strata's chat cache when MemAvailable < 21 GB.
  Port 8090 = also turnlog.py's recorder port here: don't run client_check while LDR's proxy runs.
  **Deep research round status (10-17 23:00):** phases 1-2 done (smoke test, Jan MCP + runner + gate, live-tested);
  phase 3 test set frozen (results/bench2/, FROZEN.txt); `deep-research-bench.service` runs the screen set from 09:00
  (baseline, then deep; daytime only; pauses for a Strata release > v0.1.45). Next for me: thinking-level replays,
  failure sorting, open-ended grading against results/bench2/my-research/, the checkpoint report - then wait for the go.
  **10-18 08:00:** the user allowed Jan jobs at any hour (research.conf night_pause = off; the measurement queue stays
  daytime-only). The user's 210-min Jan job from 02:18 was cut by the PC going off and continued as a seeded run at
  07:49; the bench queue waits for it. Holdout own research (o04-o06) is written and hashed in deep-research's NOTES.
  After a reboot, restart `bringup/lib/kwatch.sh` (see its header) and the tag check `work/r21/tagwatch.sh`.
- **Gotchas added:** harness reruns need `tmp/usability/venv-rt` (install.sh's step; rebuilt 10-16 22:19). Never put
  the launcher's server pattern ("/strata --serve") in a command line that runs while switch-model.sh checks for
  other servers (10-16 21:51: refused start, 8080 down 2 min). Locally "high" effort = xhigh (Strata's EFFORT map).

### 0.2.0 port round: concurrency screen (the user, 10-18) - **SKIPPED (the user, 10-19)**: v0.2.0-beta changed
nothing for batching with a helper card (batch-mtp auto is for one 24 GB+ card). Port timing (10-19): after the phase 3
checkpoint, or at 0.2.0 final if that is sooner and the research queue is between runs; the queue does not pause for
pre-releases. The section below is kept for reference.
Once the first 0.2.0 build runs with the user's settings (lossless switches, helper card), ~40 min max:
- Arms:
  - served one at a time;
  - 0.2.0's recommended multi-request mode, incl. MTP with parallel requests if it exists;
  - `--batch 2` with a small resident KV window per slot, 8K and 16K.
- N = 1/2/4 with test D's agent (27.7K prompt + tool call) and decode (4,096-token answer) sets: work/r20/conc.py,
  conc_prompts.py, d_conc.sh.
- Report: total and per-request tok/s, set wall, worst TTFT, expert-cache slots.
- Full test only if 2 or 4 at once beat one at a time by >=20% (total tok/s or wall) and 1 alone loses <=5%.
- If the notes show nothing new for batching with a helper card, skip the 0.2.0-mode arm and say so.
- 20 GiB floor applies.

### 0.2.0 port round: Strata's own tuner once (the user, 10-19; after the port builds)
- `strata tune auto <copy of our config>.json --mode thorough --use coding --no-save --gpu-lock tmp/gpu-test.lock`
  ("answers may change very slightly" = `--allow-small-differences`, left OFF; `--no-save` so no preset can be applied at
  a later start; our config is never the target). Our model and the helper card as in C*18t: the tuner has no helper-card
  knob and keeps `--expert-cache-device1 3300` from the config (checked in v0.2.0-beta's strata_control/tune_knobs.py).
- With the option off it does NOT try pcie-frac, the adapt settings (every/swaps/decay), --spec or --expert-cache (all its
  "placement" class); it does try spec-min-p (0.7 / 0.5) and one fewer pool worker (thorough only), aux CPUs,
  kv-resident, prefill chunk, host core, kv-grow (exact class). Report that to the user with the results.
- Report each setting it picks next to ours (pcie-frac 0, spec-min-p 0.5, pool workers 15 + host, adapt: engine
  defaults + STRATA_ADAPT_LAG=2 / STRATA_DISJOINT_ADAPT=1) and the speed it measured.
- Every disagreement: our usual A B B A on the ported build; keep it only if faster within our gates (exact7 /
  identity, the 20 GiB floor). Research queue paused / done first (research_wait.sh under the test lock).

### 0.2.0 port round: pictures in Jan (the user, 10-19; after the port builds)
0. Get the reader: the encoder `mmproj-Qwen3.8-Flash-Next-BF16.gguf` (0.9 GB, ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF,
   pinned revision + SHA-256, not on this PC yet) and the `strata-vision` helper (setup builds it from llama.cpp's mtmd
   beside the engine). Our config is hand-kept: add the "vision" section + `--vision cpu` to a COPY of the ported config.
1. With `--vision cpu` loaded (the CPU reader runs as its own process, nothing on the GPUs):
   - text bitwise identical: our identity gate (10 prompts + 4K/20K prompt dumps / exact7) reader on vs off;
   - decode speed A B B A, reader on vs off;
   - RAM: the reader process's RSS, and MemAvailable through a long research-style report (the report stage is where
     it dips to ~20-21 GB today), on vs off.
2. Jan: Settings > Model Providers > the Strata provider > edit the model > Capabilities: Vision on (Jan 0.8.6's
   EditModel dialog has vision/tools/audio/video toggles; without it Jan hides Add Images). Paste a screenshot: time
   from paste to answer, and whether the description is right (judge against what the screenshot shows).
3. If RAM gets too tight for research runs (MemAvailable near the 20 GB floor / more relief restarts), say so with
   numbers and suggest options - never a lower floor:
   - load the reader only when a picture arrives (0.2.0's vision "elastic": true starts it with the first picture and
     stops it after elastic_idle_s; check it works for the CPU reader, it is documented with vram_elastic);
   - keep the reader off while a research job runs (the runner could stop/start it);
   - a smaller chat cache (--chat-cache-mib, 12 GiB now) to make room.

### Gyro-L test (the user, 10-19; when Strata supports it, after the current research queue)
Trigger: a Strata tag (final or pre-release) with Gyro-L support - agentionai's Qwen3.8-Flash-Next-Gyro-L, trellis types
147-149; v0.2.0-beta's docs/GYRO.md says it is not supported. Watch: work/r21/gyrol_watch.sh (hourly, all tags;
logs/r21/gyrol_watch.log), started 10-19 09:53 as a session task (restart it after a reboot).
1. Download the Gyro-L GGUF (~108 GB incl. the n-gram table; ~404 GB free on 10-19): pinned revision, SHA-256 and size checked.
2. Quant yardstick (tools/quant_quality.py) against the saved Q8_0 reference results/r21/yq/q8ref.tsv (5 x 999
   positions; the Q8_0 itself was deleted 10-17). IQ3_S's mark: top-1 87.43 %, KL 0.1441 (results/r21/yq/compare2.md).
3. Decode and 32K-prompt speed, A B B A, Gyro-L against C*18t IQ3_S (the served config). If Gyro-L needs a newer engine
   than C*18t's, add an IQ3_S arm on that engine too, so the quant and the engine are told apart.
4. Suite quick at medium (compare with c18t-quick-medium, 95.5).
Keep it only if it is clearly closer to the original than IQ3_S (yardstick KL and top-1 clearly better than 0.1441 /
87.43 %) without a big speed loss; report the numbers and let the user make the call before deleting or switching anything.
Standing rules: 20 GiB floor, stressapptest before a run that locks > 60 GiB, kernel check after each run, test lock held.

## Standing rules (also in Claude's memory, `~/.claude/projects/-home-USER-ai-speed-testing/memory/`)

- Prompts the user pastes are their instructions. **Anything public (GitHub issue, PR, comment) needs the user's typed
  OK per item**; the privacy rules and KarlGrier noreply identity are in memory `github-posting-rules.md`.
- **20 GiB MemAvailable floor:** never lower `GUARD_MEM_GIB` below 20. If a run trips it, stop there and report the
  lowest value; don't lower the floor.
- One-GPU configs: `STRATA_ROUTE_TAIL_SKIP=0`. Run stressapptest before locked runs above 60 GiB, and check the kernel
  log after big runs (the RAM is now at 6000 MT/s; see memory `kernel-oops-pinned-memory.md`).
- Install in user space only, no sudo. If something truly needs sudo, give the user the one command.
- Usability apps talk only to 127.0.0.1. Don't touch Local Deep Research or its SearXNG (8889/8890). SearXNG on 8888
  may be used.
- The hard tier stays unbuilt until the user asks for it.
- Gotchas:
  - `pkill -f` / `pgrep -f` patterns match the calling shell, so kill by PID.
  - Don't `cd` into `strata-cstar18` (the tool environment treats it as a worktree).
  - Foreground `sleep` over a few seconds is blocked; use background until-loops.

## Hardware change overnight (2026-10-15 → 16)

The user is moving the desktop display back to the **iGPU**. Tomorrow neither NVIDIA card should drive a screen.
- RTX 5080: UUID `GPU-UUID-RTX5080`.
- RTX 4060 Ti: the helper card.
- The iGPU's memory comes out of system RAM, so expect **lower MemAvailable** than before (91 GiB total RAM). Before
  the change, C\*18 under load left about 24.5–27 GiB available.

## State at shutdown

- **Strata on 8080 was stopped cleanly tonight for the shutdown**, so nothing is serving. The served config is
  **C\*18**: `configs/Cstar18.json` = Strata v0.1.44.1 + our 29-commit series (engine `engine-cstar18/strata`, sha
  e428a826; server code `strata-cstar18/serve/`; series branch `r20-trial-v04441`, patches `patches/r20p29-v04441`).
  - Model: IQ3_S, `models/ISTA-GSQ-RCO/IQ3_S/` (2 shards).
  - Pack: `bringup/out/r20a/pack`.
  - Key args: `--vram-reserve-mib 713`, `--expert-cache auto`, `--kv int8 --kv-resident 32768`,
    `--max-context 131072`, `--spec 4 --spec-min-p 0.5`.
- **Start it:**
  - `./switch-model.sh strata` starts the default, configs/Cstar18.json.
  - With a guard attached, the way each phase ends: `bringup/lib/phase_end.sh NAME keep`.
  - Status: `./switch-model.sh status`.
  - Stop: `STRATA_PORT=8080 ./run-strata.sh stop`.
  - The server loads the engine lazily on its first request.
- **Rollback:** `STRATA_CONFIG=configs/Cstar171.json ./switch-model.sh strata` (C\*17.1).
- **The guard:** `bringup/lib/guard.py`.
  - Floors: MemAvailable 20 GiB (`GUARD_MEM_GIB`) and 5080 free VRAM 300 MiB (`GUARD_VRAM_MIB`).
  - Trigger: 3 samples × 0.2 s under a floor. In `--watch-pattern` mode it then sends SIGTERM to the watched engine.
  - It writes a CSV per label to `bringup/out/logs/guard/` (buffered) and a line to `summary.txt` on a normal exit.
  - `phase_end.sh ... keep` starts it detached.
  - **On 10-15 at 20:47 it stopped the served engine:** 5080 free VRAM fell from 316 to 176 MiB, most likely the
    desktop on the 5080. The server then stayed up with a defunct engine.

### Usability round: finished 10-15 (REPORT.md "Usability round", results/usability-summary.md)

- **Apps** (`configs/usability/`, see its README for how to start each):
  - Installed in `~/.local/opt/`: Jan 0.8.6, OpenCode 2.0.30, DeepSeek Harness 0.2.0-rc.2 (+ Node 24.22.0), Codex
    0.162.1.
  - Launchers: `configs/usability/bin/{jan,opencode,dsh,codex}-strata`. Each points the proxy at 127.0.0.1:18999,
    where nothing listens, so the connection is refused and nothing goes out.
  - Jan settings are applied by `configs/usability/jan/jan_config.py` (Jan must be closed).
  - Recommendation: **OpenCode**, or **DeepSeek Harness Minimal** for a web UI.
- **Measurement tools** (`work/usability/`):
  - `turnlog.py --listen 8090 --upstream 8080 --out logs/usability/turns` must be running for `harness_run.py` (label
    in `logs/usability/turns/LABEL`).
  - Optional `denyproxy.py --port 18999 --log logs/usability/denied.log` logs refused attempts.
  - `harness_run.py ARM TASK --tag TAG` (ARM: opencode | codex | dsh-minimal | dsh-standard | dsh-ptc; TASK:
    a1_inventory | a2_textstats | a3_cronlite | rt_effort). Results go to `tmp/usability/runs/<arm>-<task>-<tag>/`.
    Grading for rt_effort takes about 4.5 min (full serve suite).
  - `summarize.py TAGS…` makes the table; `turn_metrics.py DIR` gives per-turn numbers.
  - Existing tags: r1, r2 (rt r2 done for all four; dsh-ptc r1). Use new tags (e.g. r3, r4) for the morning reruns.
- **Think-tag finding** (all 9 rt_effort runs ended on it):
  - The model quotes `"<think>\n\n</think>"` inside a code fence in its reasoning, and `OutputParser`
    (`serve/frontend.py`, `_quoted_think_end`, #537 rule) ends the reasoning there.
  - Offline replay: `.venv/bin/python work/usability/think_fence_replay.py strata-cstar18 C`.
    - Rule C (fence only) gives 7 fixed and 495 unchanged of 503 turns.
    - The 1 "changed" is Codex r2 #18: the model ended the turn itself, so it can't be recovered.
    - Rule A (fence + inline code) misfires on dsh-ptc a3 #9.
  - Rule C is the fix for morning item 4. The replay rebuilds each turn as reasoning + `</think>\n\n` + content +
    calls in template form.
- **Open draft (NOT posted):** `results/usability-strata-think-issue-draft.md`.
- **Unfinished or caveats:**
  - At 20:31 OpenCode hung at start (its internal server logged nothing); not reproduced since.
  - rt_effort samples are small: 2 runs per harness, 1 for dsh-ptc.
  - `tmp/usability/` (1.6 GB) still exists (morning item 6 deletes it).
  - `~/.dsh` does not exist yet; dsh's first start copies the patch.

### Facts for the FP4-Local trial (morning item 7), checked 10-15 23:30

- **Disk:** `/` has **142 GB free** of 1.8 TB. Keep at least 100 GB free.
- **Deletable with the user's OK given 10-15** (an exception to the read-only rule, for these two only; first check
  that no config uses them, e.g. `grep -l r15/ configs/*.json`):
  - Q8_0 = `models/r15/Q8_0/` (6 shards, 176 GB).
  - Q5 = `models/r15/UD-Q5_K_XL/` (97 GB).
- **Not covered by that OK:** `models/r15/splice-q5/` (123 GB) is our own splice (Q5 experts + IQ3_S). Leave it unless
  the user says so.
- **Keep:**
  - IQ3_S (`models/ISTA-GSQ-RCO/IQ3_S/`).
  - UD-Q4_K_XL (location not confirmed tonight; find it with `grep -rn "UD-Q4_K_XL" configs/ NOTES.md | head`).
  - The GPTQ NVFP4 pack: `models/Maximilian228--Qwen3.8-Flash-Next-NVFP4-GPTQ-Strata/`, with `pack/`, the dense GGUF,
    `ple-fp8.gguf` and `token-embd-bf16.gguf`.
- **Converter:** `strata-cstar18/tools/nvfp4_convert.py` (plus `nvfp4_verify.py`, `nvfp4_verify_gguf.py`).
- **The "quant yardstick":** the round 9+ measure of distance from the exact computation (see NOTES.md around the
  "yardstick" entries, e.g. lines ~2419, ~2952, ~3339). Check whether it reads Q8_0 at run time before deleting Q8_0.
- **Memory warning (memory `strata-v0144-nvfp4-pack.md`):** the GPTQ NVFP4 pack with every expert in RAM idled at
  20.0 GiB free and fell to **19.7 GiB** on the first speed server (round 20 GUARD-STOP). With the iGPU now taking
  system RAM, an NVFP4-class pack will likely trip the 20 GiB floor again.
  - Measure free memory first.
  - **Update 2026-10-16 (user): NVFP4 runs may go down to 6 GiB ("like the other testing") → `GUARD_MEM_GIB=6` for
    the GPTQ pack and FP4-Local arms only.** Everything else keeps 20.

---

## MORNING QUEUE (verbatim from the user, 2026-10-15 23:25; start when they say "continue")

HARDWARE CHANGE OVERNIGHT: I'm moving the desktop display back to the iGPU, so neither NVIDIA card should drive a screen tomorrow.

MORNING QUEUE (when I say "continue"; read HANDOFF.md first):
1. Health check: confirm the display runs on the iGPU and that no desktop process (Xorg/gnome-shell, browser, Jan) sits on either NVIDIA card (nvidia-smi). Note total RAM and MemAvailable (the iGPU's memory comes out of system RAM) and check the kernel log is clean. Start C*18 on 8080 if it isn't running.
2. VRAM reserve: with the desktop off the 5080, measure how much VRAM came free and lower --vram-reserve-mib so the expert cache gets it, keeping a safe margin. Gates: A B B A decode and 32K prompt against current C*18, outputs bitwise identical, rollback config kept. Promote only if faster.
3. 8080 guard: if nothing from the desktop uses the 5080 any more, switch the guard to log-only (never stops Strata). If something still does, have it warn first, stop Strata only after 60 s straight under the floor, and tell me what it was.
4. Think-tag fix: add the one-rule fix ("a </think> inside a code fence is quoted") to our series as a new commit, with a safeguard: a code fence opened in reasoning and never closed must not swallow the real end of reasoning (e.g. at the end of the answer, fall back to treating the last </think> seen as the real one). Gates: the 503-turn replay (the 7 recoveries, no other turn changed), a test for the unclosed-fence case, and output tokens bitwise unchanged (only the reasoning/answer/tool-call split may differ). Then rerun the real bug-fix task with OpenCode and dsh Minimal, 2 runs each, and tell me if the harness recommendation still holds.
5. Issue draft: add that this is the same class as #2026 (quoted </tool_call>, fixed in 0.1.43.1) and mention the unclosed-fence safeguard. Run the privacy check, show me the final text, and wait for my typed OK.
6. Small items: turn off Jan's shell tool; delete tmp/usability/; if /usr/bin/rg exists (I may install ripgrep myself), point the OpenCode launcher at it instead of Codex's copy.
7. FP4-Local trial: nvidia/Qwen3.8-Flash-Next-FP4-Local (QAD, ModelOpt 0.47.0). Its NVFP4 scale factors use a new compressed format no public engine reads yet.
   - First find the decoder in the ModelOpt 0.47.0 source or the local-inference-lab vLLM fork's source. Read the code only; don't run their containers. If you can't find it, skip the rest of this item and tell me.
   - If found: decode to standard ModelOpt NVFP4 and prove a round trip is exact. Convert only the routed experts with tools/nvfp4_convert.py, one shard at a time (download, extract, delete). Take dense weights and MTP from our existing sources.
   - Disk: keep >=100 GB free. If you need the room, you have my OK to delete the Qwen3.8-Flash-Next Q5 and Q8_0 quant files (all their shards). This is an exception to the read-only rule for those two only. Keep IQ3_S, UD-Q4_K_XL and the GPTQ NVFP4 pack. Check no config uses them first.
   - Before deleting the Q8_0, check whether the quant yardstick needs it at run time. If it does, save its reference data first if you can without mapping a file bigger than RAM; if not, delete anyway and compare against the GPTQ pack instead.
   - Measure FP4-Local against the GPTQ pack: yardstick (if available), decode and 32K prompt speed, and a suite quick run. If its retrained n-gram table converts without loss, also measure with that table.
8. Finish with one short report covering all of the above, and leave the best promoted C*18 config running on 8080.

### Notes for the morning session

- **Item 2:** today's reserve is `--vram-reserve-mib 713` in `configs/Cstar18.json`.
  - Put the candidate in a new config (e.g. `configs/Cstar18r.json`) and keep `Cstar18.json` as the rollback.
  - Reuse the round 20 gate and speed scripts in `work/r20/` and `bringup/lib/` (A B B A decode screens, 32K prompt,
    exact7 bitwise).
  - The switch-model.sh default changes only on promotion.
- **Item 3:** the guard's VRAM floor logic is in `bringup/lib/guard.py` (main loop).
  - Add the log-only or warn-then-60 s mode behind an option or env var, so measurement runs keep the strict guard.
  - The memory floor stays 20 GiB in every mode.
  - The guard watches one engine PID. The server restarts a stopped engine on the next request ("the engine had
    stopped (exit code -15); starting it again"), and the guard exits with the old PID, so that restarted engine runs
    unguarded. For a standing 8080 guard, watch the server and its child tree, or re-find the engine.
  - `run-strata.sh stop` also stops the local SearXNG on 8888; `start` brings it back.
- **Item 4:**
  - Implement in the series branch (based on `r20-trial-v04441`).
  - Build a new engine/serve tree for the server change.
  - Re-run the replay against the patched `serve/`.
  - Re-check the tool-call rules (#804/#1058) and #537 tests in `serve/test_*.py`.
- **Item 5:** posting rules are in memory `github-posting-rules.md`. Show the final text and wait for the typed OK.
