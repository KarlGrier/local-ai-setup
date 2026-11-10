# Item 7: paid search routes for the deep research bench (write-up, 11-05)

Written 11-05 by a write-up helper, at Karl's request ("item 7, note the subagent 23rd-call bug"). It covers 10-27 to
11-05 12:3x and is desk work only: no run, search, API call or model call was made for it. Every number has its
source in brackets. The file names are listed at the end. "My sum" means a total added up here from the sources.

> **Read this first: every item 7 run worked without most of its subagents' findings.**
>
> - Every arm of item 7 ran with the subagent step-limit bug, from the baseline p4s8 through 7d.
> - Since 11-01, **148 of 217 deep subagents** stopped at exactly their **23rd model call**. They lost their findings:
>   the lead got only "Research on '...' reached iteration limit."
> - Why: LDR gives a deep subagent a LangGraph recursion limit of 2 x 30 + 10 = 70 graph steps. With our deep
>   middleware every round takes **three** graph steps (the middleware's own node, the model, the tools). So the graph
>   stops at call 23, before the middleware's step-limit wrap-up at call 29 could make the subagent write up what it
>   found.
> - Examples: 7a o01 lost 6 of 11 subagents, 7c o01 9 of 16, and p4s8 o01 13 of 17. Their 141 / 181 / 194 extractions
>   reached the lead only as "reached iteration limit". In 7a o01 this was the subagent that had read the
>   KTransformers paper.
> - The bug is in every LDR log since 10-19. The 148 / 217 count was taken 11-04 ~10:20, so 7d's later runs are not in
>   it, but they ran without the fix too.
> - **Fixed 11-05 11:14** with patch 0008 "steps": the limit is now 3 x calls + 10. A subagent that still hits the limit
>   hands its own extractions (up to 12k chars) to the lead. In the tests the subagent wraps up and answers at call 30.
>   Jan's deep jobs also start with "steps" now.
> - **What this means:** the item 7 comparisons are fair between arms, because every arm carried the bug equally. But
>   every run worked without most of its subagents' write-ups, so the absolute scores are below what the fixed build
>   may reach. The fresh baseline **p4s9** (running since 11-05 11:14) and every later plan have the fix.
> - Fixed subagents run longer (30 calls instead of 23), so fewer waves fit the budget. That needs a bench A/B.
>
> [staging/ldr-study/PAPERS.md section 1 point 1, section 4, section 5; NOTES 11-04 10:2x and 11-05 11:14;
> PLAN-7D.md section 9]

## Bottom line

| part | what it tested | verdict | by |
|---|---|---|---|
| 7a | Semantic Scholar on every search | **not tested (rate-limited)**: 616 of 650 calls failed with HTTP 429 | Karl 11-02 |
| 7b | Tavily, first come (the first 30 searches) | **a gain**: 30.0 vs 27.5 of 34, 15 vs 19 wrong claims; carried by o02 | Karl 11-01 |
| 7c | Exa Lite, first come | **no gain**: 27.0 vs 27.0, 25 vs 19 wrong claims; not adopted, no rerun | Karl 11-01 |
| 7e | Exa first come on product questions (shop-7e, s1-s4) | **a small gain**: 29.0 vs 26.0 of 40; rests on s1; Exa carried into 7d as a test arm | Karl 11-03 |
| 7d | Tavily on the lead's follow-up searches (o01-o03, s1-s4) | 4 rounds graded 11-05: mixed vs p4s8 (by PLAN-7D's rule: not a clear win), no gain vs 7b head to head, not a gain on product questions -> Phase 5 runs with no paid search (Karl 11-05) | - |
| 7dx | 7d, but Exa on the product-tagged picks | **no gain over 7d** by Karl's rule (25.5 vs 28.0 of 40); a reading, not a verdict yet | - |

- 7b is still the only route with a clean gain (a higher score and fewer wrong claims). It comes from one round and
  rests on one question (o02, the dated shopping question) [blind-p7d-OVERALL.md].
