# STRATA_ADAPT_FETCH beside the helper cache: desk study (2026-11-09; read only, nothing built or run)

This answers backlog I (Karl 11-09), steps 1-2. One fresh helper did the reading; Claude spot-checked the four key claims:
- the off-condition list;
- the clean merge;
- the pick list without a helper filter;
- the T2dv window figures.

Scratch: `work/r23/scratch-adaptfetch/` (merged-*.cpp, agg.py, the diffs). This supersedes `ADAPTFETCH-DESK-1107.md`
(Karl 11-07: "drop it for now").

## 1. Why v0.2.12 turns it off with helper GPUs

The off-conditions are at v0.2.12 `generate.cpp:12773-12784` (serve), `:20452-20461` (CLI) and `expert_source.cpp:4734-4737`.
They are unchanged in v0.2.13. P028x meets every condition except "helper GPUs":
- `STRATA_ADAPT_ASYNC=0`;
- `STRATA_DISJOINT_ADAPT=1`;
- pcie-mode auto;
- adaptive overlap off.

For our setup the helper guard is not a correctness guard:
- the slot tables stay in sync;
- admissions land only in CUDA0's (5080) cache;
- P028x's helper tier is static (filled in `open()`; its only mutator is the off `--remote-expert-opt`);
- the verify read-back reads main-cache slots only.

**The real problem is the pick list.** The share's new pick list, `mq` in the merged expert_source.cpp ~4958-4966, takes
the most-routed misses without leaving out experts the helper holds. Those picks then go to the helper and are never
fetched. Estimated effect: PCIe fetches fall from ~2.37 to ~0.5-1.2 per layer-window, and decode gets slower by about
8-13 %. So **removing the guard alone would make P028x slower.**

**Which cache gets the admission: the main 5080 cache only.**
- The fetched bytes are already on CUDA0.
- Putting them on the helper would need a second copy over the Gen4 x4 link.
- Main-only keeps DISJOINT_ADAPT's no-overlap rule.

## 2. Patch design (on 24c6c2f68 applied to r22-port028x)

**Exact (bookkeeping, or which slot holds an expert):**
- **E1:** `fetch_can` drops `remote_count == 0`.
- **E2:** the serve and CLI off-conditions drop "helper GPUs", but keep `--remote-expert-opt` off. They also add the
  session's async self-choice as an off-condition (see the possible upstream issue below).
- **E3:** `STRATA_ADAPT_FETCH_VERIFY` also in serve. It checks:
  - the admitted slot's bytes;
  - that no helper holds an admitted expert;
  - that each slot is used once;
  - that no pending tier copy targets the victim's slot.

  It runs with `STRATA_ADAPT_CHECKRES=1` and counts admissions per window and thrash. It is slow, so check runs only.
- **E4:** a per-request serve line with the counters.
- **E5 (optional):** moves the victim scan off the plan-publish path. Cost if left as is: about -0.2 to -0.6 %.

**Changes placement (rounding-level):**
- **P1 (required):** the pick list leaves out helper-held and peer-held experts, matching `nmiss`.
- **P2:** with a helper, =2 keeps the tier's own swaps out of a fetched layer only for candidates the share could take.
  With DISJOINT_ADAPT=1 this is identical to upstream.
- **Unset is bitwise identical to P028x by reading:** the `dst2` block is zeroed, and the kernels fall back to staging.
- **VRAM:** ~260 B more, carved after the cache is sized, so the slot count does not change.

## 3. Merge

- `git merge-tree --write-tree --merge-base=24c6c2f68^ r22-port028x 24c6c2f68` gives rc 0, tree df729826, no conflicts:
  9 files, +256/-35, the same as the commit. Re-checked by Claude.
- A plain `git apply` rejects one hunk, the CLI FETCH_VERIFY insertion, whose context is upstream's `mtp_q_applies`. The
  3-way pick places it correctly, so cherry-pick works.
- The fetch code is unchanged through v0.2.13, so the same patch carries over to the port.

## 4. Estimated decode gain on P028x

**Upstream:** +10.2 % (=2) / +5.0 % (=1), on one RTX PRO 5000 with 3,896 slots, `--pcie-frac 0.25` and no helper.
Its gain comes from the warm band of experts that misses and recurs. Its logged hit-rate jump overstates the real cut in
misses, because PCIe entries are left out of that line.

**Ours (measured):**

| Routed entries | Main | Helper | PCIe | CPU |
|---|---|---|---|---|
| Served P028x, 32,797 requests | 62.8 % | 17.4 % | 6.0 % | 13.8 % |
| T2dv | 62.6 % | 17.3 % | 5.7 % | 14.4 % |

- A window takes 23.17 ms, of which the CPU pool takes 9.67 ms.
- Per layer-window: 4.91 distinct CPU experts and 2.37 PCIe.
- Each distinct CPU expert per layer-window costs ~1.8 ms per window.
- The adaptive tier is at its cap of 24 swaps per window in every request, so there is unmet demand.
- The warm band sits on the static helper, so it is never fetched or admitted. Our non-helper miss share is ~20 %,
  against upstream's ~40 %+.

| Case | Cut in non-helper distinct misses | Decode |
|---|---|---|
| Low | 0-3 % | -0.5 % to +1 % |
| **Central** | ~10 % | **about +3 %** (=1: +2-3 %; =2 adds 0-1 %) |
| High | ~25 %, upstream-like | +9-10 % (=2) |

- The estimate hinges on how often non-helper misses recur within ~10 windows. Nothing in our data measures that.
- Short replies after long prompts likely gain more.
- Judge by tok/s and by main hits over all routed entries; the logged hit-rate line rises even without a real change.

## 5. Quality checks: our current ones cannot see it

- **The KL / yardstick band** scores the prompt path, teacher-forced. ADAPT_FETCH acts only in decode; it changes only
  which experts later prompts' CPU share takes.
- **exact7** runs `--adapt-swaps 0`, and the decode-path harness (decpath_rules.py) runs `--pcie-frac 0` with no
  adaptation. ADAPT_FETCH turns itself off in both. Both can still prove the *unset* build is bitwise P028x.
- **What can see it:**
  - a served-mode sampled-distribution test (as D2 did for DeepSeek C2: P vs P+FETCH, with P vs P as the noise bound);
  - upstream's token-forcing check (d486fbe7d + 65909b2d0 + cae562fa0), which conflicts on r22-port028x.

## Risks / open

1. No measurement of how often non-helper misses recur.
2. Quality, see section 5.
3. P1 is required before any test.
4. **Possible upstream issue (static reading, unconfirmed, not posted).** v0.2.12 checks `o.adapt_async` but not the
   session's own switch to the async tier (generate.cpp:13304 / :19303). With STRATA_ADAPT_ASYNC unset, a one-GPU
   serve could race. P028x pins STRATA_ADAPT_ASYNC=0; our patch guards it anyway. Any GitHub post needs Karl's typed OK.
5. Churn: up to ~115 admissions per window; E3's counters show thrash.
