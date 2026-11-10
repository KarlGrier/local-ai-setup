# Phase 3 checkpoint (final 2026-10-20 12:2x: replays and gap 4 included)

Phase 3's queue is complete (`bench2.py next` -> done, 10-20 03:07). All runs on one build: C*18t on 8080, chat-cache
parking policy off, LDR 1.10.7 with our deep patches, sampling 1.0 / 0.95 / 20 / min-p 0.05. Every run ended rc 0.
Then wait for the go (PLAN.md "Checkpoint").

## 1. Scores

**Checkable (automatic grade, each checked by hand):** easy screen set: plain LDR 15/15. Hard screen set: plain LDR
10/10; deep medium 5/5 and deep xhigh 5/5 on the five-question subset (h02 h04 h05 h06 h08). Every setup is at the
ceiling, so the checkable sets show time and regressions only.

**Open-ended (graded blind against my own research written before any run; key opened after the grades):**

| Question | Plain LDR | Deep medium | Deep xhigh | Out of |
|---|---|---|---|---|
| o01 what haven't we tried (MoE from RAM, with files) | 2.5 | 9.5 | **10** | 10 |
| o02 third 16 GB GPU | 6.5 | **11** | - | 12 |
| o03 EU AI Act 2026 | 11.5 | 11.5 | - | 12 |
| o07 open models that could replace Flash-Next | **11.5** | 7.5 | - | 14 |
| o08 local deep-research agents | 4 | **10.5** | - | 14 |

Deep medium wins 3, ties 1, loses 1. Grading notes per report: blind/grades.jsonl.

## 2. Time per question (wall minutes, median and range)

| Setup | Hard checkable | Open-ended |
|---|---|---|
| Plain LDR | 1.1 (0.7-2.5) | 30 (14-42) |
| Deep medium | 11.7 (8.5-17.7) | 150 (143-162) |
| Deep xhigh | 48.7 (35-80) | 190 (o01 only) |

Work per run in build-independent units (calls, prompt / fresh / generated tokens): tools/run_work.py. Deep medium
reads 6-8 M fresh prompt tokens per open question (plain LDR 0.4-1.7 M).

## 3. Thinking levels

* **Agent effort, medium vs xhigh** (the hard five, graded blind against the frozen answers): 5/5 each - a tie, so the
  xhigh open-ended runs were skipped (the user's rule; xhigh-decision.json). xhigh took 4.2x the wall time (median
  48.7 vs 11.7 min) and generated ~4.1x the tokens (1.85 M vs 0.45 M). On o01 (the only open question run at both): xhigh 10 vs medium
  9.5, 190 vs 162 min.
* **Extraction by replay** (30 captured page extractions sent again at low / medium / xhigh, graded blind; 10-20
  08:42-09:11): ranked first low 10 / medium 12.5 / xhigh 5.5 (28 ranked, 2 ties), mean rank 1.91 / 1.88 / 2.21;
  xhigh used 6.3x medium's tokens (median 4,374 vs 875) and 5.3x the time. No level is significantly better (low beats
  xhigh 17-9, p 0.17); same verdict as the blind re-judging of the 36 old tasks. replays/extract/summary.md.
  Note: the bench's deep runs extracted at medium. Your Jan deep profile extracted at xhigh until 10-20 11:55 (now
  medium, see below).
* **Citation check by replay** (o01-o03's own reports, the same 40 claims each at medium and xhigh; 09:11-10:00):
  same verdict on 96 of 120. On the 24 differences, judged blind: xhigh matched me 14, medium 10. They err in
  opposite directions: medium passed 10 claims I would flag (xhigh 1), xhigh flagged 9 I would pass (medium 3).
  xhigh takes 2.8x the time (35 vs 13 min for 120 claims, ~7 min more per report). **Keep the citation check at
  xhigh** - its job is catching wrong claims. replays/verify/summary.md.
* **Report writing by replay** (o01-o03's evidence written up again at medium and xhigh; 10:00-11:41; o02/o03 graded
  blind, o01 not): medium 31, xhigh 31.5 of 34 points. Each level won one pair and tied the third, and the loser lost on
  reasoning slips, not coverage. xhigh takes 3.0x the time (25 vs 76 min for 3 reports, ~17 min more per report) for
  the same output size. **Medium is enough.** replays/report/summary.md.
* **Decided and applied (the user, 10-20 11:5x): medium for every step except the citation check, which stays at
  xhigh.**
  * Before, the Jan deep profile ran agent, extraction, report and citation check all at xhigh.
  * Agent, extraction and report are now medium (research-runner.py; README "Thinking effort").
  * LDR picks this up at the next Jan deep job.
  * Measured in this round: about 4x less agent time, 6x fewer extraction tokens, and 17 min less report time per
    run, at no measured quality cost.

## 4. Failure sorting (open-ended)

* **Wrong frame at the lead agent's final answer (deep medium, o07)** (corrected 10-20 evening; this said before that the
  plan misread "24 GB VRAM" as a file ceiling): the plan was right (its subtopics: 30B-130B models "runnable on 96GB
  system RAM plus 24GB VRAM"), and the sub-agents' notes kept that frame up to the last compaction (call 649 judged
  50-80 GB files against RAM + VRAM). The lead's final answer (call 650) put Flash-Next on this PC at "15-25 tok/s"
  (llama.cpp reports from other machines; it runs at ~140-160 tok/s here), made "comfortable fit" a criterion and named
  ~35B models with "21-23 GB files" tier 1. The report outline (call 651) turned that into a "21-23 GB Q4_K_M
  file-size target", and every section followed it.
