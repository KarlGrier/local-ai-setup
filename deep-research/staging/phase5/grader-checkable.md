# Blind grading - Phase 5 holdout, checkable questions, batch {BATCH}: {QIDS}

You classify the final answers that research reports gave to short factual questions. Each question has one answer
per setup, labelled A, B (and so on) in a random order. You do not know how any of them was produced; do not try to
guess, and do not let length, style or confidence of tone decide anything.

**Files (read only; absolute paths):**
- For each id in your batch: {OUT}/checkable/<id>/question.md (the question, with its time frame) and the answers
  {OUT}/checkable/<id>/A.md, B.md, ... (only the report's Answer section; citations and links were taken out).
- The frozen answer key: one JSON line per id in
  /home/USER/ai/deep-research/results/bench2/answers/answers.jsonl (ids c..),
  /home/USER/ai/deep-research/results/bench2/answers/answers-hard.jsonl (ids h..) and
  /home/USER/ai/deep-research/results/bench2/answers/answers-p5-harder.jsonl (ids p5c..).
  Read only the lines of your ids. Fields: "answer"; "accept" (accepted forms); "number" {"value", "tol"} (a number
  within tol of value is the key's answer); "note"; "distractors" (known wrong answers); "time_frame".
- The rules (section 2): /home/USER/ai/deep-research/results/bench2/hard-build-p5/PHASE5-CHECKABLE-RULES.md

**Do NOT open anything else:** no KEY file, no other packet folder or grades file under {OUT}, nothing else under
/home/USER/ai/deep-research/results/bench2/ (runs, reports, notes, summaries), nothing under
/home/USER/ai/deep-research/jobs/, reports/, results/deep-runs/, results/quick-runs/ or data/. No web search: the key
is frozen and was verified from primary sources; grade against it, not against the web. Do not build or run anything.

**Classes - exactly one per answer:**
- **correct** - commits to the key's answer (an accepted form, or a number within tol), with no rival named as
  possibly right;
- **wrong commitment** - commits to an answer that is not the key's (a distractor or anything else);
- **hedged** - names several candidates without committing, or the key plus a rival "possibly" - not correct;
- **non-answer** - no answer, or says it could not determine / find it.

**How to apply them:**
- "Commits" = the text states one answer to the question asked as the answer. A superseded or rejected figure given
  as context ("40 on election night, 39 after the recounts") is not a rival when the text clearly settles on one.
  A rival "possibly right" is one the text leaves open ("39 or 40", "most likely 39, though 40 is possible").
- The same value written another way is the key's answer (thirty-nine = 39; a full name for an accepted
  abbreviation). A rounding that the key's accept list does not cover and that could equally be a distractor is not.
- Class by the final answer to the question as asked. An answer to another reading of the question (another approach,
  date, edition, round or category than the question names) is a wrong commitment unless its value is the key's.
- A wrong side detail next to a correct core answer (a wrong date, a wrong secondary number) does not change the class;
  name it in "why".
- An answer that commits to one value but adds a general caveat ("figures may be revised") is still a commitment; one
  that says it could not confirm the answer and offers a best guess is hedged if it names the guess, a non-answer if
  it names none.
- Grade each answer on its own against the key; do not compare A with B.
- If you think the key itself is wrong, still classify against the key and say why in "key_doubt".

**Write one file per id:** {OUT}/checkable/grades/<id>.json
{"id": "<id>", "batch": "{BATCH}", "graded": "YYYY-MM-DD HH:MM",
 "class": {"A": "correct" | "wrong commitment" | "hedged" | "non-answer", "B": ...},
 "committed_to": {"A": "the answer it commits to, or null", "B": ...},
 "why": {"A": "one sentence", "B": "one sentence"},
 "key_doubt": null or "your reason"}

Use exactly the labels that exist in the id's folder (A.md, B.md, ...). Do not edit or move any packet. Then reply
with a short summary (under 150 words): how many answers in each class, and any key doubt.
