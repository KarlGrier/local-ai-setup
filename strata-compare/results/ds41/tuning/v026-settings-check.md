# Strata v0.2.4 (96ca4383, our DeepSeek engine) vs v0.2.6 (4b9e05a2): settings check, 10-25

Read-only (git show/diff/grep at the tags; no build, no run). Line numbers at v0.2.6, `model.cu` = `src/dsv41/ds4_model.cu`.

## Every setting the round may ship or use in tests
Same parsing, default and effect for an explicit value:
- args: --ssd-cache (explicit), --dspark, --dspark-conf, --tp (still "tensor parallel 2 -> 1" with this pack), --max-context, --eos,
  --expert-profile, --no-expert-cache, --reserve-mib, --verbose (new lines only), --mmap-experts (off/on same; auto can't copy-all here)
- env: DS4_SPLIT, DS4_SETTLE_MS, DS4_SETTLE_STORE, DS4_ENGRAM_CACHE_MB, DS4_ENGRAM_THREADS, DS4_CACHE_THREADS, DS4_CACHE_MARGIN,
  DS4_CACHE_BONUS, DS4_CACHE_DECAY, DS4_CACHE_INFLIGHT, DS4_ASYNC_T, DS4_COPY_GB, DS4_IQ_CTA_PER_SM, DS4_SPEC_Q, DS4_SPEC_WASTE,
  DS4_STORE_RESERVE, DS4_STORE_GB, DS4_STORE_FLOOR_GB, DS4_LAYER_CACHE_MB, DS4_CHUNK, DS4_FLOW_STATS, DS4_PROF (+ a new line),
  DS4_TOKLOG, DS4_NO_EOS, DS4_SCORE_PREFIX, STRATA_DS4_NO_LIGHT, STRATA_IQ_PREFETCH, STRATA_DS4_PROMPT_SKIP, card order.

Changed defaults:
- --prefill-chunk unset: v0.2.4 8192 -> v0.2.6 4096 (smallest card < 16 GiB, experts read in place; ds4_experts_rule.hpp:41-50).
  Pinned: --prefill-chunk 8192 unless the round ships another chunk.
- --ssd-cache unset: auto store up to all routed experts (was capped at 48 GB). Ours is explicit.
- --experts (new): auto = 6 for our 23.9 GiB pair (5 at <= 16 GiB of cards, so single-card runs default to 5). Pinned --experts 6;
  startup line `ds4: experts per word: 6 (full quality)` (model.cu:2061). v0.2.4 rejects --experts (exit 2): keep it out of
  v0.2.4 configs (rollback).
- Server (since v0.2.4.2, baa8f616): slot keep on by default (DS41_SLOT_KEEP_DEFAULT "1"; config env STRATA_DS4_SLOT_KEEP wins) and
  auto pin on by default (STRATA_DS4_AUTO_PIN, read from the server's own environment only). v0.2.4's server has both off, so the
  measured v0.2.6 runs pin both off; the conversation-cache test sets them itself. The kept-slot identity does not include the
  expert count or the chunk: with slot keep on, 5- and 6-expert arms could reuse each other's state.
- Version 0.1.49 -> 0.1.51 is part of the slot identity: v0.2.4 slots are not reused.

## The announced changes
- DS4_MISS_SPLIT (default on; =0 = old order): store hits computed while missed experts load; per-slot rows, same bits.
- Fewer decode launches (60d856a1): one launch for a GEMV's int8 roundings, hc_mix + hc_split fused; bit-identical by construction
  (DS4_QUANT_SINGLE / DS4_QUANT_NODEDUP turn it off).
- Prompt path by length (dfd1b0f2; kPromptFlowMin 96): >= 96 new tokens -> the chunked pass, below -> windows of 16
  (DS4_PICK_MIN, DS4_PICK=adaptive = v0.2.4's picker, which predicted from measured speeds and page residency and could flip for
  prompts under 2,048 tokens: the logit flips and the ~7 s stall). The chunked path warms up after load (DS4_WARM=0 off).
- DS4_PROF adds `ds4 prof CPU lane (IQ rows) per call: n, entries/call, prep, gate+up, h-quant, down` every 1,000 calls
  (process-wide averages; with DS4_MISS_SPLIT on each late expert counts as its own call).

## Bit-identity
Not bit-identical by default: the 4096 chunk (pinned away), path choice for prompts under 2,048 new tokens (kept: it is the fix),
slot keep / auto pin (pinned off for measurements). Everything else between the tags is bit-identical or does not apply here.
Prompts that take the same path on both (>= 2,048 new tokens, e.g. the teacher-forced 12K segments) should match.

## Other notes
- 5 experts on v0.2.4: no flag or env (no DS4_TOPK); only the pack's ds4.txt num_experts_per_tok. On v0.2.6: --experts 5.
- The pack is mostly IQ1_M in the trunk experts (23,040 IQ1_M, 16,128 IQ2_XXS, 6,912 IQ2_XS matrices). v0.2.4.2's IQ1_M change is
  a no-op on Zen 5 (AVX2 fallback only). 06f313b0 (v0.2.6) reworks the IQ1_M AVX-512 rows on our CPU-lane path; each row kernel is
  checked against ggml at startup (a failed check = slower, not other bits; DS4_GG_VERBOSE=1 shows it).
- ggml pin unchanged (3cf03257); no new CMake options for strata-dsv41 (BMI2-off only for portable builds; ours is native).
