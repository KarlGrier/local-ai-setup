# Phase 5 holdout - evaluation rules (frozen 11-05 12:30 CST, before any result)

Frozen before any Phase 5 run exists (no holdout-*-p5 / *-p5final folder; the plan is not started and has no GO-p5).
Taken from results/bench2/PLAN.md (10-18: "Phase 5 holdout ... on baseline and the final setup"; "the holdout's
checkable questions are only a quick sanity check; the final result is judged on the open-ended holdout reports
(o04-o06)"), hard-build-p5/PHASE5-CHECKABLE-RULES.md (Karl 10-28, frozen), staging/phase5/README.md (the tooling and
its open questions), staging/post7d/README.md section 4 + NOTES 11-04 10:43 (Karl's answers: o01 with the 8 GB text as
its own line, checkables at 47 min, baseline pristine), staging/post7d/phase5/p5.json and PLAN-7D.md section 9.
Nothing here is a new goal; points the plan leaves open are marked **OPEN** (recommendations in
staging/post7d/WEEKEND-READY.md). The final setup's contents are Karl's adoption calls (D2-D6 there); these rules hold
for whichever setup he picks. A change after the first result needs a dated note and Karl's OK.

## 1. What is compared

| arm | what | runs folders |
|---|---|---|
| **baseline** | pristine LDR 1.10.7 (run-ldr.sh `LDR_PROFILE=baseline`: baseline/site/ first on PYTHONPATH; no deep mode, no phase-4 items, no paid search) | `<set>-baseline-p5` |
| **final** | the final setup as adopted - staged: deep, medium / xhigh, items setup critic code fixes read claims **fix:steps**, 171 / 47 min, model profile flash-next, route none (SearXNG only); Karl's calls may add a paid route (apply-p5.sh) or another profile | `<set>-deep-p5final` |

Both arms on the same engine, P028x (configs/P028x.json, f4c4f654fb24): `p5.py check-engine` at the switch and before
grading; a fresh LDR per question.

| line | questions | role |
|---|---|---|
| **open (3)** | holdout o04, o05, o06 | **the result** (PLAN.md 10-18) |
| **harder checkable (4)** | p5-harder p5c1b, p5c2, p5c5, p5c6 (FROZEN-p5-harder.txt) | its own line; each question's class shown per setup |
| **checkable (25)** | holdout c03 c04 c06 c08 c10 c12 c13 c15 c18 c19 c21 c23 c26 c28 c30 + hard-holdout h11-h20 | the sanity line |
| **o01, 8 GB text** (if Karl keeps it in) | p5-o01 o01 (FROZEN-p5-o01.txt) | its own line, outside the holdout totals: phase 4 was tuned on o01 |

Order (queue-plan-p5-holdout.json): open, harder, checkable, then the o01 pair; within each set the baseline first,
then the final setup, so the two arms of a question are close in time. Frozen files checked (`p5.py check-frozen`)
at the switch and again before grading.

## 2. Grading (blind)

- **Checkable (25 + 4):** `p5.py packets` -> results/bench2/blind-p5/checkable/: each run's Answer section only
  (else Key findings, else the lead before the sources), cleaned, citations and links taken out, labels in a random
  order. Batches of 5 (b6 = the harder four), one fresh grader per batch, grader-checkable.md, against the frozen keys
  only (no web search). Classes per answer, exactly one: **correct / wrong commitment / hedged / non-answer**; only
  "correct" scores; the four counts are reported separately per arm (Karl 10-28: guessing vs admitting it does not
  know matters). The whole-report string match is a cross-check only, never the score.
