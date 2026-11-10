## Round 18 — our ~3 % found and fixed (C\*16.1), v0.1.42, and two of our patches opened as draft pull requests (2026-10-10 01:52 → 15:30)

Chronological notes: `NOTES.md` ("ROUND 18"). Phone summary: `results/round18-summary.md`. Scripts: `work/r18/`. Raw
results: `results/r18/`. Configs: `configs/Cstar161.json` (the promoted build), `configs/r18-pr-*` (the pull-request
measurements). Engine: `engine-cstar161/` (branch r18-p1 eaa10769). Pull-request branches on v0.1.42 (61b3fb5d): `pr18/b2`,
`pr18/side` (both pushed to your fork), `pr18/gate` (local); the v0.1.41 versions are `pr18-v041/*`. Descriptions:
`publish/r18/final-pr-{b2,side,gate}.md`; what was posted: `publish/r18/MANIFEST.md`.

### Result

* **C\*16.1 = C\*16 + the side-mixer fix + this RTX 5080's own F4 table is on 8080** (promoted 07:54). Per verify round it
  equals C\*14 (16.22 vs 16.20 ms). On the served decode screen it is **+6.5 % over C\*16** (145.1 vs 136.2 tok/s; C\*14 146.7),
  with the same outputs as C\*16 (exact7 7/7). Every gate, the acceptance suite (11 / 0), a 2-hour soak and a rollback test
  passed. Rollback: stop 8080, `STRATA_CONFIG=configs/Cstar16.json ./switch-model.sh strata`.
* **The cause of the ~3 %:** two changes in our own Round 15 port, about half each. The re-ported side mixer ran its branch
  projections on the plain kernel, not F4's interleaved one, and lost the qkv-first order. Upstream's shared F4 table also
  picks other kernels than this card measures as fastest. B.3's 5–8-column cases were not it: windows that wide almost
  never occur.
* **Two draft pull requests are open (your "open 1, 2"):** **#1888** B.2 split decode attention and **#1889** the side
  mixer, both on v0.1.42 against Niko1221/Strata `main`. They are drafts because HIP and SYCL can't be built here without
  installing ROCm / oneAPI. The third, the cost-aware draft length, was not opened: with v0.1.42's tail skip off it gained
  only +0.8 % on the 5080 alone.

  | PR | 5080 alone, v0.1.42, tail skip on (upstream's default) | 5080 alone, v0.1.42, `STRATA_ROUTE_TAIL_SKIP=0` | 5080 + 4060 Ti helper (v0.1.41) | outputs |
  |---|---|---|---|---|
  | #1888 B.2 | decode +4.2 %, per round −5.1 % | +2.3 %, −3.6 % | +2.4 %, −2.7 % | rounding-level (TF NLL −0.0005 / −0.0016 nats) |
  | #1889 side mixer | +1.3 %, −4.4 % | +4.2 %, −2.9 % | +1.7 %, −2.6 % | bitwise identical |
  | (not opened) cost gate | +2.8 %, +9.3 % | +0.8 %, +10.0 % | +2.5 %, +10.2 % | distribution-preserving; greedy identical |
* **v0.1.42 came out during the round.** It already does none of the three, so none was dropped; all three were rebased,
  re-checked and re-measured. Its new default `STRATA_ROUTE_TAIL_SKIP=7` (single-GPU serve) is not lossless. Per your
  rule, every one-GPU config of yours gets `STRATA_ROUTE_TAIL_SKIP=0` when it moves to v0.1.42 or later (memory and
  bringup/RUNBOOK.md). Your served build was not changed.
* **Exact sampling is not offered:** upstream's `STRATA_SPEC_PROB` is the same algorithm and was 1.3 % faster than ours on
  current main.

**Display: the monitor is on the motherboard output (the AMD iGPU, HDMI-A-2) for the whole round**; neither NVIDIA card drives
a display. Nothing about the display was changed.

### Part 1 — the ~3 % between C\*14 and C\*15 / C\*16 (01:52 → 03:31, then the gates and the soak)

The suspects came from the ledgers. Between C\*14 and C\*15 the port dropped B.3 (Round 14 rows 16–20 and 34) for upstream's
F4. It re-ported the side mixer (row 9) onto `STRATA_DF_BRANCH`'s window and dropped rows 28 and 30. Everything else applied
unchanged. B.3's 5–8-column cases were ruled out by the window statistics: windows are 1–4 tokens almost always (5:
never; 6: 3 of 392 rounds, suffix drafts).

