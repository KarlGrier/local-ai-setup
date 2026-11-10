## Round 19 — GitHub follow-ups (#1682, #1683), the RAM fault, catch-up to v0.1.42 (2026-10-10 15:30 → 2026-10-11)

Chronological notes: `NOTES.md` ("ROUND 19"). Phone summary: `results/round19-summary.md`. Scripts: `work/r19/`. Raw
results: `results/r19/` (the integrity checks in `results/r19/integrity/`). Drafts and what was posted: `publish/r19/`
(`MANIFEST.md`). Series: branch `r19-port` (C\*16.1's 28 commits on v0.1.42, `patches/r19p28`) and **`r19-port2`** (C\*17's:
minus our exact sampling and our cost gate, + the guard fix; `patches/r19p27`, tree 20b227e2).

### Result

* **C\*17 is on 8080 (promoted 2026-10-11 17:43):** v0.1.42 + C\*16.1's series (our exact sampling and cost gate kept),
  `STRATA_PREFILL_CPU_SHARE=0.4` on prompt chunks below 1,792 tokens, C\*16.1's other flags. It computes what C\*16.1 computes
  plus the share's prompt-read change, and it carries v0.1.42's fixes that reach the server (the logit-bias fix, #1624's
  tool-order cache fix, #984's thinking budget). Decode is about 1 % lower than C\*16.1 (decode screen −1.4 %, full
  −0.8 %, LDR −0.2 %); short prompts read faster (512 / 1,000 tokens −15 / −21 %; the LDR's prompts under 4K −4.7 %). Every
  gate, the sampler checks, a 2-hour soak (440 requests, 0 errors) and the rollback test passed; the acceptance suite
  passed on the same combination in B3 (11 / 0). Rollback: stop 8080,
  `STRATA_CONFIG=configs/Cstar161.json ./switch-model.sh strata`.
* **The two replies are posted** (#1682: fio + the thread-count A/B, unbuffered +24–26 % at every setting; #1683: 72 = 66,
  `--resident-experts` holds the lent slots).
* **Upstream's `STRATA_SPEC_PROB` is biased** at a temperature-0.6 near-tie (62 % vs 52 % with speculation off; not at
  1.0); our exact sampling is not (it matches upstream's default exact-match drafting). So C\*17 keeps ours. An issue
  waits for the same check on stock v0.1.43 (Part D).
* **The cost-gate PR is not worth opening** (+4.2 % decode on two cards, but −2.0 % after 120K prompts).
* **The Q4 config** (`configs/r16-q4.json`) now runs on C\*17 with `--resident-experts`: a 32K prompt reads 20 % faster and
  pulls 1.2 GB instead of 29 GB from the drive; tail skip 0.
* **The RAM fault** behind the 10-07 / 10-10 kernel faults was the RAM at 6200 MT/s (now 6000, memtest and stressapptest
  clean); no files were damaged.
* Waiting for your OK (together, after Part D): the #1684 thank-you, the CMake issue, and Part D's drafts.

### 1. The RAM fault (correction) and the recovery

* **What happened.** On 10-10 at 15:42:58, during a #1682 run that page-locks a 64 GiB RAM copy, the kernel's memory
  compaction thread oopsed; after that every large allocation was OOM-killed until the reboot. The 10-07 "Bad pagetable"
  event (Round 15) was the same kind. **The cause was the RAM** (your memtest86+: bit errors at 6200 MT/s; now 6000 MT/s 1:1,
  a full pass clean), not Strata, the kernel or the NVIDIA driver; my earlier guesses at those were wrong and are corrected
  in the notes and in memory. Every number in issues #1682 / #1683 (Rounds 15–17) was measured at 6200 MT/s.
* **Checks after the reboot (all clean):** this boot's kernel log; every model file with a source hash (72 files, 1,141 GB;
  the HF files also match the hub's listing); `git fsck --full` on 24 repos and all 239 worktrees against their index;
  the workspace's recorded hashes, text and JSON. The engines were rebuilt from fresh build directories; CUDA builds are not
  byte-reproducible here (two clean builds of one tree differ), so the check is behaviour: the five rebuilt engines repeat
  their recorded exact7 outputs **35/35**. RAM bandwidth 76.6 GB/s (= Round 1's).
* **Your condition for runs above 60 GiB:** `stressapptest -M 80000 -s 3600 -W` → **Status: PASS** (0 errors, 68 GB/s; no EDAC
  controller on this non-ECC board, so corrected errors cannot be reported). A kernel-log watcher (`bringup/lib/kwatch.sh`)
  stops everything at the first error line, and every run is followed by a check (`kcheck.sh`); none fired except my own
  argument-less `tools/membw` call (a segfault in my tool, not a fault). The biggest locked run since: 70.5 GiB, clean.
* **Driver:** your `apt install` of the 610 meta package pulled **nvidia-driver-615-open 615.71.09** (was 610.57.04). Everything
  from 10-11 00:43 is on 615 at 6000 MT/s; comparisons stay within one session.

### 2. Part A — the two replies (posted 10-11 with your OK)

* **#1682** ([comment](https://github.com/Niko1221/Strata/issues/1682#issuecomment-6106416336)): fio with the owner's command
  on the Q8_0 expert shards: 10,104 / 8,976 MB/s (psync: `--iodepth` has no effect), 7,848 MB/s with libaio. The read rule vs
  `STRATA_UNBUFFERED_LOAD=1`, B A A B, stock v0.1.42 with the tail skip off: **+24.6 % (threads unset, two blocks), +25.8 % (16),
  +24.2 % (64)**; the unbuffered means are 16.04 / 15.93 / 16.20 tok/s, so the thread count makes no visible difference
  (on Linux it only sizes the PLE reader's pool). One buffered run was stopped by your swap rule (the first big run after the
  reboot, swap empty); a second default block replaced it.
* **#1683** ([comment](https://github.com/Niko1221/Strata/issues/1683#issuecomment-6106416706)): why 66 (sized before the first
  start; the lend region was not in the sum), and 72 measured: **72 = 66 exactly** (RAM copy 63.95 GiB, 0 of 2,258 lent slots
  in RAM, 32K read 11.2–11.3 s, 29 GB from the drive per prompt, lowest MemAvailable 16.9 GiB); `--resident-experts` 70.53 GiB
  (= the complement + the lent slots' 6.59 GiB), all 2,258 in RAM, 8.8–8.9 s, 1.2 GB, 12.8 GiB.

### 3. Part B — v0.1.42

* **B1, the port.** Branch `r19-port` = v0.1.42 + C\*16.1's 28 commits (4 conflicts, both sides kept each time). The
  runbook on clean clones (rebuilt after the RAM fix): the release repeats itself 7/7; with every switch off the port
  computes what the release computes (7/7); every switch's gate passes (B.2 and B.1 teacher-forced within 0.002 nats, the
  side mixer and A.2 bit-identical pairs, exact sampling and the cost gate chi-square ALL PASS); with every switch on it
  computes **exactly what C\*16.1 computes (7/7)**.
* **B2, the tail skip on two cards.** The start-up line says `STRATA_ROUTE_TAIL_SKIP=7 is ON (default)`, but the dispatch
  never skips with a helper card: 0 "route tail skip" lines in 12 requests (on one card the line comes with every
  request). Only the start-up line is misleading. Every one-GPU config on a v0.1.42+ engine gets `STRATA_ROUTE_TAIL_SKIP=0`
  (the Q4 config, C\*17's fallback config; Round 18's measurement configs left as recorded).
* **B3, `STRATA_PREFILL_CPU_SHARE=0.4` vs 0: kept.** Repeats itself 4/4 (the `auto` default does not, #1684); time to the
  first token **−15.4 % at 512 tokens, −21.2 % at 1,000**; the acceptance suite with it: 11 pass, 0 fail. One addition,
  found by B6's LDR screen: with an explicit share the engine applies it to chunks up to `STRATA_PREFILL_CPU_SHARE_MAX` =
  3,072 tokens, and between ~2,000 and 3,072 it is slower here (2,000 tokens +6 %, 3,000 +27 %). With
  `STRATA_PREFILL_CPU_SHARE_MAX=1792` the gain stays up to 1,500 tokens and the cost above disappears (2,000 −5.7 %,
  3,000 −21.3 % against the default limit; 512–1,500 unchanged).
* **B4, `STRATA_PREFILL_HELPER_SOURCE=1`: not kept.** It works (50.8 GiB of experts taken from the 4060 Ti's cache in one
  request) but the first token comes no sooner: +2.2 / +0.9 / +0.2 % at 8K / 32K / 120K.
* **B5, our exact sampling vs upstream's `STRATA_SPEC_PROB=1` (both with our cost gate):** 144.5 vs 144.5 tok/s on the decode
  screen, a tie — by the rule, a switch to upstream's. **That switch was then undone (§3a).**
* **B5b, the cost-gate pull request (pr18/gate) on two cards** (your bar: ≥ 2 % and decode after 32K / 120K not slower): the
  PR build rebuilt clean and repeating Round 18's outputs 7/7 in all three modes; `STRATA_SPEC_PROB` alone vs + the gate,
  B A A B: decode screen **+4.2 %**, after 32K **+4.3 %**, after 120K **−2.0 %** (6 requests per arm, 124–153 tok/s).
  **Not worth opening.**
* **B6, the new build vs C\*16.1.** C\*17 as promoted = r19-port (our exact sampling + the gate) + share 0.4 below 1,792 tokens. It computes C\*16.1's
  outputs plus the share's (exact7: the 3 long items = C\*16.1's, the 4 short = B3's share-0.4 hashes; repeats 7/7).
  Speed against C\*16.1, A B B A in one session (the variant with upstream's sampling + gate, the same speed as ours by
  B5): decode screen −1.4 %, full screen −0.8 %, LDR −0.2 %; with the 1,792 limit the LDR's prompts under 4K got their
  first token 4.7 % sooner. Soaked decode screen 142.9 vs C\*16.1's 145.2 (−1.6 %, different days). So **C\*17 is about
  1 % slower in decode and qualifies by v0.1.42's server fixes** (the logit-bias fix, #1624, #984), not by speed. Every
  gate passed (needles 72/72, stop at 120K, #652 17/19, stops, tool calls, #931, repeat, round trips, browser 42/1),
  the sampler checks (our chi-square, the 6 near-tie cases), the 2-hour soak (440 requests, 0 errors, MemAvailable ≥
  21.8 GB, swap 0) and the rollback test. The full acceptance suite ran in B3 on the same combination (our exact
  sampling + gate + share 0.4, with the share's default 3,072 limit): 11 pass, 0 fail. **Promoted 17:43.**
* **B7, the Q4 config.** `configs/r16-q4.json` (UD-Q4_K_XL) moved to C\*17 (its tree built with K-quants: `engine-cstar17-kq`) with
  `STRATA_ROUTE_TAIL_SKIP=0`; it starts and answers. Your addition, `--resident-experts` vs `--resident-budget-gib 66`,
  B A A B, served, the #1683 method: **the 32K read 8.97 vs 11.27 s (−20.4 %)**, drive reads **1.2 vs 28.9 GB** per 32K
  prompt, decode 67.7 vs 65.7 tok/s (+3.0 %), the RAM copy 70.54 GiB with all 2,258 lent slots vs 63.95 GiB with none,
  lowest MemAvailable 11.9 vs 16.2 GiB (floor 6); every run clean. Lossless: the long exact7 items are identical, the
  four short ones differ with the CPU share on (its split depends on where the experts live) and are identical with it
  off (4/4). **Adopted.** (The budget-66 version is kept as `configs/r16-q4.json.b7-b66`.)

### 3a. The sampler bias (why C\*17 keeps our exact sampling)

C\*17's first acceptance suite (with upstream's `STRATA_SPEC_PROB`) failed one sampler row: at a near-tie inside a speculative
window (the "arith" prompt, 4th token, temperature 0.6; the model's own probabilities 50.7 / 48.6 %, 51.8 % for `=` after the
filters) upstream's sampling picked `=` far too often. Re-measured with 2,000 samples per arm on the same build, against the
build's own probabilities through the sampler's filter chain (the same order as the engine's non-speculative sampler):

| arm (same build, prompt and position) | `=` | vs speculation off |
|---|---|---|
| speculation off (the ground truth) | 52.3 % (T 0.6), 50.0 % (T 1.0) | – |
| upstream's `STRATA_SPEC_PROB`, no gate | **62.2 %** | z 6.2 |
| upstream's `STRATA_SPEC_PROB` + our cost gate | **59.6 %** | z 4.6 |
| upstream's `STRATA_SPEC_PROB` + gate, T 1.0 | 52.6 % (vs 51.1 % expected) | not significant |
| our exact sampling + gate (C\*17), 6,000 samples | 54.5 % | +2.2 pp, z 2.3 |
| upstream's default exact-match drafting, 4,000 samples | 54.0 % | +1.6 pp; vs ours −0.5 pp, p 0.62 |
| speculation off, 6,000 samples | 52.3 % | – |

Exact-match drafting is by construction a plain sample of each verify window's p, and it lands where our exact sampling does:
the ~2 pp both show against speculation off is the window's numerics (the tie's logits computed inside a multi-token
window, not one token at a time; at a T 0.6 near-tie a logit difference of ~0.06 is enough), not our sampler. Upstream's
`STRATA_SPEC_PROB` is ~8 pp beyond that at T 0.6 (with or without our gate; none detected at T 1.0): a sampler bias. So
C\*17 keeps our exact sampling and the gate (C\*16.1's combination; B5: no speed difference). The upstream issue is drafted only after the same
check on stock v0.1.43 (Part D). Two of my mistakes on the way: I first concluded that our gate is not read under
`STRATA_SPEC_PROB` (I had checked a server that had not served a request yet) and built a C\*17 without the gate (B6:
−4.2 %, then rebuilt with the gate); the corrected build's acceptance suite is what caught the bias.

### 4. Part C — drafts (nothing posted without your OK)

* **#1684, a one-line thank-you** (`publish/r19/04-comment-1684.md`): thanks for the docs note (#1687, in v0.1.42), with
  the 0.4 result on v0.1.42 (4/4 repeats, the first token 15 % / 21 % sooner at 512 / 1,000 tokens, our checks against
  llama.cpp passed) and that we now run with 0.4. C\*17 runs it (below 1,792 tokens).
* **A CMake bug report** (`publish/r19/03-issue-cmake-native-experts.md`): `STRATA_NATIVE_EXPERTS` is read (line 538) before
  its `option()` (line 1199 on v0.1.42), so the four native-expert tests register only from the second configure of a GPU
  build (108 → 112 tests); reproduced with two configures, CPU-only builds are not affected; one-line fix. To update to
  v0.1.43 in Part D (the same use at 538, the option at 1210).
* Both wait, with Part D's drafts (the #1896 test comment, the sampler issue if stock v0.1.43 shows it, the #1889
  force-push), for your OK together. Privacy check CLEAN on every draft so far.

### 5. Slips

* **The gate "finding" (B5b):** I concluded from one server's log that our cost gate is never read under upstream's
  sampling; that server had not served a request yet, and the gate prints its line on first use. I stopped a valid A/B
  (b5b, after a minute), built C\*17 without the gate and ran B6 on it (−4.2 %) before finding the mistake. Cost: one runbook
  pass and one B6 (about 2 h). The cost-gate PR verdict is unaffected (measured on the PR's own build).
* **The fallback's start (11:36–11:45):** the fallback build script was not executable, then my edit to it had cut the
  helper that writes the configs. Both found by the pipeline at once; 8080 was down 11:36–12:45 instead of ~11:45–12:45.
* **Two false alarms of my own tooling (10-10 evening):** `tools/membw` run without arguments segfaulted and the kernel-log
  watcher stopped everything (correctly, by its rule); `stress.sh` read stressapptest's trailing timestamp line and marked
  a PASS as FAIL. Both fixed and tested before anything else ran.
* **The queue's PID file** first held the PID of `setsid`'s parent, not the queue's (setsid forks when it is a process
  group leader); fixed by reading the PID with `pgrep` after the start, so the kernel watcher can stop the queue's jobs.

### 6. State

* 8080: **C\*17** (`configs/Cstar17.json`, `engine-cstar17` sha 4b486ce2…, tree 1c05934d = branch r19-port); one-GPU
  fallback `configs/Cstar17-single.json` (tail skip 0). Rollback: `configs/Cstar161.json`. SearXNG on 8888.
* The 48-hour monitor runs on C\*17 (`logs/r19/uptime-c17/`); Part D's steps stop and restart 8080 (each noted there).
* RAM 6000 MT/s, NVIDIA driver 615.71.09, kernel 7.0.0-38; the kernel-log watcher runs during every queue.
* Next: Part D (v0.1.43, `work/r19/PARTD.md`), then every draft together for your OK.
