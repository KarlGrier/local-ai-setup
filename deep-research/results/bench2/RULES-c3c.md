# C3c (bigger fixed sizes at 131K) - evaluation rules (frozen 11-05 12:30 CST, before any result)

Frozen before any C3c result exists (at freezing: the fresh baseline p4s9 o01 is running; no C3c replay or pc3c run
has started). Taken from strata-compare/results/BACKLOG-1027.md row C3c (Karl 10-27), results/bench2/PLAN-ITEMS5-8-1027.md
("C3c goes before Phase 5, so Phase 5 measures the final build"), staging/post7d/README.md section 3 (Karl 11-04),
staging/post7d/profiles/flash-next-c3c.env and the grading method of blind-p7d. Nothing here is a new goal; points the
plan leaves open are marked **OPEN** (recommendations in staging/post7d/WEEKEND-READY.md). A change after the first
result needs a dated note and Karl's OK.

## 1. The question

Part (1) of C3c: at the current 131K context, do bigger fixed sizes help Qwen3.8-Flash-Next? Four values change
(profiles/flash-next-c3c.env = flash-next.env, sha256 28732eeb029b, with only these four lines different):

| size | flash-next (auto at 131072) | C3c | phase |
|---|---|---|---|
| LDR_DEEP_SUB_RETURN_MAX_CHARS (the lead's view of each subagent report) | 16000 chars | 32000 | research |
| LDR_DEEP_SNIPPET_CHARS (per search result) | 300 chars | 600 | research |
| LDR_DEEP_REPORT_EVIDENCE_TOKENS (evidence per section call) | 48000 tokens | 72000 | report |
| LDR_DEEP_REPORT_FINDINGS_TOKENS (subagent findings per section call) | 12000 tokens | 24000 | report |

Part (2) - 256K context - runs ONLY if part (1) helps, as its own test with Karl's OK; not in this chain.

## 2. What is compared

| comparison | C3c side | current side | what it isolates |
|---|---|---|---|
| **A: report half** (replays, Fri) | r-p4s9-c3c-oNN (fix-replay write on p4s9's evidence, evidence 72K + findings 24K) | r-p4s9-fn-oNN (the same evidence, flash-next sizes) | the two report-stage sizes, same evidence |
| **B: whole runs** (queue-plan-c3c.json, ~Sat) | screen-deep-pc3c oNN in-run reports (profile flash-next-c3c, all four sizes) | screen-deep-p4s9 oNN in-run reports | all four sizes, research included |

- Questions o01-o03 in both. Same settings on both sides: P028x (f4c4f654fb24), deep, medium / xhigh, items setup
  critic code fixes read claims **fix:steps**, 171 / 47 min, SearXNG only, a fresh LDR per question. The replays use
  `--fix all,read,claims --setup --critic --budget-left 3045` (staging/post7d/replays.sh).
- The hard five are not run (tied 5/5 at the ceiling). Item 8's retry at C3c sizes (r-p8m-c3c vs r-p4s9-c3c) is
  item 8's comparison (RULES-item8.md).
- A replay marked VOID (a phase-4 gap opened while it ran) is not graded; its rerun is. A run the watchdog requeued
  is graded on its finished attempt and flagged.
- **Amendment 2026-11-06 (Karl; from this point on, not applied to finished runs):** "A run whose end check passes
  counts as complete; log the trip and flag it in the results." A run that trips tools/ldr-client.py's during-run search
  rule (research_common.search_health: the latest 6 searches all empty, or more than half of >= 6 failed) is no longer
  FAILED for the trip alone; the end check (search_health at the end of the run) decides. Passed -> complete as normal
  (summary.json, bench.json), the trip logged (search-trip.json: when, the rule's counts, the empty searches in a row,
  the outage until searches came back; a "flagged: search trip, end check passed" line in logs/bench2-queue.log) and
  flagged in bench.json ("search_trip"); the flag is shown beside the grades (staging/post7d/tools/relief_counts.py's
  flag column: p4s9 pc3c) and in each round's SUMMARY.md; failed -> FAILED as before. LDR is no longer sent a terminate
  at the trip (it never stopped a deep run: p4s9 o03 11-05 ran on to "completed"). Runs that ended before this amendment
  keep their class (p4s9 o03's tripped first attempt, failed-attempt-1105-233256, stays a failed attempt; its rerun is
  the graded run).

## 3. Grading (blind, the method of 7a-7e)

- Rounds, compared within a round only: **blind-c3c-rep** (A: r-p4s9-c3c vs r-p4s9-fn, o01-o03, after the replays)
  and **blind-c3c** (B: pc3c vs p4s9, o01-o03, after queue-plan-c3c.json finishes).
- tools/blind-open.py, BLIND_OUT=results/bench2/blind-<round>, BLIND_DROP="Setup check,Check these,Version
  check,Arithmetic check,Consistency check" (+ inline marks); one fresh Claude grader per question; prompt =
  blind-p7d/grader.md with the o-question parts (my-research/o01-moe-from-ram.md 10, o02-third-gpu.md 12,
  o03-eu-ai-act.md 12 = 34; user-setup.md hardware lines; 2 / 1.5 / 1 / 0.5 / 0; wrong claims counted; claims
  checked on the report's own date); grades to grades.jsonl before the key is opened; no undecided pages.
- Each round's SUMMARY.md carries the step-bug line (section 6).

## 4. Metrics

Scored: the checklist total per side (per question, of 34) and wrong claims per side.

Reported beside the grades - the backlog's "plus run time and steps completed (bigger reads are slower; the lead
compacts more often)":
- run time: bench.json wall_s and research_clock_s, deep/stats.json report_seconds and left_s (under Fix 6 the whole
  run is held to its 171-min budget, so cost shows as less research done or checks cut, not as a longer run);
- steps completed: searches, pages_read, sources_seen, subagents (deep/stats.json); subagent findings lost to the step
  limit (expected 0); lead compactions ("Compacting lead history", research-logs.json); plan_notes / skipped (checks cut
  to fit the time); summary.json largest_prompt / largest_context (vs the report writer's 121.8K limit), errors,
  min_avail_gb;
- relief restarts per question (staging/post7d/tools/relief_counts.py p4s9 pc3c; replays: replays-summary.txt);
  a pair where one side had many more is flagged.

## 5. Decision rules (Karl's rule, as for 7a-7e)

Per comparison: **gain** = the C3c side's total higher AND its wrong claims not higher; **mixed** = a tie or a split
(questions in opposite directions, or score and wrong claims in opposite directions) -> ask Karl; **worse** = lower
total -> ask Karl. Grader noise as in RULES-item8.md (**OPEN (D9)**: a gain within <= 1.5 points of 34).
11-05 Karl: the OPEN (D9) points confirmed as recommended (set before any result).

| A (report half) | B (whole runs) | reading |
|---|---|---|
| gain or tie | gain | **C3c helps** -> candidate for adoption: the bases in deep/modelprofile.py change so 131K derives the bigger sizes (the profile's own note); part (2), 256K, becomes eligible (Karl's OK) |
| gain | tie, mixed or worse | **OPEN (D9)** - ask Karl; candidate = the two report sizes only; 11-05 Karl: the OPEN (D9) points confirmed as recommended (set before any result). |
| worse | gain | **OPEN (D9)** - ask Karl; candidate = the two research sizes only; 11-05 Karl: the OPEN (D9) points confirmed as recommended (set before any result). |
| no gain | no gain | C3c not adopted; no 256K test |

- Either way (backlog C3c, Karl 10-27): the sizes become derived from the profile's context setting (C3b), at today's
  values unless C3c is adopted.
- Cost: reported, not a gate - the plan sets no threshold (**OPEN (D9)**; recommendation: a C3c run that hits its
  client stop, or a section prompt over the 121.8K limit, makes that run's result "worse" whatever its score).
  11-05 Karl: the OPEN (D9) points confirmed as recommended (set before any result).
- C3c's B result arrives after Phase 5 would start on Saturday; Phase 5's model profile is Karl's call (D4 in
  WEEKEND-READY.md), not decided by these rules.

## 6. The step-bug note (Karl 11-04; PLAN-7D.md section 9)

Every arm since p4s8 (p4s8 and all of item 7 through 7d) ran with the subagent step-limit bug until 11-05 (deep
subagents stopped at their 23rd model call before writing findings: 148 of 217 since 11-01; staging/ldr-study/PAPERS.md
section 4). Both C3c comparisons run with the fix (fix:steps, installed 11-05 11:14) against the fresh baseline p4s9.
Their scores are not comparable with any round before 11-05; the line goes into each round's SUMMARY.md. (With the fix,
subagents now write findings that used to be lost, so the findings per section - one of the four sizes - may matter
more than the 10-27 backlog row assumed.)
