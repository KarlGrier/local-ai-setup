# Item 7d - paid search on the follow-up searches (plan, staged 2026-11-03 09:00 CST; nothing installed or started)

**Karl's inputs.** 10-31: "consider spending the paid searches on the specific follow-up queries instead of first
come, first served." 7b (Tavily on every search) = a gain; Tavily is the source we kept. 7c (Exa Lite, research
questions) = no gain. 7a (Semantic Scholar) = not tested (HTTP 429 without a key). 7e (Exa, product questions) = a
small gain; 11-03: "carry Exa into 7d for product-type searches only, as a test arm." The paid-search rule stands
(<= 30 per test run, 25 % of the month kept for Jan chat, all stop at 10 % left; paid_budget enforces it), a fresh LDR
per question, each question's relief-restart count beside its grade.

**In short.** A deterministic rule picks the run's follow-up searches: nothing paid until the lead searches again after
its first wave of subagents has reported (or until search 101), then 3 paid searches per subagent and 10 for the lead,
up to the cap of 30. Two arms: **p7d** (Tavily on those searches; o01-o03 + s1-s4) and **p7dx** (the same, but Exa
instead of Tavily for product-tagged picks; s1-s4). 11 runs, ~32 GPU h, ~1.4 days of queue; <= 330 Tavily and
<= 120 Exa searches in the worst case (expected ~230 Tavily, ~50 Exa = $0.20), well inside November's credit.
Staged code + tests: `staging/item7d/` (install note `staging/item7d/INSTALL.md`).

## 1. What the logs show (the evidence for the rule)

Sources: `logs/paid-route.jsonl` (test rows of p7a/p7b/p7c/p7ex; p7b o03's discarded first attempt left out) joined
with each run's evidence store (`runs/<run>/deep/evidence.jsonl`: the agent, time and results of every search, later
fetches and reads) and its report (cited URLs), for the 20 open / product runs of p4s8, p7a, p7b, p7c, p7ew, p7ex, plus
the hard five. Script and full tables: `staging/item7d/analysis/followup_analysis.py` -> `followup-analysis.txt / .json`.

**How a run searches.** The lead makes 1-2 opening searches, then wave 1's subagents run one at a time (one worker),
each 1-32 searches. The lead's **first search after the subagents report** - its follow-up - comes at search 66-156
(median ~97 of 111-340; p7c o01 at search 5, its sub2-sub5 made no searches), 1,784-4,310 s into the run (median
~3,100 s). After it come the lead's own checks and wave 2+
(subtopics the lead picked from wave 1's findings). 2 of 20 runs (p7a o01, p7ex s4) had no lead follow-up search.
The hard five are lead-only (2-17 searches, no subagents).

**Where first come, first served put the 30.** Always searches 1-30 = the lead's opening + the first 1-3 subtopics:
3.6 agents per run on average; o02 p7b lead 2 + sub1 19 + sub2 9; s3 p7ex lead 1 + sub1 21 (21 rephrasings of the
board's slot layout) + sub2 8; o01 p7b lead 1 + sub1 3 + sub2 15 + sub3 11. On average 1.3 of the 30 fell in the
follow-up phase, all in one run (p7c o01). The refused searches were 79-91 % of every open run (115-295 per run).

**What follow-up searches look like** (all 20 runs; % of searches):

| group | n | words | quoted | number / model / version | store named | product tag | SearXNG URLs new to the run | SearXNG URLs used |
|---|---|---|---|---|---|---|---|---|
| lead opening | 41 | 11.2 | 0 | 95 | 2 | 27 | 94 % | 16.6 % |
| searches 1-30 (what 7b/7c/7e paid for) | 600 | 12.3 | 54 | 82 | 16 | 20 | 69 % | 7.6 % |
| wave 1 (all) | 2,034 | 12.4 | 53 | 81 | 16 | 25 | 61 % | 6.6 % |
| **lead follow-ups** | 317 | 13.6 | 32 | 95 | **30** | **42** | **44 %** | 9.2 % |
| **wave 2+** | 2,189 | 12.0 | 58 | 87 | 19 | 26 | **47 %** | 6.2 % |

- The lead's follow-ups are direct fact checks on named things: "RTX 5060 Ti 16GB Best Buy current price November
  2026 in stock deal under $650", "Gigabyte X870E AORUS ELITE WIFI7 manual "PCIEX4_1" "PCIEX4_2" slot position",
  "llama.cpp --moe-cache-mib expert cache pull request". Wave 2+ chases items wave 1 found: named papers and repos
  (CommitMoE, DALI, MoBiLE, DuoServe in o01), used-card listings (A4000, 3090) and slot / power checks (o02, s3).
- Karl's premise half-holds: the first 30 are the *opening*, but not broad - 54 % already carry quoted phrases and 82 %
  numbers or model names. "Specific" does not separate opening from follow-up; the run's phase does.
- SearXNG runs dry as a run goes on: the share of its URLs not seen earlier in the run falls 69 % (searches 1-30) ->
  59 -> 58 -> 51 -> 45 % (151+); 44 % on the lead's follow-ups, 47 % in wave 2+ (61 % in wave 1). A second engine has
  more to add there.
- Paid results were used about twice as often as SearXNG's at every point we can measure (only searches 1-30 ever
  sent): paid-only URLs later fetched / read / cited 22.2 % / 20.4 % / 13.5 % for an agent's 1st / 2nd-3rd / 4th+
  search, against 13.3 / 10.6 / 5.4 % for SearXNG's URLs of the same searches. No sign the paid source helps less on
  narrower searches. Per search, an agent's first three give 1.24-1.30 used paid URLs, its 4th+ 0.88 - hence 3 per
  subagent.
- Caveat: no paid search was ever sent past search 30 of an open question, so the value at follow-up positions is
  inferred from SearXNG's redundancy and the per-rank pattern, not measured. 7d measures it.

## 2. The rule (staged `search_route.select_step`, profiles `7d` / `7dx` in `paid-route.json`)

1. **Opening:** no paid source until the lead searches again after a subagent has searched, at least 15 min after the
   run's first search (the time guard keeps a parallel opening search from counting - the lead searched during sub1's
   first minutes 6 times in the 20 runs; the real follow-up came >= 1,784 s in), **or** until search 101 (backstop for
   runs without a lead follow-up).
