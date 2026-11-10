# DeepSeek C: the sampled-distribution test (plan, 11-07, desk only)

Karl 11-03: drafting may go daily only after a **sampled-distribution test**. Under our normal sampling (T 1.0, top-p 0.95,
top-k 20, min-p 0.05), drafting must not change the output distribution beyond rounding. Karl 11-07: run it on whichever
C-N ends up recommended (GAP-C234-PLAN.md, gap D2).

**Status: desk only.** No GPU, engine, server or gate/gap script was run. Only the harness's own selftest ran, on
synthetic data. The harness is in `work/ds41/gate/sampled/`. The rule below is fixed now, before gap D1.

## 0. In short

- **The engine's scheme is exact in exact arithmetic.** It is standard speculative sampling. The draft is a point mass
  (the drafter's argmax). It is kept with probability p~(d), and a rejection draws from the residual (p~ without d).
  `--dspark-conf` and `STRATA_DS4_DSPARK_CUM` only decide how many drafts are verified.
- **A seeded identity test cannot work.** This is by design, not because of rounding. At a drafted row the accept test
  and the residual use Philox streams keyed differently from the plain draw. So seeded C0 and C-N part ways at the first
  drafted row where the two draws differ. The test therefore compares distributions.
- **The test.**
  - Three served arms, each answering the same 16 short requests (4 prompts x 4 samples x 512 tokens, thinking off):
    - R1 = C0;
    - X = C-N;
    - R2 = C0 at `--vram-experts 0.98`. R2 runs only when needed.
  - One teacher-forced scoring run per arm on the same reference config.
  - The statistic is a calibration distance D2, chi-square with 3 df.
  - **Time: ~22 min typical, ~31 min worst case** (when R2 is needed).
- **The rule.**
  - PASS if D2(X, R1) <= max(11.34, D2(R2, R1)) and the test had enough power.
  - FAIL if it is above that band.
  - NOT DECIDED for too few samples, invalid data, or no drafting.
  - The literal 11-04 band (the reference pair's distance alone) would fail a correct drafter about half the time under
    sampling noise. So the band has a noise floor. **This, and the power floor, need Karl's decision (section 7).**

## 1. What the engine does (strata-v026p343-slotram = the source of engine-v026p343-slotram-ds41)

Paths are under `strata-v026p343-slotram/`.

### 1.1 How drafts are verified under sampling

- **The drafts are the drafter's argmax.**
  - In `src/dsv41/ds4_model.cu:6718`, `drafts_q` is true only with `DS4_DSPARK_SAMPLE=1`, a test switch (lines 911-916)
    that no C config sets.
  - So the argmax path at line 6847 runs, and q is a point mass at d (lines 6938-6948: `p[0] = 1.0`).
- **One verify window.** `verify()` (lines 6907-6976) runs [y, d1..dn] through the trunk as one window of n+1 rows (line
  6917). It then calls `sample_verify` (line 6959).
- **The rule in `src/dsv41/vendor/sampler.cu:469-507`**, per row t:
  - The chain is the same one the plain draw uses: top_k, then top_p over the k, then min_p, then temperature. The
    selection code is shared, MODE 0 / 2.
  - pd = p~(d), with pd = 0 if d is cut.
  - The draft is kept iff `U_A * qd < pd`, with qd = 1 (line 484). That is probability p~(d).
  - Otherwise x is drawn from max(0, p~ - q) renormalised (lines 486-505). With point-mass q, that is p~ restricted to
    x != d.
  - So P(out = d) = p~(d), and for x != d, P(out = x) = (1 - p~(d)) * p~(x) / (1 - p~(d)) = p~(x). **Exact.**
  - If every draft stands, the bonus token is a plain MODE-0 draw on row n (`ds4_model.cu:6963`).
  - Rows past the first rejection are computed but never used (the host loop stops at the first mismatch).
    - Their uniforms are drawn again by the next round at the same counter values.
    - Nothing observed depends on those discarded looks, so independence holds.
- **Rounding-level only:** Philox gives 24-bit uniforms (sampler.cu:52), so acceptance is p~(d) to within 6e-8.
- **The knobs change only how many drafts are verified, never the rule.**
  - `--dspark-conf` (and a request's `dspark_conf`) and `STRATA_DS4_DSPARK_CUM` (a request's `dspark_cum`) set the
    `keep` loop in `round()`: `src/dsv41/ds4_main.cpp:179-184`, with the default at 152-162 (0 = off).
  - The "cool" rule skips the drafter for one round after a round with no draft above the floor (`ds4_main.cpp:903`,
    `:913`).
  - `DS4_DSPARK_MAX` caps the drafts (`ds4_model.cu:6727`).
  - All of these are deterministic functions of the drafter's confidences, which are a function of the past. They do not
    depend on the uniforms, so exactness holds for any setting.
  - They do change which positions go through verify windows. That changes the realized tokens for a given seed, and
    which kernels compute a row (section 1.3).
  - `DS4_DSPARK_CONF` (`ds4_model.cu:901`) is read into `conf_threshold`, which nothing else uses.

### 1.2 RNG, and why a seeded identity test does not work

- **There is a request seed.**
  - `seed=N` on the GEN line (`ds4_main.cpp:309`).
  - server.py forwards an integer seed > 0 (`strata-v026/serve/server.py:1423-1425`).
  - server.py does **not** forward `spec=` (lines 1388-1460). So drafting cannot be toggled per request on the served
    path: C0 and C-N need separate engines.
- **The stream is counter-based Philox of (seed, counter)** (`sampler.cu:29-53`).
- **The counter is engine-lifetime.** It is set once in `serve()` (`ds4_main.cpp:327`), not per request. It advances once
  per emitted position in both paths: line 848 (first token), 202 (plain step), and 193 (`counter += acc + 1` after a
  verify round). So a position maps to the same counter value, but:
  1. **Different keys at drafted rows.** The plain draw uses `philox(seed, counter)` (sampler.cu:442). A drafted row uses
     `philox(seed ^ kSpecAcceptKey, counter)` for its accept test (line 484) and `seed ^ kSpecResidKey` for its residual
     (line 494); the keys are at line 178.
     - With one seed, C0's token there is F^-1(U), and C-N's is "d if U_A < p~(d), else a residual draw with U_R".
     - The two agree with probability sum_x p~(x)^2 only.
     - After the first disagreement the contexts differ, and so does everything after.
     - Over 512 tokens with ~70 % of rows drafted, the two texts part almost at once, with or without rounding.
     - So divergences would not be near-ties, and a "seeded identity + near-tie classification" test has nothing to
       classify.
  2. **Counter offsets between requests.** An EOS inside accepted drafts leaves the counter past the dropped tokens
     (`ds4_main.cpp:193` vs the serve loop's EOS break). Later requests on one engine then start at different counter
     values in C0 and C-N.
- **The scheme is distribution-exact but not realization-preserving.** It is not "sample, then match the draft". The
  test must compare distributions empirically.
- The greedy check (11-04, 11-07) was possible only because greedy has no randomness.

### 1.3 Does the verify window compute differently from single-token decode? Yes, in places

| part | T = 1 (decode) | T = N+1 (verify window) | same rounding? |
|---|---|---|---|
| dense GEMVs (BF16 path read) | `mv_launch<1>` | `mv_launch<2/4/8>` (`ds4_gguf.cu:1109-1116`) | Per column the same fmaf chain and warp sum (`ds4_gguf.cu:66-111`): **same**. The Q8_0 / MXFP4 / low-bit `iq::mv` paths were not read. |
| attention | split-KV kernel | the same kernel ("decode T = 1, DSpark verify T = 2..5", `ds4_attn_split.cuh:3-4`) | One block per (head group, chunk, query): very likely the same per query; not checked line by line. |
| routed experts on the GPU | token path `x3::moe_gate_up` / `moe_down` (`ds4_model.cu:9092-9112`) | window path `gf::moe_win_group` + window kernels (`ds4_model.cu:9113-9122` on) | **Different kernels: the main source of rounding differences.** |
| RAM-store experts | computed on the GPU from the store's slot (zero-copy), at **T == 1 only** (`ds4_model.cu:6527`) | computed by the CPU lane | **Different hardware.** |
| CPU-lane experts | each token's experts summed in expert-id order (`ds4_model.cu:6556-6600`) | same order | same |
| state after a rejection | - | ring rows restored; the compressor re-run over the kept rows at once (`compress_win`, `ds4_model.cu:7011`) | Possibly different rounding in the compressed KV; not checked. |
| placement over time | routing counts | **every verify row counts, rejected drafts too** (`ds4_model.cu:6518`) | The adaptive cache moves other experts between VRAM and the CPU lane, so rounding drifts (as gate README "Greedy runs in frozen arms" says). |

So C-N's sampled tokens can differ from C0's by rounding: kernels, hardware and placement drift. The test must therefore
allow rounding, which the noise band does.

## 2. The test

### 2.1 Arms

Each arm is one fresh served engine through tunearm.sh, as the 11-07 C0f/C1f arms ran:
- a fresh copy of the gap's profile snapshot;
- its own emptied slot folder;
- `SERVER_ENV="STRATA_DS4_AUTO_PIN=1 STRATA_DEBUG=1"`. STRATA_DEBUG only makes server.py print each request's generated
  ids, stop token included (server.py:5296-5298, 5556-5558); tie_served.py checks that the binary does not read it.

| role | config | why |
|---|---|---|
| R1 | `configs/DS41-gate-C0.json` (C's placement, the drafter loaded, `--dspark off`) | the non-drafting reference |
| X | the recommended C-N config from gap D1 (C2: `DS41-gate-C2.json`; C3 / C4: the same with `--dspark-block 3 / 4`) | the arm under test; any N works |
| R2 | C0 with `--vram-experts 0.98`, derived into the run folder | Karl's 11-04 placement variant "Aa" (A at 0.98) applied to C0: the rounding that happens in normal use. **Runs only if stage 1 does not pass.** |

**The scorer** is one teacher-forced reference, the same for every arm:
- `work/ds41/tune/scorearm.sh` on `configs/DS41-gate-A.json`, `--window 128`. This is the KL harness's proven path, ~100
  runs.
- A fresh copy of the same snapshot goes in before each scoring run.
- The scorer does not decide anything. It only gives each token's own context distribution, which removes the variance
  between contexts.
- Its offset from the served arms (placement, window kernels) is common to every arm, and cancels in D2(X, R1).
- Alternative: cfg-C0f through cliarm.sh (C's own placement, frozen). Window 128 never ran on that placement (the 5080
  has ~570 MiB free; 128 rows of logits = 66 MB).

### 2.2 Requests (`sampled_client.py`, tunearm.sh's CLIENT)

- **Prompts.** These reuse the gate's prompts, all short, so prompt + answer stays under `STRATA_DS4_SLOT_MIN` (1024).
  That means no conversation is set aside to RAM or disk between requests.
  - math: W1 = the greedy check's G-W1, 87 prompt tokens.
  - code: W2 = G-W2, 104 tokens.
  - conv: C-conv from the calib set, about 600 words asked.
  - prose: C-prose ("Write an essay on the Odyssey").
  - G-P4K0 (4,115 tokens) is left out: every repeat would save a 4.6K-token slot, and its prompt rows would triple the
    scoring time.
- **Settings.**
  - Thinking off, no nonce, so the bytes are identical in every arm.
  - `max_tokens` 512; T 1.0 / 0.95 / 20 / min-p 0.05.
  - presence_penalty 0. The engine ignores penalties anyway: `ds4_main.cpp:304-313` parses none.
- **Seeds.** seed = arm base + 1000 x prompt + round. The bases are R1 1,000,000, R2 2,000,000, X 3,000,000. Every arm
  has its own seeds, because shared seeds would couple the arms' first tokens (counter 0, plain key).
- **Order.** K = 4 rounds of (math, code, conv, prose) = 16 requests, about 8,192 generated tokens per arm. R2 runs
  K = 3 (12 requests).
  - Interleaving keeps the prompts balanced if the 480 s budget cuts the plan short.
  - It costs a fresh ~2.3 s prompt read per request.
- **Records.** Per request: prompt_tokens, completion_tokens, finish, and the drafts offered / kept (from the engine log,
  as greedy_client.py reads it).

### 2.3 From answers to scores

- `sampled.py ids ARM` takes the printed ids (one "raw ids" line per request, in order) and adds each prompt rendered with
  the server's own template code (tie_check.py's way).
- It keeps a sample only if:
  - the rendered length equals the server's prompt_tokens (one rendering only);
  - the id count equals completion_tokens.
- It then writes the engine's `--score` file, one segment per sample, each scored from a fresh state.

### 2.4 The statistic

- **Per token.** For each generated token x_t, the scorer's row gives the top-64 log-probabilities. From them, p~_t is
  rebuilt exactly as `sampler.cu` builds it:
  1. top_k 20;
  2. top_p 0.95 over the 20;
  3. min_p 0.05 against the top;
  4. temperature 1.0;
  5. ties to the lower id.
- **Features.** f(x) = (x is p~'s top-1, x is p~'s rank 2, log p(x) over the whole vocabulary).
- **Excess.** d_t = f(x_t) - E_{x ~ p~_t} f(x).
- **Why this works.** If an arm draws from p~, then d_t has mean 0 given everything before it (a martingale difference).
  So the sum has no autocorrelation, and its variance is the sum of d_t d_t'.
  - This tests the conditional distribution at every position, given the arm's own past.
  - It also catches dependence bugs. For example, two drafts sharing one uniform would give P(keep d2 | kept d1) =
    min(p1, p2) / p1 instead of p2.
- **Per arm.** Per prompt: the mean m and its variance V (empirical, centred). Then an equal-weight mean over the 4
  prompts.
- **Distance.** D2(A, B) = (m_A - m_B)' (V_A + V_B)^-1 (m_A - m_B). If A and B draw from the same distribution, D2 is
  chi-square with 3 df.
  - Rounding enters as a small context-dependent offset. It is common to arms with the same kernels; X's verify
    kernels add their own, which is what R2's band allows for.

### 2.5 The pass rule (fixed now; `sampled.py rule` writes it to `rule.txt` before any engine run)

```
sampled.py rule, fixed 2026-11-07 at the desk, before any engine run (Karl 11-03: under T 1.0 / top-p 0.95 / top-k 20 /
min-p 0.05 drafting must not change the output distribution beyond rounding)
arms (one fresh served engine each, same request plan, own seeds): R1 = C0 (C's placement, --dspark off), X = C-N (the
recommended arm, --dspark on --dspark-block N), R2 = C0v (C0 with --vram-experts 0.98: Karl's 11-04 Aa placement variant);
the scorer = one teacher-forced reference config, the same for every arm.
statistic: D2(A, B) = Mahalanobis distance of the arms' calibration vectors (top-1 rate, rank-2 rate, log p - each minus
what the scorer's p~ predicts per token; equal weight per prompt; empirical variance); chi-square, 3 df if A ~ B.
noise bound c = chi2(3) 99th percentile = 11.3449.
band = max(c, D2(R2, R1))   [the 11-04 noise-band style: the reference pair's distance, never below pure sampling noise]
PASS iff D2(X, R1) <= band, the data are valid and the test has the power below.
FAIL iff D2(X, R1) > band and the data are valid (R2 present and valid).
NOT DECIDED iff any of: an arm needed has < 4000 valid scored generated tokens, or < 3 valid samples of one of
math, code, conv, prose, or > 10% of its samples invalid (ids count != completion_tokens, rendered prompt length !=
prompt_tokens, score rows / targets not the sample's, error or cancel finish); X drafted < 30% of its tokens or R1 / R2
drafted at all; D2(R1, scorer) > 100 (the scorer does not track C0); D2(X, R1) > c with R2 missing or invalid;
for a PASS: the least favourable top-1 shift seen with 80% probability, sqrt(lambda80 * (V_X + V_R1)[top-1]), above
0.02 (lambda80: the noncentrality that chi2(3) needs to pass c with probability 80% = 15.458).
stage 1 (R1, X): PASS if D2(X, R1) <= c and the rest holds (R2 is not needed: band >= c); else R2 runs, then the final
judgement. Proposed 11-07; the noise bound c, DELTA_STAR, N_MIN and R2's form need Karl's OK (C-SAMPLED-TEST-PLAN.md).
```

**Why not the literal 11-04 form ("C's distance must sit inside the reference pair's distance").**
- Under the KL harness that form works, because teacher-forced scores carry no sampling noise.
- Here every distance is mostly sampling noise. If X and R1 have the same distribution, D2(X, R1) is above D2(R2, R1)
  about half the time; with two reference pairs and their maximum, about a third.
- So the band keeps Karl's form, the reference pair's distance, but never below the 99 % noise bound. Under exact
  drafting a FAIL then has probability <= 1 %.
- R2 is only needed when D2(X, R1) > c, so it runs lazily. This is the same rule as always running R2, because band >= c.

**Could-not-decide, in short:**
- too few tokens or samples;
- invalid data;
- the arm under test did not draft, or a reference did;
- the scorer does not track C0, a gross alignment error (real rounding gives D2 of ~1-15);
- R2 was needed but is missing;
- a PASS without the power to see a 2-point top-1 shift.

### 2.6 Power and sample size

- **Inputs.**
  - Per-token variance of the top-1 feature under our chain, computed from stored teacher-forced rows: 0.048 for the KL
    harness's 2,040 rows (gate-1103-1354/kl/base) and 0.069 for the 34 greedy G-P4K0 rows (tie/score-w1.tsv). Script:
    `work/ds41/gate/sampled/scratch/power_estimate.py`.
  - Sampled answers are probably less certain: acceptance is 81-83 % sampled vs 93 % greedy. Planning value: 0.09.
- **Detectable shift.** At 8,192 tokens per arm, the smallest top-1 shift seen with 80 % probability, in the least
  favourable direction (3 df, alpha 0.01, lambda 15.46), is:

  | variance | 0.048 | 0.069 | 0.09 |
  |---|---|---|---|
  | detectable shift | 0.0135 | 0.0161 | 0.0184 |

  The 0.02 floor holds up to a variance of ~0.106. Above that the verdict is NOT DECIDED, not a guess.
- **The bugs a drafter could have:**
  - **The textbook speculative-sampling bug** (the replacement drawn from p~ instead of the residual) on ~70 % of rows
    shifts top-1 by 0.034-0.048, about 2-3x the detectable shift. Selftest: caught in 30/30 synthetic tests at 4,000
    tokens, and at half strength in 20/20 at 8,192.
  - **Accepting with the untruncated p** instead of p~ shifts top-1 by about -0.007 to -0.015. This is at or below the
    detectable shift, so it would **not reliably** be caught.
- **False FAIL:** <= 1 % by construction. Selftest calibration: 1 in 200 synthetic exact-drafting tests (0.5 %).

## 3. GPU minutes (with 8080 down; gap open / close ~3 min not included)

| step | estimate |
|---|---|
| R1 = C0 served: start ~0.7 (`COOL_MIN=10`: not a speed arm; the drive's 50 C rule stays), 16 requests x ~25.6 s at ~24 tok/s = 6.8, stop + kernel check 0.3 | ~7.8 min |
| X = C-N served: 16 x ~23.3 s at ~27 tok/s | ~7.2 min |
| score R1, score X: scorearm.sh, ~15 s start + 16 segments of ~575 rows = ~80 windows of 128 at ~2.4 s each (the teacher runs: 2,047 positions in ~38 s) | 2 x ~3.5 min |
| `sampled.py judge --stage1` (CPU) | < 0.2 min |
| **typical total** | **~22 min** |
| only if stage 1 does not pass: R2 served (K = 3) + scored | + ~8.8 min |
| **worst case** | **~31 min** |

Notes on the estimates:
- The default `COOL_MIN` of 60 would add ~2.5 min.
- Prompt-major order would save ~0.6 min per arm, but loses the balance if the budget cuts the plan.
- R2 should start only if >= 10 min remain of the test's allowance. Otherwise the result is NOT DECIDED.

## 4. Running it in gap D2

Nothing below is written as a script yet. It follows `gap-ctie-served.sh`'s `sarm`.

1. Create the run folder `O = results/ds41/gate-MMDD-HHMM-csampled/`. Write `sampled.py rule > O/rule.txt` before any
   engine starts. Preflight: `sampled.py selftest` must print `SELFTEST OK`.
2. Run each served arm (R1, then X) with:
   `SAMPLED_ARM=<role> CLIENT="<envcheck> && python3 -I .../sampled/sampled_client.py \$URL \$OUT" SERVER_ENV="STRATA_DS4_AUTO_PIN=1 STRATA_DEBUG=1" COOL_MIN=10 SOFT_GB=14 DS_SERVER=strata-v026/serve/server.py PROFILE=<snapshot copy> bash work/ds41/tune/tunearm.sh csampled-<role> <cfg> 8>&- 9>&-`.
   Then link `O/<role>` to the arm folder.
3. Run `sampled.py ids O/<role>` (CPU).
4. Copy the snapshot, then run
   `SCORE_LIMIT_S=420 bash work/ds41/tune/scorearm.sh O/<role>/score configs/DS41-gate-A.json O/<role>/score-ids.json`.
5. Run `sampled.py judge O --stage1`:
   - exit 0: PASS;
   - exit 2: NOT DECIDED;
   - exit 3: R2 is needed. Run steps 2-4 for R2 with `SAMPLED_K=3`, then `sampled.py judge O`, which gives the final
     exit 0 / 1 / 2.
6. `O/verdict.md` and `verdict.json` hold the result. DS41-daily.json is unchanged.

## 5. What a PASS proves, and what it does not

**It proves:**
- On these four prompts, at our sampling settings, for this N, C-N's tokens are calibrated against the reference the
  same way C0's are, within the larger of:
  - the 1 % sampling-noise bound;
  - the distance of C0's own placement variant.
- The test had at least an 80 % chance of seeing any 2-point top-1 shift. The textbook speculative-sampling bug, even at
  half strength, would have been caught with near certainty.
- Together with the source reading (section 1.1: the exact accept / residual rule), this is the evidence for "drafting
  does not change the distribution beyond rounding".

**It does not prove:**
- That the same seed gives the same tokens. It cannot, by design (1.2).
- That shifts below ~1.5-2 points of the top-1 rate are absent. The "accept with the untruncated p" class sits about
  there.
- Anything about errors that leave the three features' conditional means unchanged, for example a shuffle among
  rank >= 3 tokens with equal log-probabilities.
- Anything about the draft position. A fault only at draft position 3 or 4 is diluted by the share of tokens accepted
  at that depth. Without `DS4_ROUND_LOG`, the ids do not say which rows were drafted.
- Anything about:
  - thinking-on text and the server's thinking-budget wrap-ups;
  - prompts above ~1K tokens: the prompt skip, slot restore and 128K paths;
  - tool calls;
  - other sampling settings;
  - another N or drafter pack;
  - hours of adaptive-cache drift.

## 6. Harness (`work/ds41/gate/sampled/`)

- **`sampled.py`**: the rule, `ids`, `judge [--stage1]` and `selftest`. Pure Python: its own chi-square and noncentral
  chi-square, no scipy or numpy.
- **`sampled_client.py`**: the request driver. **Written, not run.**
- **The selftest** (run 11-07, `nice -n 19`, ~100 s): **SELFTEST OK**, 22 of 22 checks
  (`scratch/selftest.txt`). It covers:
  - the chi-square quantiles and the power constant;
  - the sampler chain: min_p, top_p, ties, and top_k then top_p;
  - 13 file-level cases in the engine's own formats: identical -> PASS; the textbook bug -> FAIL; half strength -> FAIL;
    half strength inside a wide reference band -> PASS; too few tokens -> NOT DECIDED; enough tokens but under-powered
    -> NOT DECIDED; bug without R2 -> NOT DECIDED (and stage 1 exit 3); identical without R2 -> PASS; a misaligned
    scorer -> NOT DECIDED; R1 drafted -> NOT DECIDED; X did not draft -> NOT DECIDED;
  - the raw-id parser;
  - a calibration study: false fails 1 in 200; the bug caught 30/30 and, at half strength, 20/20.
- The synthetic rows are shaped like the stored KL rows: E[p(1-p)] 0.070, 2.8 tokens kept on average, 65 % nearly
  certain. The synthetic arm data are deleted after judging; `SAMPLED_KEEP=1` keeps them.

## 7. Needs Karl's decision

1. **The band's noise floor.** band = max(chi2(3) 99th percentile = 11.34, D2(C0v, C0)). The literal reference-pair
   band would fail a correct drafter ~50 % of the time. The alternative is no R2 at all (band = the noise floor only):
   always ~22 min, but no allowance for placement-level rounding.
2. **The "too few samples" rule.** The power floor is DELTA_STAR = 0.02 at 80 %, plus N_MIN 4,000 tokens, >= 3 samples
   per prompt, <= 10 % invalid, alpha 0.01.
3. **R2's form.** One Aa-style variant (`--vram-experts 0.98`), not Aa + Ab. It runs only when needed, at K = 3.
4. **The scorer.** DS41-gate-A through scorearm.sh (proven), or cfg-C0f through cliarm.sh (C's placement; window 128
   untried there).
5. **Coverage.** Thinking off, short prompts only (section 5).
6. **Time and cool-down.** `COOL_MIN=10` for these non-speed arms. The worst case of ~31 min is just over the ~30 asked
   for, and happens only when stage 1 does not pass (<= 1 % if drafting is exact).

## 8. Karl's decisions (11-08) - FIXED

All six items of section 7 approved as designed (noise floor max(11.34, R2's distance); DELTA_STAR 0.02, N_MIN 4,000 and
the sample minimums; R2 single and conditional; A's config as scorer; COOL_MIN=10 and ~31 min worst case). Coverage adds
an INFO-only thinking-on arm at effort low (C0 and X only, same statistic, beside the main result) if it fits in ~10
extra minutes under the gap cap; otherwise skipped and said so. Full quote: GAP-C234-PLAN.md section 6.
