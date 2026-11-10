### Decision point (end of Phase A)

Ranked by measured recoverable time × confidence ÷ effort; see the table in results/round8-summary.md and NOTES.md.
Two of my own Phase A estimates were wrong and are corrected here:
- **Policy model.** My first model assumed draft 1 is always proposed. The engine applies `--spec-min-p` to draft 1
  too (`T = 1; while T < S && dprob[T-1] >= floor: ++T`). With the real rule, a higher draft floor is worth ≤ +1–2 %
  (not +4–5.5 %), and exact speculative sampling +3.5 % vs today (not +9–12 %). The corrected model tracks the 37
  decode screens to within 2–3 %.
- **Group copies.** The A.2 profile put the per-expert MMQ group copy at 10.4 % of prompt GPU time. Removing it saved
  1 %, because the copy had left the weights hot in L2 for the matrix kernels.

### Phase B — build tracks

**Track 1: upstream PR245** (fork Eddoursul `cf307ea` + `8208f3f`, transplanted behind `STRATA_EXPERTS_OLD=1`;
`patches/r8-B/0013`)
- Real-expert parity is bitwise identical on sm_120 and sm_89 (7 format pairs × windows 1–8; 2,520 rows each).
- Engine greedy output is identical with a fixed cache.
- Exact mode: −6.0 % (math) / −8.0 % (code) per round.
- **Served A/B (2 alternating pairs, your settings): +4.5 % decode** (109.8 / 111.6 vs 107.1 / 104.6 tok/s), ms per
  round −4.2 %; prompts unchanged.

**Track 2: the prompt's MMQ reads streamed experts in place** (`patches/r8-B/0014`; pr-drafts/31)
- **Mechanism:** per-expert byte offsets in MMQ, stored below the weight address so the weight pointer stays derived
  from the kernel's restrict parameter (mmq.cuh edited in the build tree, the pinned checkout untouched). Blobs are
  DMA'd to the end of 4 KiB-padded ring slots, and slots are held until their group's products are queued. A group
  whose slots span half the ring or more falls back to the gather; groups never change.
- **Exactness:** greedy output is identical at 2K, 32K and 112K and on repeated-token 4K / 9K prompts; forced fallback
  mixes (`STRATA_PREFILL_PTR_SPAN`) are identical too.
- **Speed vs C\*8 (untimed, 2 alternating rounds): 32K 9.48 → 9.21 s (−3.0 %), 112K 31.94 → 30.94 s (−3.1 %).**
  The profile's 10.4 % "copy" share was not all recoverable: the copy had left the weights hot in L2.
- **A regression caught in Phase C:** the first version made prompts 6 % slower. A table of absolute pointers made
  1,152 read-only global loads generic (SASS), in every launch, and my own A/B had only compared on vs off inside the
  patched binary. Fixed and re-measured against C\*8.

**Not built**, with the measured or modeled ceiling: exact speculative sampling (+3.5 % modeled), PDL (≈ 1.8 % of a
window, microbenchmark), dropping the commit → draft-1 sync (≈ 0.5–0.7 %), the draft layer's prompt pass on a second
stream (≤ 6.7 % of a 32K prompt, 2 % at 112K), HC/dense GEMVs toward 80 % of bandwidth (low confidence), and MMQ tile
shapes (ceiling unknown).

**Dropped with measurements:**
- thread-affinity fix: no effect;
- GDN chunked prefill (FlashQLA): BF16 only and not faster;
- coupled drafting: −1.9 % tokens per window;
- `--mtp-window 16384`: prompts −1–3 %, long-context decode risk;
- `--spec-split`: −10 to −26 %;
- every `--spec` / `--spec-min-p` combination screened: none beat 4 / 0.5.
