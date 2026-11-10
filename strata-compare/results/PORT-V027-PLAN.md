# Qwen patch-series port: target v0.2.7 (Karl 10-27; replaces v0.2.6)

When: after the LDR week (not held for Qwen4). Nothing here runs before then. Source of every rule below: the v0.2.7 tag
(`include/strata/core/sm120_series.hpp`, `defaults_026.hpp`, `ple_residency.hpp`, `src/core/verify.cpp`,
`docs/release-notes-0.2.7.md`), read 10-27 11:10-11:30.

## Order
1. **Repeat-run gate first** (unchanged): v0.2.5's self-chosen `--adapt-async` default against `STRATA_ADAPT_ASYNC=0`
   (it applies to our two-card arena setup). Until it passes: `STRATA_ADAPT_ASYNC=0`, `STRATA_ROUTE_TAIL_SKIP=0`,
   `STRATA_PREFILL_CPU_SHARE` explicit (P021m: 0.4).
2. **Series on v0.2.7 with every 0.2.7 default off** (Karl: "pin these new defaults off unless they pass the gate").
   Baseline switch `STRATA_DEFAULTS=026` (all 0.2.7 Qwen defaults back to 0.2.6; a variable set by name still wins), plus
   by name: `STRATA_ROUTE_PRIOR=0`, `STRATA_PROMPT_ATTN_IMMA=0`, `STRATA_PREFILL_LAYER_MAJOR=0`, `STRATA_PLE_AUTO_RAM=0`.
   P021m's own `STRATA_GR_V3=1` stays (adopted earlier; on v0.2.7 it is also the sm_120 default).
   `bringup/patchtest.sh lossless` fails a config that leaves any of these unset; the runbook's log check catches the
   start lines of route prior, layer-major prefill and the PLE residency policy.
3. **Gate + speed A/B per switch**, one at a time against step 2 (Karl's KL gate where the output can change; speed only
   where it is bitwise):

| switch | acts on | output | test |
|---|---|---|---|
| `STRATA_GR_UP_WIDE` (wide HC up read; sm_120) | 5080 | bitwise per upstream's rule comment (Karl's note says not bitwise: check) | bitwise check, then KL gate if it differs; speed A/B |
| `STRATA_GR_V3` (split HC read) | 5080 | not bitwise | already on in P021m (adopted); nothing new unless the port changes it |
| `STRATA_MMVQ_IL_89` (Ada row tables, from a 4070 / 4080) | 4060 Ti | bitwise | speed only; check it against P021m's own `STRATA_MMVQ_IL=1` + `STRATA_MMVQ_IL_ROWS` table (which wins on the 4060 Ti) |
| `--mtp-draft-vocab draft_vocab_en.bin` | drafts only | should be exact | confirm with our exact sampling (T 1.0 / 0.95 / 20 / min-p 0.05, `STRATA_SPEC_EXACT=1`, `STRATA_DRAFT_CUM=1`) and the adaptive draft rule: greedy pair + served distribution check, then speed (upstream: +2.7-3.1 % English decode) |
| `STRATA_PREFILL_LAYER_MAJOR` (**not in Karl's list**: on by default for a 2-card CUDA layer split = us) | prompts | another summation order (upstream KL-checks it) | KL gate + TTFT A/B. Upstream on 2x A4000 with streamed experts: first word after 32K 141.8 s -> 27.7 s, decode equal. Could matter for LDR's long prompts |
| `STRATA_PROMPT_ATTN_IMMA` | both cards | rounding level | stays 0: failed Karl's gate in gap 9 (top-1 104 / 120 vs floor 108); retest only as backlog D3 |
| `STRATA_ROUTE_PRIOR` | **the 4060 Ti** (rule is per card: discrete NVIDIA <= 13 GiB; `Verifier::init` asks each card) | lossy (changes experts) | stays 0 unless Karl wants it gated |

4. **`--ple-io ram`: does not fit under the 12 GB floor (paper check, 10-27).** The served engine's resident set is
   64.7 GB (61.6 GB anonymous: the expert arena); the table adds 28.8 GB = 93.5 GB of 96.4 GB, leaving ~3 GB for the
   OS, LDR, SearXNG and the desktop. Also `ulimit -l` is 11.5 GiB (hard limit the same; no sudo), so the table could not
   be locked anyway: it would stay evictable page cache, which is just the mmap path. So no A/B unless the arena shrinks.
   Upstream's automatic version (`STRATA_PLE_AUTO_RAM`, new default) wants only 8 GiB headroom (under our floor), so it
   stays pinned off; the PLE read mode itself is lossless (upstream: identical md5 for direct / mmap / ram).

## Fixes in v0.2.7 that touch our setup
- #3350 / #3470: a leaked copy stream shrank the **second card's free memory with every long cold prompt on a layer
  split** (our VRAM guard setup). Worth checking against P021m's helper-card free-memory drift.
- #3602: a failed PLE row read no longer leaves the next request waiting for ever.
- #1503 (conversation cache reusing another conversation's K/V): only with `--batch` slots. P021m has none, so it does
  not affect the served build.
- #3416: upstream fixed the `STRATA_SPEC_PROB` gate bias of our issue #2028 (opt-in, "refs #2028": the gate is now part
  of the proposal law). Port step: compare with our own exact path (`STRATA_SPEC_EXACT=1`); if equal, one of our patches
  could go (with D2's SPEC_COST A/B). Nothing posted.

## Not Qwen
- No Qwen4 support in v0.2.7 (the tag watch's Qwen4 scan: no new lines since v0.2.6).
- **Gyro-L is supported now** (#3806: TQP5/6/7 on the CPU, CUDA and the MMQ prompt path; upstream has not run the 50 GiB
  file). Backlog D11 no longer waits for upstream; still the disk and Karl's order.
- **DeepSeek (next DeepSeek round, Karl 10-27 item 4):** rebase #343 and the slot-RAM cap onto v0.2.7; `--vision off`
  (0.2.7 starts DeepSeek with its vision tower by default, taking its VRAM from the expert cache); keep `--experts 6`
  (0.2.7's 5-of-6 "Faster" default); A/B the new prompt-path defaults with `DS4_DEFAULTS=026` as the one-switch
  baseline (staging ring, chunk rule, attention buffer, pinned copy, huge-page arena, matrix-core attention, drafter cut,
  RAM store spare slots and its pre-fill after a prompt, ...). Note: the RAM store is no longer pre-filled after a prompt
  ("the first words after a long prompt can come slower"), which touches our slot-keep setup. ISTA re-published shard 1
  of every DeepSeek set on 10-26 with a larger chat template; ours is the older one (our server swaps in its own V4.1
  template anyway).