2. **Follow-up phase:** each subagent's first 3 searches and the lead's first 10 get the paid source; paid_budget's run
   cap (30, both providers together) refuses the rest.
3. Searches without an agent label (not LDR's deep mode): none for the first 30, then first come, first served.
4. Unpicked searches = SearXNG only, exactly as p4s8.

The agent label is LDR deep mode's own ContextVar (`local_deep_research.deep.current_agent`), read by paid_search from
`sys.modules` in the web_search tool's thread - the same label the evidence store writes for that search. No change to
the LDR package or its hook. The per-run state is a locked file keyed by run id + run-file stamp (no month reset).

**Replay of the staged code over the 20 past runs** (same order and agents; `followup-analysis.txt`):

| | first come (7b/7c/7e) | 7d rule |
|---|---|---|
| paid searches per run | 30 | 26.9 (30 in 15 of 20; 28 p7ex s3; 19-20 s4; 15 p7a o01; 6 p7ew s1, which stopped at 111 searches) |
| share in the follow-up phase | 4 % | 86 % (the rest from the search-101 backstop) |
| agents reached per run | 3.6 | 7.7 (e.g. o02: lead 10 + sub7-sub16) |
| lead follow-up checks paid | 2.1 (its opening) | 7.5 |
| SearXNG URLs new to the run, on the paid searches | 69 % | 48 % |
| hard five | every search (2-17 per question) | 0 (lead-only) |

Rejected alternatives: skip the first N only (31-60 = again 2-3 subtopics); the classifier's tags as "specific" (see
the table: no separation); per-agent caps from search 31 (9.8 agents, but mostly wave 1's later subtopics, 2.7 lead
checks); lead follow-up only, no backstop (0 paid in 2 of 20 runs). Per subagent 4 reaches fewer agents (6.5); lead 12 gives
the lead 8.3 checks - the numbers are fixed before the runs (open choice d).

## 3. Arms and questions

| arm | route | questions | against |
|---|---|---|---|
| **p7d** - Tavily on the follow-up searches | 7d | o01-o03 + s1-s4 (7 runs) | p4s8 (o), p7ew (s), and p7b (o: first come vs the rule) |
| **p7dx** - p7d, but Exa instead of Tavily on product-tagged picks (the test arm) | 7dx | s1-s4 (4 runs) | p7d (s: the Exa read), p7ew |

