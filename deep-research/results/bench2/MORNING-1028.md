# Morning write-up - Wed 10-28, 07:05

## Headlines

- **Stage 3 p4s6 (six fixes): open questions graded blind.** The six fixes lead overall: **29.0 of 34**, against 28.0 for
  stage-3 setup and 22.5 for the baseline. They won o01 and o02 clearly and came last on o03 by one point.
- **The hard five are running.** h02 and h04 are done (rc 0); h05 is running; h06 and h08 follow. They should end ~09:00.
  Then the script grading and the **bundle gate verdict to you (~09:30)**.
- **Strata v0.2.7.1 paused the queue at 05:27.** I reviewed it and accepted it at 05:31. Everything on our path is DGX
  Spark / Mac only. **Needs your confirm.**
- **Machine healthy all night.** Kernel check ok (07:03), engine swap 0, no paid search used.

## Overnight timeline

| time | what |
|---|---|
| 10-27 20:53 | Queue started stage 3 p4s6 (171 min open / 47 min checkable, items setup + critic + code + fixes) |
| 23:47 | o01 done -> o02 started |
| 10-28 ~00:00 | o01 graded blind; all 5 version-check flags found false -> staged fix |
| ~00:30 | Effort table corrected (see below) |
| ~01:02 | Routine 8080 relief restart (MemAvailable reached the 20 GiB trigger) |
| 02:36 | o02 done -> o03 started |
| ~03:00 | o02 graded blind; 2 false arithmetic alarms -> staged fix |
| 03:39, 04:29 | Two more routine relief restarts during o03 |
| 05:27 | o03 done; queue paused on Strata v0.2.7.1 |
| 05:31 | v0.2.7.1 reviewed + accepted; queue resumed with the hard five (GPU idle ~4 min) |
| ~05:35 | o03 graded blind |
| 06:10, 06:51 | h02 (39 min), h04 (41 min) done, rc 0 |

## Stage 3 p4s6 - open questions, graded blind

One fresh grader per question, against my reference research, with the real hardware. Grades were written before
the key was opened and before the check sections were read.

| question (out of) | baseline (p4base) | stage-3 setup (p4s3) | six fixes (p4s6) |
|---|---|---|---|
| o01 MoE from RAM (10) | 6.0 | 7.5 | **8.5** |
| o02 third GPU (12) | 5.0 | 9.5 | **10.0** |
| o03 EU AI Act (12) | **11.5** | 11.0 | 10.5 |
| **total (34)** | 22.5 | 28.0 | **29.0** |

- **o01:**
  - **Six fixes:** the only report with the hardware fully right: AVX-512 yes, no AMX, 4060 Ti 8 GB on the chipset x4
    link. It checked ideas against Strata's own results.
  - **Its slips:** KTransformers' deferral called lossless; learned-prefetch papers mostly missing; some numbers
    contradict each other.
- **o02:**
  - **Six fixes:** reasons from Strata v0.2.6's own multi-GPU docs and reaches the reference's key point: replacing the
    4060 Ti beats adding a third card.
  - **Its slips:** an expired September price deal and an August Micro Center price dated Oct 22; DeepSeek gains that
    assume three 16 GB cards; "45 GB of experts per token".
  - **Baseline:** ignores Strata and recommends an AMD card.
- **o03:**
  - All three reports have the core right, so the 1-point spread comes from slips.
  - **Six fixes, application dates wrong:** GPAI duties "from 2026" (they applied from 2025); GPAI fines "from 2025"
    (they apply from 2026); Arts. 102-110 described wrongly; EN 18286's date wrong.
  - **Six fixes, writer notes:** two notes such as "[from research context, not in the cited evidence set]" read as
    placeholder sourcing.
  - **Baseline:** one slip (a EUR 15 M / 7 % mix-up).

## What the held-out checks did (six-fix run, judged after grading)

| check | o01 | o02 | o03 | verdict |
|---|---|---|---|---|
| Second reading (critic) | real arithmetic catches; follows the question's 16 GB over the profile | 7 of 7 real | 6 of 6 real | useful |
| Consistency check | ~11 of 14 real | ~11 of 12 real; 1 endorsed a misdated price | 7 of 7 real; caught one graded slip | useful |
| Setup check | 9; 2 wrong ("no active MTP") | 19: ~9 real, ~8 "compare like with like" noise, 1 wrong ("no root" applied to you) | - | noisy |
| Version check | 5 of 5 FALSE | - | - | broken on whole-project questions -> staged fix |
| Arithmetic check | 0 | 2 of 2 FALSE | 0 | two false-alarm kinds -> staged fix |

**Missed by every check:**
- expired and misdated prices (o02);
- wrong application dates (o03).

Item 5 (claims dated from their quotes) is meant for these; the replays will show whether it catches them.

## Staged overnight (bundle copy only; installed LDR untouched)

- **Fix 1, false flags** (A8 (4)). Two causes:
  - The engine folders came from the overlap of two model answers, so a whole-project question left out src/core.
  - The repo-wide grep's 400-hit cap filled up with bench/results files.

  The fix marks folders only one answer names as "disputed" and searches the engine and shared folders on their own.
  Offline with a model that answers "another engine" for all 5: 4 of 5 come out "unsure" (not flagged), and the fifth
  (a server-only setting) is left to the model.
- **Fix 3, two more false-alarm kinds:**
  - a unit written on one side only;
  - a calculation that continues past its "=".

  Offline (no model): o02's 2 false alarms -> 0. The 3 planted errors are still caught, and the combined rerun's one
  real error is still flagged. None of the six graded reports gains a flag.