- 7d worked as designed: it reached 6-10 agents per run instead of 3-4. But its paid results were not used more, and
  were cited less [blind-p7d-OVERALL.md].
- **Phase 5's paid route: none** (Karl 11-05, by PLAN-7D's own rule - see "Decided 11-05" at the end).

## What was common to every arm

- **Build and settings.** Strata P028x (engine f4c4f654fb24) on 8080. LDR deep mode with the items setup, critic,
  code, fixes, read and claims. Budgets 171 min for open questions and 47 min for the checkable "hard five" (under
  Fix 6 that is ~120 / ~31 research min, the report after) [NOTES 10-27 20:28, 10-30 17:16; blind-p7* SUMMARY.md].
- **Baselines.**
  - **p4s8:** o01-o03 + the hard five, SearXNG only. It ran 10-30 17:16 - 10-31 12:32 on one long-lived LDR, with
    relief restarts 1 / 0 / 1. h08 was cut by the 10-31 suspend and rerun from its start [NOTES 10-30 17:16, 10-31
    11:5x, 10-31 12:3x].
  - **p7ew:** s1-s4 without paid search. It ran 11-02 on a fresh LDR per question [blind-p7e/SUMMARY.md].
- **The paid-search rule** (Karl 10-27): at most 30 paid searches per test run and 100 per run of Karl's research.
  Tests and research stop when 25 % of a month is left; all paid search stops at 10 % left. tools/paid_budget.py
  enforces it [PLAN-ITEMS5-8-1027.md section 3; PLAN-7D.md].
- **A refused search is a SearXNG-only search, not an empty one.** The hook always takes SearXNG's results first. The
  route adds the paid source's new URLs only when the search is sent [NOTES 10-31 22:12].
- **Blind grading.** tools/blind-open.py strips the setup / check / consistency notes and the inline marks
  (BLIND_DROP). Fresh Claude graders (one per question in 7a-7e, one per round in 7d) graded the open questions
  against my-research/ checklists with the real hardware, and s1-s4 against 7e's answer keys with prices checked on
  the reports' dates. Grades were written before the key was opened. Wrong claims were counted. Each question's
  relief-restart count sits beside its grade; a pair is flagged when one side has 2 or more extra
  [blind-p7*/SUMMARY.md; PLAN-7D.md section 6].
- **Karl's verdict rule.** A gain needs the higher score with wrong claims not worse. A tie or a split is mixed, and
  goes to Karl [PLAN-7D.md section 6; blind-p7a/SUMMARY.md].

## The parts, one by one

### 7a: Semantic Scholar on every search (free API)

**Asked:** would a paper index help the research questions? **Arms:** p4s8 vs p7a (route 7a), o01-o03 + the hard
five. p7a ran on a fresh LDR per question. **Graded blind** 11-02 02:5x-03:02 [blind-p7a/SUMMARY.md].

| question (out of) | p4s8 | p7a | wrong claims p4s8 / p7a | relief restarts p4s8 / p7a |
|---|---|---|---|---|
| o01 (10) | **9.5** | 7.0 | 2 / 8 | 1 / 2 (flagged) |
| o02 (12) | 8.5 | **10.0** | 8 / 5 | 0 / 2 (flagged) |
| o03 (12) | 10.5 | **11.5** | 5 / 3 | 1 / 2 (flagged) |
| open total (34) | 28.5 | 28.5 | 15 / 16 | 2 / 6 |
| hard five | 5 / 5 | 5 / 5 | | 0 / 0 |

**What Karl decided, in order** [blind-p7a/SUMMARY.md; NOTES 11-02 03:5x, 07:2x, 08:0x]:
1. 11-02 03:5x: "no gain", route dropped, by his rule "If it made more wrong claims: record 'no gain' and drop it"
   (16 vs 15).
2. 11-02 07:2x: revised to "no worse" after his o01 check. Only 2 of o01's 8 wrong claims trace to paper sources, so
   Semantic Scholar was kept as a possible 7d route for paper-type queries.
