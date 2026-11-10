# SUPERSEDED (2026-09-27 13:55): Strata v0.1.7 added real sampling; the measured result is in REPORT.md §9.

# Adding real sampling to Strata (assessment, not built)

**Today.** The server ignores every sampling field. The engine's `--serve` path decodes only through verify windows
(`Verifier::run`), which computes the **full-vocabulary logits for every window position** (`head_logits_`, T × 248,320)
and then calls `sample_tokens(..., sp.greedy = true)` — an argmax per row. The loop then keeps the drafts that
equal the argmax (`while (a < T-1 && window[a+1] == outv[a]) ++a`) and commits `a + 1` tokens; the rollback of
rejected drafts (GDN/PLE/indexer state snapshots and KV positions) already exists. A non-greedy CUDA sampler also
exists (`src/kernels/cuda/sampler.cu`: penalties → top-k → top-p → temperature, Philox RNG keyed by
(seed, position)) but it is only wired into the single-token `generate` path, it runs **one thread per row**
(k passes of a max-scan over 248,320 logits: ~5 M serial comparisons per row, several ms), and it has no min-p.

**The correct algorithm is almost a drop-in.** With deterministic drafts (Strata's MTP drafts are argmax drafts,
gated by the MTP's own confidence ≥ 0.5; the suffix drafter is deterministic too), exact speculative sampling is
"sample-and-match": at every window position t draw x_t from the *target* distribution p_t (after top-k 20,
top-p 0.95, min-p 0.05, temperature 0.6, in llama.cpp's order), accept draft d_{t+1} iff x_t == d_{t+1}, stop at the
first mismatch and emit x_t there (or the bonus token after the last position). Each emitted token is a draw from
p given the accepted prefix, so the output distribution is **exactly** the non-speculative one (this is the
q = point-mass case of Leviathan et al./Chen et al. speculative sampling; llama.cpp's
`common_sampler_sample_and_accept_n` does the same). Draft probabilities are not needed. The acceptance probability
of a draft becomes p_t(d) instead of 1[d = argmax p_t] — lower on open-ended prose, nearly unchanged on
predictable text/code, since temperature 0.6 sharpens p.

**What it would take** (estimate: 2–4 days for someone who knows the code base, ~300–500 lines + tests):
1. A block-parallel sampler for T rows (top-k via per-warp partial top-k + block merge, then top-p/min-p/temperature
   on ≤ 20 survivors, Philox draw) — ~0.05 ms per window instead of several ms. Add min-p to the chain.
2. `Verifier::run`: pass real `SamplerParams` with a per-request seed and `counter = position` (counter-based RNG
   makes the draw at a position independent of how many windows were rejected before it → reproducible per seed).
3. Protocol: extend `GEN` with temperature/top-k/top-p/min-p/seed (server.py already receives them in the request
   body and passes the dict to `generate`, which ignores it today); keep greedy when temperature is 0.
4. The adaptive drafting heuristics (`--spec-min-p`) stay valid; optionally draft only while p_draft is high.
5. Tests: (a) exactness — at temperature → 0 the output must equal today's greedy output token for token;
   (b) distribution — for a few fixed prefixes, histograms of the next token from 10⁴ speculative draws vs. 10⁴
   single-token draws (chi-square / KL), and a forced-wrong-draft test (the existing `--spec-corrupt`) must not
   change the distribution; (c) seeds reproduce.

**Expected cost.** Per-window cost is unchanged apart from the sampler (negligible with a parallel kernel; ~5–10 %
with the existing one-thread-per-row kernel). Fewer accepted drafts per window: on xhigh reasoning the greedy
acceptance measured here is reported in the main REPORT (tokens per window); with sampling at 0.6 expect somewhat
fewer, i.e. a decode-speed loss of the order of 5–15 % vs greedy Strata, while keeping the MTP speed-up.

**Feasible? Yes.** It is the most valuable missing feature for daily chat use (greedy decoding makes long `xhigh`
reasoning more repetition-prone), and the engine's structure (full logits per window, rollback, counter-based RNG)
is already the right one. The risk is in testing, not in design.
