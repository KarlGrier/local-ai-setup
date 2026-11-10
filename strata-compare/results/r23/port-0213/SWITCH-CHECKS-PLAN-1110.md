# v0.2.13 port: the switch checks (Karl 11-10) - plan and proposed rules

**Karl 11-10:** "the v0.2.13 port's switch checks, on the fetch-patch engine (web search end-to-end, the served-output
comparison against P028x, the C++ parity tests for the files our patches change, the sampled test, and how often the
lost-answer guard fires). Desk prep now, gaps today, aiming to finish before this evening. Nothing switches; report the
verdict."

These are the before-switch requirements of results/r23/port-0211/PORT.md:166-179 (from REVIEW-1105.md section 4), plus
the sampled test. **Nothing switches.** 8080 stays the daily.

## The two arms

| Arm | What | Engine | Server tree |
|---|---|---|---|
| **B** | the daily as served now: configs/P028x.json, test form (no picture reader, fallback or guard key) | engine-r23afetch 153ce47d3ef0 (v0.2.8 + 28 + the fetch patch) | strata-r22p028x/serve |
| **P** | the port: configs/P0213x-af2.json = configs/P0213x.json + STRATA_ADAPT_FETCH=2 (the daily's one switch P0213x lacks), same test form | engine-r23p0213 639dfb1b7042 (v0.2.13 + 36, r23-port0213 6dd81ecd1) | strata-r23p0213/serve |

- P0213x.json carries the port's pins: v0.2.11's pins, plus GDN_TC=0, CONVL2=0 and ARENA_FILE_CACHE=0 (Karl 11-09).
- Apart from those pins and the paths, the two arms are the same config: both have U, sampling 1.0 / 0.95 / 20 / min-p
  0.05, and the same args.

## The checks and the proposed rules

**C1. C++ parity and unit tests for the files our patches change.**
- The programs: build-switch (building now under nogap-run) = the test set, the shape gap's GEO_TESTS at the default
  shape, and REVIEW-1105 4.3's list:
  - verify_parity, verify_batch_parity, sampler_parity;
  - gr_parity, gr_multi_parity, gr_upmix_parity;
  - elementwise_parity, q8k_quant_parity, native_dense_ple_key_test;
  - prefill_fused_iq_test with and without --v2.
- The CPU ones run before the gap. So do the server's own test suite and the node tests (REVIEW 4.4), with the known
  failure test_hip_ordinal. The GPU ones run in the gap, before any server.
- The fetch patch's own files (expert_source.cpp, generate.cpp) have no parity program. Their check is the read-back
  start: one P start with STRATA_ADAPT_FETCH_VERIFY=1, the same check as the 11-09 gap.
- **PASS** = every program passes (a test's own documented skip is allowed) AND the read-back shows 0 mismatch lines
  with at least 200 slots read back.

**C2. Served outputs against P028x (the server path, output for output).**
- 8 fixed requests through each arm's own server: 4 prompts x 2 seeds, at the standard sampling with fixed seeds. One
  prompt is long enough for an answer_room continuation. The generated token ids are recorded (STRATA_DEBUG raw ids).
- B runs them twice (B, then B again: the reference's own reproducibility); P runs them once.
- **Result EXACT** = P's ids equal B's on every request where B equals itself.
- **Result DIFFERS** = some request where B is reproducible gives other ids on P. That is not a fail by itself: C3
  then decides, the same "exactness or distribution" test as for every upstream path.
- A request where B differs from itself is information only.

**C3. The sampled test** (results/r23/SAMPLED-QWEN-DESIGN-1109.md, unchanged math).
- R1 = B and X = P at K=8 (32 requests each); R2 = B again at K=4 (16 requests, the noise bound).
- The 4 prompts: W1-think, W2-code, C-conv and C-prose, thinking off, 512 tokens. The x28h scorer.
- **PASS** = D2(X, R1) <= band = max(11.345, D2(R2, R1)).

**C4. Web search end to end.**
- On each arm's own server, 3 search prompts with the server's own web search ("strata_web": true, the web page's
  path through run_with_mcp). Local SearXNG (8888) only: no paid search.
- The round that ends without its end event (the 5f5aebcc2 fix) is covered by the server suite in C1.
- **PASS** = on P, every request that completes on B also completes, with at least one search round, an answer that
  cites at least one fetched source, and no error or fatal line.

**C5. How often the lost-answer guard (#3961) fires.**
- The port's server prints "[strata] a request ended without an answer and without a finish reason" each time. Each
  firing restarts the engine and drops every parked conversation.
- It is counted over all P requests in the gap, and on our workload: one pass of the 9-workload screen (research-call
  replays and agent turns) and the three chat fixtures.
- **Information:** the count per number of requests, each firing named. A firing on our workload also gets a
  recommendation on whether a small switch patch is worth carrying.

**Information only, because it costs little while the screen runs anyway:**
- the screen's speed, P against B (one pass each);
- exact7 of P against P028x's stored x28h-e7a.

**Not covered (not on today's list):**
- **The port's baseline gate** (exactness on the CLI path, long40, the 3-pass screen and Basalt's speed rule) has never
  run on v0.2.13. The v0.2.11 port's gate failed only on prompt speed. A switch would still need it, or Karl's call.
- REVIEW 4.7: the single-card fallback config, still Cstar18-single, would run neither build.

## Verdict

- **SWITCH CHECKS PASS:** C1, C3 and C4 pass, and C2 is EXACT or DIFFERS-with-C3-PASS. C5 is reported.
- **FAIL:** any of C1, C3 or C4 fails, naming which.
- **INCOMPLETE:** a check could not run.

Nothing switches either way.

## The gap

- **How it runs:** one gap driver, work/r23/switch-gap/gap-switch0213.sh. It reuses the ADAPT_FETCH gap's reviewed
  machinery: the arm starts with env checks, the lock sweep, the kernel-error stop, the Qwen4 priority rule and
  port_gap4.sh. It gets a fresh review before it runs.
- **8080 down:** about 90-110 min, with a deadline of 150.
  - parity programs about 8;
  - the read-back start 4;
  - served outputs 12;
  - sampled arms about 15, plus the scorer about 20 (CPU, with 8080 still down);
  - web search 15;
  - the screen and fixtures, P then B, about 20;
  - the end 3.
- **Kernel errors:** any new Xid or kernel error stops at once, P028x comes back, an alert goes out, and kwatch is
  not cleared.
- **Qwen4 priority:** if open Flash weights appear, the gap holds and day one comes first.