3. 11-02 08:0x, **final: 7a NOT TESTED (rate-limited).**
   - The route's Semantic Scholar calls failed on **616 of 650** searches (o01 143 / 149, o02 254 / 269, o03 219 /
     232). The cause is HTTP 429 from the unauthenticated pool; s2_search.py swallowed the error.
   - The calls added 5 results in all, so p7a ran essentially SearXNG-only. The grades compare two SearXNG runs.
   - Karl will request a free key himself (~/.config/deep-research/semanticscholar.key, read from the file only). On
     11-03 14:3x he made it optional; nothing waits on it.
   - s2_search.py now reads the key when it exists and logs each call's HTTP status (installed with 7d).
   - The two paper errors in o01 came through ordinary search results: backlog C6 "LDR misreads papers".

No paid credit was used (Semantic Scholar is free).

### 7b: Tavily on every search, first come (cap 30)

**Asked:** does a second, paid web index help? **Arms:** p4s8 vs p7b, o01-o03 + the hard five, on the long-lived
LDR. **Graded blind** 11-01 11:33 [blind-p7b/SUMMARY.md].

| question (out of) | p4s8 | p7b | wrong claims p4s8 / p7b | relief restarts p4s8 / p7b |
|---|---|---|---|---|
| o01 (10) | **9.0** | 8.0 | 4 / 4 | 1 / 0 |
| o02 (12) | 7.5 | **10.5** | 9 / 6 | 0 / 2 |
| o03 (12) | 11.0 | **11.5** | 6 / 5 | 1 / 4 (flagged, against p7b) |
| open total (34) | 27.5 | **30.0** | 19 / 15 | 2 / 6 |
| hard five | 5 / 5 | 5 / 5 | | 0 / 0 |

- **Route log:** searches wanted / sent to Tavily / refused were o01 190 / 30 / 160, o02 201 / 30 / 171 and o03
  202 / 30 / 172. On the hard five every search was sent (3 / 4 / 17 / 3 / 5). Only the first ~30 searches of an
  open question reached Tavily [blind-p7b/SUMMARY.md; NOTES 11-01 10:11].
- **The cap breach (my bug, 10-31 19:43).** p7b o03's first attempt sent 60 Tavily searches. paid_budget.py cleared
  the per-run counts at the UTC month change (19:00 local). Karl chose option 1: rerun o03 after the hard five and
  delete nothing. The attempt is kept in runs/screen-deep-p7b/o03/failed-attempt-1031-220945/, and its count was
  renamed so the rerun got its own 30. The fix (run counts that survive the month change) was planned for after
  item 7's parts [NOTES 10-31 19:43, 22:12].
- **Karl's picks:** six points the checklist could not decide went to his To-rate page. 11-01 12:16: he did not rate
  them ("I do not know what's right and wrong there"). **7b verdict on the graders' scores: a gain**, not dropped.
  From 7c on there are no undecided pages, only a plain question in chat when needed [blind-p7b/SUMMARY.md; NOTES
  11-01 12:16].
- **The restarts run against p7b** (6 vs 2), so they do not explain its lead.

### 7c: Exa Lite on every search, first come (cap 30)

**Arms:** p4s8 vs p7c, o01-o03 on the long-lived LDR, then the hard five on a fresh LDR each. **Graded blind** 11-01
14:4x-14:56 [blind-p7c/SUMMARY.md].

| question (out of) | p4s8 | p7c | wrong claims p4s8 / p7c | relief restarts p4s8 / p7c |
|---|---|---|---|---|
| o01 (10) | **9.0** | 6.5 | 4 / 8 | 1 / 3 (flagged) |
| o02 (12) | 7.0 | **9.5** | 11 / 10 | 0 / 4 (flagged) |
| o03 (12) | 11.0 | 11.0 | 4 / 7 | 1 / 4 (flagged) |
| open total (34) | 27.0 | 27.0 | 19 / 25 | 2 / 11 |
| hard five | 5 / 5 | 5 / 5 | | 0 / 0 |

