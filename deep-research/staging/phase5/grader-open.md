# Blind grading - Phase 5 holdout, open question {QID} (one fresh grader per question)

You are grading research reports that answer the same question, labelled {LABELS}. You do not know how any of them
was produced; do not try to guess, and do not let length or formatting alone decide.

**Files (read only; absolute paths):**
- The reports: {OUT}/open/{QID}/{LABEL_FILES}.
- The reference research and its grading checklist: /home/USER/ai/deep-research/results/bench2/my-research/{REF}. It
  was written before any run ({REF_DATE}). Where a report is right and the reference is out of date or wrong, credit
  the report and say so.{REF_NOTE}
- The user's real hardware (for "fits / runs / helps on this PC" claims): the hardware lines (CPU, RAM, GPU 1, GPU 2,
  Total VRAM, OS) of /home/USER/ai/deep-research/user-setup.md.
- You may use web search to check facts, prices and dates. The question's date is {QDATE}.

**Do NOT open anything else:**
- under /home/USER/ai/deep-research/results/bench2/ (no key, runs, items folders, checkable packets, answers, fixes,
  notes, other grades, SUMMARY or REPORT files);
- under /home/USER/ai/deep-research/jobs/, reports/, results/deep-runs/, results/quick-runs/ or data/.

Do not build or run anything; use absolute paths.

**Grade each report on every checklist item of the reference:**
- 2 = covered correctly and usefully;
- 1.5 = covered, a minor slip;
- 1 = partly, or with a real error;
- 0.5 = touched only;
- 0 = missing or wrong.

The total is the sum ({QID}: {N_ITEMS} items = {MAX}). Check the important claims; mark down confident claims that are
false, overpromised gains, misdated or undated status claims, and advice that does not fit the user's hardware. Also
count, for each report, the confident factual claims you checked and found wrong (a number, a date, a version, a quote
or a source that does not say what the report says it says).

**Write** {OUT}/open/grades-{QID}.json:
{"id": "{QID}", "graded": "YYYY-MM-DD HH:MM", "rank": ["better", "worse"] (or ["tie"]), "checklist_items": ["..."],
 "checklist": {"A": [..], "B": [..]}, "totals": {"A": x, "B": x}, "wrong_claims": {"A": n, "B": n},
 "top_errors": {"A": ["claim - what is true, with the source you checked"], ...}, "strengths": {"A": ["..."], ...},
 "why": "three sentences on the ranking"}

Then reply with a short summary (under 250 words).
