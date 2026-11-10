### Part 1 — known bugs and loading safeguards

| item | finding | action | result |
|---|---|---|---|
| 1. #838 (q8_1 scale / sum stored without the #606 clamp) | upstream's 2 sites (the shared expert's fused SwiGLU — on by default; gfx906's fused gate/up) **plus a 3rd in our tree: PR245's `native_gus_kernel`, every decode window**. The q8_0-style stores (fp16 scale only, no fp16 sum) overflow only past \|x\| > 8.3 M — listed, not changed | #838 + our site, behind nothing (finite blocks bit for bit) + a fixture (`check_gus_finite`) | C\*13's kernels: **619 / 700 (x 1e3) and 700 / 700 (x 1e4) blocks stored inf**; fixed: 0 differ from the old kernels, 0 non-finite, both cards; exact7 7/7 |
| found on the way | upstream's own native_grouped_parity: **1,229 failures on C\*13** — PR245's kernels take one group per grid row, but 0.1.38+ launches the PCIe call with 4 rows striding over up to 16 groups | grid-stride loop | 0 failures; C\*13 never hit it (`--pcie-frac 0`: that call has no groups), a config with pcie-frac > 0 would have |
| 2. #931 (control-token text in a message becomes a real control token) | our #567 port vs #567's head: rebased on 0.1.39, **the encoder now takes #537's plain spans** (incremental also with literals), test reference = a full encode_prompt (d55679c), a tools test-vector fix | listed; d55679c's test change taken; the rest not ported | – |
| | **reproduced on C\*13** (synthetic documents): copy a line with control text **3/20** exact (`IM_END = "<\|"`, `print("Hello, World!")`), a forged turn in a document marked untrusted **followed 30/30**; ids: 1,739 / 1,739 prompts with control text carry forged control ids (57,101) | ported (3 commits, one conflict at our encode_prompt) + `STRATA_CONTROL_LITERALS_OLD=1` | **copy 20/20, forged 0/30**, plain 0/30, no warning 30/30 (ordinary injection, unchanged); **ids 0 differences on prompts without control text** (389 prompts / 851,570 tokens; #567's own check 0 in 28,545,945); stop test 9/9; server tests = C\*13's |
| 3. crash recovery | kill -9 mid-answer, SIGSEGV mid-prompt, kill -9 idle: the client gets what was sent + an error event; **the next request restarts the engine and answers in 12.2 s**; lost: the request in flight and the whole chat cache (A's cached turn 0.35 → 2.7 s) | **no gap → #788 / #748 not ported** | both PRs' own tests fail on 0.1.39's server code (#788: BrokenPipeError at shutdown — seen once here, harmless exit 1; #748: a verify timeout leaves /health loaded=true — a kill does not exercise it) |
| 4. loading safeguards | each trial-merged alone, built, exact7 | **#958, #648, #896 taken; #619 code taken** (its only conflict: docs/MODELS.md) | 7/7 identical each alone and together |
| 5. iq_multi_parity on CUDA 13.3.73 | #538: 13.2.78 miscompiles IQ3_S / IQ2_S on sm_120 | – | **all checks pass on both cards; IQ3_S ref rel <= 6.8e-8, IQ2_S <= 5.7e-5** (the healthy range) |
| 6. Cstar13.json's settings | neither key set | – | **repeat_stop_tokens = 256** (default), **reasoning_budget_tokens = 0 (no budget)** |

### Part 2 — the patch ledger and guards → C\*13.1

- **patches/LEDGER.md**: 53 rows (one per commit of patches/r13c39). Classes: exact 16, rounding-level 2 (B.1, B.2),
  distribution-preserving 1 (exact sampling), fixes 15, serve / UI 7, measurement / test 12. Upstream PRs carried: 12
  (#550, #567, #652, #454, #700, #838, #931, #958, #619, #648, #896, PR245) plus 6 fork Eddoursul ideas.
- **The audit**: our patches read upstream's constants almost everywhere; the model-bound numbers in our own code are
  B.1's scratch (26,368 floats, 52,736 = 2×; tied to N / HC / LR by static_assert), B.3's row classes (speed only) and
  A.2's n_embd % 256. 40,525 and 248,320 are read from files. **Upstream itself hard-codes the embedding vocabulary
  248,320** — a new vocabulary needs upstream. The rest are per-file calibrations in the config → the runbook.
- **Guards**: 8 startup guards cover the 12 rows whose assumptions go beyond upstream's own checks; a mismatch logs one
  line and turns that patch off. Unit test 12 synthetic mismatches / 12; **engine negative test: for every guard the forced
  guard = the switch off by hand, hash for hash** (and it confirms the classes: exact patches off still give C\*13's
  hashes). The server checks its 54 fixed template-string uses against the model's tokenizer and template at start
  (serve/model_check.py). One false positive found and removed (the hc weights' GGUF type).
- **Inactive patches**: side-stash and the dump-routing patch are inert without their flags but entangled with active
  patches (the chat cache is built on side-stash's code; #652 and exact sampling sit on dump-routing's lines) — kept,
  documented.
- **C\*13.1** = v0.1.39 + 53 patches, clean clone; exact7 7/7 = C\*13; needles 72/72; Stop at 120K 7/7; #652, stops,
  #931, tool calls, repeat 3/3, round trips, browser 41/2 (the known non-bugs); **screens vs C\*13: LDR +0.3 %, decode
  +0.3 % (within noise)**.

### Part 3 — inspector and fit planner

- `bringup/inspect_model.py` (headers only, 0.2 s; works on 16 MB partial downloads of each shard): roles, trunk vs MTP,
  tokenizer / template / control tokens, n-gram table; upstream's fixed geometry and formats and each guard's
  assumption, with the constants parsed from the engine tree. **IQ3_S: RUNS. UD-Q4_K_XL: RUNS (+ `-DSTRATA_MMQ_KQUANTS=ON`
  for MMQ prompt reads of its K-quant experts). Signal AP-Q4_K_XL: NEEDS UPSTREAM — token_embd Q6_K** (Round 11's v39-f6k
  branch has the dequantizer; C\*13 cannot load Signal).
- `bringup/fitplan.py`: **predicted vs real 5080 slots 4,655 / 4,559 (+2.1 %), 2,580 / 2,646 (−2.5 %), 3,233 / 3,226
  (+0.2 %)**; helper max 3,583 (Round 11: 3,500 ran, 3,600 refused); RAM 60.5 GiB vs C\*13's soak peak 60.2 GiB; Signal's
  arena 54.96 vs 54.97 GiB. The starting config it writes for IQ3_S = C\*13's with helper 3200.
- Synthetic headers: hidden 3072, a 2-layer MTP block, undeclared nextn tensors, a Q4_0 embedding — **each NEEDS UPSTREAM
  with the exact constant / predicate named, and fitplan refuses each**; a declared 1-layer nextn (#619) RUNS.
