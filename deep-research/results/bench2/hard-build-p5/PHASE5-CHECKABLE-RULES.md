# Phase 5 checkable questions - Karl's decisions (2026-10-28 ~11:30)

1. **The four new questions are approved** (p5c1b, p5c2, p5c5, p5c6). Each states its time frame in the question (an
   "as of" date, or the specific election, edition or reporting period), so the frozen answers cannot drift:
   - p5c1b: the October 5, 2026 election; "after the judicial recounts, as of October 28, 2026" (recounts ended 10-22);
   - p5c2: the 2026 Hugo Awards; the official statistics "as of October 28, 2026";
   - p5c5: "reported for 30 September 2026 in their Q3 2026 earnings releases";
   - p5c6: "the 2026 Solheim Cup".
   FROZEN 10-28 (no pilot): results/bench2/questions-p5-harder.jsonl and answers/answers-p5-harder.jsonl (answer,
   accepted forms, distractors, time frame); sha256 in results/bench2/FROZEN-p5-harder.txt.
2. **Grading, every checkable question in Phase 5 (the 25 and the 4): the Answer-section rule, graded blind.** The grader
   reads only the report's "## Answer" section (the key findings if there is no such section) and puts each answer in
   exactly one class:
   - **correct** - commits to the key's answer (an accepted form), with no rival named as possibly right;
   - **wrong commitment** - commits to an answer that is not the key's (a distractor or anything else);
   - **hedged** - names several candidates without committing, or the key plus a rival "possibly" - not correct;
   - **non-answer** - no answer, or says it could not determine / find it.
   Only "correct" scores. The report shows the four counts separately (Karl: guessing vs admitting it does not know
   matters), per arm, for the 25 and for the 4 on their own lines. The old whole-report string match is kept only as
   a cross-check, never as the score.
3. **Pilot: SKIPPED (Karl 10-28):** all four are kept as they are, with no drop step. With only four, an easy question
   just ties and costs nothing; dropping one would make the line smaller and noisier and would tilt it against the
   baseline (the quick profile runs pristine LDR, the baseline's code). tools/p5-pilot.sh is kept but not run.
4. **Scoring line-up:** the 4 are added to the holdout's 25 checkable questions and reported as their own line:
   "checkable (25)", "harder checkable (4)", "open (3)". Within the harder line, each of the four questions' class
   (correct / wrong commitment / hedged / non-answer) is shown per setup.
