# K4 - the consistency pass applies a rule to the user's setup before it compares (staged 10-29)

STAGED ONLY - nothing installed. `checks.py` here = Fix 1b's staged `checks.py` (copy kept as `checks.py.fix1b`,
identical to `staging/fix1b/checks.py`) with only the consistency pass changed, plus its docstring line and
`EST["consist"]`. `checks.py.diff` is the unified diff (227 changed lines). **Install order: Fix 1b first, then this.**
This file holds Fix 1b's changes too.

## Why K4 was still missed after A8

The F5c replay (b-f5c-full, 10-28) gave the focused `--dspark` call everything it needed in one prompt:
- the three K4 claims: Tier A's "The default `--dspark auto` loads the 8 GB Q8_0 DSpark drafter", the Answer's
  "freeing the 8 GB DSpark drafter", and plan item 1's "`--dspark none` ... recovers the measured 8-16% decode loss";
- the DSpark section's rule: `g.n_mtp = 0` "when routed experts exceed 1.5x the available room";
- the whole task: backbone 138 GB, RTX 5080 16 GB + 4060 Ti 8 GB, 5.9 GB dense;
- the setup facts: Fix 5's question-wins path, i.e. hardware only, "Total VRAM 24 GB".

So the miss was not in gathering the sentences. The model never applied the rule: it reported a weaker pair (8 GB vs
5.6 GB freed). The prompt only said "apply any rule", and nothing in the reply showed whether it had.

## What changed (`deep/checks.py`, consistency pass only)

1. **The focused prompt is rule-first** (`CONSIST_FOCUS_PROMPT`). For each setting, in this order, with a reply field
   for each step:
   - **RULES:** list each rule, threshold, condition, guard or cap the sentences state, at most 3 per setting. Give
     each input with its number and source (the task first, then the setup facts, then a sentence id). Write the
     arithmetic out. Say whether the condition holds (yes / no / unknown) and what the rule gives here.
   - **CLAIMS:** only then compare that outcome with each claim about this setup. Two more lines: "a conflict often
     shows only once the rule is applied to the user's numbers", and "a test the task says the user tried once is not
     the current state" (the task's DSpark attempt).
   - **OTHER CONFLICTS:** plain sentence-vs-sentence pairs, as before.

   The arithmetic example uses neutral numbers ("1.5 x 20 GB = 30 GB"), not K4's.
2. **Sentence ids.** Each sentence gets an id (S1, S2, ...). The model answers with ids, which map back to the exact
   report sentence. The quotes are then exact, and the replies stay short: a claim that agrees is just
   `{"claim": "S8", "agrees": "yes"}`.
3. **Parsing** (`focus_reply`):
   - A rule-vs-claim conflict becomes a pair with `step: "rule"`: quote_a is the claim, quote_b the rule, plus an
     `evaluation`.
   - Such a pair is dropped when holds = "unknown", because the rule could not be applied.
   - The evaluation's arithmetic is recomputed in code (`recheck_evaluation`: Fix 3's equation checker plus `a > b`
     comparisons). When a step is wrong, the pair stays but is "not settled", and the recomputed step is in its why.
   - Replies in the old shape, salvaged cut-off replies and wrong types are all handled. A reply with no JSON is
     counted in `focused_unparsed`.
4. **Output:**
   - A rule pair's mark names the rule by its condition, then gives the fix and the deciding step, e.g. "...
     138 GB > 27.15 GB".
   - The section adds a "The rule applied to this setup: condition / inputs / arithmetic / holds / outcome" line.
   - `consistency.json` gains `rule_checks`: every rule evaluated, with or without a conflict.
   - Marks and section lines of all other pairs are byte-identical to before.
5. **`EST["consist"]` 480 -> 900.** The pass already took 729 / 747 s on the F5c replays, against an estimate of
   ~400 / ~500 s at their scale (480 x 0.83 / 1.04). Re-measure in the replays below.

**Unchanged:**
- the main prompt (byte-identical);
- which settings and sentences are picked;
- the calls: 1 + at most 2, with the focused prompts +2,000 chars each (~+600 tokens);
- the setup facts;
- everything outside the pass.

## Offline test