- Exa *replaces* Tavily on a product pick (one paid source per pick, cap unchanged), so p7dx vs p7d isolates Exa on
  product follow-ups. The replay gives p7dx ~12 Exa picks per s-run (s1 ~5, s2 ~12, s3 ~17, s4 ~15): s1's contrast is
  weak (the classifier tags most SSD queries "general").
- **Not run:** the hard five (the rule pays nothing on lead-only runs, so they would replicate p4s8 - and every arm so
  far was 5/5); o02 in p7dx (only 5-14 of its picks are product-tagged; open choice b).
- Order (`queue-plan-7d.json.draft`): the s-pairs first, each pair back to back with the arm order flipped (s1 p7d ->
  p7dx, s2 p7dx -> p7d, s3 p7d -> p7dx, s4 p7dx -> p7d) so prices drift little within a pair and p7ew (11-02) stays
  close; then o01-o03 p7d. Same settings as 7a-7e: deep, medium / xhigh, items setup critic code fixes read claims,
  171 / 47 min, cache off, a fresh LDR per question; s-runs read user-setup-7e.md (bench2-queue.sh, as 7e).

## 4. Baselines

- **p4s8 for o01-o03: reusable**, on the same terms as 7a (which also ran on a fresh LDR against it): same engine
  (P028x f4c4f654fb24), settings and budgets; its SearXNG path = an unpicked 7d search. Differences: p4s8 ran on one
  long-lived LDR (restarts 1 / 0 / 1) and before the 10-31 item 7 install (routing off, SearXNG path unchanged); dates
  10-30/31 vs ~11-04 (o02 and o03 ask about October 2026; graders check on the report's date). p4s8 was graded three
  times: 27.5 / 27.0 / 28.5 of 34 - about +-1.5 per question is grader noise.
- **p7ew for s1-s4: reusable** (11-02, same build, setup file and fresh-LDR condition, SearXNG only). Caveats as in
  7e: s1 p7ew ended at 121 min on the model's own decision; 2-3 days of price drift.
- **Can NOT be reused:** a pair for p7dx - p7d's s1-s4 must be new (same days as p7dx). p7ex is not a baseline for
  either arm (Exa first come on every tag), only context.
- **p7b vs p7d (o01-o03)** is the direct test of the 10-31 idea, but not a clean baseline: p7b ran on the long-lived
  LDR (restarts 0 / 2 / 4, o03 flagged). Graded as its own round.

## 5. Costs

**Paid searches** (November so far, `tools/paid_tracker.py` 11-03 08:4x: Tavily 92 of 1,000 - tests stop at 750;
Exa $0.916 of $10 - tests stop at $7.50):

| | runs | cap (30 / run) | replay estimate |
|---|---|---|---|
| p7d o01-o03 | 3 | 90 Tavily | ~86 |
| p7d s1-s4 | 4 | 120 Tavily | ~97 |
| p7dx s1-s4 | 4 | 120 (Exa + Tavily) | ~97: Exa ~49 ($0.20), Tavily ~48 |
| **total** | 11 | **330** | **~231 Tavily, ~49 Exa** |

Worst case (all Tavily): 92 + 330 = 422 of 1,000 (328 left for tests / research below the 750 line; chat to 900).
Exa worst case: $0.916 + 120 x $0.004 = $1.40 of $10. The month lines are not approached.

**GPU and clock:** 11 runs x ~172 min (171-min budget + report; 7e's ran 169-176) = **~32 GPU h**, plus ~1 min per
fresh LDR. Start-to-end ~32-34 h of queue time plus any phase-4 gap that holds the queue between runs: installed and
started by ~11:00 11-03 -> done ~19:00-21:00 11-04 (night runs allowed, run/night-ok). Grading ~1.5 h after the last
run (rounds in parallel). The bench queue is idle now (7e finished 05:01; nothing live at 09:00).
While 7d runs, gap 17 (the v0.2.9 / v0.2.10 port), the NLL gap and the Basalt follow-ups take phase-4 gaps between
runs, as before.

## 6. Grading (blind, the method of 7a-7e)

`tools/blind-open.py`, the same `BLIND_DROP` (+ inline marks); one fresh Claude grader per question; o01-o03 against
my-research/ checklists with the real hardware; s1-s4 against 7e's answer keys (my-research/s1-s4, sha256 re-checked
against WRITTEN-7e.txt) and their 10-point checklists, prices checked on the reports' dates, US / USD,
user-setup-7e.md. Grades written to grades.jsonl before the key is opened; wrong claims counted; relief restarts
beside each grade (`staging/item7d/tools/relief_counts.py`, which also reads shop-7e runs), pairs with many more on one
side flagged; no undecided pages (a plain question in chat if a verdict hangs on Karl's preference). Rounds:

1. **blind-p7d**: p4s8 vs p7d, o01-o03 - the rule with Tavily against no paid search (as 7a-7c).
2. **blind-p7dx**: p7d vs p7dx, s1-s4 - the second read on Exa for product searches.
3. **blind-p7d-shop**: p7ew vs p7d, s1-s4 - Tavily follow-ups on product questions.
4. **blind-p7d-p7b**: p7b vs p7d, o01-o03 - first come vs the rule, same provider (recommended; grader time only).

Verdict per Karl's rule (7a / 7e): a gain needs the higher score with wrong claims not worse; a tie or a split is
mixed -> ask Karl. Per run also reported from the route log's `select` records: picks, where the follow-up began,
per agent, sent / refused.

## 7. Open choices for Karl

a. **Hard five:** skip (recommended: 0 paid searches under the rule, so a replicate of p4s8) or run them as in 7a-7c
   (+5 runs, ~3.7 GPU h, no paid search).
b. **o02 in p7dx:** no (recommended; weak contrast) or yes (+1 run, ~2.9 h, <= 30 paid, ~10 of them Exa).
c. **Round 4 (p7b vs p7d):** recommended yes.
d. **Rule numbers** (fixed before the first run): per subagent 3, lead 10, backstop search 101, guard 15 min - or
   more depth per agent (4 per subagent: 6.5 agents reached instead of 7.7; lead 12: 8.3 checks instead of 7.5).
e. **If 7d is adopted later:** lead-only runs (checkable questions) would get no paid search, and a research run
   (cap 100) would use only ~30-40 at 3 / 10 - the numbers would need scaling for Karl's research. Not part of the test.
f. **S2:** staged, not used by 7d - `s2_search.py` now reads `semanticscholar.key` when it exists and logs each call's
   HTTP status (`logs/s2-search.jsonl`). When the key is there: a 7a rerun, or an S2-on-academic arm on top of 7d -
   cost to Karl first.

## 8. Staged files (nothing installed)

- `staging/item7d/tools/`: search_route.py, paid_search.py, paid-route.json (+ 7d, 7dx; every other profile
  unchanged), s2_search.py (key + status log), relief_counts.py (+ shop-7e; run from staging).
- `staging/item7d/tests/run_all.sh`: test_select 52, test_paid_search_7d 29, test_s2 13 checks, and item 7's own three
  suites against the staged code - all pass 11-03 (offline: 127.0.0.1 mock, fake keys, temp files in
  staging/item7d/scratch).
- `staging/item7d/check.sh pre|post` (read-only), `install.sh` (not run), `INSTALL.md` (files, backups *.before-7d,
  checks, unit switch, confirmation, rollback; only with no LDR run, Jan job, bench queue, replay or grading live).
- `results/bench2/queue-plan-7d.json.draft` (11 steps; dry `bench2.py next --wide` -> s1 / p7d / route 7d).

## 9. Write-up note (Karl 11-04)

- **Every arm of item 7 (p4s8 through 7d) ran with the subagent step-limit bug (148 of 217 deep subagents since 11-01
  lost their findings at call 23).** Source: staging/ldr-study/PAPERS.md section 4 (recursion limit 2 x 30 + 10 = 70
  graph steps = the 23rd model call, before the step-limit wrap-up). This line goes into 7d's write-up - each 7d
  grading round's SUMMARY.md (results/bench2/blind-p7d, blind-p7dx, blind-p7d-shop, blind-p7d-p7b) - and into the
  item 7 summary sent to Karl. The fix (patch 0008, item "steps") is installed after 7d (staging/post7d); every later
  plan runs with it, against the fresh baseline p4s9.
