# Basalt head-to-head: plan only (10-30; nothing installed, nothing run)

**Status (Karl 10-30): NO-GO for now - nothing downloaded.** Kept for the catch-up round after the LDR work, or for Qwen4
day one if Basalt supports Qwen4 before Strata does (with basalt-prompt-commits.txt).

**Why:** the PR #90 check put our prompt reading more than 15 % behind Basalt's row: P021m cold 16K -20.1 %, 64K
-10.9 %; the v0.2.8 port -24.5 % / -15.3 % (report.md). Decode is ahead: P021m blend +7.4 %, port +0.9 %. Our 5080 is on
PCIe 5.0 x16, theirs on 4.0 x16, so the link favours us. The difference is therefore Basalt's prompt path, or our
two-card setup, or both. Only a run on this machine separates the two.

## Steps (one gap, about 1.5 h of GPU, after a download)

1. **Model file.**
   - **Recommended: download** `Qwen3.8-FN-GSQ-RCO-IQ3_S.basalt` (~81 GiB). It holds the same GSQ-RCO IQ3_S weights we
     serve. Check its sha256 against the Hugging Face listing, as on 10-20. At 10-20's 25 MB/s that is about 1 h, with
     no GPU needed.
   - **Alternative: convert our GGUF** with Basalt's `tools/convert/convert.py --gguf`. It still needs either a base pack
     (`--sections-from`, i.e. the same download) or the BF16 MTP tensors fetched from Hugging Face (`mtp_fetch.py`). It
     also means running Basalt's code to write an 81 GiB file. The only gain is a byte check against our GGUF; not
     worth it.
2. **Disk.**
   - 264 GB free today. After the pack plus a build (~3 GB), about 175 GB remain.
   - Basalt also extracts pack sections into `BASALT_CACHE`; we point that into its own folder, as on 10-21.
   - Check free space right before extraction. Stop at less than 110 GB free, so the 100 GB floor is never crossed.
3. **Build** (as `basalt-ab/scripts/build.sh` on 10-21):
   - CUDA 13.3 (Basalt needs CUDA 13; installed) and arch 120 only.
   - cmake + ninja inside `unshare -rn` (no network), with HOME and BASALT_CACHE inside its folder.
   - ≤ 16 jobs under our build memory guard, inside a gap, with nothing timed running.
4. **Cards.** Basalt runs on Blackwell only, so the 5080 alone. We run three arms, all with the same `bp90_client.py`,
   the same fixtures and Basalt's community-1 settings:
   - Basalt on the 5080;
   - P021m as served (5080 + 4060 Ti);
   - P021m on the 5080 alone (no `--expert-cache-device1`, `CUDA_VISIBLE_DEVICES` = the 5080). This arm shows how much
     of the prompt gap is the second card's split and how much is engine code.

   Each arm runs cold 3 passes plus warm, and on 127.0.0.1 only.
5. **Commits to read** (`basalt-prompt-commits.txt`: 41 prompt-path commits since fb0944c7, our v2 port base). The
   FP4-only ones are skipped (we serve IQ3_S). Candidates for IQ3_S:
   - `e8f3b84b`: a long prompt starts with a short first chunk;
   - `c8dc0f4e`: a first stage keeps its last chunk;
   - `31aacda2`: a short chunk prefetches the next layer's likely experts during attention;
   - `e9bea488`: a deeper expert ring for long streamed chunks;
   - `10f338cc`: the hc up product and the mix in one kernel;
   - the peer-tier series `6f354bae`, `27a4e058`, `97184350`, `8ae0d95b`, `45585161`, `652b9515`: a long prompt read
     across the main card and the tier card.
6. **Afterwards.**
   - Delete the pack and build only with your OK, as on 10-23.
   - Nothing is posted.

## What could come back to us

- **Only exact pieces.** Basalt's defaults fail our lossless rule (the two-stage Q6_K head is lossy where its cap binds;
  10-21).