- **Route log:** 30 Exa searches per open run, the first refusal at search #31 in each. The hard five sent 19 / 19
  [blind-p7c/SUMMARY.md].
- **Verdict (Karl 11-01, option 1): no gain.** Route 7c is not adopted and not rerun. Exa stays an option for 7d.
- **Caveat:** p7c had 11 relief restarts against 2, every pair against p7c, on the long-lived LDR. That may hide a
  small effect [blind-p7c/SUMMARY.md; NOTES 11-01 15:0x].

### 7e: Exa first come on product questions (the shop-7e set)

**Asked:** Exa 3.0 added a shopping index (listings with prices and availability) that 7c's research questions never
exercised. **Questions:** s1-s4, Karl's 10-28 picks, frozen with hashed answer keys (s1 PCIe 5.0 SSD, s2 192 GB RAM,
s3 second GPU, s4 cold storage). **Arms:** p7ew (SearXNG only) vs p7ex (route 7c, Exa, first 30 sent), each on a
fresh LDR. They ran 11-02 07:03 - 11-03 05:01 [NOTES 11-02 07:03, 11-03 05:01].

**Karl's steps** [NOTES 11-02 07:03, 07:1x, 08:0x; 11-03 06:5x]:
1. 11-02 07:03: "Bring me 7e's questions now so 7e can run first."
2. 11-02 07:1x: switch the paid arm to Tavily, unless 7e was designed for Exa. It was (the shopping index), I said
   why, and Karl put it **back to Exa as designed**, with no third arm.

**Graded blind** 11-03 05:0x-05:25 [blind-p7e/SUMMARY.md].

| question (out of 10) | p7ew (without) | p7ex (Exa) | wrong claims w / Exa | relief restarts w / Exa |
|---|---|---|---|---|
| s1 SSD | 5.5 | **8.5** | 6 / 6 | 0 / 2 (flagged) |
| s2 RAM | **6.5** | 5.5 | 7 / 4 | 3 / 2 |
| s3 GPU | **7.0** | 6.5 | 6 / 10 | 2 / 1 |
| s4 storage | 7.0 | **8.5** | 6 / 6 | 1 / 1 |
| total (40) | 26.0 | **29.0** | 25 / 26 | 6 / 6 |

- s1's "without" run ended at 121 min on the model's own decision: completed, no errors, 3,023 s of budget left
  [blind-p7e/SUMMARY.md].
- **Verdict (Karl 11-03): a small gain for Exa on product questions.** It rests on s1: without s1 the arms tie,
  20.5 / 20.5. Karl: "carry Exa into 7d for product-type searches only, as a test arm."
- The same summary records s1's subagents "each at its 23-call limit, as usual": the step bug, seen before anyone
  knew it was one.

### 7d: paid search on the follow-up searches (Tavily; 7dx = Exa on product picks)

**Karl's idea (10-31):** "consider spending the paid searches on the specific follow-up queries instead of first
come, first served" [NOTES 10-31 22:12; PLAN-7D.md].

**What the earlier route logs showed** [PLAN-7D.md section 1, 20 past runs]:
- First come always spent the 30 on the lead's 1-2 opening searches plus the first 1-3 subtopics: 3.6 agents per
  run, and only 1.3 of the 30 fell in the follow-up phase.
- The lead's first follow-up comes at search 66-156 (median ~97).
- SearXNG runs dry as a run goes on: 69 % of its URLs are new to the run on searches 1-30, but only 44-47 % at the
  follow-ups.
- Paid URLs were used about twice as often as SearXNG's at every measured rank.

**The rule (staged 11-03 09:00, installed and started the same morning):**
- No paid search until the lead searches again after its first wave of subagents (at least 15 min in), or until
  search 101 as a backstop.
- Then each subagent's first 3 searches and the lead's first 10 get the paid source, within the run cap of 30.
- A replay over the 20 past runs gave 26.9 paid searches per run, 86 % of them in the follow-up phase, reaching 7.7
  agents instead of 3.6 [PLAN-7D.md section 2; NOTES 11-03 09:0x].

