# ADAPT_FETCH=2: owner exception to the prompt no-loss rule (2026-11-09)

**Karl, 11-09, after the ADAPT_FETCH gap:**

> ADAPT_FETCH: make =2 the daily, as a recorded owner exception to the prompt no-loss rule. R4 came in -0.1% against
> its 0.1% noise, on a path ADAPT_FETCH doesn't touch. =2 had the higher decode (+12.7% vs +10.2%), matches upstream's
> =2 > =1, and passed the sampled test and the read-back. Record it as an exception for this decision only; the rule
> itself stays unchanged.

## What the rule said

The gap's decision is `gap/decision.txt`. Its rules were frozen before any engine started: `gap/rules.txt`, sha `210e1eb0e7e3`,
from `work/r23/afetch-gap/afetch_rules.py`, sha `355cac03de46`. The forms were B3_PROMPT_FORM tol1, GAIN_FORM screen and
ORDER_FORM vf-first.

| | F1 (`=1`) | F2 (`=2`) |
|---|---|---|
| Build vs switch (exact7 7/7, long40 0/40) | PASS (shared) | PASS (shared) |
| Screen decode geomean vs P | +10.2 % (noise 2.9 %) | +12.7 % (noise 3.4 %) |
| Prompt geomean vs P (within -1 %) | +0.11 % | +0.18 % |
| Per-workload prompt no-loss | none slower beyond its noise | **R4-agent33k -0.1 % (noise 0.1 %)**: FAIL |
| Sampled test D2 (bound 11.345) | 7.31 PASS | 1.83 PASS |
| Read-back (91,345 slots) | PASS | PASS (VF = X2) |
| Verdict by the rule | PROPOSAL | FAIL (speed FAIL (screen)) |

## The exception

- **Scope:** this decision only, to adopt `STRATA_ADAPT_FETCH=2` on P028x as the daily. It is not a precedent.
- **The rule is unchanged:** `afetch_rules.py`, the frozen `gap/rules.txt` and `gap/decision.txt` stay exactly as they are,
  and every later gap is judged by the rule as written.
- **The owner's reasons:**
  - R4's loss is -0.1 % against a 0.1 % noise, on the prompt path, which ADAPT_FETCH does not touch (it acts in decode
    windows).
  - `=2` has the higher decode, and that matches upstream's ordering (=2 > =1).
  - Quality passed on both the sampled test and the read-back.
- **What is adopted:**
  - `configs/P028x.json` runs the fetch build (`engine-r23afetch/strata`, sha `153ce47d3ef0`, r23-adaptfetch
    `f381bfdf5`) with `STRATA_ADAPT_FETCH=2`.
  - The adoption ran outside the gap's driver: `work/r23/afetch-adopt/gap-afetch-adopt.sh`, results in
    `results/r23/afetch-adopt/`.
- **Fallback and rollback:** `work/r23/afetch-adopt/served-afetch.sh afetch1` switches to `=1`, the gap's PROPOSAL.
  `served-afetch.sh p028x` puts P028x back as it was before.
