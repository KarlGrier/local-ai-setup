# The Qwen served-mode sampled-distribution test (2026-11-09, desk; built, not run)

**Karl 11-09: approved as designed.** ADAPT_FETCH's plan as proposed below: K=8 for P028x, =1 and =2, 16 requests for
the second P028x run (always run), the read-back start on =2 only, PASS = sampled PASS for each candidate AND 0
read-back mismatches, exact7 + long40 with the switch unset. The presence-penalty finding: P028x.json stays as it
is (Qwen's own setting for thinking off; none of our paths use it), noted in HANDOFF.md.

Karl 11-09: ADAPT_FETCH's quality is judged by "a Qwen version of D2's driver, with P028x against itself for the noise
bound, then =1 and =2", plus one STRATA_ADAPT_FETCH_VERIFY=1 start. The driver must be reusable: the port switch
requirements and Qwen4 day one need it too.

Code: `work/r23/sampled-qwen/`. A fresh helper built it, and Claude re-ran both selftests:
- `sq.py selftest`: SELFTEST OK, 55 checks;
- `sq_client.py selftest`: CLIENT SELFTEST OK.

No engine, server or gap has run it yet.

## Files

- `sq_stat.py` holds the statistic and the rule. The math is **copied verbatim** from DeepSeek's
  `work/ds41/gate/sampled/sampled.py` (sha 368b45e50b8e): chi2 / ncx2 / lambda, `kept`, `token_terms`, `inv3`, `quad`,
  `Acc`, `combine`, `d2`, `parse_row`, and the nine constants. The selftest checks by AST that they are identical. It is
  a copy so that a later edit to sampled.py cannot change this rule.
- `sq_client.py` sends the requests and records them, with per-request byte ranges of the server and engine logs.
- `sq.py` is the command line:
  - `rule` writes rule.txt before any engine run;
  - `derive`, `envcheck`, `ids`, `score`, `envwatch`, `verify`;
  - `decide` writes decision.txt / .json and exits 0 / 1 / 2, or 3 at stage 1;
  - `selftest`, plus `selftest-real` for the gap's preflight.
- `spec-adaptfetch.json` is the first use, with arms R1, R2, X1, X2 and VF.
- `STEPS-adaptfetch.txt` is the step list for the gap's sampled part.

## Design: how Qwen differs from DeepSeek (the server and engine are strata-r22p028x)

**Arms.** Each arm is a base config plus `same_as` and top-level / env / arg changes, with optional `check_equal`,
`exe_sha12` and `binary_has`.
- `derive` makes the test form of the served config the way u_adopt.py does: no picture reader, fallback or guard key.
- It checks R1 = x28h.json + STRATA_HC_UPMIX=1 key by key.
- It refuses an arm with a `.shared-settings.json` beside its config.

**Generated ids.** They come from `STRATA_DEBUG=1`: server.py prints `[strata] raw ids:` (5803-5805, stop token
included). The engine binary never reads STRATA_DEBUG; `derive` checks every arm's binary for that. API logprobs were
rejected: they change the engine's path and give only the top 20.

**Seeds.** A request's seed goes to the engine as `seed=N` (server.py 1443-1445). The Philox counter is the token's
position (verify.cpp:3386; sampler.cu:543), so every request has its own seed: base + 1000 x prompt + round, with
disjoint ranges per arm.

**Why a seeded identity test cannot work.** STRATA_SPEC_EXACT is exact in distribution: three tagged streams, min(1, P/Q)
acceptance, residual max(P-Q, 0). But a row's stream depends on whether it was drafted. Drafting depends on the drafter's
raw probabilities, and placement rounding (ADAPT_FETCH's whole effect) flips those. So the test compares distributions.

**Prompt bytes.** Thinking stays off (`chat_template_kwargs {"enable_thinking": false}`), giving a plain render and
encode with the arm's own frontend and tokenizer. `ids` repeats that render and requires:
- the rendered length = prompt_tokens;
- the same prompt ids in every arm.

The client always sends presence 0, frequency 0 and repetition 1. Otherwise the model card's thinking-off default,
presence_penalty 1.5, would apply (see below).

**p~, the distribution each draw comes from** (sampler.cu `sampled_tail_warp`): top-k (ties to the lower id), then top-p
(min_keep 1), then min-p, then temperature, then one draw. This is the same chain as DeepSeek's, so the math is reused
unchanged.

**The scorer** is x28h on the decode-path reference: decpath_rules.py's "dec" form, `--spec 2` with 2-row windows,
`STRATA_LOGPOS` + `STRATA_LOGPOS_TOPK=64`, and the yardstick's fixed settings (CPU expert pool, no adaptation, no PCIe
share). ADAPT_FETCH cannot reach it, and one engine scores every arm. It ran on 11-05 (8 texts, ~189K positions,
67-74 tok/s).

**Gap pattern.**
- Served arms run as gap-basalt-speed.sh's `srvrun`: with_server.sh, `br envcheck`, then `sq.py envcheck` (exactly one
  engine of the arm's binary, no spec switch set behind the config).
- The scorer runs as gap-decpath.sh's `decarm`, with guard.py and `sq.py envwatch --kill`.

## The ADAPT_FETCH plan (proposed)

- **Prompts:** W1-think, W2-code, C-conv and C-prose, with thinking off and max_tokens 512.
- **Arms:**
  - R1 = P028x;
  - X1 = the fetch build + STRATA_ADAPT_FETCH=1;
  - X2 = the fetch build + STRATA_ADAPT_FETCH=2;
  - R2 = P028x again, with its own seeds (the noise bound: band = max(11.345, D2(R2, R1)));
  - VF = X2 with STRATA_ADAPT_FETCH_VERIFY=1, not scored. Its log is checked for read-back mismatches.
- **Size:** R1, X1 and X2 at K=8 (32 requests each), R2 at K=4, VF at K=2. That is ~3,300-3,700 decode windows per
  arm, enough for admissions to act. The detectable top-1 shift is ~0.012, against the 0.02 floor.
- **Time:** ~38 min with 8080 down, at a planning speed of 100 tok/s served. K=4 would take ~27 min.
- **Overall:** PASS needs the sampled test to PASS for each candidate **and** the read-back to show 0 mismatches.

## To fill in before rule.txt is written

- The fetch build's exe path and `exe_sha12` (now "FILL-IN"; `derive` refuses until both are set).
- The serve-side VERIFY line and the per-request admissions line (patch steps E3 / E4). The patterns default to
  v0.2.13's CLI lines (strata-r23p0213 generate.cpp:21570-21586).
- "Build vs switch": R1 runs P028x's engine and X runs the fetch build, so the gap also needs the fetch build's
  unset = P028x bitwise check (exact7 7/7 + long40). That is already in the gap plan.

## Not covered

- Thinking on: the server writes its own tokens there, and its loop recovery raises T and the presence penalty.
- Prompts over ~1.2K tokens.
- Hours of drift and thrash.
- Penalized sampling.
- With two candidates, the chance of a false FAIL is up to ~2 % for the pair.

## Side finding: the presence penalty on thinking-off requests

server.py `MODEL_CARD_SAMPLING["qwen4exp"]["instruct"]` (8687-8689) gives presence_penalty 1.5 when thinking is off.
`_run` (5303-5307) merges the defaults in this order: model card, then the config's `sampling` block, then the shared
Chat settings, then the request's own fields. P028x.json's block sets temperature / top_p / top_k / min_p but not
presence_penalty, and P028x.shared-settings.json does not set it either. So **every thinking-off request on 8080 that
sends no presence_penalty runs at 1.5**. Thinking-on requests get none, because the card's thinking set has no penalty.
Whether any of our clients send thinking-off requests, and whether this is wanted, is Karl's call.

## Filled in 11-09 14:1x (the fetch build exists)

- X1 / X2: engine-r23afetch/strata, sha12 153ce47d3ef0 (r23-adaptfetch f381bfdf5).
- The exercise counter: `^strata serve: fetch: (\d+) admissions in \d+ windows`, at least 100 admissions per arm.
- The read-back:
  - any `^strata serve: FETCH VERIFY ` line is a mismatch: a differing slot, an expert also on a helper, a slot held
    twice, or a pending copy's target;
  - the summary is `^strata serve: fetch verify: (\d+) admitted slots read back, (\d+) differ`;
  - at least 200 slots must be read back.
- `sq.py derive` passes.