* **Facts about the user's own setup (deep, o01):** CPU called a 16-core 9800X3D, the 5080's link given two ways, an odd
  model name.
* **Stale or missing sources (plain LDR, o08):** its sources stopped in mid-2025 (it said so itself); no 2026 releases.
* **Numbers off (plain LDR, o02):** wrong bandwidths and slot layout.
* **Citation links (plain LDR, o07):** every inline link pointed to a different source than the numbered list.
* **No access to the user's files (plain LDR, o01):** pristine LDR has no file input.
* **Conflicting facts between reports:** o03's two reports disagreed on whether EN 18286 was cited in the OJ; one web
  search settled it (cited 14 Oct 2026). Deep medium's report was the wrong one.

## 5. Research vs chat waits (the user's checkpoint item)

At medium (13.5 h of deep medium runs): a chat message arriving at a random moment waits p50 11 s, p90 65 s, over a
minute 11 % of the time (xhigh: p50 50 s, p90 147 s, 43 %). The longest calls are now compaction (p50 64 s). By the
user's rule, pre-empt-and-replay is **not proposed**. Table: wait-table-2026-10-20.md.

## 6. Memory and stability

* 20 relief restarts across phases 1-3, all in report / citation-check stages. Lowest values: 16.7 GB (o08, 10-19 18:07,
  relief then at 18). Relief now 20 GB until proposal A; floor 12 GB since 10-19 evening.
* Dip breakdown (h05 xhigh, 10-20 01:10, 20.00 GiB) vs o03's 20.74: Strata +1.8 GiB (the rest of the engine; arena and
  parked chat cache the same), Chrome 3.1 GiB new; LDR and SearXNG smaller.
* No kernel error in phase 3 (kcheck after every run). One crash before phase 3 settled (10-18, ldr-web, lxml parsing
  in threads -> one page fetch at a time since).

## 7. Strata (the port round)

