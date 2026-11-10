# Plan: items 5-8, the v0.2.7 port, Phase 5 (Karl's decision 10-27; dated 10-27 20:45)

Karl's order: items 5 + 6 as one bundle (with the six-fix follow-ups folded in), then the Strata v0.2.7 port for Qwen,
then item 7 in parts, then item 8, then Phase 5; Opus 4.5 inside 11-01..11-24 once the credits are confirmed; the Sonnet
experiment last.

**How each step goes:**
- Each result goes to Karl when it is in, and I go on unless it is bad or mixed. Then I stop and ask.
- Jan's jobs go first, so any date can slip by a few hours.
- Every timed run holds the GPU test lock and gets the kernel check and the swap rule.

## Dates (targets)

| when | step | GPU h |
|---|---|---|
| Tue 10-27 night | Combined six-fix rerun ends ~21:00. Stage 3 p4s6 starts by itself at the matched budgets (171 / 47 min). I grade the rerun tonight: blind vs run-full, answer key, code references, citations. | ~12.5 (stage 3) |
| Wed 10-28 | Stage 3 ends ~09:30 and I grade it vs p4s3. **The six fixes' result to Karl: this is the gate for everything below** (bad or mixed = I stop and ask). Bundle code starts in a staging copy; the installed LDR package stays untouched until stage 3 has ended. | - |
| Thu 10-29 | Bundle code done and installed. Replays start: the follow-ups, item 5, item 6's offline pass. | ~4 |
| Fri 10-30 | Replays and a correction round. Evening: one combined rerun, then one stage 3 overnight (one chain). | ~4 + ~16.5 |
| Sat 10-31 | Grading. **Items 5 + 6 + the follow-ups result to Karl.** I also ask about the API credits for the Opus 4.5 run (before 11-02). | - |
| Sun 11-01 - Wed 11-04 | **Strata v0.2.7 port for Qwen** (results/PORT-V027-PLAN.md): repeat-run gate first, the series with every new default off, then a KL gate + speed A/B per switch. 8080 switches only when the gates pass; P021m stays as the rollback. **Result to Karl.** | ~10-13 |
| Wed 11-04 night | Fresh baseline on the new engine: one stage 3 side with the final build, the "without" side for items 7 and 8. | ~12.5 |
| Thu 11-05 - ~Fri 11-13 | **Item 7, one part at a time** (below). One side a night, graded by day; each part's result to Karl. | ~65 |
| ~Fri 11-13 - Tue 11-17 | **Item 8**: the merge test first; short runs only if it looks good. | ~3, then ~18 |
| ~Wed 11-18 - Fri 11-20 | **C3c bigger fixed sizes** (see "Not in Karl's message"). | ~12-16 |
| ~Sat 11-21 - Mon 11-23 | **Phase 5 holdout** on the final build and engine. | ~17-20 |
| 11-01 .. 11-24 | **Opus 4.5 hard-set run**, API only, at 09:00 on the first day after Karl confirms his credits have reset. | 0 |
| after Phase 5 | **Sonnet 5.5 experiment** (C4, $60 stop), needs C3b's Sonnet profile. Late November if the $100 still covers it after Opus, else December. | 0 |

## 1. Items 5 + 6 bundle, with the six-fix follow-ups

**Item 6 leads: every cited source must have been fetched and read.**
- Today ~85 % of cited sources are snippets nobody opened. Pages that are opened are already read up to 120K chars.
- The rule goes into code, not just the prompt:
  - A source becomes citable only after its page is fetched and read.
  - When an agent cites an unread source, the page is fetched and read at once.
  - The report writer only gets read sources.
  - Fix 4's citation guard also removes or marks a citation to an unread source.
  - A page that cannot be fetched (paywall, error, oversized PDF) cannot be cited; the claim needs another source or is
    marked.
- Then link following, one step deep, from a secondary page (news, blog) to its primary source (regulator, paper, repo,
  vendor docs).
- Metrics: the share of cited sources read (target 100 %), primary vs secondary sources, and the fetch time this costs.
- Fix 6's budget is fixed, so the reading comes out of search time. The runs measure that trade-off.

**Item 5: claims with quote, URL, date.**
- Extraction writes claims whose quotes are checked word for word against the page text, in code.
- The report writer picks each section's evidence from the claims.
- The citation check reads the quotes.

**Follow-ups (backlog A8), after the six fixes are graded:**
1. Fix 1's misses in the 10-24 report, grouped by kind (prose mentions, config keys, env vars without code formatting,
   other), with detection extended for the biggest groups.
2. Fix 5 checks recommendations against the question's own stated setup; the profile counts only for what the question
   does not say.
3. The consistency pass: why it missed K4 (DSpark), fixed if it is a pattern.

