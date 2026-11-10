# Phase 5 holdout - staged tooling (2026-10-29; nothing installed, nothing run)

The holdout on the baseline and on the final setup, and its blind grading: the 25 checkable questions (holdout c03-c30
+ hard-holdout h11-h20), the 4 harder checkable questions (p5-harder, FROZEN-p5-harder.txt) and the 3 open ones
(o04-o06). Checkable = the Answer-section rule with four classes (hard-build-p5/PHASE5-CHECKABLE-RULES.md); open =
blind-open.py packets graded against my-research/, as blind-p4s7.

## Files

| file | what |
|---|---|
| p5.json | the config: arms, engine, time limits (p4s7's: open 171 / checkable 47 min), lines, order. **Placeholders here.** |
| p5.py | `plan`, `check-engine`, `check-frozen`, `swap-mark`, `status`, `packets`, `tally` (docstring) |
| p5-start.sh | the one command: checks, installs bench2.py, writes the plan, points deep-research-bench.service at it, starts it |
| bench2.py (+ .orig) | the minimal bench2.py change: sets `p5-harder` / `p5-o01`, answers-p5-harder.jsonl in `answers()` (cross-check), `next` uses a step's own budgets (it assumed 30 / 120; only matters if the night rule comes back). bench2-queue.sh needs no change. |
| grader-checkable.md, grader-open.md | grader prompt templates; `packets` renders one per batch / question |
| queue-plan-p5.preview.json | the plan as it will be, with the placeholder showing |
| o01/ | o01 with "RTX 4060 Ti 8 GB" (set p5-o01) + a draft hash file - NOT frozen, off by default (see below) |
| tests/ | offline tests on phase 3/4 runs: `nice -n 19 /home/USER/ai/deep-research/.venv/bin/python -I -B tests/test_p5.py` (16 pass) |

## Placeholders (p5.json) - fill in after the adoption calls

- `arms[1].items` - the final setup's items (p4s7's were setup, critic, code, fixes, read, claims). Only items
  bench2-queue.sh can switch are accepted. An adopted item 7 part (paid search, S2), item 8 (merge) or a C3c model
  profile needs queue support first: bench2.py refuses LDR with the search fallback or S2 on, and nothing checks
  run/ldr.modelprofile.
- `engine.config` + `engine.sha12` - the Strata config both arms run on (e.g. configs/P021m.json; P021m's exe =
  7b38796237f5). check-engine compares both the server on 8080 and the promoted config strata-ensure.sh starts after an
  idle stop.
- If a new item writes its own report section, add it to `blind_drop`.

## Run, in order (once the build is final)

1. `bash /home/USER/ai/deep-research/staging/phase5/p5-start.sh --check` - every check, changes nothing live (safe
   any time).
2. `bash /home/USER/ai/deep-research/staging/phase5/p5-start.sh` - checks again (no HOLD-p5 file, no
   tmp/bench2.stop, no placeholder, final engine, frozen hashes, the bench service and ldr-* chains idle, bench.lock
   free, kcheck). Then, under bench.lock: tools/bench2.py (backup .before-p5), results/bench2/queue-plan-p5.json, swap
   mark; then the unit's BENCH2_PLAN (backup .before-p5) and start. After that the queue's usual rules apply.
   Order: o04-o06, then the harder four, then the 25; within each set the baseline first, then the final setup.
   Folders: runs/<set>-baseline-p5, runs/<set>-deep-p5final. Estimate: final ~31 h, baseline ~2 h.
3. Progress: `p5.py status` (runs per arm and set, swap since the start, engine VmSwap). The end is the line
   "queue finished (queue-plan-p5.json)" in logs/bench2-queue.log. Then run kcheck.
4. `p5.py packets` -> results/bench2/blind-p5/: checkable/<id>/{question,A,B}.md, the key, MANIFEST.json,
   grader-b1..b6.md (b6 = the harder four); open/<id>/ + grader-o04..o06.md.
5. One fresh grader per prompt file, in parallel. They write checkable/grades/<id>.json and open/grades-<id>.json.
6. `p5.py tally` - refuses until every grade is in; then opens the keys and writes REPORT.md + p5-results.json:
   - the checkable (25) line;
   - the harder (4) line, with each question's class per setup;
   - correct / wrong commitment / hedged / non-answer / not run in separate columns;
   - the open totals;
   - the string cross-check and where it disagrees;
   - key doubts, and the engine and rc per run.
7. Fix 1c on held-out data (Karl 10-30): its 29-of-33 recovery was measured on the same Fix 1b replays it was built
   from, so report the version check's marks on the holdout's final-setup reports SEPARATELY: each flagged name judged
   right / wrong against the code at the question's version (as fix1-judge), plus the names it left unflagged that a
   reader would take as this engine's. Not part of the grades above.

## Open questions for Karl

1. **Time:** ~33 GPU h at p4s7's limits (29 x 47 + 3 x 171 min), vs the plan's 17-20 h (planned before the four and
   the 47-min budget). Keep, or use checkable 30 min (~24 h)?
2. **o01 is not in the holdout.** Phase 5 takes its open questions (o04-o06) from questions-holdout.jsonl. o01 is
   only in questions-screen.jsonl (FROZEN.txt, 10-17), so nothing in Phase 5 reads it. If you want it in: copy
   o01/questions-p5-o01.jsonl and the draft (as FROZEN-p5-o01.txt) into results/bench2/, chmod 444, and set
   `include_o01: true` (+~3 h). This makes a new versioned file; FROZEN.txt and questions-screen.jsonl stay as they are.
3. **o05's reference (10-18) says Qwen4 Flash is unreleased.** If it is out by then, add a dated addendum (or an
   `open_ref_notes` line) before grading.
4. **Baseline = pristine LDR** (PLAN.md, the rules' item 3), not a deep run without items. Right?
5. **The baseline's answer text.** Its quick summary usually has no "## Answer" heading, so its packet is the whole
   summary before the sources (~2-4 KB, vs deep's ~1-2 KB Answer). Keep it whole, or cut it at the first sub-heading?
6. **Locks and checks.** The queue does not hold strata-compare's gpu-test.lock (no LDR queue has) and runs no
   per-question kcheck or swap rule. We get kcheck at the start and `status`'s swap change. Is that enough?
7. **Write protection.** The p5-harder question, answer and FROZEN files are 0664; the older frozen files are 0444.
   I left them as they are. Should they be made read-only?