**Arms:**
- p7d: Tavily under the rule, on o01-o03 + s1-s4.
- p7dx: the same, but Exa replaces Tavily on product-tagged picks, on s1-s4.
- The hard five were not run (the rule pays nothing on lead-only runs). **Karl 11-03 14:3x kept the defaults:** no
  hard five, no o02 in p7dx, grading round 4 kept, and the rule's numbers 3 / 10 / search 101 / 15 min [NOTES 11-03
  14:3x].

**Graded blind** 11-05 12:07-12:18, one fresh grader per round [blind-p7d*/SUMMARY.md, blind-p7d-OVERALL.md]:

| round | arms | score | wrong claims | relief restarts | questions won | reading (not a verdict) |
|---|---|---|---|---|---|---|
| 1 blind-p7d (o01-o03, of 34) | p4s8 / p7d | 28.0 / **31.0** | 8 / 11 | 2 / 2 | p7d 2, tie 1 | mixed: higher score, more wrong claims; carried by o02 (+2.5) |
| 2 blind-p7dx (s1-s4, of 40) | p7d / p7dx | **28.0** / 25.5 | 22 / 19 | 2 / 3 | p7d 3, p7dx 1 | no gain for Exa on product follow-ups; only s4 (-2.5) beyond noise |
| 3 blind-p7d-shop (s1-s4, of 40) | p7ew / p7d | 27.0 / **28.0** | 17 / 22 | 6 / 2 (3 pairs flagged) | p7ew 3, p7d 1 | not a gain: +1.0 with 5 more wrong claims, resting on s1; without s1 p7ew leads 21.5 / 19.5 |
| 4 blind-p7d-p7b (o01-o03, of 34) | p7b / p7d | **30.0** / 27.5 | 12 / 15 | 6 / 2 (o03 flagged, against p7b) | p7b 2, tie 1 | no gain for the rule over first come with the same provider |

Per question [the four SUMMARY.md files]:

| question | round 1: p4s8 / p7d | round 4: p7b / p7d | round 2: p7d / p7dx | round 3: p7ew / p7d |
|---|---|---|---|---|
| o01 (10) | 9.0 / 9.0 (p4s8 ranked ahead) | **8.5** / 8.0 | | |
| o02 (12) | 8.0 / **10.5** | **10.0** / 8.0 | | |
| o03 (12) | 11.0 / **11.5** | 11.5 / 11.5 | | |
| s1 (10) | | | **8.5** / 8.0 | 5.5 / **8.5** |
| s2 (10) | | | 5.0 / **6.5** | **7.0** / 6.5 |
| s3 (10) | | | **7.0** / 6.0 | **7.5** / 6.5 |
| s4 (10) | | | **7.5** / 5.0 | **7.0** / 6.5 |

**What the route logs showed** [blind-p7d-OVERALL.md; blind-p7d/SUMMARY.md, blind-p7dx/SUMMARY.md,
blind-p7d-p7b/SUMMARY.md]:
- **The rule worked as designed.** Paid searches started at the lead's follow-up, between searches 79 and 136. The
  exception was p7dx s3: its follow-up came at search 245, and the backstop sent 27 of the 30.
- **It reached more agents.** 6-10 agents per run against 3-4 under first come, and the lead got 3-10 paid checks
  (p7b: 1-2, all in its opening). 7 of 11 runs hit the cap of 30.
- **It searched where SearXNG repeats itself.** 34-56 % of SearXNG's URLs were new to the run on the picked searches,
  against 59-76 % under first come.
- **But the paid results were not used more:**

| | paid-only URLs later used | cited |
|---|---|---|
| open questions, 7d | 9.0 % | 3.8 % |
| open questions, 7b (first come) | 9.7 % | 6.7 % |
| product questions, Tavily on follow-ups (p7d) | 7.7 % | 6.0 % |
| product questions, Exa first come (p7ex) | 18.2 % | 9.0 % |
| product-tagged picks: Exa (p7dx) | 23.1 % | 12.0 % |
| product-tagged picks: Tavily (p7d) | 5.1 % | 3.5 % |