v0.2.1 (final, 10-20 03:04; engine 0.1.46) ported: our 26 commits applied without conflicts. Tested in gap 3
(03:08-04:19): quality identical to the 0.2.0 port (exact7 7/7, the same repeat hash; needles 72/72; probes as
C*18t), chat cache resumed = fresh (ALL PASS), speed vs C*18t: decode -1.7 / -2.0 %, prompts 0.7-0.9 % faster; our
GR_FORK / QSA_SPLIT_ATTN beat 0.2.0's sm_120 defaults (gap 2); Strata's tuner: "already fastest". Pictures (CPU
reader): ~1 GB RAM, no speed cost, text identical with the reader loaded once the expert cache size is pinned (the
engine's --vision costs 2 cache slots otherwise); a screenshot answered in 3.6-4.5 s to the first token with a few
misread digits at 300 image tokens. Not promoted: waits for this checkpoint and the user's OK. Details: strata-compare
results/r22/port-020-beta.md.

**Gap 4's answer (10-20 11:45-12:13): there is no decode loss.**
* With the same work in both arms (answer_room off), 0.2.1 decodes at parity with C*18t: 154.6 vs 153.2 tok/s, +0.9 %,
  inside the 150-156 per-arm spread.
* Thinking per round, acceptance and the 32K prompt are all level or slightly better.
* Gap 3's -1.7 / -2.0 % was answer_room: 0.2.1 stopped thinking at 3,072 tokens, C*18t thought to the cap.
* 0.2's RTX 50 defaults make no measurable difference here (off: -0.5 %), so they stay on as shipped.
* Afterwards: back on C*18t with the policy off; kernel log clean.
* **Ready to promote with answer_room on**, on your OK. Details: port-020-beta.md "Gap 4".

The background (why gap 4 was run):
* Before promotion (the user, 10-20): find the 1.7-2.0 % decode loss, 1 h gap after the replays (work/r22/gap4.sh).
* Already found without the GPU: the CPU pool is the same in both (15 workers on CPUs 1-15, host on 0), so 0.2's
physical-core rule changes nothing here. But 0.2.1's server closes thinking at 3/4 of max_tokens ("answer_room", new
since 0.1.45), so gap 3's decode screen did different work in the two arms (4,096-token long reasoning: C*18t thinks to
the cap; 0.2.1 thinks 3,072, then answers): its per-round numbers moved together (+7.6 % tokens per round, +9.5 % ms per
round). Gap 4 measures 0.2.1 with answer_room off (the same work) and with 0.2's new RTX 50 defaults off
(STRATA_SM120_PERF set, MMVQ_IL_120, MMVQ_IL_WIDE). Strata's tuner (gap 2, 0.2.0 port): "already fastest", no gains
-> no second run (the user's rule).

## 8. Phase 4 build list, ranked

### Build order (the user, 10-20 13:1x, final)

The "#" numbers refer to the candidate list below, which keeps its numbering for reference.

| order | item | candidate # | first test |
|---|---|---|---|
| 1 | Hardware profile + setup-claim check | #1 | stage 1: lead-answer replays (o07 call 650, o02 call 635) and the reports written from them; report replays from the original lead answers; the setup check on the saved o01 / o02 / o07 reports |
| 2 | "Not yet" fresh check | #2 | stage 1: on the saved o03 reports |
| 3 | Critic / verifier with two sources per claim | #8 + #7 | stage 1: the critic and verifier on the saved o02 / o03 reports; the second-source searches and re-research need stage 2 |
| 4 | "Tried / ruled out" list | #10 | stage 2 (changes what is searched): o01 |
| 5 | Evidence store (claims with quote, URL, date; round brief) | new | stage 1: build the store from the saved evidence (evidence.jsonl) and rewrite o01-o03; then stage 2 |
| 6 | Read sources whole, follow links to primary sources (round brief) | new | stage 2 (changes what is fetched) |
| 7 | Extra search sources: Tavily, Exa Lite, S2; Exa highlights; Exa shopping (product questions) - when credits allow | #6 + #4 + #9 | Exa highlights: stage 1 extraction replay; the rest stage 2 |
| 8 | Merged short runs (2-3 short runs merged vs one long run; round brief) | new | stage 2 |
| 9 | Early stop - last | #3 | stage 2 |

**Changes, the user 10-23 (after the phase 4 checkpoint):**
* Item 2 ("not yet" check) gets no separate stage 2-3 runs: it is bundled into the next item's stage 2-3 runs (item 4,
  the "tried / ruled out" list) - the "with" side runs both, o01 (item 4's test case) and o03 (item 2's) at stage 2.
* Early stop (order 9) is DROPPED from deep research. It stays only as an idea for quick research (parked below).
* Next: item 4, the "tried / ruled out" list.

Early stop (order 9, dropped from deep research 10-23), the user's rule:
* Keep it only if it does not cut thoroughness. The test: with early stop, the deep reports keep the same answers,
  sources and checklist points as without it.
* Consider it for quick research only. Long deep runs are fine with the user.

Measurement profile for phase 4: the Jan deep profile as decided 10-20 (medium; citation check xhigh), on P021 with the
chat-cache policy on.

### Candidate list (numbers as referenced above)

1. **The user's hardware/setup profile** given to the lead agent (in its system prompt, so its planning turn has it
   too; there is no separate planner) and the report writer, and claims about the user's setup checked against it.
   Cheap. Addresses o07 (the lead's final answer, not the plan, set a 21-23 GB file target on a PC that runs the 125B
   model from 96 GB of RAM; section 4) and o01's wrong CPU / link facts. Near the top by the
   user's decision (10-20).
   * **Test cases** (added by the user 10-20):
     * o07's 21-23 GB file target (first in the lead's final answer, call 650; the report outline made it a criterion);
     * o02's hardware mistakes in the report-writing replay (replays/report/o02/report-medium.md):
       * it claims the 9060 XT's x16 link "avoids throttling" in a chipset x4 slot (an x4 slot is x4 for any card);
       * it gives PCIe 4.0 x4 as "1/227th of the 5080's 960 GB/s", a ratio that is for the 5090's 1,792 GB/s.
     * Also in o02: the user's 4060 Ti taken as the 16 GB model - first in the lead's final answer (call 635; the plan
       only priced a 4060 Ti 16 GB as a candidate third card), then in the deep report and both replay reports.
     * Where each starts: o07's target and o02's 16 GB card in the lead's final answer; o02's x16 and 5090-ratio slips
       in the report writer (the medium replay only; the deep report and the xhigh replay got the 5090 ratio right).
   * **Pass:** the profile or the setup check removes or corrects each one.