- **The o03 writer notes** are already covered by item 6's writer rule, which says to support a point with a read
  source or leave it out. The replays will check this.

## Correction: combined-rerun effort table (sent 10-27, fixed 00:30)

My first version counted the version check's own greps (66 calls, made in the report stage) as research calls, and I
told you the per-minute rate was about the same. Research phase only:

| run | research min | code-tool calls (search / read / tree / GitHub) | per research min | answer key (blind) |
|---|---|---|---|---|
| rerun, no fixes | 246 | 487 (237 / 115 / 15 / 120) | 1.98 | 3.5 of 7 (overall 3.0 of 10) |
| six fixes | 180 | 261 (99 / 63 / 8 / 91) | 1.45 | 2.0 of 7 (overall 4.5 of 10) |

**Reading:** the fixes run had 66 fewer research minutes. It also searched less per minute (0.55 vs 0.96). There was
one run each, so this may be run-to-run variation; the fixes act in the report stage. The bundle's rerun gets the same
240 min, and all three are re-graded together in one round.

## Strata v0.2.7.1 review (accepted 05:31 - please confirm)

Six files on our Qwen path changed:
- an sm_121 (GB10 / DGX Spark) defaults table and fused-prompt tile rule;
- linux-aarch64 in the platform list;
- a Metal-only ggml table guard;
- arm64-only CMake branches;
- the version bump to 0.1.53 and a new test target.

Our cards are compute capability 12.0 and 8.9, so none of this runs here. P021m is a fixed binary anyway. The v0.2.7
port needs no new pins and stays on v0.2.7.

I accepted under your 10-27 rule (pause only for Jan jobs or you). Until now every accept on our path was yours. The
accept is logged in both NOTES.md files, and the release watch is running again.

## Machine and budget

- **Kernel:** check ok at 05:27 and 07:03.
- **Swap:** engine VmSwap 0 after every run; system swap used flat at 2.21 GiB all night.
- **Memory:** three routine relief restarts at the 20 GiB trigger. The 12 GB floor was never touched; the lowest
  MemAvailable was 19.85 GiB.
- **Disk:** 272 GB free.
- **Paid search:** none overnight. October so far: 7 Exa calls ($0.03) and 2 Tavily calls, all on 10-19 / 10-24.
- **Jan:** no Jan jobs overnight. o03 was held 2 min in total; the hard runs so far 0.
- **Services:** all up (tag watch, ram-dip, kwatch, SearXNG watch, research runner, bench queue, gap-12 waiter).

## Not done overnight

Plan v2 also had these for the overnight gap:
- item 7's paid-search ledger code;
- item 8's merge tool.

Neither is written: the grading and the two staged fixes took the night. The counters' limits come first (this
morning, staged). The merge tool waits for the bundle's store format (after install). Item 7 starts Friday at the
earliest and item 8 on 11-02, so neither date moves.

The port branch is as of 10-27 22:48:
- 14 of 30 patches applied clean;
- the continuation fix, #652 and the chat-cache owner tag ported by hand;
- the rest measure-first under your rule.

## Today (targets)

| when | GPU | me |
|---|---|---|
| now - ~09:00 | hard five (h05, h06, h08) | item 7's limits in the search counters (a staged copy: the live counters serve Jan) |
| ~09:00 - ~09:30 | gap 12 starts on its own | script-grade the hard five; **gate verdict to you** |
| ~09:00 - ~14:30 | **gap 12:** port build, repeat-run gate, measurement twin, upstream's sampler tests, near-tie distribution test, lossless series, KL, speed screen P021m vs r27a vs r27a-prob | if the gate passes: install the bundle (nothing live on LDR), the items in the scripts |
| ~14:30 - ~23:00 | bundle replays (Fix 1 on o01 + the 10-24 report, Fix 3, Fix 5 + consistency, items 5 + 6 on o01-o03) | grade the replays; gap 12 summary -> port decisions |
| ~23:00 - Thu ~15:30 | combined rerun (240 min) then the bundle's stage 3 | grading |

If the gate is mixed or bad, I stop there and ask before installing anything.

## Decisions for you

1. **v0.2.7.1:** confirm my accept, or overrule it.
2. **Item 7e:** pick 3-5 of s1-s5 (bench2/ITEM7E-QUESTIONS-DRAFT.md); needed by ~10-30.
3. **o01's question text says "RTX 4060 Ti 16 GB"** (the PC has 8 GB). Under your Fix 5 rule the question wins, so the
   critic followed it. **My recommendation:** keep the frozen text through the bundle's stage 3 so the arms stay
   comparable, and correct it for the Phase 5 holdout.
4. **user-setup.md:** add one line saying the served Qwen runs MTP speculation (draft 7, min-p 0.5). The setup check
   twice "corrected" a report for having no active MTP. **My recommendation:** yes, after the hard five end (~09:00).
5. **Setup check noise:**
   - drop the "compare like with like" notes that only point at your own baselines (~8 of 19 on o02);
   - state in the profile that you have root (the no-sudo rule is the test harness's, not yours).

   **My recommendation:** yes, in the bundle before its replays. Both are small prompt/profile changes.
6. **SearXNG safe_search 1** after the LDR tests: a few odd queries pulled adult-site URLs into the source lists (none
   cited, none in any report). **My recommendation:** yes, after the LDR week.
7. **Opus 4.5 credits:** I ask by ~10-31 as planned.
