# Round 18 summary: our ~3 % fixed (C\*16.1), v0.1.42, and draft pull requests #1888 and #1889

2026-10-10, 01:52 to 15:30. The monitor is on the motherboard output (amdgpu HDMI-A-2; neither NVIDIA card drives a display).
The display setup was not changed. Details: NOTES.md "# ROUND 18"; raw tables in results/r18/.

## Part 1: the ~3 % between C\*14 and C\*15/C\*16 (01:52 to 03:31, then gates and soak)

**Cause.** Two changes in our own port, each about half the gap:

1. **The re-ported side mixer** (ledger row 9, rewritten on v0.1.40's window in Round 15). Its branch projections (the
   GDN gate projection and the QSA queries) ran on the plain `native_mmvq` kernel, not F4's interleaved one (C\*14's
   B.3 used its own interleaved kernel there). The qkv projection was also no longer dispatched before the branch's
   launch.
2. **F4's rows table.** Upstream's shared table (measured on an RTX 3060 and an RTX 5070) picks other kernels than this
   RTX 5080 measures as fastest. B.3's table had been measured on this card.

B.3's 5 to 8-column cases cannot be the cause: windows are 1 to 4 tokens almost always (5: never; 6: 3 of 392 rounds).

| measurement | C\*16 | + side-mixer fix | + this card's F4 table (= C\*16.1) | C\*14 |
|---|---|---|---|---|
| CLI, GPU wait per round vs C\*16 (math / code) | 0 | −0.31 / −0.23 ms | −0.44 / −0.32 ms | −0.56 / −0.46 ms |
| served decode screen (A B C D D C B A), tok/s | 136.2 | 142.1 (+4.4 %) | **145.1 (+6.5 %)** | 146.7 |
| ms per verify round | 17.33 | 16.67 | **16.22** | 16.20 |

Per verify round C\*16.1 equals C\*14. C\*16's first arm ran in the CPU pool's slow mode. Against its second arm alone
(16.84 ms) the gain is still −3.7 % per round.

**A confound found on the way.** The CPU expert pool's time per round is bimodal from one server start to the next,
whatever the switches are (math ≈ 23 vs ≈ 19.5 ms). It follows the arena's load rate, not transparent huge pages (their
share stayed at 0.920). My first pre-screen's "side mixer off is 9 to 12 % faster" was this flip, and I withdrew it.
From then on the decisions used GPU wait (CLI) and A B B A served screens.

**The #567 transplant is kept.** On the candidate, a cached turn at 31K took 0.133 s with it and 0.142 s without; at 98K
both took 0.163 s. Round 17's "no gain" was confounded: its NEW arms ran another test on the same server first, so
their cache was already full.

**Decision: C\*16.1 = C\*16 + the side-mixer fix (folded into row 9, no new switch) + `STRATA_MMVQ_IL_ROWS` = the F4
table measured on this 5080. Promoted 07:54.**

- Gates: exact7 7/7 = C\*16's hashes; needles 12 × 6/6; Stop at 120K; #652; stop strings; tool tags; #931; browser.
- Acceptance suite: 11 pass, 0 fail, 2 reported. TF short = C\*16's to the digit; round trips identical in all three
  cases.
- 2-hour soak: MemAvailable min 21.2 GB, swap 0. The only log lines flagged as errors were 29 start-up "no error"
  lines. After the soak, decode is at or above C\*16's Round 16 soak on every request.
- Rollback test: C\*16 started and answered, then the default C\*16.1 came back and answered.
- Rollback: stop 8080, then `STRATA_CONFIG=configs/Cstar16.json ./switch-model.sh strata`.

**Pull request candidates from Part 1.** Both are table rows upstream lacks:

- The sm_120 table measured on this RTX 5080: below 1 % alone, so it doesn't qualify.
- An sm_89 table measured on the RTX 4060 Ti (identical over 3 runs; upstream's MMVQ_IL_TABLE.md asks for per-card
  tables): no gain can be measured here, because the helper card runs no dense projections.

Both are on branches (pr18/t89 for sm_89), and neither is in this round's three. The side-mixer fix is part of the
side-mixer pull request.

## Part 2: pull requests (03:32 to 15:20)

**Ranked by single-card gain** (C\*16.1's one-card copy, one patch off at a time; then a decision screen on stock main
for the ones that overlap upstream switches):

