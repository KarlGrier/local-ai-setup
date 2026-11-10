# Qwen port to Strata v0.2.7 - log (branch r22-port027, worktree strata-r22p027; from P021m = r22-port021-cont2)

Plan: results/PORT-V027-PLAN.md. Code only until the GPU gap (no compiling during LDR runs).

| # | commit (P021m) | on v0.2.7 |
|---|---|---|
| 1 | 25758565 serve: --side-stash | applied clean |
| 2 | 26ab6dde serve: --chat-cache | applied clean |
| 3 | 47a0687e web app: several chats, attached files keep their text | **skipped**: upstream 0.2.7's chat history (saved chats, edit/rewind, branch; #1787 #2615 #3823 #4004) replaces it. To check on the ported page: an attached file's text survives a reload / chat switch (our commit's second half) |
| 4 | c6e88dbb serve: --chat-cache keeps the shared-prefix checkpoint | applied clean |
| 5 | ebfd5299 serve + web app: Web search switch | server part clean; the page: upstream's 0.2.7 page kept, our Web search button / CSS / `web` setting / loadWeb added by hand (3 places). No node here for a JS syntax check: test the page in the port gap |
| 6 | 8cbfbb9a web search: today's date; www. = bare host | applied clean |
| 7 | 05dd1731 web app: two tabs keep each other's chats | **skipped**: it builds on our chats store (commit 3, skipped). To check: two tabs of 0.2.7's page do not overwrite each other's saved chats |
| 8 | ad022192 sampling: exact speculative sampling (STRATA_SPEC_EXACT) | **parked (decision)**: v0.2.7 rebuilt speculative sampling around a gated "proposal law" (prepare_gated_window, source_policy, invariant pools) incl. #3416, upstream's fix of our #2028 bias. Options: (a) re-implement our exact path on that structure (hours, risky); (b) use upstream's fixed probabilistic path and A/B it against P021m's arm C (SPEC_EXACT + DRAFT_CUM + cost gate) - with D2's STRATA_SPEC_COST arm. Recommendation: (b) first |
| 9 | 1042be4e serve: commit only the tokens a verify window hands out (#652) | conflict (generate.cpp) - to port by hand (or check whether 0.2.7 merged #652) |
| 10-13 | ROUTER_Q8K (4 commits) | applied clean |
| 14-15 | GR_FORK (+ its scratch on batched PLE) | conflict (fused_gr.cu, verify.cpp) - by hand; 0.2.7's own HC reads (GR_V3, GR_UP_WIDE) to compare against it |
| 16, 18, 21 | patch guards (+ gr_fork / mmvq_il guards) | conflict - they follow the patches they guard; port last |
| 17 | #619 nextn | applied clean |
| 19 | serve/model_check.py | applied clean |
| 20, 27 | cost gate (+ past the priced steps) | parked with 8 (sampling decision) |
| 22-25 | chat cache non-finite drop; think-fence; Tavily / Exa fallbacks | applied clean |
| 26 | chat cache owner tag + chat_drop | conflict (generate.cpp) - by hand |
| 28 | STRATA_DRAFT_CUM | parked with 8 |
| 29 | STRATA_PREFILL_V2 | conflict (CMake, guards, prefill) - by hand |
| 30 | answer_room continuation fix | conflict (server.py, test_server.py, generate.cpp) - by hand; required before any switch |

**State 10-27 22:00:** 14 of 30 applied, 2 skipped (superseded by 0.2.7's chat page), 4 parked for the sampling
decision (8, 20, 27, 28), 10 to port by hand (9, 14, 15, 16, 18, 21, 26, 29, 30 + the guards).

P021m's served switches that depend on them: SPEC_EXACT, COST_GATE, DRAFT_CUM, GR_FORK, PREFILL_V2, the continuation
fix. A port that serves 8080 needs all of them, or an A/B showing that 0.2.7's own path is as good.

**Gap plan:**
- **Wed morning:** build this partial port and run the repeat-run gate (--adapt-async) and the lossless series with
  0.2.7's defaults pinned off. Neither needs the hand-ported patches.
- **Wed-Thu:** the hand ports, code only, during the LDR runs.
- **Thu afternoon gap:** the per-switch gates, plus upstream's fixed proposal path against arm C.
| 26 | a8a5ee60 chat cache owner tag + chat_drop | ported by hand: three additive conflicts (0.2.7's prefill=1 split-serving key, nibble recheck) kept both sides |
| 30 | a653ae6c answer_room continuation fix | ported by hand with #652's engine half (commit only what is handed out, `emit`, the tcap lift): 0.2.7's serial loop head / gated draft call kept, `max_new` -> `lim` there; DRAFT_CUM / cost-gate context left out (parked). Hooks count as on P021m (live_transient 5, req_keep 4, req_tcap 3, req_tend 5). Server tests: 36 of the think-cap / keep / owner / chat_drop tests OK (strata-compare .venv) |

**10-27 ~22:00 - order for the remaining engine patches (my proposal; measure before porting):**
- **#652 (commit 9): done** - its engine part came in with commit 30.
- **0.2.7 has its own equivalents of the rest:**
  - GR_FORK ~ 0.2.7's GR_V3 / GR_UP_WIDE hyper-connection reads;
  - PREFILL_V2 ~ 0.2.7's reworked prompt path (layer-major prefill etc.);
  - SPEC_EXACT + DRAFT_CUM + the cost gate ~ 0.2.7's gated proposal law (#3416) + STRATA_SPEC_COST (backlog D2).
- **Wed morning gap:**
  - build this branch;
  - the repeat-run gate and the lossless series as planned;
  - plus speed (W1-W3, decode, 32K prompt) of 0.2.7's own paths against P021m.
- **Hand-port only what loses**, with its guards (16, 18, 21), during Wednesday's LDR runs; build and gate in Thursday
  afternoon's gap.
- The switch of 8080 needs either the hand ports or a measured tie. If that is not ready Thursday night, the fresh
  baseline waits for it. Karl wants items 7 and 8 measured on the new engine, so I report the slip and ask what
  should fill the GPU meanwhile, rather than starting item 7 on P021m.

**10-27 ~23:00 - Karl's rule and what it changed (gap 12 edited before it started; backups *.before-neartie / *.before-twin / r27a-prob.json.before-top):**
- **Karl:** measure upstream's path against the served P021m first, and port ours only if upstream's loses. Upstream's path
  must also pass his rule: exact or distribution-preserving, shown by a token-distribution test like the one our exact
  sampling passed, not just faster. The same applies to GR_FORK and PREFILL_V2.
- **Finding (generate.cpp `gated_proposal_usable`):**
  - 0.2.7's fixed proposal law (#3416, the default "pick" gate) only runs with serial decode on one device, `--adapt-swaps 0`,
    `--lookup-chain 0` and `--pcie-frac 0`. Our served form has the second card's peer tier, adaptive swaps and the auto PCIe share.
  - Anywhere else it keeps the OLD acceptance rule (the #2028 bias) and prints one warning, which names
    `STRATA_SPEC_PROB_GATE=top` as exact there.
  - So `r27a-prob` (speed arm B) and the twin arm now set the top gate. The top gate decides the window on q's largest
    probability before the draw (our SPEC_EXACT's rule). Round 19 measured it on v0.1.43: -1.5 points, p 0.29.
  - Gap 12 greps arm B's log for the warning.
- **Measurement twin:**
  - branch `r22-port027-meas` (worktree strata-r22p027m) = r22-port027 + patches/r20-meas-v04441 (4 commits);
  - 6 conflicts, all additive, both sides kept: the verify.hpp tap API, the teacher-force block after 0.2.7's draft_next,
    the `forced.empty()` loop guard on 0.2.7's `lim` head, the server's logprobs key / rejected-tool-call fields;
  - `strata_ids` added before `openai_collect`'s return;
  - syntax-only compile at nice 19 (4 s): generate.cpp, verify.cpp, expert_source.cpp, native_dense.cpp have no errors,
    so the hand-ported commits 26/30 type-check too; elementwise.cu was only preprocessed.
- **Gap 12 additions (~2 h more, ~5.5 h in all):**
  - **1b:** the twin build (`build-port027.sh twin`, tests ON, with upstream's sampler tests);
  - **2b:** upstream's spec_prob_test, gated_proposal_test, spec_verify_parity, spec_proposal_parity;
  - **7:** round 19's near-tie test (arith-j3, T 0.6, 4,000 speculation off vs 4,000 SPEC_PROB + top gate,
    work/r22/neartie_compare.py). It reproduces round 19's table exactly: biased rule +4.1 points, p 0.003; top gate p 0.29;
    ours p 0.25.
  - A p < 0.05 is not a verdict: 4,000 more on each side first, as round 19's sp_more.sh did.
- **GR_FORK / PREFILL_V2 under the same rule:**
  - their test is output equality rather than sampling: exact7 repeat, lossless series, the 40-prompt KL rule;
  - gap 12 runs these on r27a, which is 0.2.7's 0.2.6-default paths with the new defaults pinned off;
  - 0.2.7's own new prompt path (PREFILL_LAYER_MAJOR=1) and GR_UP_WIDE need their own KL / exact7 rows before they can
    stand in for PREFILL_V2 / GR_FORK. That is for Thursday's gates, if the speed screen makes them candidates.

## Gap 12 results (10-28 08:45-10:51, 126 min; results/r22/gap12/summary.txt, speed-table.md, sp/, pfy/)

- **Builds:** r27a (v0.2.7 + 17 commits, engine 2accf218) and the twin (+ upstream's sampler tests, 04b67c3e).
- **Server tests:** 1229 run, 1 failure: test_hip_ordinal (a Windows HIP ordinal case). It fails the same way on
  PRISTINE v0.2.7 on Linux (checked 10-28 from `git archive v0.2.7`), so it is upstream's, not the port's.
- **Upstream's sampler tests** (spec_prob, gated_proposal, spec_verify_parity, spec_proposal_parity): all rc 0.
- **Repeat-run gate:** r27a 7/7 identical run to run, r27a --adapt-async 7/7 (and both give the same outputs) - PASS.
- **Lossless config:** PASS (0.2.7's new defaults pinned off: ROUTE_PRIOR=0, PROMPT_ATTN_IMMA=0, PREFILL_LAYER_MAJOR=0).
- **KL (pf_yardstick long40 vs gap 8's references):** r27a top-1 37/40, KL mean 0.132, p90 0.096, rows > 1: 1 - PASS
  (inside both references).
- **Speed screen, P021m test form (M) vs r27a (A) vs r27a-prob (B), 2 passes each (M A B B A M):** decode geomean
  A/M 0.925, B/M 0.897. Per workload A/M: W1 1.00, W2 0.89, W3 0.91, A-edit 0.97, B-write 0.97, R1 0.90, R2 0.82,
  R3 0.92, R4 0.96. Prompt (TTFT) about 5 % slower on A (24K: 5.79 vs 5.49 s; 54K: 12.66 vs 11.95 s). Draft acceptance
  lower on A (R2 54-56 % vs 71 %; R1 69-70 % vs 78 %) - the parked drafting/sampling patches (DRAFT_CUM, cost gate,
  SPEC_EXACT) are the likely main part; GR_FORK and PREFILL_V2 the prompt part.
- **Near-tie distribution test (Karl's rule), arith-j3 T 0.6, 4,000 each:** speculation off ('=' 51.9 %) vs upstream's
  STRATA_SPEC_PROB=1 + top gate ('=' 51.0 %): -0.9 points, p 0.41 - PASS (no difference shown). Speculation really ran
  (0.471 vs 0.430 s a sample; the "spec depth" grep is a P021m-only log line, so its 0 says nothing). Secondary check
  vs the reference probabilities: off p 0.41, upstream's path p 0.047 ('=' 1952 vs 2013 expected) - borderline; not
  significant after the two-test correction (0.025), but not a clean pass either.

**What it means for the port (Karl's rule: upstream's path first; ours only where upstream's loses):** upstream's own
paths lose on speed (-7.5 % decode, -5 % prompt), and upstream's speculative sampling path (B) is slower still and only
borderline on the second exactness check. So: hand-port ours - the sampling trio (SPEC_EXACT, which passed Karl's test
before, + DRAFT_CUM + the cost gate), GR_FORK and PREFILL_V2, with their guards - code only during the LDR runs; build
and the per-switch gates (KL + speed A/B, plus 0.2.7's GR_UP_WIDE, MMVQ_IL_89, --mtp-draft-vocab, layer-major prefill)
in Thursday afternoon's gap. The switch still needs the hand ports or a measured tie.

**Karl 10-28 ~11:05:** agreed - hand-port ours (exact sampling, the draft-length rule (DRAFT_CUM), the cost gate,
GR_FORK, PREFILL_V2). **Before the switch, rerun BOTH distribution checks on the hand-ported speculative path and both
must pass cleanly:** (1) the hand-ported speculative arm vs speculation off (the '=' frequency, arith-j3 T 0.6), and
(2) EACH arm vs the reference probabilities (sampling_probe analyze own). Clean = every p >= 0.05, no multiple-test
correction to lean on (gap 12's upstream path had p 0.047 on (2): that would not pass).

## Hand-port done, code only (10-28 ~15:40-16:30, during the bundle rerun; nothing built)

Branch r22-port027 (worktree strata-r22p027), 10 commits on 9bacbe42; each keeps the original message plus a "Port to
v0.2.7" note; the Claude co-author / session trailers of the original commits are left out (today's two GR_FORK picks
rewritten with filter-branch, trees unchanged; 240dbc85 / 697d9f4a from 10-27 still carry them - local only, strip before
anything is published):
- 3f8c84a6 GR_FORK (7d841abf) - fused_gr.cu: 0.2.7's GR_V3 default-on helper kept, the fork kernels after it; the fork
  branch first in fused_gr_read_multi, then 0.2.7's v3_env. Note: 0.2.7 turns GR_V3 ON by default on a cc 12.0 card with
  > 13 GiB (our 5080); STRATA_GR_FORK=1 runs before it, and the port pins 0.2.7's new defaults off anyway.
- b0641739 GR_FORK scratch (cf8183ac) - clean.
- fd019b94 / 3a8e17e8 / 9427d13f patch guards (1929176a, 40497567, 0e43c036) - CMake source list both sides.
- b7f25d8c PREFILL_V2 (785e45df) - additive conflicts with 0.2.7's opt-in NT=256 / F16 / WS prompt kernels: both kept
  (the v2 section reopens the !__HIPCC__ block; setup_nt closed before setup_v2); the guard files taken in P021m's final
  form (incl. the DRAFT_CUM guard). 0.2.7's opt-in WideBatch path returns before v2 only when asked for; the w11 / f16
  block before it is HIP-only.
- 6644cb9c SPEC_EXACT (ad022192) - verify: the exact branch first, then 0.2.7's gated-measure / SPEC_PROB branch and
  tail; generate (server + CLI): 0.2.7's gated_proposal / older-path split kept, the lookup check compares the drafter's
  raw argmax (ess_top(0)) when exact, set_spec_window after set_spec_proposal / set_spec_q, exact windows on the normal
  expert pool (0.2.7's invariant pool stays for its own SPEC_PROB), 0.2.7's out-of-memory retry kept. Exact excludes
  SPEC_PROB (no q buffer -> prob() false -> gated_proposal false). Two sample_tokens_spec overloads as on P021m.
  The plain sampling chain is unchanged in 0.2.7 (#3416 touched only the spec_* paths; SamplerParams identical).
- 846a97e1 / 7fe2c0a7 cost gate (94b00fbe, 4518c9b3) - the window size inside 0.2.7's older-path branch (after its
  gated_proposal and opt-in STRATA_SPEC_COST branches); the drafter's chain stop falls back to 0.2.7's chain_rule_
  (STRATA_SPEC_COST) when the gate is off or past its table, else --spec-min-p.
- 09d63f51 DRAFT_CUM (632ae8b7) - window size: DRAFT_CUM, then the cost gate, then --spec-min-p; the threshold update
  after 0.2.7's generation = {} and before its GatedDraftLimit / draft call (both loops).
Checks done without compiling: the patches' own files are byte-identical to P021m's (spec_exact.hpp, cost_gate.hpp,
draft_cum.hpp, both tests, xor_scatter.cuh, patch_guard.*); the v2 section, the fork section and ess_draft_sample are
identical to P021m's; FusedGrArgs / GrMulti / Batch / NativeGeom / Tables / SamplerParams and the constants they use
are unchanged in 0.2.7.
**Still to do:** the measurement twin (r22-port027-meas) rebased on this head; then in the Thursday gap: build (tests ON),
upstream's sampler tests + patch_guard_test + cost_gate_test + draft_cum_test, the per-switch gates (exact7, KL rule,
speed A/B vs P021m), and BOTH distribution checks on the hand-ported speculative path (Karl: every p >= 0.05).
- Measurement twin: r22-port027-meas rebased onto the new head (old head kept as branch r22-port027-meas-pre-handport =
  7615279e); the 4 MEASUREMENT commits applied cleanly (aec26ac7, 06933252, e40df40d, 46ecaed4).

## Gap 13 prepared (10-29 ~09:50): the hand-port's gates, after the second 10-24 rerun
- work/r22/gap13.sh (started by unit port-gap13-wait once the rerun ends cleanly): build (27 commits) + twin (31, tests ON
  incl. patch_guard_test, cost_gate_test, draft_cum_test, prefill_fused_iq_test --v2 - build-port027.sh backup
  .before-handport), server tests, upstream's sampler tests, exact7 x2 on r27h (pin 2500), lossless, KL (long40 vs gap
  8's references), speed screen P021m test form vs r27h (2 passes, turned order), and Karl's two distribution checks on
  the twin: r27t-hnospec (served switches GR_FORK + PREFILL_V2, speculation off) vs r27t-ess (+ SPEC_EXACT, DRAFT_CUM,
  COST_GATE; --spec 7 --spec-min-p 0.5, lookup on, --adapt-swaps 0 as gap 12), 4,000 each at arith-j3 T 0.6, each also vs
  its own probabilities. Clean = every p >= 0.05; anything else = no switch, report to Karl. gap 12's binaries kept as
  engine-r22p027*-g12. Start lines checked per arm.

## Gap 13 so far (10-29 12:38-, results/r22/gap13/summary.txt)
- Builds OK: engine-r22p027 = v0.2.7 + 27 commits (f80f3b37...), twin + 31 (32967912...).
- Server tests: 1,229, one failure = test_hip_ordinal (upstream's own; also on pristine v0.2.7 and in gap 12).
- Upstream's sampler tests rc 0 (4/4); ours: cost_gate_test, draft_cum_test, prefill_fused_iq_test --v2 rc 0;
  patch_guard_test rc 2 in the script = called WITHOUT its arguments (usage error) - run by hand with the model + MTP dir:
  0 failures, 7 guards, FORCE=all turns all 7 off (gap13/patch_guard_test-args.txt).
- Repeat gate: exact7 r27h 7/7 MATCHED (pin 2500). Lossless: cfg PASS.
- **KL check FAILS on r27h**: top-1 33/40 (>= 34), mean 0.585 (<= 0.401), p90 0.890 (<= 0.366), rows > 1: 3 - against
  gap 12's r27a (0.2.7 paths, none of our switches): PASS, mean 0.132. One of the hand-ported switches (or their
  interplay with 0.2.7's prompt path) moves the prompt logits beyond rounding level: diagnose per switch in the next gap
  (pf_yardstick long40 on r27h without PREFILL_V2, without GR_FORK, without both; ~9 min each). No switch while it fails.
- Script slips (fix before reuse; the running copy is not edited): patch_guard_test needs its two arguments; starts()
  reads the config's log, which exact7 does not write (empty counts on r27h; the with_server arms are right).
- **Distribution checks (Karl's rule):** (1) the hand-ported speculative path vs speculation off, arith-j3 T 0.6: '='
  53.4 % vs 53.1 %, p 0.772 - PASS. (2) each arm vs the build's own reference probabilities: speculation off p 0.006
  ('=' 2035 vs 2119 expected), the hand-ported path p 0.020 ('=' 2053 vs 2125) - BOTH FAIL. Gap 12's 0.2.7 build
  without our switches: off p 0.41 (pass). The speculation-off arm failing too means the gap is between this build's
  prompt-path probabilities (the reference) and its decode sampling, not in speculation - consistent with the KL
  failure. Suspects: PREFILL_V2 and / or GR_FORK on 0.2.7 (GR_V3 is on in both builds). **NOT clean -> no switch.**
- Gap 13 done 14:27 (108 min, kcheck clean; P021m back on 8080).
- Next (needs Karl's go): per-switch diagnosis in a GPU gap - pf_yardstick long40 + the check-(2) near-tie arm on r27h
  without PREFILL_V2, without GR_FORK, without both (~9 min KL each; ~35 min per near-tie arm).

## Karl 10-29 ~14:40: go on the per-switch check (gap 14, queued)
"The KL check and the check-2 arm without PREFILL_V2, without GR_FORK, and without both. If one switch is the cause and
can't be fixed cleanly, port the rest without it and report the prompt-speed cost."
- work/r22/gap14.sh (unit port-gap14-wait starts it after ldr-night-1029 and ldr-toggle-1029 end; ~3-3.5 h): KL on
  r27h-nov2 / -nofork / -noboth (with r27h), check (2) on r27t-hnospec-<v> (each vs its own probabilities), the pick (KL
  PASS + p >= 0.05; one-switch drops first), checks (1) + (2) on r27t-ess-<v> for each passing variant, then a speed screen
  r27h vs the passing variants (the prompt-speed cost). Configs created 10-29 (r27h-*, r27t-hnospec-*, r27t-ess-*).
- After it: if one switch is the cause, look at whether it can be fixed cleanly (its kernels vs 0.2.7's prompt path);
  if not, the port goes on without it and Karl gets the prompt-speed cost.

## Karl 10-29 ~19:20: v0.2.8 is the new baseline and the port's target
- Accepted (tagcheck --accept 19:17). After gap 14: rebase the hand-ported series v0.2.7 -> v0.2.8 (its Qwen-path changes
  are small; the server's tool-call fixes are why), rerun the same gates on v0.2.8.
- tool_call_recovery (on by default in 0.2.8: serve/server.py tool_call_recovery_setting, frontend.py OutputParser recover):
  test on the port with Jan and the coding harnesses - real tool calls recovered; text that talks about or quotes tool
  calls never turned into calls.

## The series rebased onto v0.2.8 (10-29 ~19:30-20:00; code only, nothing built)
- Branch r22-port028 (worktree strata-r22p028) = v0.2.8 + the 27 commits; twin r22-port028-meas (strata-r22p028m) = + the
  4 MEASUREMENT commits (31). r22-port027 / -meas untouched (gap 14 uses their binaries). Trailers stripped on the new branch.
- Conflicts, all resolved by hand:
  - serve/server.py (Web search switch): v0.2.8's stop ids (end_token_ids - the stop-id fix 43f32b30) kept, our self.web added.
  - serve/frontend.py (our think-fence commit vs v0.2.8's #4077 stray-think / #4427 handling): both kept - our fence hold
    (a </think> inside a code fence of the reasoning is held until the fence closes) and upstream's stray-think drop after
    the reasoning; our end-of-turn flush before upstream's rcall check. v0.2.8's corpus test "4077-stray-think-in-a-fence"
    expected upstream's behaviour (reasoning cut at the quoted tag, the rest leaking into the answer); with our rule the
    reasoning stays whole and the answer is empty - the call arrives either way; the specimen's expected text updated with
    a comment (serve/test_tool_corpus.py). test_tool_corpus OK, test_tool_routes OK, test_server think/fence/tool OK.
  - src/kernels/cuda/fused_gr.cu (GR_FORK): v0.2.8 split fused_gr_read_multi into a per-slice function plus a wrapper for
    windows > kFusedGrMaxT (8); the fork block placed before the new slice function, a leftover old header removed.
    Caveat: the wrapper offsets the scratch per 8-token slice; GR_FORK's scratch layout assumes <= 8 tokens - fine at
    --spec 7 (windows <= 8), not for STRATA_WINDOW_MAX_T > 8 with GR_FORK (guard or note before such a config).
  - Everything else applied cleanly (continuation fix, SPEC_EXACT, cost gate, DRAFT_CUM, PREFILL_V2, guards); checked: the
    exact branch first in verify, the window-size order and set_spec_window in both generate loops.
- ggml pin unchanged (3cf03257). work/r22/build-port028.sh (from build-port027.sh; PORT_COMMITS after a culprit drop).
- Next: gap 14's verdict -> drop the culprit commit from r22-port028 if it can't be fixed cleanly -> build + the same gates
  on v0.2.8 (gap 15) + the tool_call_recovery test with Jan and the coding harnesses.

## tool_call_recovery - the offline test on the v0.2.8 port's parser (10-29 ~19:40; work/r22/toolrecovery/)
61 specimens x every feed mode (whole, pieces of 1 / 3 / 7, cut at every byte, streaming on / off), recovery on vs off;
upstream v0.2.8's own parser gives the same results except 2 think-fence cases only our port passes.
- (a) real calls: 21 of 22 pass, every recovery form included. The one failure is a baseline bug (recovery off too): a
  write whose file content holds </parameter>, </function>, </tool_call> on their own lines is cut at 141 of 218 chars and
  the rest leaks into the visible answer.
- (b) text that only discusses / quotes calls: 19 of 36 pass.
  - 6 false calls ONLY with recovery on, all outside fenced code: a bare <function=read> block in an unfenced doc,
    <tool_call>{json}</tool_call> in a sentence or on its own lines, a bug report quoting a <parameter=read> opener, a
    quoted earlier call in JSON form, an indented bare block (depends on the stream's cuts); recovery also adds 2 calls in
    an unfenced pytest file where the baseline already makes 1.
  - 9 with recovery off too (baseline parser): a template-form call outside a fence; a four-backtick fence closed by its
    inner fence; indented code not treated as code; in thinking turns v0.2.8's stray-</think> rule drops the tag even
    inside a fence of the answer (a fenced example then makes a call; 2 more texts lose the tag); a call drafted as the
    last thing before </think> read as real.
  - Fenced code, inline code, blockquotes, bare JSON and reasoning drafts pass.
- Live test ready for gap 15 (toolrecovery_live.py: 27 prompts x 3 in Jan / OpenCode / DeepSeek-harness shapes, the same
  seeds with recovery on and off).
- Karl 10-29: the served port gets "tool_call_recovery": false UNLESS gap 15's live test shows real calls lost without it
  AND no false calls with it.
- Upstream issue DRAFTS (pr-drafts/v028-parser/, NOT posted - Karl's OK per item): 1 file write cut at a closing-tag line
  (content truncated, the rest leaks into the answer), 2 a four-backtick fence closed by an inner ```, 3 an indented code
  block read as a call, 4 the #4077 stray-think rule removing a </think> inside a fence the answer opened (and a fenced
  test with a thinking block + call making a real call). All reproduced on pristine v0.2.8 (git archive), recover off,
  whole / byte by byte / pieces of 7; shared setup in HEADER.txt, script repro.py; privacy grep clean.
