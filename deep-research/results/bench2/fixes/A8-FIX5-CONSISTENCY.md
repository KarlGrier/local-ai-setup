# A8 (2) and (3): Fix 5's question setup, and why the consistency pass missed K4 (10-27 ~21:00; read-only analysis)

## (3) Consistency pass: why K4 (DSpark) was missed

**The two statements** (the code-tool rerun report, codetool/run-full):
- **Tier A #1 and plan item 1:** "The default `--dspark auto` loads the 8 GB Q8_0 DSpark drafter into VRAM", so
  `--dspark none` "recovers the measured 8-16 % loss" (the headline win).
- **The DSpark section:** the engine "sets `g.n_mtp = 0` (disabling the drafter entirely) when routed experts exceed 1.5x
  the available room".
  - That is right (ds4_model.cu 1998-2006).
  - On this PC the routed experts (~289 GB) are far more than 1.5x the VRAM, so `auto` already leaves the drafter out.

**Why it was missed: wording, not distance or extraction.**
- **Not distance.** K1's pair (the Answer vs a code section ~300 lines later) was caught in the same pass.
- **Not claim extraction.** The pass reads the whole report in one call and has no extraction step.
- **The cause:** the DSpark section states a *general rule with a condition*. It never says "so on this PC auto does
  not load it". The contradiction only appears once the rule is applied to the user's numbers, which sit in a third
  place.
- The prompt even tells the model to "ignore statements about different conditions that are both right". A
  conditional rule reads exactly like that.

**A pattern, not a one-off.** These reports, especially with the code tool, often describe a rule (a threshold, a
default that depends on the hardware, a guard on one GPU) in one section and assert an outcome for this PC in the
Answer or action list. K1 had the same shape, a single-device guard against "use layer-major". It was caught only
because its rule says "single-device only" in plain words.

**Fix:**
1. **The prompt** asks for the rule-vs-instance case explicitly: "a rule, threshold or condition stated in one place
   that, applied to this setup (the task's hardware and numbers), gives a different outcome than a claim about this
   setup elsewhere". The "different conditions" exemption applies only when the condition does not hold for this setup.
2. **A focused second step for the action list.** For each recommended setting in the Answer and action list (the top
   ~10):
   - gather every sentence in the report that mentions it or its subject (`--dspark` -> DSpark / drafter), plus the
     task's setup facts;
   - ask one small question: applied to this setup, do these agree?
   - Small prompts, so distance stops mattering, and the time plan can cap the count.
3. **Replay targets:**
   - K4 caught on the code-tool rerun report, and K1 still caught;
   - tonight's rerun report checked too;
   - false alarms counted on both.

## (2) Fix 5: the question's own setup wins

**Now:**
- Since round 4 the rule text says the task's own description wins, and the profile counts only for the hardware when
  the task is about another state.
- The model still judged against the profile's current values in a few places (the profile's prompt chunk 8192 on the
  10-24 question).
- Text alone is not enough.

**Fix, in code:**
1. One small call extracts the task's stated setup as key: value lines (versions, settings, measured speeds, sizes).
2. The setup check is given those facts first, under "the question's setup (wins)".
3. It then gets only the profile facts whose subject the question does not mention, matched on setting names and
   keywords (prompt chunk, store, experts, DSpark, split, version).
4. When the question names another version than the profile, the profile keeps only hardware facts (as now).
5. "Already set" and "gain against the baseline" are judged against this merged list, so the 10-24 question's "store
   already 70 GB", "DSpark auto", "v0.2.4" and "22.6 tok/s" come from the question.

**Replay targets:**
- The code-tool rerun report: the "already set" marks for `--ssd-cache 70` and `--dspark` stay; the marks against the
  profile's prompt chunk go.
- Tonight's rerun report: the same check.
- An o-question report whose task states no setup: the profile is still used whole.

**Added 10-27 ~21:05, from the combined rerun's blind grading (stage 1):** the fixed rerun's report itself, not just its
setup check, used facts from today's profile instead of the question's:
- v0.2.6 with local patches;
- 28.3 tok/s;
- the 68 GB store;
- 350 / 700 tok/s prompts.

The grader counted that against it. The profile gained these DeepSeek numbers on 10-27 after the code-tool rerun (Karl's
Fix 5 step), so the earlier rerun never saw them.

**The fix goes wider:** the same "question's setup wins" filter applies to the profile block given to the lead agent and
the report writer. When the task describes another version or state, they get only the profile's hardware facts. A
question with no setup of its own still gets the whole profile.

Both changes are coded in a staging copy during stage 3 p4s6 and installed only after p4s6 is graded (A8's condition).
