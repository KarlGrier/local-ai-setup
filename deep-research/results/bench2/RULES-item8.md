# Item 8 stage 2 - evaluation rules (frozen 11-05 12:30 CST, before any result)

Frozen before any item 8 stage 2 run exists (at freezing: the fresh baseline p4s9 o01 is running; no p8a/p8b/p8c
run, no merge and no replay of this stage has started). Taken from results/bench2/PLAN-ITEMS5-8-1027.md section 4,
staging/post7d/README.md section 3 (Karl's answers 11-04), staging/item8/README.md, the method of
results/bench2/blind-i8/SUMMARY.md (stage 1, 10-30) and blind-p7d/grader.md, and PLAN-7D.md sections 6 and 9. Nothing
here is a new goal; points the plan leaves open are marked **OPEN** (with the recommendation in
staging/post7d/WEEKEND-READY.md). A change after the first result needs a dated note and Karl's OK.

## 1. The question

Do three short research runs, merged into one evidence store and written up as one report, beat one long run with
the same research time? (PLAN-ITEMS5-8-1027.md section 4: "If it looks good: short runs at stage 2, then stage 3.")

## 2. What is compared

| side | runs | evidence | report stage |
|---|---|---|---|
| **merged** | screen-deep-p8a, p8b, p8c, o01 and o03 (queue-plan-item8.json): 62-min whole-run budget each (Fix 6: 3 x 40.3 = 120.9 research min = one 171-min run's research) | merged per question by staging/item8/tools/merge-evidence.py (`--lead-share-tokens 10000`, interleaved order) -> staging/post7d/item8/merged/oNN-p8; `test_merge.py --verify` must pass first | replay **r-p8m-fn-oNN** |
| **long** | screen-deep-p4s9 oNN (queue-plan-p4s9.json, the fresh baseline, one 171-min run) | the run's own deep/evidence.jsonl | replay **r-p4s9-fn-oNN** |

- Both sides: P028x (f4c4f654fb24), model profile flash-next, deep, medium / xhigh, items setup critic code fixes read
  claims **fix:steps**, SearXNG only (no paid search), a fresh LDR per question.
- Both reports come from the SAME report stage: `tools/fix-replay.py write --fix all,read,claims --setup --critic
  --budget-left 3045` (a 171-min run's report time; staging/post7d/replays.sh). So the comparison isolates the
  evidence (three short explorations merged vs one long one), not the report writer.
- **Retry at C3c's report sizes (Karl 10-29; on):** **r-p8m-c3c-oNN vs r-p4s9-c3c-oNN** - the same pair with the
  report stage's evidence 72K and findings 24K tokens per section (the merged stores have 1.5-1.8x the read pages of
  one run, and the fixed sizes may eat the gain - staging/item8/README.md open point 4).
- Questions: o01 and o03 only. o02 belongs to stage 3 (later). The hard five are not added (tied 5/5 at the ceiling).
- Not compared: the short runs' own in-run reports; p4s9's in-run reports (C3c's comparison side, RULES-c3c.md).
- A replay marked VOID by replays.sh (a phase-4 gap opened while it ran) is not graded; its rerun is.
- **Amendment 2026-11-06 (Karl; from this point on, not applied to finished runs):** "A run whose end check passes
  counts as complete; log the trip and flag it in the results." A run that trips tools/ldr-client.py's during-run search
  rule (research_common.search_health: the latest 6 searches all empty, or more than half of >= 6 failed) is no longer
  FAILED for the trip alone; the end check (search_health at the end of the run) decides. Passed -> complete as normal
  (summary.json, bench.json), the trip logged (search-trip.json: when, the rule's counts, the empty searches in a row,
  the outage until searches came back; a "flagged: search trip, end check passed" line in logs/bench2-queue.log) and
  flagged in bench.json ("search_trip"); the flag is shown beside the grades (staging/post7d/tools/relief_counts.py's
  flag column, per run: p8a p8b p8c p4s9) and in each round's SUMMARY.md; failed -> FAILED as before. LDR is no longer
  sent a terminate at the trip (it never stopped a deep run: p4s9 o03 11-05 ran on to "completed"). Runs that ended
  before this amendment keep their class (p4s9 o03's tripped first attempt, failed-attempt-1105-233256, stays a failed
  attempt; its rerun is the graded run).

## 3. Grading (blind, the method of 7a-7e and blind-i8)

- Two rounds, scores compared within a round only:
  - **blind-i8s2**: r-p8m-fn vs r-p4s9-fn, o01 + o03 (can start when replays.sh logs "item 8 replays done");
  - **blind-i8c3c**: r-p8m-c3c vs r-p4s9-c3c, o01 + o03 (after the last replay).
- `tools/blind-open.py`, BLIND_OUT=results/bench2/blind-<round>, BLIND_DROP="Setup check,Check these,Version
  check,Arithmetic check,Consistency check" (+ inline marks stripped, as every round since blind-p7a).
- One fresh Claude grader per question. Prompt = results/bench2/blind-p7d/grader.md with the o-question parts only:
  references my-research/o01-moe-from-ram.md (5 items = 10) and o03-eu-ai-act.md (6 items = 12); the hardware lines
  of user-setup.md; scale 2 / 1.5 / 1 / 0.5 / 0 per checklist item; wrong claims counted (confident factual claims
  checked and found wrong); a claim that matches its source on the report's own date is right (the replays are written
  11-06 from evidence gathered 11-05/06). No key, runs, notes or other rounds opened; grades written to grades.jsonl
  before the key is opened; no undecided pages (a plain question to Karl if a verdict hangs on his preference).
- Each round's SUMMARY.md carries the step-bug line (section 6).

## 4. Metrics

Scored:
- checklist total per side, per question and summed (out of 22);
- wrong claims per side (the graders' count) and the top errors.

Reported beside the grades (not scored):
- relief restarts: per replay (staging/post7d/item8/replays-summary.txt, "relief N" = research-runner.log relief
  restarts inside the replay's window) and per run (staging/post7d/tools/relief_counts.py p8a p8b p8c p4s9); a pair
  where one side had many more is flagged;
- the merge: merge-summary.json (sources per run -> merged, pages read, subagents, lead tokens whole -> share);
- per run: deep/stats.json searches, pages_read, sources_seen, subagents; subagent findings lost to the step limit
  ("reached iteration limit" in deep/subagents.md - expected 0 with fix:steps); lead compactions ("Compacting lead
  history" in research-logs.json); wall_s;
- per replay: calls.json seconds, stats plan_notes (checks cut to fit 3045 s), skipped checks.

## 5. Decision rules (Karl's rule, as for 7a-7e)

- **Gain** = the merged side's total is higher AND its wrong claims are not higher.
- **Mixed** = a tie, or a split: the two questions go opposite ways, or the score and the wrong-claim count point
  opposite ways (the reading used in 7c's verdict) -> stop and ask Karl.
- **Worse** = the merged side's total is lower -> stop and ask Karl.
- Grader noise: p4s8 graded three times scored 27.5 / 27.0 / 28.5 of 34 (PLAN-7D.md section 4).
  **OPEN (D9):** does a higher total within that band (<= 1.5 points) count as a gain, or as mixed?
  11-05 Karl: the OPEN (D9) points confirmed as recommended (set before any result).
- What follows (no GPU step is chained on it; each result goes to Karl when it is in):
  - blind-i8s2 a gain -> item 8 goes on to stage 3 (o02 with o01 + o03, the long side p4s9) after Karl's OK; the
    research-only mode for short runs and Fix 6's N-window budget (staging/item8/README.md open point 6) are coded then.
  - blind-i8c3c a gain while blind-i8s2 is not -> the merge needs C3c's report sizes: read together with
    RULES-c3c.md; mixed -> ask Karl.
  - neither a gain -> item 8 is dropped (no stage 3), noted with the step-bug line.
- Item 8 is not part of Phase 5 in any case: the queue cannot run merged short runs and the final build has no code
  for them (**OPEN (D7)**, recommendation: confirm).

## 6. The step-bug note (Karl 11-04; PLAN-7D.md section 9)

Every arm since p4s8 (p4s8 and all of item 7 through 7d) ran with the subagent step-limit bug (deep subagents
stopped at their 23rd model call before writing findings: 148 of 217 since 11-01; staging/ldr-study/PAPERS.md section 4)
until 11-05. Both sides here run with the fix (fix:steps, LDR patch 0008, installed 11-05 11:14): p4s9 is the fresh
baseline and p8a/p8b/p8c come after it. So this stage's scores must not be compared with stage 1 (blind-i8, 10-30:
merged p4s3 + p4s6 + p4s7 vs b-w-bundle, inputs from before the fix and not counted for the bug) or any round before
11-05; the line goes into each round's SUMMARY.md.