**Replays (~6-8 GPU h + a correction round):**
- Follow-ups: Fix 1 on the 10-24 report (Karl's OK covers this); Fix 5 and consistency on our own reports.
- Claim stores built from p4s6's saved o01-o03 evidence; the reports rewritten with and without them.
- Item 6's offline pass: the cited-but-unread pages fetched now and fed into the same stores.

**One combined rerun (~4 h): the 10-24 DeepSeek question, not o03 as my estimate said.**
- It is compared with tonight's rerun: same question, same 240-min budget, same engine; only the bundle differs.
- It carries the answer key (K4 is the DSpark contradiction), the wrong-engine count for Fix 1, and Fix 5's setup case.
- o03 is still covered by stage 3.

**One stage 3 (~12.5 h):** o01-o03 + the hard five at 171 / 47 min, vs p4s6.

**Risk:** a bad or mixed bundle result means splitting it, which costs one more stage 3 (~12.5 h).

## 2. Strata v0.2.7 port (Qwen)

As in results/PORT-V027-PLAN.md:
1. The repeat-run gate first (v0.2.5's `--adapt-async` default).
2. The series with the 0.2.7 defaults pinned off: `STRATA_DEFAULTS=026` plus `ROUTE_PRIOR`, `PROMPT_ATTN_IMMA`,
   `PREFILL_LAYER_MAJOR` and `PLE_AUTO_RAM` = 0.
3. KL gate + speed A/B for `GR_UP_WIDE`, `MMVQ_IL_89`, `--mtp-draft-vocab` and layer-major prefill.

`--ple-io ram` does not fit under the floor (93.5 of 96.4 GB), so it is not tested. Disk is fine (272 GB free). If
Strata adds Qwen4 support before then, I tell Karl first, since that could change the target.

## 3. Item 7 in parts (Karl's new search rule)

**Karl's rule:**
- Paid search is now allowed in test runs, up to 30 paid searches per run. Karl's own research may use up to 100 per run.
- Monthly credits are about 850 Tavily and 2,250 Exa Lite searches ($9), shared with Jan's chat search.

**How I read the thresholds** (say if this is wrong):
- Test runs and Karl's research stop at 25 % of the month left (that 25 % is Jan chat's).
- All paid search stops at 10 % left.
- Per month that leaves about 637 Tavily and 1,687 Exa searches for tests and Karl's research.

**Code:**
- The existing month counters (exa_fallback.py's dollar counter, the Tavily counter) gain the per-run caps and the two
  thresholds, for every caller: test runs, Karl's research through the runner, and Jan's chat search.
- Keys stay in their files, never printed or logged.

**What 30 a run means:**
- An open question makes ~175-250 searches, so 30 paid ones cover ~12-17 % of them.
- The hard five make only a few searches, so they are covered fully.
- My rule for spending the 30: alongside SearXNG on each subagent's first search, and on any search where SearXNG
  brings fewer than 3 new results, until the 30 are used.

**The parts, each one stage 3 side (≤ 240 paid searches) vs the fresh baseline:**

| part | when | paid searches | note |
|---|---|---|---|
| 7a Semantic Scholar | ~11-05 | 0 (free) | already in Jan's runs |
| 7d Exa highlights, extraction replay | ~11-05 | ~30 Exa | decides whether the 7d side runs |
| 7b Tavily | ~11-06 | ≤ 240 Tavily | |
| 7c Exa Lite | ~11-07 | ≤ 240 Exa | |
| 7d Exa highlights side | ~11-08 | ≤ 240 Exa | only if its replay passes |
| 7e Exa shopping | ~11-10 to 11-11 | ≤ 150 Exa | 3-5 product questions; I send them to Karl ~11-02 to approve and freeze; new questions need their own "without" side |

November total: ≤ 240 Tavily of ~637 and ≤ 660 Exa of ~1,687, before Karl's own research. If his research uses more, the
remaining parts move into December.

**Stopping rule for item 7:** each part is judged on its own. A part with no gain is dropped (it has not earned its
credits) and I go on, since the next part does not depend on it. A part that makes things worse, or a mixed result,
means I stop and ask.

## 4. Item 8

**Correction to Karl's note:** the merge test needs no new research runs, but it is not zero-GPU.
- Merging the saved runs costs nothing.
- Writing the three merged reports on the local model takes ~3 GPU h.

**The test:**
- o01-o03's 4-5 saved full runs each (p4base, p4s2-p4s6) are merged into one evidence store per question.
- One report is written per question and graded blind vs the fresh baseline's reports (same engine, same writer).
- If it looks good: stage 2 short runs (o01 + o03, 3 short runs each in the same total time, ~5.7 h), then stage 3
  (~12.5 h).

## Not in Karl's message: where C3b and C3c go

- **C3b (per-model profile files, no change in behaviour):** in code gaps during item 7. It is needed before the Sonnet
  experiment and before Qwen4.
- **C3c (bigger fixed sizes):** changes the build, so I've put it after item 8 and before Phase 5, so Phase 5 measures
  the final build. Karl can move it after Phase 5 instead.

## Totals

| | code h | GPU h |
|---|---|---|
| Bundle (incl. follow-ups) | ~12-17 | ~24-25 |
| Port + new baseline | ~10-14 | ~23-26 |
| Item 7 | ~5-8 | ~65 (4 sides at ~12.5 h + the 7d replay + 7e's two sides ~15 h; my estimate's ~50 still used the old 8.5-h side) |
| Item 8 | ~3-5 | ~3-21 |
| C3c | ~2-3 | ~12-16 |
| Phase 5 | ~1 | ~17-20 |
| **Sum** | **~33-48** | **~145-175** |

That is about four weeks of queue time, ending around 11-23 if nothing slips.