2. **Fresh check of status claims** (added by the user 10-20):
   * **What counts:** any "not yet published / released / available / supported" claim.
   * **The check:** a new search, dated, for anything newer than the sources before the claim goes in a report. The
     report gives the result with its date.
   * **Test case:** o03's EN 18286 miss. It was published in the Official Journal on 14 October 2026.
     * Both report-writing replays say its citation is "pending".
     * So did one of the two 10-19 reports.
     * In the citation-check replay, xhigh flagged the claim against a cited source and medium passed it.
   * **Pass:** o03's report gives the 14 October publication.
   * Cheaper and narrower than item 7 (it checks only claims that something hasn't happened yet).
3. **Early stop** once the answer is confirmed in two sources. Deep spends 12-80 min on questions plain LDR answers in
   about a minute.
4. **Exa highlights instead of local extraction on some pages**, with the verbatim check. Extraction is 37 % of deep
   medium's LLM time (4.9 of 13.2 h of calls).
5. ~~A "frame check" after planning~~ - dropped from phase 4 by the user (10-20 evening): o07's error came after the
   plan, so it would not have caught it. Parked, see "Parked ideas" below.
6. **Extra sources, A/B on the screen set, judged blind:** Exa Lite, Tavily, Semantic Scholar. Cost-limited (Exa's $9
   cap covers ~9-35 deep runs; Tavily 950 searches/month).
7. **Two independent sources for important claims**, with disagreements recorded (o03's EN 18286 case).
8. Fresh-context critic + targeted re-research + revision; a verifier that removes unsupported claims.
9. Exa's shopping index for product questions (prices and where to buy).
10. **A "tried / ruled out" list from the user's files** (round brief): extracted once per file set, saved for the user
    to check, and given to the planner so known dead ends are not searched again. Test case: o01, whose checklist item 1
    is separating new ideas from ones already tried.

### Parked ideas

* **Early stop for quick research** (was order 9 / #3; dropped from deep research by the user 10-23): stop once the
  answer is confirmed in two sources. Only for quick research, where it could save time; long deep runs are fine.

* **Frame check after planning** (was #5; parked by the user 10-20 evening): a fresh-context pass that tests the plan's
  assumptions (budget, platform, dates, scope) against the question before research starts. Revisit if a screen run
  shows a wrong non-hardware assumption in a plan.

### How phase 4 tests each item (the user, 10-20)

**Stage 1: replay the saved runs.** Each item is first tried on the saved phase 3 runs.
* Pass: the error is gone in all 3 replays with the item, and still there in at least 2 of 3 replays without it.
* Sampling is at T 1.0, so a single replay can miss or fix the error by chance.
* If the error doesn't reproduce in the replays without the item, the replay can't decide. The item then goes to
  stage 2.

**Stage 2: full deep runs of the test case.** Only items that fix their test case get these, with and without the
item, on the new build. Judged blind.

**Stage 3: the screen set.** Only items that pass stage 2 get it.
* The screen set is the deep set used in phase 3: o01-o03 and the hard five, about 8.5 h per side.
* o07 and o08 are run as well when an item targets them.

Items that change what gets searched start at stage 2.

| item | stage 1 (replay) | test case |
|---|---|---|
| 1 hardware profile | at the step where each error starts: the lead's final answer replayed +/- the profile (o07 call 650, o02 call 635) and reports written from those answers; report replays from the original lead answers +/- the profile; the setup check on the saved reports (o01, o02, o07) | o07's 21-23 GB target and o02's 16 GB 4060 Ti (lead's final answer); o02's x16-in-x4 and 5090-for-5080 slips (report writer); o01's CPU/link facts |
| 2 "not yet" check | run directly on the saved o03 reports (deep medium, both replays, baseline) | EN 18286. False-alarm check: the same on the o01, o02 and o07 reports |
| 4 Exa highlights | extraction replay: Exa highlights vs our extraction on ~30 saved pages, blind, verbatim check (~30 Exa requests) | extraction quality |
| 8 critic + revision | the critic and verifier on the saved o02 and o03 reports. Its re-research needs stage 2 | o02 / o03 slips |
| 3, 6, 7, 9, 10 | none: they change what gets searched | 3: the hard five; 6: screen set; 7: o03; 9: new product questions; 10: o01 |

### Estimate

The estimate counts GPU time on the new build. My build time fits in the gaps between runs. Jan jobs go first and
can push things back.

| step | GPU time | when |
|---|---|---|
| Switch point (0.2.1 on 8080, memory checks, chat-cache policy) | ~1 h | right after your OK |
| New-build baselines, the "without" side for stages 2 and 3: o01-o03 + hard five + o07 | ~11 h | the first night |
| Stage 1 builds for items 1, 2 (profile + replay tools ~3 h, "not yet" checker ~3 h of my time) and their replays (#5 dropped 10-20 evening) | ~3 h | day 1 |
| Stage 2 for items 1, 2 if they pass: o07, o02, o03 with the item | ~10 h | night 2 |
| Stage 3: one "with" side for the items that passed (separate sides only if it regresses) | ~8.5 h | night 3 |
| **Items 1, 2 through all three stages** | **~34 h** | **~3 days** |
| Item 4 (Exa highlights): replay, then test case + screen side | ~11 h | +1 day |
| Item 8 (critic + revision): saved-report dry run, then full runs (longer runs) | ~15 h | +1-2 days |
| Items 3 and 10 (early stop, tried list): full runs, then screen side | ~18 h | +1-2 days |
| Item 7 (two sources): o03 runs, then screen side | ~11 h | +1 day |
| Item 9 (shopping): 3-5 product questions written and frozen first, 2 sides | ~15 h | +1 day |
| Item 6 (Tavily, Exa Lite, S2): one screen side each | ~25 h | limited by search credits |
| **Everything, if every item passes every stage** | **~130 h** | **~1.5-2 weeks** |

**Update for the final build order (10-20 13:2x):**
* Three items were added: evidence store, read sources whole, and merged short runs. Each needs full runs, roughly
  15-20 h more each.
* The whole list becomes about 180 GPU h, about 2-2.5 weeks.
* Items 1-3 of the new order through all stages: about 50 h, about 4-5 days.

Items that fail at stage 1 or 2 drop out, which shortens the whole thing. Item 6 depends on search credits:
* Tavily's 1,000 free credits a month cover about one screen side.
* Exa's $9 cap is also shared with the fallback.

So item 6 may wait for next month's allowance or a paid month.

My grading time is not in the table: about 30-45 min per pair of open-question reports.

Phase 4 runs on the new build (0.2.1 port + the chat-cache policy) and is compared with phase 3 by calls and tokens,
not minutes (the user's rule).

## 9. Decisions for the user

Decided 10-20:
* Morning:
  * Nights on for good (run/night-ok).
  * Pictures always on at the switch point (no load-on-demand patch).
  * Watchers as user services (done).
  * o07's frame error near the top of phase 4 (item 1).
* 11:5x: the Jan deep profile at medium except the citation check (xhigh). Applied to research-runner.py; the runner was
  restarted at 11:55.
* 12:0x: two additions to the phase 4 list:
  * the "not yet" check (item 2);
  * o02's mistakes as test cases for item 1.
* 12:1x: the replay-first testing order (section 8).
* Evening: the frame check (#5) dropped from phase 4 and parked as an idea; o07's error origin corrected (section 4:
  the lead's final answer, not the plan); item 1's stage 1 replays cover the lead's final answer and the report for o07
  and o02.

Open:
* Go for phase 4, and the order of the build list (section 8; the items 1, 2, 5 path is ~3 days).
* OK to promote the 0.2.1 port to 8080 at the switch point. Gap 4 found no decode loss (section 7).
  * What the promotion includes:
    * answer_room on;
    * pictures always on;
    * after the memory checks, the chat-cache policy on.
  * Then the queue service starts phase 4.
  * Also proposed (13:05): fold Strata v0.2.1.3 into the port at the same time.
    * The engine is unchanged.
    * It brings small server fixes: a 503 instead of a dropped connection when the engine can't start, and the
      picture reader's work folder is recreated if it's removed.
    * It merges with no conflicts.
    * Only a server smoke test is needed, and gap 3/4's measurements stand.