- Exa's product results were used about 4x as often as Tavily's, but the grades did not move with them.
- **Wrong claims:** p7d had more than the other arm in 3 of the 4 rounds (+3, +5, +3). Recurring 7d errors:
  - overpromised gains (a 47-55 % Engram repack on a table that is already 4-bit, a "27-34 %" bottleneck);
  - spec slips (the 5080 at "1,792 GB/s", the 2080 Ti called "Ampere");
  - board-map errors (a "PCIe 3.0 x2" slot, M2D_SB lane sharing);
  - the trap pick on s3 (a used 4060 Ti 16 GB).
- **Dates:** p4s8 and p7b ran 10-30 to 11-01, p7d's o-runs on 11-05, and o02 / o03 ask about October 2026. Each report
  was judged on its own date [blind-p7d/SUMMARY.md; PLAN-7D.md section 4].

## Paid-search spend

| part | Tavily | Exa | source |
|---|---|---|---|
| 7a | 0 | 0 | Semantic Scholar is free; 650 calls, 616 HTTP 429 [blind-p7a] |
| 7b | 122 = 90 on the open questions (30 x o01, o02, o03 rerun) + 32 on the hard five; plus 60 in o03's discarded first attempt = **182** | 0 | blind-p7b; NOTES 10-31 19:43, 11-01 10:11 (my sum) |
| 7c | 0 | 90 open + 19 hard five = **109** (~$0.44) | blind-p7c (my sum; it matches the November counter's $0.436 at 11-01) |
| 7e | 0 | 30 x 4 = **120** (~$0.48) | blind-p7e (my sum; the counter went $0.436 -> $0.916) |
| 7d + 7dx | **273** | **63** (~$0.25) | blind-p7d-OVERALL.md (includes p7dx s2's stuck attempt: 10 Tavily + 3 Exa); the plan expected ~231 / ~49, worst case 330 |
| **item 7** | **455** | **292** (~$1.17) | my sum |

- **The month counters** [PLAN-7D.md section 5; NOTES 11-04 10:0x]:
  - Before 7d (11-03): Tavily 92 of 1,000 and Exa $0.916 of $10.
  - Mid-7d (11-04 10:0x): Tavily 201 and Exa $1.01.
  - 7d's 273 / 63 would put November at about 365 Tavily and $1.17 Exa if nothing else used them. That is my
    arithmetic: the end-of-7d counter is not in these sources, and Jan chat and Karl's research share the credits.
- **Limits:** the test stop lines are 750 Tavily and $7.50 Exa. They were never approached. The only per-run cap
  breach was 7b o03's first attempt, the month-change bug above.

## Grader noise: compare within a round only

- **p4s8 graded four times:** 27.5 (7b round), 27.0 (7c), 28.5 (7a), 28.0 (7d round 1). The same reports moved by up
  to 1.5 points on one question [blind-p7a/SUMMARY.md; blind-p7d-OVERALL.md].
- **Other repeats:** p7b scored 30.0 twice (two graders). p7ew scored 26.0, then 27.0.
- **p7d's o-reports:** 31.0 in round 1 and 27.5 in round 4. o02 alone got **10.5 and 8.0**, 2.5 apart on the same
  report and the widest spread so far.
- **So a gap of up to ~2.5 on one open question can be grader noise.** Every comparison above is within one round.
- The 7d rounds used one grader per round, not one per question (the 7d brief allowed at most four).

## Relief restarts and the long-lived LDR

- **The restarts.** The runner restarts 8080 when MemAvailable drops below 20 GB. They came 1-7 a day on 10-28..10-31
  and 14 on 11-01 by 10:10. ldr-web grew from 301 MiB to 4.7 GB on one long-lived LDR [NOTES 11-01 10:11].
- **A fresh LDR for every question (Karl 11-01 11:27)**, from p7c h02 on. p4s8, p7b and p7c's open questions ran on
  one long-lived LDR; p7a, 7e and 7d ran fresh [NOTES 11-01 11:27, 11:33].
- **Leak study (11-04).** No large object leak was found: ldr-web keeps the memory of its biggest transient peak,
  because glibc does not return freed memory. The 0007 memwatch patch (malloc_trim after each research and after big
  pages) was installed 11-05 11:14 with the step fix [staging/ldr-study/MEMORY.md as summarized in NOTES 11-04 10:2x;
  NOTES 11-05 11:14].

## The 11-03 stall, the fetch guard and the watchdog

- **The stall (11-03 18:47 - 22:3x).** 7d's s2 p7dx stopped calling the model.
  - Subagent sub6 had fetched Team Group's compatibility "result" page with no product chosen: **263.7 MB of HTML**
    (5.5 MB gzip), one table of 165,933 rows. The G.Skill page was innocent (66.6 KB).
  - LDR's extraction pipeline (BeautifulSoup, then trafilatura, then newspaper4k, which grows roughly with the square
    of the row count, >= 3 h) ran on the whole page. It held the process-wide fetch lock, and the one subagent worker
    was taken.
  - The per-subagent backstop counts research-clock time, and that clock stops while the GPU gate is held.
  - Result: 215 CPU-min on one thread and a 16.9 GB peak. Relief restarts could not help, and 8080 idle-stopped.
  - The attempt's 10 Tavily + 3 Exa stay on its own record [staging/fetchguard/REPORT.md section 1; NOTES 11-03
    22:3x].