- **Open (3):** tools/blind-open.py packets (BLIND_OUT=blind-p5/open, BLIND_DROP from p5.json = "Setup check,Check
  these,Version check,Arithmetic check,Consistency check" + any section a newly adopted item writes); one fresh
  grader per question, grader-open.md, references my-research/o04-moe-projects.md (5 items = 10), o05-qwen4-flash.md
  (5 = 10), o06-ups.md (7 = 14); scale 2 / 1.5 / 1 / 0.5 / 0; wrong claims counted; claims checked on the report's
  own date.
- **o01 line:** its own round, blind-p5-o01 (blind-open.py, the same BLIND_DROP, grader-open.md with
  my-research/o01-moe-from-ram.md, 5 items = 10, and the 8 GB card in the question). Not in p5.py's tally.
- Grades written before any key is opened; `p5.py tally` refuses until every grade is in, then writes REPORT.md +
  p5-results.json. No undecided pages.
- Fix 1c on held-out data (Karl 10-30): the version check's marks on the final setup's reports are judged
  separately (staging/phase5/README.md step 7), not part of the grades.
- REPORT.md carries the step-bug line (section 5).

## 3. Metrics

- open: totals per arm (of 34), wrong claims per arm, top errors;
- harder (4): the class of each question per arm;
- checkable (25): correct / wrong commitment / hedged / non-answer per arm (+ not run);
- the string cross-check and where it disagrees;
- per run: engine sha + rc, wall time; swap since `p5.py swap-mark`; relief restarts per question
  (staging/post7d/tools/relief_counts.py p5 p5final - the item7d copy does not read holdout folders), pairs with many
  more on one side flagged; with a paid route: paid searches sent / refused per run (tools/paid_tracker.py), and a run
  the watchdog requeued is flagged (its rerun keeps only the run's remaining cap of 30).

**Amendment 2026-11-06 (Karl; from this point on, not applied to finished runs):** "A run whose end check passes
counts as complete; log the trip and flag it in the results." A run that trips tools/ldr-client.py's during-run search
rule (research_common.search_health: the latest 6 searches all empty, or more than half of >= 6 failed) is no longer
FAILED for the trip alone; the end check (search_health at the end of the run) decides. Passed -> complete as normal
(summary.json, bench.json), the trip logged (search-trip.json: when, the rule's counts, the empty searches in a row,
the outage until searches came back; a "flagged: search trip, end check passed" line in logs/bench2-queue.log) and
flagged in bench.json ("search_trip"); the flag is shown beside the grades (relief_counts.py's flag column; p5.py
REPORT.md "## Runs": "flagged runs"); failed -> FAILED as before. LDR is no longer sent a terminate at the trip (it
never stopped a deep run: p4s9 o03 11-05 ran on to "completed"). Runs that ended before this amendment keep their
class (p4s9 o03's tripped first attempt, failed-attempt-1105-233256, stays a failed attempt; its rerun is the graded
run).

**Amendment 2026-11-05 (Karl; recorded before any Phase 5 result - no Phase 5 run had started, the queue was still on
p4s9):** a checkable dropped on one arm (the queue's 3-failure rule, results/bench2/queue-failures.tsv "dropped") is
left out of BOTH arms for the checkable comparison: the tallies above are computed over the checkables run on both arms
only. The number of dropped pairs is reported next to the result ("checkable: N of 25 pairs compared, D dropped: <ids>").
If more than 3 of the 25 are dropped, the Phase 5 comparison is marked WEAKENED in the write-up.

## 4. Reading the result

Phase 5 is the final measurement of the adopted setup, not an A/B toward a further adoption; the plan sets no pass
threshold. The reading is frozen as:
- **Result** = the open line: the final setup is **better** when its open total is higher and its wrong claims are not
  higher (Karl's rule); a tie or a split (questions in opposite directions, or score and wrong claims in opposite
  directions) is reported as **mixed**; a lower total as **worse**. Grader noise reference: +-1.5 of 34 (p4s8 graded
  three times, PLAN-7D.md section 4).
- **Sanity lines** (harder 4, checkable 25): **OPEN (D9)** - recommended: a regression = the final arm has fewer
  "correct" or more "wrong commitment" answers than the baseline on that line; a regression is flagged to Karl beside
  the open result, whatever the open line says.
  11-05 Karl: the OPEN (D9) points confirmed as recommended (set before any result).
- The o01 line is reported on its own (Karl's real hardware question), never added to the totals.

**OPEN (D9; staging/phase5/README.md open questions, recommendations in WEEKEND-READY.md):**
11-05 Karl: the OPEN (D9) points confirmed as recommended (set before any result).
- Q3 o05's reference (10-18) says Qwen4 Flash is unreleased: if it is out by grading time, an `open_ref_notes` line
  for o05's grader before grading.
- Q5 the baseline's answer text (no "## Answer" heading): keep the whole summary before the sources (as p5.py does).
- Q6 locks and checks: kcheck at the switch, `p5.py status` swap change, kwatch running; + kcheck when the queue
  finishes.
- Q7 write protection: chmod 444 on the p5-harder question / answer / FROZEN files (the hashes do not change).

## 5. The step-bug note (Karl 11-04; PLAN-7D.md section 9)

Every arm since p4s8 (p4s8 and all of item 7 through 7d) ran with the subagent step-limit bug until 11-05
(staging/ldr-study/PAPERS.md section 4). Phase 5's final arm runs with the fix (fix:steps); the baseline arm is pristine
LDR, which has no deep subagents, so the bug does not apply to it. No pre-11-05 run is a Phase 5 comparison side, and
Phase 5's scores are not compared with any phase-4 round's.