- **A scheduling or overlap change** (chunk order, prefetch, a second card's share) can keep our output bit for bit:
  - it must pass exact7 and logits that are byte-identical against today's build;
  - otherwise the full KL rule (mean, p90, KL>1, top-1, NLL) and the distribution checks.
- **A kernel change** (`10f338cc`) needs the same tests as PREFILL_V2 did.

## Your call

- Go or no-go for the download (~81 GiB, ~1 h) and one gap (~1.5 h).
- Whether to include the 5080-alone arm for P021m. I recommend it: without it, the comparison mixes engine code with the
  two-card setup.

## Catch-up list (Karl 11-02, after the Basalt 0.2.0 settings test - basalt-020/REPORT.md)

- **Port Basalt's prompt path, exact parts only** (the scheduling / overlap pieces and kernels in
  basalt-prompt-commits.txt, plus what 0.2.0 added since b2fe96bf30), **after gap 17** shows how much v0.2.9's GDN
  paths (GDN_TC / GDN_CONVL2) recover on the 16K / 64K cold prompts. **Size the port against the gap that is left**:
  11-02 Basalt 0.2.0 defaults on the 5080 alone vs P028x (gap 16): 16K 5,064 (five of six runs ~5,350) vs 3,827, 64K
  5,440 vs 4,383; 9-workload screen prompt +15.3 %, decode +2.8 % (noise).
- Exact parts only: each piece passes exact7 + byte-identical logits, or the full KL rule and the distribution checks.
- **No further Basalt work for now** (Karl 11-02): no quality gate, no switch.
- **Keep the pack and build until Qwen4 lands** (basalt-020/models: 87.6 GB; basalt-020/src/bin).
- **Basalt follow-up decision (Karl 11-03): no local Basalt branch for now** - the +13 % rests on the helper carry-over,
  and the BF16 hyper-connection path is new kernel work for a Flash-Next-only engine. The real finding is single-card:
  on the 5080 alone Basalt with the exact head decodes 156.7 vs P028x's 134.5, still ~149 with the estimated BF16 hc
  cost (~+11 % lossless).
- **Single-card decode study (Karl 11-03), next to the prompt-path port:** what makes Basalt's single-card decode faster,
  limited to exact changes portable into Strata (kernels, MoE tail planning, adaptive tier policy, ...), with gain and
  effort each: basalt-020/SINGLE-CARD-STUDY.md (read-only; being written). **No code work until item 7 and gap 17 are
  done.**
  - **The study is written (11-03; basalt-020/SINGLE-CARD-STUDY.md, read-only, no gain measured on P028x yet):** same
    tokens / drafts per window, but 21.4 ms per window (Basalt) vs 25.7 ms (P028x solo). Split: ~1.2-1.5 ms exact
    engine work (PDL everywhere, ~800 vs ~2,000 graph nodes, the GPU plans the MoE step, L2 prefetch + GDN commit during
    the CPU's turn, the draft chain as one conditional graph); ~0.7-1.0 ms Basalt's lossy int8 hc copy (it also buys its
    ~4 % extra slots: lossless Basalt ~147, not 149); ~2 ms window shape (its adaptive tier + newer starting profile:
    14 % fewer misses per window; 53 swaps a window vs our <= ~24). CPU tier: our one-token groups go to ggml's AVX2 dot;
    Basalt's AVX-512 rows with gathers, one pool batch a layer. Ranked: (1) bitwise switches already in our tree -
    STRATA_DF_PDL=1, STRATA_IQ_GATHER=1 (never tried on Zen 5; Zen 4 -3-5 %), STRATA_GRAPH_PRIO=1, STRATA_FUSE_WAIT=2:
    ~+2-6 %; (2) rounding-level settings - a faster adaptive tier, Basalt's starting profile, --spec 8, IQ_MT_MIN=1:
    ~+2-6 %; (3) small code (L2 prefetch, unpinned pool workers) ~+1-4 %; (4) medium bitwise code (one pool batch, GPU
    MoE planning, conditional-graph drafts) ~+3-7 %; (5) large (GDN persistent kernel, BF16 hc). Next step it proposes: a
    solo-arm gap with STRATA_DECODE_TIMING=1 (+ once STRATA_VERIFY_PROFILE=1) to measure the waits - Karl's call.