- **Karl's answers (11-03 22:5x):**
  - a stuck-run watchdog;
  - a per-page guard ("a pathological page gets skipped, logged and counted");
  - the s2 pair moved after the s3 and s4 pairs;
  - a report on LDR's background document scheduler.
- **The watchdog** was installed 11-03 23:08 in gap 17a, with no LDR run live.
  - A run with no model-call progress for 30 min is stopped, marked faulted and requeued once on a fresh LDR. A second
    hang of the same run sends an alert and stops.
  - results/bench2/watchdog-faults.tsv does not exist (checked 11-05), so it has not fired since [NOTES 11-03 23:08].
- **The fetch guard** (LDR patch 0006) was installed 11-03 23:22-23:3x [NOTES 11-03 23:3x, 11-04 07:3x; REPORT.md
  sections 2-3].
  - A 16 MiB cap on the decompressed download, and a 400,000-tag cap before any parser.
  - Each skip is logged and counted (logs/fetch-guard.jsonl, summary.json "fetch_guard"). A 60-s watchdog logs slow
    pages but cannot stop a parse.
  - It is live from the s3 pair on. Karl kept the 16 MiB cap on 11-04. By 07:3x it had 403 page records, 0 skips and
    a largest page of 2.7 MiB.
  - Over 13,564 past extractions since 10-18, only the Team Group page never finished.
  - My slip: its install first dropped the watchdog's --watchdog-min option. That was fixed before any run.
- **s2 p7dx was rerun** 11-04 with a fresh 30 paid searches (Karl 11-04 (2)) [NOTES 11-04 07:3x].

## The scheduler-off change (11-04) and the queue's failure stop

- **The document scheduler.** LDR's background "Process Documents" job copied the newest researches' sources into
  karl's LDR library [fetchguard/REPORT.md section 4].
  - Nothing we measure reads it.
  - Its cost: ~6-7 % of a core, ~0.7-2 GB of downloads and many 403s per LDR lifetime, and it shares rate-limit keys
    with research PDF fetches.
- **Karl 11-04: off** (LDR_DOCUMENT_SCHEDULER_ENABLED=false in run-ldr.sh), for the bench, the runner and Jan's
  research [NOTES 11-04 07:3x].
  - The 7d s1 and s3 pairs and the stuck s2 attempt ran with it **on**.
  - The s4 pair, the s2 pair and o01-o03 ran with it **off**.
  - p4s8, p7b, p7c, p7a and 7e all ran with it on.
  - Within round 2 every pair ran under the same condition. Rounds 1, 3 and 4 compare p7d (off) with baselines (on).
    The expected effect is only wall-clock noise (<= 1-2 %, not measured), with no effect on model calls, searches or
    the report.
