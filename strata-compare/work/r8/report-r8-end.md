### Ranked backlog (not built this round, with the numbers that decided it)
1. **Exact speculative sampling.** Corrected model: +3.5 % decode vs today (oracle on 9,007 positions; per drafted
   window +3.9 %). The coupled-drafting kernels already sample drafts from q on the GPU, so the build is a separate
   proposal RNG key, q lists written out, and an accept / residual tail in the verify sampler (~1–1.5 days incl.
   tiny-vocab and chi-square tests). Below the 8 % bar.
2. **The draft layer's prompt pass on a second stream** (with KV streaming). 0.69 s per prompt ≥ 32K: 6.7 % of a 32K
   prompt, 2 % at 112K (≈ 0.3 % of your time). 1–2 days.
3. **PDL in the window graph.** ≈ 0.14 µs per kernel boundary × ~2,576 ≈ 1.8 % of a window (microbenchmark); every
   kernel touched.
4. **Drop the commit → draft-1 sync.** ≈ 0.1–0.16 ms ≈ 0.5–0.7 % of a round.
5. **HC kernels (48 % of the read ceiling) / dense GEMVs (62 %) toward 80 %.** ≤ ~1 ms / ~0.8 ms per window if
   reachable; low confidence (HC v5 after two tuning rounds).
6. **MMQ tile shapes for 64–256 tokens per expert.** Inside the 22 % of prompt GPU time the expert GEMMs take; ceiling
   unknown, needs a microbenchmark first.
7. **Make the adaptive tier's swap landing deterministic** (apply finished swaps at a fixed round boundary, or wait
   for them). It would remove the rare tier-on rounding differences; speed cost unknown.

**Dropped with measurements:**
- thread affinity: no effect;
- GDN chunked prefill (FlashQLA): BF16 only, ~1,600× less accurate, and not faster with conversions;
- coupled drafting: −1.9 %;
- sparse drafter attention: nothing to recover;
- `--mtp-window 16384`;
- `--spec-split`;
- every draft-length setting;
- stream threshold 1,280.

### Open decisions for you
- **16 chat slots instead of 6** (same 16 GiB cap). With 7–16 chats open, going back to one takes 0.22 s instead of
  ~3.6 s. The cost: with big pasted chats the cache uses its whole 16 GiB, and MemAvailable fell to 20 GB in the needle
  test (6 slots: 23.7 GB). Try it: `--chat-cache 16` in a copy of `configs/Cstar9.json`. A lower `--chat-cache-mib`
  (e.g. 12288) would bound the RAM but drop big chats earlier.

### Patches and PR drafts
- Patches: `patches/r8/0001–0012` (C\*8), `patches/r8-B/0013` (PR245 transplant), `patches/r8-B/0014` (MMQ expert
  offsets); the combined series is `patches/r8c/` (superseded v1 of 0014 in `patches/r8-B/superseded/`).
- PR drafts (not posted):
  - 26: status, fixed upstream in 0.1.28;
  - 27: conversation cache vs chat cache;
  - 28: the CLI cache size depends on prompt length;
  - 29: the stream threshold, with its correction;
  - **30: PR245 measured** (bitwise on sm_120 and sm_89, +4.5 % decode);
  - **31: prompt MMQ expert offsets** (exact, −3 % prompt time, with the generic-load lesson).

### My corrections this round
1. **Policy model:** assumed draft 1 is always proposed → overstated the floor (+4–5.5 % → really ≤ 2 %) and exact
   sampling (+9–12 % → +3.5 %).
2. **A.2 copy share:** 10.4 % "recoverable" was really ~3 % (L2 effect).
3. **Track 2's first version:** 6 % slower prompts (generic loads), and an A/B that only compared the switch inside the
   patched binary.
4. **16 chat slots:** adopted on a screen whose chats were too small, then failed the memory floor in the needle test.
5. **Phases A and B ended without C\*8 on 8080** (they ran back to back in the queue). Fixed with a phase-end step
   from then on.
6. **Small workspace-boundary slips, each fixed at once:** a stray /tmp file, a TileLang cache in ~ (now redirected
   into tmp/r8), and a queue insert that raced the runner.