Command: `nice -n 19 .venv/bin/python -I staging/k4/tests/test_k4.py`. It uses a fake model: no real model calls,
no GPU. **ALL OK, 75 checks** (`tests/test-output.txt`):
- On b-f5c-full, the K4 claims (S1, S9, S16), the 1.5x rule (S12), the task's numbers and the evaluation instruction
  are in the same `--dspark` call, and all ids map back to sentences that can be marked.
- Fake replies:
  - a correct K4 catch gives 3 pairs and a placed mark;
  - non-catches give no pair, and the evaluation is kept;
  - malformed replies (no JSON, cut off, wrong types, the old shape) cause no crash;
  - wrong arithmetic makes the pairs "not settled".
- The marks, section and marked report from both saved F5c results are identical to Fix 1b's.
- `tests/judge_k4.py` on the old replays: b-f5c-full has K4 NOT caught and K1 kept (pairs 5 and 21), which matches
  BUNDLE-1028. b-f5c-fixes is n/a, because that report gets K4 right.

## Later: install, then the GPU replays (needs a GPU gap and no run live; not done)

```bash
WS=/home/USER/ai/deep-research; P=$WS/.venv/lib/python3.12/site-packages/local_deep_research/deep
# 0. Fix 1b installed first (staging/fix1b/README.md); then, holding run/bench.lock, no run live:
cmp $P/checks.py $WS/staging/k4/checks.py.fix1b || echo "STOP: installed checks.py is not Fix 1b's"
cp -p $P/checks.py $P/checks.py.before-k4 && cp $WS/staging/k4/checks.py $P/checks.py \
  && $WS/.venv/bin/python -m py_compile $P/checks.py
cp -p $WS/patches/ldr/0001-deep-package.patch $WS/patches/ldr/0001-deep-package.patch.before-k4
bash $WS/patches/ldr/make-patches.sh
# 1. the replays (each takes run/bench.lock itself; from a script that holds a lock -> add 8>&- 9>&-)
PY="$WS/.venv/bin/python -I $WS/tools/fix-replay.py"; R=$WS/results/bench2
$PY check --fix baseline,consist --setup --label b-k4-full --run $R/codetool/run-full
$PY check --fix baseline,consist --setup --label b-k4-fixes --run $R/codetool/run-full-fixes
# 2. judge (files only)
$WS/.venv/bin/python -I $WS/staging/k4/tests/judge_k4.py b-k4-full:b-f5c-full b-k4-fixes:b-f5c-fixes
```

Each replay takes about 20 min: a setup check of ~400 s plus the pass. Rollback is `checks.py.before-k4`, which is
Fix 1b's file.

**Pass:**
1. **b-k4-full: K4 caught.** judge says "strong": a K4 claim is marked wrong against the 1.5x rule, and the rule's
   evaluation shows ~132-289 GB of experts > 1.5 x the room (24 GB or less), holds yes. "weak" (not settled) is
   partial. Runs are T=1.0, so on a miss run `-r2` and `-r3` and pass on 2 of 3.
2. **b-k4-full: K1 kept.** At least one layer-major vs single-device pair.
3. **b-k4-fixes: no K4-reversed false alarm.** Its correct "DSpark auto-disabled" statements are not marked wrong.
   `--dspark` is not among this report's focused settings, so this replay is the false-alarm control.
4. **False alarms, judged by hand.** Use the answer key and the code at v0.2.4. judge lists every rule pair and every
   pair new against F5c. Pass if:
   - each report has at most 2 false rule pairs, and no more than 1/3 of its rule pairs are false;
   - total pairs grow by 10 or fewer over F5c (26 / 29);
   - `focused_unparsed` is 0.
5. **Time.** 3 consist calls per report. The seconds are compared with `EST["consist"]` x scale (~750 / ~940 s); if
   the pass is over that, raise the estimate.

## Unresolved / watch

- **The model's verdicts are untested.** The offline test shows only that the right material and instruction reach
  the model.
- **Dropped pairs.** "holds unknown" pairs are dropped (kept in `rule_checks`), so a real conflict the model could not
  evaluate is lost.
- **The arithmetic recheck is heuristic.** It downgrades only on a step it parsed and found wrong; anything it cannot
  parse is not checked.
- **The higher estimate** may skip the consistency pass more often under tight budgets. The alternative is
  overrunning the deadline, as it does now.