- **The three-search-failures stop** now exits 0 instead of 1. Before, systemd's Restart=on-failure restarted the
  queue after 60 s with the failure count reset [NOTES 11-04 07:3x].

## Other events that touched item 7

- **10-31 11:40: a suspend, not a power loss.** The power key suspended the PC during p4s8 h08. h08 was rerun from
  its start, and Karl had the PC rebooted before the item 7 install [NOTES 10-31 11:5x - 12:52].
- **10-31: the DST audit.** Budgets and deadlines use epoch or monotonic time. Several logs carry naive local
  timestamps. Their fix was planned together with the paid_budget month fix after item 7's parts. Neither is
  recorded as done in these sources [NOTES 10-31 10:08, 22:12].
- **After 7d (11-05 11:14):** the LDR fixes 0007 + 0008 were installed (not 0009 "papers"), pillow went to 13.0.0,
  and the bench moved to queue-plan-p4s9.json, the fresh baseline with fix:steps [NOTES 11-05 11:14].

## Decided 11-05 (Karl), after this write-up's first draft

- **Phase 5's paid route: none.** Karl: apply 7d's own decision rule from PLAN-7D.md as written (section 6: "a gain
  needs the higher score with wrong claims not worse; a tie or a split is mixed"), not a judgment after the results;
  anything short of a clear win means no paid search, including borderline or mixed rounds. blind-p7d (p4s8 vs p7d,
  o01-o03) is 28.0 vs 31.0 of 34 with wrong claims 8 vs 11 - mixed, not a clear win. So Phase 5 runs SearXNG only:
  results/bench2/queue-plan-p5-holdout.json (66 runs, ~38.5 GPU h, paid cap 0, o01 8 GB line in, the final arm =
  the deep profile with p4s8's items + fix:steps, the papers fix off), armed 11-05 12:5x by staging/post7d/GO-p5 =
  its sha256 3e1d0589fcc7.... Engine P028x.
- The 7d / 7dx round readings stand as recorded above (mixed vs p4s8; no gain vs 7b; no gain on product questions;
  no gain for Exa on product picks).

## Open decisions (Karl's; nothing here decides them)

1. **A paid route later:** (c) settle 7b vs no paid search on the fixed build against p4s9 - every item 7 arm carried
   the step bug, so the fixed build's subagents may change what a second index adds. For Karl's own research (cap
   100): first come would spend all 100 on the opening searches, and 7d's 3 / 10 numbers only ~30-40 (open choice (e)
   in PLAN-7D.md).
2. **Semantic Scholar:** a 7a rerun, or an academic arm, only once Karl's optional key exists, with the cost told to
   him first [NOTES 11-02 08:0x, 11-03 14:3x].
4. **Housekeeping planned "after item 7's parts":** the paid_budget month-change fix and the local-time log stamps.
   Neither is recorded as done.

## Sources

- results/bench2/PLAN-ITEMS5-8-1027.md (section 3: the credit rule)
- results/bench2/PLAN-7D.md (sections 1-9)
- results/bench2/blind-p7a/, blind-p7b/, blind-p7c/, blind-p7e/, blind-p7d/, blind-p7dx/, blind-p7d-shop/,
  blind-p7d-p7b/ (SUMMARY.md, KEY, grades), and blind-p7d-OVERALL.md
- NOTES.md 10-27 to 11-05 12:3x (the 7a-7e lines, the GRADED BLIND lines, Karl's decisions)
- staging/ldr-study/PAPERS.md (the step bug: sections 1, 4, 5)
- staging/fetchguard/REPORT.md (the 11-03 stall, the guard, the document scheduler)
- results/bench2/watchdog-faults.tsv: not present on 11-05