| measurement | C\*16 | + side-mixer fix | + this card's F4 table (= C\*16.1) | C\*14 |
|---|---|---|---|---|
| CLI, GPU wait per round vs C\*16 (math / code) | 0 | −0.31 / −0.23 ms | −0.44 / −0.32 ms | −0.56 / −0.46 ms |
| served decode screen (A B C D D C B A), tok/s | 136.2 | 142.1 (+4.4 %) | **145.1 (+6.5 %)** | 146.7 |
| ms per verify round | 17.33 | 16.67 | **16.22** | 16.20 |

C\*16's first arm ran in the CPU pool's slow mode (below); against its second arm alone (16.84 ms) C\*16.1 is still 3.7 %
faster per round.

* **The side-mixer fix** (folded into row 9, no new switch): the branch's GDN gate projection and QSA query projection read
  F4's interleaved q8_1 copy (written on the main stream before the fork) through the interleaved kernel. The qkv projection is
  again recorded before the branch, so its grid is dispatched first.
* **The F4 table:** `STRATA_MMVQ_IL_ROWS` set to the table measured on this RTX 5080. Upstream's shared table was measured
  on an RTX 3060 and an RTX 5070.
* **A confound found on the way:** the CPU expert pool's time per round is bimodal from one server start to the next,
  whatever the switches are (math ≈ 23 vs ≈ 19.5 ms per round). It follows the arena's load rate (about 6.1 vs 6.4 GiB/s), not
  transparent huge pages (their share stayed at 0.920). My first pre-screen's "side mixer off is 9–12 % faster" was this
  flip, and I withdrew it. The decisions then used the GPU wait (CLI) and A B B A served screens.
* **The #567 transplant stays:** a cached turn at 31K took 0.133 s with it and 0.142 s without; at 98K both took 0.163 s.
  Round 17's "no gain" was confounded: its NEW arms had run another test on the same server first, so their cache was
  already full.