| rank | patch | 5080 alone | two cards | result |
|---|---|---|---|---|
| 1 | B.2 split decode attention | −4.4 % per round, +4.2 % decode | −4.6 % per round (R14) | **draft PR #1888** |
| 2 | side mixer + today's fix | +2.9 % decode over upstream's `STRATA_DF_BRANCH` | −4.7 % per round (R14) | **draft PR #1889** |
| 3 | cost-aware draft length (on `STRATA_SPEC_PROB`) | +1.3 % over `STRATA_SPEC_PROB` alone | +3.1 % (R15) | drafted, not opened |
| – | exact sampling | −1.3 % vs upstream's `STRATA_SPEC_PROB` (the same algorithm) | | superseded |
| 5, 6 | B.1, A.2; the two F4 tables | ≤ 1.6 % per round / < 1 % | | not this round |

**Each PR:** one commit (KarlGrier, noreply), opt-in by a switch, a draft because HIP and SYCL can't be built here.

**v0.1.42 (released during the round).** It does none of the three, so none was dropped. All three were rebased (no
conflicts) and re-checked:

- **Stock v0.1.42:** exact7 equals v0.1.41's hashes and repeats itself.
- **Switch off:** 7/7 identical on every branch.
- **Own gates:** each passes again.
- **ctest:** 109 / 112 pass on stock and every branch, with the same 3 environment failures.

They were re-measured on the 5080 alone against stock v0.1.42, with its new tail skip on (upstream's default) and off:

| PR | tail skip on: decode / per round | `=0`: decode / per round | 5080 + helper (v0.1.41) |
|---|---|---|---|
| #1888 B.2 | +4.2 % / −5.1 % | +2.3 % / −3.6 % | +2.4 % / −2.7 % |
| #1889 side mixer | +1.3 % / −4.4 % | +4.2 % / −2.9 % | +1.7 % / −2.6 % |
| cost gate | +2.8 % / +9.3 % | **+0.8 %** / +10.0 % | +2.5 % / +10.2 % |

Prompt reads were unchanged in every run. The gate's rounds are longer by design (more drafts per round).

**State:** your "open 1, 2" → both branches pushed to your fork and opened as **drafts #1888 and #1889** against
Niko1221/Strata `main`. The posted bodies equal the shown ones; the privacy check was clean. Nothing else was posted. The
cost gate stays local (`pr18/gate`, `publish/r18/final-pr-gate.md`).

**Your new rule:** every one-GPU config of yours gets `STRATA_ROUTE_TAIL_SKIP=0` when it moves to v0.1.42 or later (the
tail skip is not lossless). It is saved in memory and in bringup/RUNBOOK.md. Your served build was not changed: C\*16.1 is
on 8080, with the 48-hour monitor running since 15:03 (logs/r18/uptime-c161).

## Slips

1. **The promoted build between steps.** Part 1's steps from 02:01 to 03:33 ran back to back, without the promoted build
   on 8080 between them. Phase ends were added after that.
2. **The twin configs for C\*16.1's round trips, twice.**
   - They first pointed at C\*16.1's own server, which has no force hooks, so the round trips returned nothing.
   - They then lacked Round 16's `STRATA_STATE_HASH=1` and `--adapt-swaps 0`, because I built them from C\*16's config.
   - Both were fixed and re-run; the gate passes with the state hash.
3. **Round 17's #567 confound** (above): the Round 17 report called #567 "no gain", which was wrong.
4. **Restarting the decision screen.** My first stop of 8080 left out the port, so the screen's start-up check refused
   to run. Two servers never ran at once.
5. **Launch checks matching my own shell.** Several times a "server / script running" check matched my own launching
   shell: twice a start was refused, once a wait ran its full 2 minutes. No other effect.
6. **B.2's first measurement was refused** (the needle server was still exiting). The scripts now wait up to 60 s; it
   was re-queued.
7. **The cost gate's first version changed greedy outputs** (exact7 2/7 with it on). It is fixed to apply only under
   `STRATA_SPEC_PROB`; its half-done measurement was stopped and redone (about 35 minutes).
8. **The first filled descriptions** lacked `--vram-reserve-mib 713`, `--max-context`, three environment switches and
   min-p 0.05. They were corrected before you saw them.
9. **pr_build.sh printed "rc 0" for a failed build.** B.2's v0.1.42 twin did not compile: a hook needs a server-hook
   commit I had skipped. The run stopped at its own binary check; I fixed it and restarted 2 minutes later.
