# Which queue runs may be dropped after 3 failures (11-05, Karl's queue-failure rule)

Karl 11-05: "Queue failures: when one run fails 3 times, record it as failed and move on, the same way as D8, but
only where its frozen rules can still judge with that run missing. Otherwise, stop. If a second run reaches 3
failures, stop the queue and alert me."

Read from the frozen rules only (RULES-item8.md, RULES-c3c.md, RULES-p5.md, all frozen 11-05 12:30; PLAN-7D.md and
staging/post7d/WEEKEND-READY.md add nothing on missing runs). Where a rule does not clearly allow a missing run, the
answer is NO (the queue stops). The queue reads `results/bench2/queue-droppable.json` (exact run keys
SET/PROFILE/LABEL/ID per plan file); a plan not listed there (e.g. queue-plan-p4s9.json) has nothing droppable.

| plan | runs | droppable | not droppable (3rd failure = stop) |
|---|---|---|---|
| queue-plan-item8.json | 6 | **none** | screen/deep/p8a, p8b, p8c x o01, o03 |
| queue-plan-c3c.json | 3 | **none** | screen/deep/pc3c o01, o02, o03 |
| queue-plan-p5-holdout.json | 66 | **50: the 25 checkables on both arms** - holdout/baseline/p5 + holdout/deep/p5final c03 c04 c06 c08 c10 c12 c13 c15 c18 c19 c21 c23 c26 c28 c30; hard-holdout/baseline/p5 + hard-holdout/deep/p5final h11-h20 | the open three (holdout o04-o06, both arms), the harder four (p5-harder p5c1b p5c2 p5c5 p5c6, both arms), the o01 line (p5-o01 o01, both arms) |

At most one run per plan is dropped: a second run of the same plan reaching 3 failures stops the queue, droppable or not.

## item 8 - nothing droppable

- Each side is built from all three short runs per question: "screen-deep-p8a, p8b, p8c, o01 and o03 ... 62-min
  whole-run budget each (Fix 6: 3 x 40.3 = 120.9 research min = one 171-min run's research)", "merged per question by
  staging/item8/tools/merge-evidence.py". A missing short run leaves the merged side with two thirds of the long run's
  research time - not the comparison the rules define, and no rule says how to merge two.
- The score needs both questions: "checklist total per side, per question and summed (out of 22)"; "Mixed = ... the
  two questions go opposite ways".
- replays.sh itself refuses without all six ("runs/screen-deep-$l/$q is not finished").

## C3c - nothing droppable

- "Scored: the checklist total per side (per question, of 34)" (= o01 10 + o02 12 + o03 12); "mixed = a tie or a
  split (questions in opposite directions ...)". The B comparison is the three in-run reports vs p4s9's; no rule
  covers a missing question.

## Phase 5 - the 25 checkables only

- Allowed: RULES-p5.md section 3, "checkable (25): correct / wrong commitment / hedged / non-answer per arm
  (**+ not run**)". The 25-question line has a "not run" column by rule, and the tooling does it:
  staging/phase5/p5.py `packets --allow-missing` ("the missing ones become 'not run' in the report"), `tally` counts
  "not run" per arm. The line is "the sanity line"; the result is the open line.
- Not allowed:
  - open o04-o06: "**Result** = the open line: the final setup is better when its open total is higher ..." -
    "open: totals per arm (of 34)"; no "not run" there.
  - harder four: "harder (4): the class of each question per arm" - no "not run"; PHASE5-CHECKABLE-RULES.md (Karl
    10-28): "dropping one would make the line smaller and noisier and would tilt it against the baseline".
  - o01 line: "its own line ... reported on its own"; one question, two arms - nothing left to report without it.

## For Karl (reading, not decided here)

- A dropped checkable counts as "not run" for that arm only, so the sanity reading (D9: "a regression = the final arm
  has fewer 'correct' ...") can flag a regression - or hide one - by that one question. Recommended reading: compare
  the line on the questions both arms ran, beside the counts as tallied.
- At grading: `p5.py packets` needs `--allow-missing` when a run was dropped; `p5.py status` shows it as "not yet"
  (its folder is in results/bench2/runs-failed/); the record is results/bench2/queue-failures.tsv.