* **Gates of C\*16.1:** exact7 7/7 = C\*16's hashes; needles 12 × 6/6; Stop at 120K; #652; stop strings; tool tags; #931;
  the browser check. Acceptance suite 11 pass / 0 fail / 2 reported (TF short = C\*16's to the digit; round trips identical
  in all three cases, with Round 16's state hash). 2-hour soak: MemAvailable min 21.2 GB, swap 0; the only log lines flagged
  as errors were 29 start-up "no error" lines. Rollback test: C\*16 started and answered, then C\*16.1 came back and answered.
* **Pull-request candidates from Part 1:** the sm_120 table measured on this card (below 1 % alone, so it doesn't
  qualify) and an sm_89 table measured on the RTX 4060 Ti (identical over 3 runs; upstream's MMVQ_IL_TABLE.md asks for
  per-card tables, but no gain can be measured here because the helper card runs no dense projections). Both are on local
  branches (pr18/t89 for sm_89); neither is in this round's three. The side-mixer fix is part of the side-mixer pull request.

### Part 2 — pull requests (03:32 →)

**Upstream main fetched at the start** (`git fetch origin main --tags`, the only download): main = v0.1.41 = fb58e0db, no
commits since Round 16. All branches start from fb58e0db, and stock main's engine is the Round 16 build of the same commit.
**No HIP or SYCL toolchain on this PC** (no hipcc, ROCm, icpx or oneAPI); installing one would be a system change, so every
pull request is marked draft and says so.

**2.1 The ranked list.** Single-card gains were measured on C\*16.1's one-card copy (the 5080 alone), switching one patch off
at a time, mirrored order, fresh servers (results/r18/p2-rank.md). Then a decision screen ran on stock main for the
patches that overlap upstream switches (results/r18/p2-decide.md).

| rank | patch (switch) | gain, RTX 5080 alone | gain, two cards | upstream overlap | this round |
|---|---|---|---|---|---|
| 1 | B.2 split decode attention (`STRATA_QSA_SPLIT_ATTN=1`) | −4.4 % per round, +4.2 % decode (C\*16.1) | −4.6 % per round, LDR +3.0 % (R14) | none | **#1888 (draft)** |
| 2 | side mixer + the Round 18 fix (`STRATA_SIDE_MIXER=2`) | +4.1 % decode vs main, +2.9 % vs `STRATA_DF_BRANCH` (decision screen) | −4.7 % per round, decode +2.5 % (R14) | `STRATA_DF_BRANCH` (opt-in, fewer steps) | **#1889 (draft)** |
| 3 | cost-aware draft length (`STRATA_COST_GATE=FILE`) on `STRATA_SPEC_PROB` | +1.3 % decode over `STRATA_SPEC_PROB` alone | +3.1 % over it (R15) | none | drafted, not opened |
| – | exact speculative sampling (`STRATA_SPEC_EXACT=1`) | +7.9 % on C\*16.1, but −1.3 % vs `STRATA_SPEC_PROB` on main | +2.7 % vs it (R15) | `STRATA_SPEC_PROB` = the same algorithm | no: superseded |
| 5 | B.1 hyper-connection read (`STRATA_GR_FORK=1`) | −1.6 % per round vs `STRATA_GR_V3` | −2.2 % per round | v0.1.41's staged read | later |
| 6 | A.2 router Q8_K rows (`STRATA_ROUTER_Q8K=1`) | −1.3 % per round (decode −0.1 %) | −1.0 % per round | #851's quantizer | later |
| – | the 5080's F4 table / an sm_89 table | −0.4 % per round (noise) / not measurable here | ~0.6 % / – | upstream's shared table | no (< 1 % / no gain) |

The helper-aware tier was dropped in Round 14 for upstream's `STRATA_DISJOINT_ADAPT` and is not a candidate. Other
authors' transplants (#567, #619, #652) and our server / web-app features aren't candidates either.

**2.2 The three pull requests.** Each is one change on fb58e0db, opt-in by an environment switch, committed as KarlGrier with
the noreply address. Checks: exact7 on stock main and on the branch with the switch unset (both cards, the community
report's flags, `STRATA_PREFILL_CPU_SHARE=0` on both), exact7 with the switch on, the patch's own gate, and upstream's whole
ctest suite on both builds. Measurement: stock main vs main + this patch only, A B B A with a fresh server per arm
(page cache dropped), the 5080 alone and with the helper card, the decode screen and the prompt-read screen, the
community report's flags (#1681).

* **B.2 (`pr18-v041/b2` 391dba55, 4 files +319).** exact7 switch off 7/7 = main; on 3/7 (it sums in another order).
  Teacher-forced NLL on − off: math −0.0005, corpus −0.0016 nats (bound 0.005). Needles 6/6 at 32K / 128K.
  * Measured on v0.1.41: 5080 alone decode 113.8 → 118.7 tok/s (+4.3 %), per round −2.2 %.
  * With the helper: 125.7 → 128.8 (+2.4 %), −2.7 %.
  * Prompt reads within ±1.2 %.
* **Side mixer (`pr18-v041/side` 2fbb1fac, 2 files +203/−68).** While preparing it I found it created its streams and
  events even with the switch unset; they are now created only when it is set. exact7 off 7/7 and on 7/7.
  * Measured on v0.1.41: 5080 alone 115.0 → 118.1 (+2.7 %), −1.1 % per round.
  * With the helper: 125.1 → 127.2 (+1.7 %), −2.6 %.
  * Against upstream's `STRATA_DF_BRANCH` (decision screen): +2.9 % decode, −1.9 % per round.
* **Cost gate (`pr18-v041/gate` 8467f937, 6 files +297/−3).** Its first version also set greedy requests' window lengths:
  exact7 with it on was 2/7, with three greedy items changed. Upstream keeps greedy byte-identical under its
  sampled-drafting switches, and the table's acceptances are rejection sampling's. So the gate now applies only where
  `STRATA_SPEC_PROB` judges the drafts; I stopped the first version's measurement and re-ran the checks and the
  measurement. Second version: exact7 off 7/7; on, greedy 5/5 identical and sampled as with `STRATA_SPEC_PROB` alone;
  `spec_prob_test` 74/74 (gated joint chi² 96.0, bound 162.8; its control fails as it must).
  * Measured on v0.1.41, both arms with `STRATA_SPEC_PROB=1`: 5080 alone 118.8 → 120.3 (+1.3 %).
  * With the helper: 126.4 → 129.6 (+2.5 %).
  * Its rounds are about 10 % longer by design (more drafts per round).

**Upstream's tests:** on v0.1.41, main and every branch passed 96 of 99, with the same 3 failing (they read model files from fixed paths this PC does not have). The count took a fix:
upstream's CMakeLists uses `STRATA_NATIVE_EXPERTS` (line 488) before its `option()` (line
1131), so four native-expert tests are registered only from the second configure on. Main's build had been configured once
(95 tests). I re-configured it and ran the four (4/4 pass). It may be worth an upstream issue; not filed.

**2.3 v0.1.42 (your 12:00 message).** Upstream released v0.1.42 during the round (61b3fb5d, 235 commits after v0.1.41;
fetched with `git fetch origin main --tags`, upstream history only; its llama.cpp pin is unchanged, so nothing else was
downloaded).

* **Overlap: none superseded, none dropped.** Its attention changes are opt-ins for AMD's gfx906 only, so it has no split
  decode attention. In `record_window` its changes come after the mixer (`STRATA_ROUTE_PRIOR`, per-GPU route counters), plus
  a one-line commit-flag change, and `STRATA_DF_BRANCH` is unchanged. In the window rule, its near-end clamp (e85567b6)
  runs after the window length is chosen, and the lookup-chain re-probe (71eaee17) is a separate path. Its docs have
  no cost-aware length.
* **Rebased:** one commit each, cherry-picked onto v0.1.42 without conflicts (KarlGrier, noreply): `pr18/b2` 79043bee, `pr18/side` 602a8128, `pr18/gate` 8ae486eb. B.2's
  scoring twin needed its server hook commit resolved by hand (two conflicts, both sides kept).
* **Checks on v0.1.42:**
  * Stock v0.1.42's exact7 equals stock v0.1.41's seven hashes, and it repeats itself.
  * Every branch with its switch unset: 7/7 = v0.1.42.
  * With the switch on: B.2 3/7 (the same rounding-level hashes as on v0.1.41); side mixer 7/7; gate: greedy 5/5
    identical, sampled as with `STRATA_SPEC_PROB` alone.
  * Own gates: B.2's teacher-forced NLL passes (math −0.0005, corpus −0.0016 nats; bound 0.005) and its needles are 6/6;
    `spec_prob_test` passes 74/74.
  * ctest: 112 tests; 109 pass on v0.1.42 and on every branch, and the same 3 environment tests fail on all.
  * The CLI is unaffected by the tail skip (its default is set only at serve start-up), so exact7 is a clean check.
* **The tail skip** (`STRATA_ROUTE_TAIL_SKIP=7`, on by default for CUDA serve with one GPU or a layer split; not with a
  helper GPU) changes the output. Each PR was therefore re-measured on the 5080 alone against stock v0.1.42 twice, with
  upstream's defaults and with `STRATA_ROUTE_TAIL_SKIP=0` in both arms. The two-card numbers stay from v0.1.41 and are
  labelled so.

| PR | setup | stock v0.1.42 → + patch, decode tok/s | ms per verify round | prompt reads |
|---|---|---|---|---|
| B.2 | tail skip on | 131.0 → 136.6 (+4.2 %) | 15.19 → 14.41 (−5.1 %) | ±0.7 % |
| B.2 | `=0` | 114.9 → 117.5 (+2.3 %) | 17.37 → 16.75 (−3.6 %) | ±0.3 % |
| side mixer | tail skip on | 132.8 → 134.5 (+1.3 %) | 15.18 → 14.52 (−4.4 %) | ±0.5 % |
| side mixer | `=0` | 113.5 → 118.2 (+4.2 %) | 17.50 → 16.99 (−2.9 %) | −2.6 to 0 % |
| cost gate (both arms `STRATA_SPEC_PROB=1`) | tail skip on | 135.0 → 138.7 (+2.8 %) | 15.05 → 16.44 (+9.3 %) | ±0.7 % |
| cost gate | `=0` | 115.9 → 116.8 (+0.8 %) | 17.24 → 18.96 (+10.0 %) | ±0.6 % |

The engine logs confirm the setting: the "tail skip ON" line appears in every default arm and never in the `=0` arms.
The tail skip itself made stock v0.1.42 about 14 % faster in decode here (114.9 → 131.0, B.2's stock arms), with changed
outputs. The side mixer's two runs with the tail skip on differed (136.7 vs 132.3 tok/s), so its decode gain there is
smaller than its per-round gain. The cost gate's +0.8 % with the tail skip off is inside its arms' spread, and in that run
its answers after the 32K / 120K prompts decoded 4 % and 8.5 % slower (not seen with the tail skip on or on v0.1.41). This
is why I flagged it as borderline.

**2.4 State of each pull request.**

| # | pull request | state |
|---|---|---|
| 1 | B.2 split decode attention | **opened as draft #1888** (https://github.com/Niko1221/Strata/pull/1888), fork branch `qsa-split-decode-attn` = 79043bee |
| 2 | side mixer | **opened as draft #1889** (https://github.com/Niko1221/Strata/pull/1889), fork branch `side-mixer-graph-branches` = 602a8128 |
| 3 | cost-aware draft length | not opened (your choice); local branch `pr18/gate` 8ae486eb and `publish/r18/final-pr-gate.md` are ready if you want it later |

Before posting: the privacy check was clean (19 files + the three branches), commits are KarlGrier with the noreply address
with no trailers, and the posted bodies equal the shown files (read back). Nothing else was pushed, posted or commented.

### State at the end

C\*16.1 on 8080 (de53cbb9), the 48-hour passive monitor running since 15:03 (`logs/r18/uptime-c161`, stop:
`kill $(cat logs/r18/uptime-c161/monitor.pid)`). The served build was not changed for v0.1.42.

### Slips

1. **The promoted build between steps.** Part 1's steps from 02:01 to 03:33 ran back to back, without the promoted build
   on 8080 between them. Phase ends were added after that.
2. **The twin configs for C\*16.1's round trips, twice.**
   * They first pointed at C\*16.1's own server, which has no force hooks, so the round trips returned nothing.
   * They then lacked Round 16's `STRATA_STATE_HASH=1` and `--adapt-swaps 0`, because I built them from C\*16's config.
   * Both were fixed and re-run; the gate passes with the state hash.
3. **Round 17's #567 confound:** the Round 17 report called #567 "no gain", which was wrong.
4. **Restarting the decision screen.** My first stop of 8080 left out the port, so the screen's start-up check refused
   to run. Two servers never ran at once.
5. **Launch checks matching my own shell.** Several times a "is a server / script running" check matched my own launching
   shell. Twice that refused a start; once it made a wait run its full 2 minutes. No other effect.
6. **B.2's first measurement was refused** (08:46). The needle server before it was still exiting. The scripts now wait
   up to 60 s; the measurement was re-queued and ran 10:01–10:48.
7. **The cost gate's first version changed greedy outputs.** I only caught it in its exact7 with the switch on (2/7),
   after side's measurement. Its v0.1.41 measurement was stopped mid-way and redone with the fix (about 35 minutes
   lost).
8. **The first filled descriptions stated the flags and the sampling incompletely.**
   * The flags lacked `--vram-reserve-mib 713`, `--max-context` and three environment switches.
   * The sampling lacked min-p 0.05 (from the config, under the chat settings' temperature 1.0).
   * Corrected before anything was shown to you.
9. **pr_build.sh reported a failed build as "rc 0"** (its `$(date)` reset `$?` before it was read). The v0.1.42 run then
   stopped at its own binary check (B.2's twin did not compile: a hook needs the server-hook commit I had skipped). I
   fixed the report and resolved that commit by hand; the run restarted 2 minutes later.
