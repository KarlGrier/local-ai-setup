# Strata v0.2.10 port review (gap 17, retargeted from v0.2.9) - read-only, 2026-11-02

Scope: what v0.2.8 -> v0.2.10 changes on OUR path (Qwen3.8-Flash-Next IQ3_S, native pack, CUDA, RTX 5080 sm_120 = CUDA0,
RTX 4060 Ti sm_89 = `--expert-cache-device1 3300` helper, `strata --serve` via serve/server.py, configs/P028x.json), and how
our 28-patch series (r22-port028x @ 8f7a48aab) lands on it. Nothing built, run, fetched or changed; git read-only.

- Upstream: `strata/` tags v0.2.8 = 870aedd9e (10-29), v0.2.9 = c62d5e3a1 (10-31), v0.2.10 = ffa80d731 (11-02, engines 0.1.56,
  CUDA engines built from 06698c674). 877 commits v0.2.8..v0.2.10 (169 to v0.2.9, 708 after). 967 files, +99k lines.
- File:line refs are `v0.2.10:` unless marked. Scratch (logs, extracted files, trial-apply tree, rejects):
  `results/r22/port0210-scratch/` (see section 7).

---

## 0. Bottom line and the pin block

1. **Our STRATA_DEFAULTS=026 pin does NOT cover most of the new 0.2.9/0.2.10 defaults.** It still gates the BW-DENSE pair
   (GR_V3_PF, SMALL_UNR) and the small-card prompt path. It does **not** gate the lookup-12 default, the server's GDN stack,
   the PCIe start share, PDL, QSA_FUSE_NR, IL_PAD, GR_R2, the arena RAM fallback, the MTP drop, the penalty window, or the
   server's new `fit_start` / drafting rewrite. Each needs its own pin (below).
2. **Lookup windows up to 12 ARE on for P028x as configured.** The helper card does not count as "multi GPU"
   (section 1.2). Our exact sampling handles them correctly: lookup rows are point masses, so the distribution is preserved.
   It is still a new default with new graph sizes (VRAM) and a new prompt-window grouping, so pin it off until it is gated.
3. **GDN_TC + GDN_CONVL2 are switched on by serve/server.py, not by the engine.** On the port they arrive with upstream's
   server.py. KL-class change (upstream: KL mean 0.0019, max 0.0125), not bitwise.
4. **Rebase:** 15 of 28 patches apply as-is (offsets and fuzz only). 13 have rejected hunks: 6 mechanical (context only), 7
   semantic. The semantic ones are SPEC_EXACT, COST_GATE x2, DRAFT_CUM, the continuation fix, the fork scratch and the
   think-fence. Most of them come from upstream moving the serve/CLI window-size logic into `spec/window_rule.hpp`
   (`choose_window`), plus `draft_long`, `req_df2` and `exit_if_gpu_fatal` (section 5).

**Pins to add to the ported config's `env`** (all are no-ops on the v0.2.8 engine. "=" is the exact off value the code reads):

| variable | value | what it keeps as in v0.2.8 |
|---|---|---|
| `STRATA_LOOKUP_MAX_T` | `0` | lookup windows stay at the --spec+2 rule (8). Equivalent: `--lookup-max-t 0` in args (the flag wins over the env) |
| `STRATA_GDN_TC` | `0` | server.py's GDN stack (setdefault, so the config's value wins) |
| `STRATA_GDN_CONVL2` | `0` | same |
| `STRATA_GR_V3_PF` | `0` | already 0 under DEFAULTS=026. Explicit pin for clarity |
| `STRATA_GR_R2` | `0` | v3 HC read's exact-T 5..8 kernels (default 2, not 026-gated). Matters only if the fork guard turns GR_FORK off |
| `STRATA_SMALL_UNR` | `0` | already 0 under 026. Explicit |
| `STRATA_QSA_FUSE_NR` | `0` | prompt QSA norm+rope fusion, default on, CUDA too |
| `STRATA_IL_PAD` | `0` | IQ4_XS 5-col interleaved MMVQ as 6 cols (default 1). Type 23 is in our MMVQ_IL_ROWS |
| `STRATA_DF_PDL` | `0` | PDL on the all-resident verify graph on sm_120 (new default) |
| `STRATA_PCIE_START` | `old` | PcieAuto start share from the link only (0.55), not the new pool-size formula |
| `STRATA_ARENA_RAM_FALLBACK` | `0` | the arena loaded the old way when RAM is short (no silent switch to the file / RAM-copy source) |
| `STRATA_MTP_KEEP` | `1` | the draft layer is never dropped at start for "short of VRAM" |
| `STRATA_SPILL_OFF` | `1` | belt and braces: the spill paths are already off because `--vram-reserve-mib` is given |
| `STRATA_PENALTY_PROMPT` | `1` | the penalty window counts prompt + answer as before (matters only if a client sends penalties) |

**Config keys to add** (server-side behaviour new in v0.2.10's server.py):
- `"drafting": "mtp"`. Today `drafting.apply` leaves us alone only because our `model_name` ("strata-qwen3.8-flash-next-iq3s")
  fails `_SUPPORTED_NAME` (strata_control/drafting.py:251). Auto now means DFlash2 wherever the engine has it.
- `"user_args": ["--kv-resident", "32768"]`. Without it, server.py:3525 `vram_fit.fit_start` may lower `--kv-resident`.
  It prices the card at NVML index 0 (gpu_list is empty, so `[0]`; server.py:3462-3471), and `args` values count as not
  set by the person (strata_control/vram_fit.py:279-326). Check that the start log has no "short of GPU memory" line.
  An alternative is to drop the call in our server patch.
- Already safe, nothing to add: the on-demand picture reader skips configs with `--expert-cache-device1`
  (server.py:9367). The parallel stack needs `--batch`. The all-cards split engine needs an exe named `strata-split-*`.

---

## 1. Karl's gate list

### 1.1 v0.2.9's GDN prompt paths: GDN_TC, GDN_CONVL2 (status in v0.2.10)

- **Engine defaults: off.** `STRATA_GDN_TC` is unset = off (src/prefill/kernels.cu:3040). `STRATA_GDN_CONVL2` is unset = 0
  (kernels.cu:2904). Mode 2 is the single-pass conv+SiLU+L2 (`gdn_conv_w_kernel`), mode 1 the older fused conv+L2, 0 the
  tiled conv + separate L2.
- **Server default: on.** serve/server.py:4022-4054 (`GDN_STACK_CUDA = {"STRATA_GDN_TC": "1", "STRATA_GDN_CONVL2": "2"}`,
  `gdn_stack_env`, called from `child_env` at :4071). It applies on Linux CUDA when `cfg["arch"]` is unset or `qwen4exp`
  (P028x has no `arch`, so it applies). It uses `env.setdefault`, so a value in the config's `env` wins.
  Upstream's evidence (comment at :4022): KL mean 0.0019 / max 0.0125, 61-task suite 55 vs 54, prompt +4.4% at 4K,
  +5.5% at 16K, +5.7% at 32K (l620). This is **KL-class, not bitwise**.
  Commits: bee469c46 (server stack), 06f212aef / dc149ef00 (TC opt-in, the 99-KB-card split plan), 0ea3e455f / d3af2d42a
  (CONVL2=2), 51567de1a / 714438ec1 (`STRATA_GDN_TC_TILES`), ee0511484 / 1a865fb3d (`STRATA_GDN_TC_FUSE`, the fused output
  norm, default on inside TC only). All are in v0.2.9.
- **On the RTX 5080:** the TC path is runtime-gated (kernels.cu:3040-3100). On a 99-KB card (sm_86/89/120) the full plan fails
  and the split single-buffered plan (`kGdnTcSplit`) runs. `STRATA_GDN_TC_TILES` gives 2 tiles a head only on cards with
  >= 96 SMs. The 5080 has 84 SMs, so 1 tile, and with 1 tile TC_FUSE writes y16 directly. Minimum chunk 128 tokens
  (`kGdnTcMin`).
- **Changes v0.2.9 -> v0.2.10: none to GDN_TC / CONVL2.** `git log v0.2.9..v0.2.10 -- src/prefill/kernels.cu` holds only the QSA
  norm+rope fusion (14a85eca9, 66545a497). gdn_tc.cuh did not change, and server.py's GDN block did not change.
- **Pin:** `STRATA_GDN_TC=0`, `STRATA_GDN_CONVL2=0` in the config env. Gating them later is item 7's job (KL rule plus
  16K/64K cold prompts).

### 1.2 Prompt-lookup windows up to 12 (`--lookup-max-t`, #4040)

**Commits:** 03627326d (10-31, the opt-in port of PR 4040 by merbanan), cc703b5e4 (11-01, default 12, owner decision),
285fa48b9 / fea8a3e63 / 909ab78af (the rule moved into a header, Metal kept off), e20842779 (`--lookup-long-match` reverted),
2fb096b93 (gate check), 4c5a55491 (`--draft auto` MTP requests keep the MTP width).

**When it is on.** src/program/generate.cpp:4139-4154 calls `strata::core::default_lookup_max_t`
(include/strata/core/lookup_default.hpp, all of it). The flag defaults to -1 ("not given", generate.cpp:977). The default
is 12 only if ALL of these hold:
- `STRATA_LOOKUP_MAX_T` does not start with '0';
- `kVerifyMaxT == kVerifyNarrowT` (the 8-row CUDA build; CMake `STRATA_WINDOW_MAX_T=auto` gives 8 on CUDA,
  CMakeLists.txt:108-122);
- not Metal;
- `--serve`;
- `!multi_gpu`;
- no `--layer-split`;
- `--batch` <= 1;
- `--draft` != dflash2;
- no `--lookup-chain`;
- `--suffix-draft` > 0 (default 3);
- `--spec` >= 2.

**Does the helper count as one GPU? Yes.** `multi_gpu = !split_devs.empty() && !split_same` (generate.cpp:3956), and
`split_devs` comes only from `--layer-split` / `--split-device`. `--expert-cache-device1` and two cards in
CUDA_VISIBLE_DEVICES do not set it. So **P028x gets lookup windows up to 12 on v0.2.10.**

**What the windows become for us** (--spec 7):
- The suffix rule gives `mtp_max_t` = 7 and spec = 8 (generate.cpp:4134-4137). The lookup rule then gives spec = 12
  (:4156-4159). `spec_cap` = kVerifyLongT = 16 (:4171).
- The MTP keeps windows of <= 8 rows (S_mtp 7). The MTP drafter keeps `min(spec, 8)` rows; `MtpDrafter::draft_long` catches
  it up after a long window (src/core/mtp.cpp, 03627326d).
- Allowed lookup sizes come from `lookup_size_mask` (generate.cpp:1303): 1..7, 8, 9, 12. **Sizes 9 and 12 are new CUDA
  graphs**, about 20-35 MiB each by DETAILS.md:1086, captured lazily by `graph_fits` / `Verifier::prepare`. A size that finds
  no VRAM is dropped (generate.cpp:13417-13440).
- A window past 8 rows runs as two token groups of <= 8 (src/core/verify.cpp:1354, `G = 2`; the --spec-split layout, which
  is exact). The head runs in column chunks of kFusedGrMaxT (verify.cpp:2535). A layer split refuses it (verify.cpp:3257).
- **The prompt path changes too.** `read_windows` (prompt tokens read through verify windows) now uses up to 12-row windows
  of the allowed sizes (generate.cpp:16236-16243). Short prompts and follow-ups get another grouping.

**Interaction with STRATA_SPEC_EXACT (ours, 06f3a67fc): it stays exact.**
- A lookup window is verified through our exact path. `set_spec_window(on, from_sfx ? nullptr : qlists, from_sfx ? 0 : T-1)`
  means every lookup row is a point mass q = 1 at the draft.
- `sample_tokens_spec` then accepts x with probability min(1, p(x)/1) = p(x) (acceptance stream, counter pos0+t). On reject
  it draws from normalize(p - delta_x). This equals sample-and-match's law, whatever the window length.
- Sizes are fine. `sample_tokens_spec` takes up to `kSplitMaxRows` = 64 rows (src/kernels/cuda/sampler.cu:645) and sizes its
  scratch to max(T, 16). Our call in `Verifier::run` has no `T <= kVerifyMaxT` limit (upstream's SPEC_PROB branch has one,
  verify.cpp:3598). `m_tok_` / `m_out_` are allocated at `max_t` = 12. Our q lists are only read for MTP windows (<= 7 drafts).
- **Distribution check of the decisions.** The lookup-vs-MTP choice is `policy.choose(T, k, match)` with T from the raw
  probabilities. Its gate is `sbuf[0] == ess_top(0)`, the raw argmax. `graph_fits` drops a size only on VRAM. All of these
  are decided before the window's draws, so the window is still distribution-preserving. The policy's learned costs depend
  only on committed history.
- Upstream without our switch uses sample-and-match: exact per seed. Greedy keeps the output if the 2-group layout is
  bitwise per row, which upstream claims ("bitwise by the author's checks", "Same answers on file rewrites").

**STRATA_DRAFT_CUM (ours):**
- It only sizes MTP windows. Lookup windows are not observed (`!from_sfx` guard in our hunk), so long lookups do not skew
  the threshold.
- Its arrays (`cpr[kVerifyMaxT]` in mtp.cpp) only see MTP steps (<= 7).
- On rebase, our `set_draft_cum` stays before the draft call, which is now `draft_long` (generate.cpp:18587). draft_long ->
  draft() uses the member state.

**COST_GATE (ours):** it prices MTP chain steps only (mtp.cpp `more` lambda). It is not involved in lookup windows. Its table
and theta were fitted on <= 8-row windows, so nothing changes for it.

**Existing lookup/suffix drafts:**
- The suffix drafter (`--suffix-draft` 3) is still the source. Proposals now run up to `S_look - 1` = 11 tokens (S_look = S
  for us; the `S_mtp_narrow` cap at generate.cpp:15233 is inside the `--draft auto` bandit block).
- `DraftPolicy::kMaxT` is now 16 (include/strata/spec/draft_policy.hpp:31). Sizes 9-16 are priced by an extrapolated
  `kShape` of +0.4 a token (src/spec/draft_policy.cpp:14) until measured.
- `--lookup-chain` stays off. `--lookup-long-match` was reverted (e20842779).

**Measured (upstream, DETAILS.md:1086):** file rewrites and agent edit turns +11..14% decode (A6000 IQ3_S), prose and code
within 1% at 12.

**Pin:** `STRATA_LOOKUP_MAX_T=0`, or `--lookup-max-t 0` in args. Both read as 0, so the old `--spec+2` rule applies. Note the
env is read only when the flag is absent, and any value starting with '0' counts as off.

**To gate later:**
- exact7 / byte-identical with the window on vs off (greedy, plus the prompt-window regrouping);
- chi-square of SPEC_EXACT on 9- and 12-row lookup windows (point masses, so it should pass trivially);
- VRAM: the two new graphs against our 713 MiB reserve;
- W1-W3 / edit turns.

### 1.3 STRATA_GR_V3_PF=133 (sm_120 default; register-blocked down kernel)

**Commits** (all v0.2.10): 9abe0d6c4 (the variants, default 0), 3ce5193eb / 08b20b104 (default 5 on cc 12.0, BW-DENSE),
686c0d42c (up RB, bit 6), 4ab81c796 (down RB, bits 7/8), 5f24b96db (5 -> 133; serve A/B spec 6 +1.21%, spec 8 +1.4%,
ids identical 96/96), 27a3e056a (merge), ddd88c9f8 then 4deb89ef7 (bit 9 "another summation order" added, then
reverted), 6467ec76a (spill table).

**What it changes:**
- The mask is read at src/kernels/cuda/fused_gr.cu:2669-2692 (`v3_pf_mask`; an explicit env wins).
- 133 = bit 0 (gr_down: staging loads of all tokens in flight together) + bit 2 (gr_up: partial sums / row inputs loaded
  before use) + bit 7 (gr_down for windows of 5+ rows: 2 rows a warp, register-blocked dot phase, activations read once).
- The dispatch is at fused_gr.cu:2901-2908 (`pfm & 128 && n_tok >= 5` -> `gr_down_rb_dispatch_k<2>`).
- Only the load order and thread mapping change; "same dots, same order".
- `gr_v3_screen` (src/kernels/gr_v3_screen.cpp) checks every output bitwise for T 1-8 ("0 differing").
- So it is bitwise **vs the plain v3 kernels**. It is not comparable to the default (non-v3) read or to the fork. v3 is
  "another summation order" by its own comment.

**Relation to GR_FORK and GR_V3 (our env sets both = 1):**
- `fused_gr_read_multi_slice` runs the q8 branch, then **our fork (if STRATA_GR_FORK=1)**, then the v3 read. In the trial
  rebase our fork branch lands at fused_gr.cu:3111, before v3 at :3122, as on v0.2.8.
- So with GR_FORK on, the v3 kernels and GR_V3_PF are never reached in the verify window's HC read.
- They matter only if the gr_fork patch guard sets STRATA_GR_FORK=0 (a model mismatch). Then GR_V3=1 runs v3 with the new
  defaults.
- The default is already 0 for us, because `gr_v3_pf_default` = `sm120_default && !qwen_defaults_026() ? 133 : 0`
  (include/strata/core/bw_dense_defaults.hpp:16).
- A sibling in v0.2.9 is **not** 026-gated: `STRATA_GR_R2` (default 2, fused_gr.cu:1594; 21f950b4b), the v3 exact-T 5..8
  kernels. `GR_R2=0` reproduces v0.2.8's v3 dispatch exactly (n_tok 7/8 fall to `<1,kFusedGrMaxT,false>`).

**On the 4060 Ti (sm_89): no.**
- `v3_pf_mask` is per device, and `sm120_default` requires cc 12.0.
- `gr_v3_default_on` needs 12.0 and more than 13 GiB.
- The helper only runs routed-expert work for the experts it holds. HC reads run on CUDA0.

**Pin:** `STRATA_GR_V3_PF=0` (explicit; 026 already gives 0) and `STRATA_GR_R2=0`.

### 1.4 STRATA_PF_GROUP_SCRATCH / STRATA_PF_HC_REGION

- **Defaults: both off (opt-in).** src/prefill/prefill.cpp:1526-1541 and :1562-1565 (`v != nullptr && atoi(v) != 0`).
  Commits fbf6e1c75 and 3cc47f029 (10-31), DETAILS row 5206a299f.
- **GROUP_SCRATCH:**
  - The MMQ path's GU / H / Hq (gate/up output, SwiGLU, q8_1 copy) hold one expert group's rows instead of the chunk's
    (`moe_bufs`, prefill.cpp:1584-1589). Group cap from `group_cap_rows` (:1544).
  - It is ignored, with one start line, unless every layer takes MMQ (no FP16 / pf_wmma path, no `STRATA_MMQ_DIRECT`).
  - **It never applies to a fused layout** (`if (!fused && pf_group_scratch())`). With `STRATA_PF_FUSED=1` our streamed
    chunks run the fused int8 experts, so it is inert there. Only a last chunk below `stream_all_min()` would be MMQ.
- **HC_REGION:**
  - The prompt HC read's scratch (xn16, lo, lo16, gated, the BF16x2 lows) moves into the attention/MoE shared region as a
    fourth set (prefill.cpp:1557-1565; used at :1929 and :2781).
  - It applies to any layout except `gr_unfused()`, our fused one included. "The same kernels on the same values: the same
    bits."
- **PREFILL_V2 (ours):** v2 sits in the fused path's MoE set. Its 64-byte item counters are added by `group_bytes` only when
  v2 is requested. GROUP_SCRATCH does not touch it. HC_REGION shares a region with the MoE half, after the half's HC read
  is done. A v2 parity run would be needed with HC_REGION=1 if it is ever enabled.
- **Gain for us: probably none.** The gain is a bigger `--prefill auto` chunk from 0.3-0.5 GiB of freed borrowed slots, and
  upstream measured it "only with STRATA_PREFILL_CPU_SHARE=0". We run share 0.4, MAX 1792, a fused layout, and `auto:16384`.
- No pin needed (opt-in).

### 1.5 DFlash2's Q4_0 selector (174 MiB less)

- **What it is:** the DFlash2 drafter's two selector codebooks stored as Q4_0 rows instead of bf16. It is nazeshinjite's
  idea: the community GGUF, Apache-2.0.
  - Commits 8ec2c8a91 (`--q4_0-selector`, dequantized in the select kernel), f4561cbe0, ebac5686f (the pack is converted
    locally from the checked Q4_0 pack), d4c8ca1f6 (VRAM figures), 45c71cf9c.
  - The engine prints "selector codebooks: Q4_0 rows (about 174 MiB less than bf16)" (src/core/dflash2.cpp:400).
  - Upstream: "draft ms, acceptance and the committed text equal" (strata_control/drafting.py:205-213).
- **VRAM:**
  - `DRAFTER_MIB` (drafting.py:48): dflash2 890 MiB, dflash2_selq4 715 MiB, mtp 1082 MiB.
  - The engine's own drafter line goes from 800 to 625 MiB. 174 MiB is about 88 expert slots.
  - **Against our MTP drafter on the 16 GB 5080:** 1082 - 715 = about 367 MiB, about 188 slots at 1.95 MiB/slot, about +4% on
    our ~4,585 slots. Of that, 174 MiB comes from the new selector; the rest is DFlash2 vs MTP as before.
- **Why it does not drop in for us:**
  - `--draft dflash2` loads no MTP layer (5a048c6c0), so the MTP-only parts are gone: SPEC_EXACT, DRAFT_CUM, the cost gate.
  - The lookup-12 default is off with DFlash2.
  - It needs the DFlash2 pack (not on disk).
  - Upstream's own speed claim is on RTX PRO 5000 (+7.8% short / +1.1% long thinking). It is "slower" on sm_86, and sm_120
    16 GB is unmeasured.
- A note for later, no action. `"drafting": "mtp"` keeps Auto from ever choosing it (section 0).

---

## 2. Every other new default reachable on our path (engine), with its off switch

Method:
- Diffed the set of `"STRATA_*"` names in src/include/serve: 738 at v0.2.8, 760 at v0.2.9, 851 at v0.2.10. 113 are new;
  every non-DeepSeek/DF2 read site was read (scratch `env-new-sites.txt`).
- Also checked every `sm120_default()` / `qwen_defaults_026()` site and the "default" commit subjects (scratch
  `log-defaults.txt`).
- "026?" means whether STRATA_DEFAULTS=026 already turns it off.

| switch (commit, release) | what changes on our path | default | 026? | bitwise claim | pin |
|---|---|---|---|---|---|
| `--lookup-max-t` / `STRATA_LOOKUP_MAX_T` (cc703b5e4, .10) | section 1.2 | 12 | no | per row (2-group layout) | `STRATA_LOOKUP_MAX_T=0` |
| `STRATA_GDN_TC`, `STRATA_GDN_CONVL2` (bee469c46, .9) | set by server.py | 1 / 2 (server) | no | KL 0.0019 | `=0` / `=0` |
| `STRATA_GR_V3_PF` (5f24b96db, .10) | v3 HC read (bypassed by fork) | 133 on cc 12.0 | **yes** (0) | yes vs v3 | `=0` |
| `STRATA_SMALL_UNR` (08b20b104, .10) | bf16 router read, GDN a/b projection constant-trip loads (native_bf16.cu:343, verify_kernels.cu:1187) | 3 on cc 12.0 | **yes** (0) | yes (hashes) | `=0` |
| `STRATA_GR_R2` (21f950b4b, .9) | v3 down 5..8-token exact-T kernels (fused_gr.cu:1594) | 2 | no | yes vs v3 | `=0` |
| `STRATA_QSA_FUSE_NR` (14a85eca9 + fix 66545a497, .10) | prompt QSA K/query/indexer-query rms+rope in one pass (prefill.cpp:563, used :4158, :4224, :7416) | on (CUDA and HIP) | no | "same bits". A rounding fix followed, and its parity test is HIP-only ("not run on a GPU yet" at commit) | `=0` |
| `STRATA_IL_PAD` (4c5a55491, .10) | IQ4_XS 5-column interleaved MMVQ runs as 6 (native_mmvq.cu:2247). Type 23 is in our `STRATA_MMVQ_IL_ROWS` | 1 | no | yes | `=0` |
| `STRATA_DF_PDL` (081d1c04d, .10) | programmatic dependent launch on the all-resident verify graph on cc 12.0 (verify_kernels.cu:1770-1789, verify.cpp:1390). Our partly resident cache mostly runs the doorbell graph, which keeps plain launches | on (sm_120) | no | yes (bit-identical) | `=0` (verify.cpp:1390 then still asks, and pdl_supported() answers no) |
| `STRATA_PCIE_START` (06ebf2e4d, .10) | PcieAuto start share from pool workers (min(65, 4 GB/s x workers)) instead of 0.55 (generate.cpp:12142-12160). On HIP upstream kept the old start because it "flips near-tie tokens in the first ~50 windows" | new (CUDA) | no | **no** (changes which experts the CPU computes early) | `=old` |
| `STRATA_ARENA_RAM_FALLBACK` / `STRATA_ARENA_FALLBACK_RESIDENT` (067b74338, 43543e9b0, .10; #4846) | when RAM is short at the arena, the run silently switches to the mmap file source plus a RAM copy of the hottest experts (generate.cpp:7066-7110) | on | no | experts same bytes; speed and RAM change | `STRATA_ARENA_RAM_FALLBACK=0` |
| `--ram-keep-gib` / `STRATA_RAM_KEEP_GIB` (b537586e6, .10) | RAM to leave free for the arena decision | 0 (no change) | - | - | none |
| `STRATA_MTP_KEEP` (ecf7424b5, .10) | at start the MTP layer is dropped if free VRAM < layer + head + 1.77 GiB (generate.cpp:6721-6742). Will not fire on an empty 5080, but it is silent | drop allowed | no | n/a | `=1` |
| `STRATA_SPILL_OFF`, `STRATA_HEAD_HOST_OFF` (2e7db84bc, ecf7424b5, .10) | short-of-VRAM loan to 16 slots, priced spill, head to pinned host (generate.cpp:7604, 7651, 7680) | on | no | n/a | already off for us (`!o.vram_reserve_given`). `STRATA_SPILL_OFF=1` optional |
| `STRATA_PENALTY_PROMPT` (618cd7a4b, then 31c3a16f4, .10; #4590) | the penalty window counts only the reply's tokens (include/strata/kernels/sampler.hpp:99, generate.cpp:17187). Only with penalties (our sampling block sets none; check clients) | reply only | no | n/a (semantics) | `=1` |
| `STRATA_KV_RESIDENT_MIN` (2e7db84bc, .10) | floor of `--kv-resident` 20480 -> 4096 (src/core/layer.cpp:776) | 4096 | - | - | none (we use 32768) |
| `STRATA_PREFILL_LAYER_MAJOR` (3eb55adff, .10) | default now OFF everywhere (include/strata/core/sm120_series.hpp diff) | off | - | - | keep our `=0` |
| small-card prompt path / `STRATA_PF_SMALL` (fd59c9c39, .10) | one card, native pack, default chunk < 8192: unfused experts + layer-major (generate.cpp:10279; sm120_series.hpp `small_card_prompt_path`) | on | **yes**. Also off because we set STRATA_PF_FUSED and STRATA_PREFILL_LAYER_MAJOR | KL | none needed |
| `STRATA_PLE_BATCH` (78316c8df, .10) | default off only for a CUDA 12.8 build on cc 12.0 | on (we build CUDA 13.3) | - | - | none |
| `STRATA_PREFILL_CPU_SHARE_MAX` (c4082ce8c / de8308005, .10) | default limit 1024 -> 3072 | 3072 | - | - | none: our explicit 1792 wins (prefill.cpp:291-302) |
| `STRATA_MTP_MULTI_COPY`, `STRATA_OLD_Q80_SCALED`, `STRATA_ARGMAX_ROWS` (1f8ca8de1, .10) | the RDNA4 PR. On CUDA the defaults are what CUDA already ran (multi-copy, warp-a-block quantize); only HIP changed. The copy kernel grid changed (data move only) | CUDA unchanged | - | - | none |
| `STRATA_GDN_TC_FUSE` (ee0511484, .9) | only inside GDN_TC | on | - | - | covered by GDN_TC=0 |
| `STRATA_AUTO_NOBORROW` (cda6463e8, .10) | no slot loan only when every expert is resident | n/a for us | - | KL 0.006 | none |
| FP16 weight cache `STRATA_PF_W16_CACHE_MIB` (d8c94b45c, 88a79a7ef) | back OFF by default in .10 (not bit-exact on sm_120) | off | - | - | none |
| `STRATA_SERVE_STOP_BOUND` (243fdb213, .10; #4677) | HIP-only code (`#if STRATA_USE_HIP`, generate.cpp:17403-17410, 18490-18497) | not compiled on CUDA | - | - | none. See 5.2 (overlaps our #652 half) |

Opt-in only, no pin needed:
- `STRATA_PREFILL_ROUTED_STREAM` (5273fb667);
- `STRATA_MTP_ROOM_MIN` (606f6272d);
- `STRATA_PW_WITH_BATCH`;
- `STRATA_PF_GROUP_SCRATCH`, `STRATA_PF_HC_REGION`;
- `STRATA_COALESCE_*` and `STRATA_PAR_COUNTERS` (server, batch);
- `STRATA_BATCH_CONCURRENT_READ`;
- `STRATA_PREFILL_CPU_SHARE_BATCH`;
- `STRATA_MMVF_CHECK`;
- `STRATA_CRASH_BT`, `STRATA_STALL_STACKS`, `STRATA_INJECT_FATAL*`, `STRATA_DRAFT_LOG`, `STRATA_DISPATCH_*`.

Not reachable on our path:
- HIP / gfx12 only: `STRATA_PA_TRIM` / `STRATA_PA_RPF` (the `prompt_attn_wmma_kernel` is built only for gfx11/gfx12,
  qsa_prompt_attn.cu:1896-1905), `STRATA_QSA_FUSE_GATE` (HIP only, qsa_prompt_attn.hpp:32-35), `STRATA_GDN_W12_LB`,
  `STRATA_GDN_FUSE`, `STRATA_PF_Q8D_F16`, `STRATA_PF_FUSED_IQ2S`, `STRATA_GR_Q32_*`, `STRATA_GR_Q8_PFS`,
  `STRATA_SELECT_ALT_MIN_TOKENS`, `STRATA_LM_HIP`, `STRATA_AMD_COMMUNITY_TUNING`.
- Windows only: `STRATA_KEEP_IO_PRIORITY`, `STRATA_PF_OWN_CHECK`, `STRATA_PREFILL_BORROW`.
- `STRATA_COMMIT_GROWTH` (DeepSeek).
- All `STRATA_DS4_*`, `STRATA_DF2_*` / `STRATA_BATCH_DF2*`, the SYCL / Metal ones, and `FNX_*` (split engine).

New engine flags (args parse): `--lookup-max-t`, `--lookup-sizes`, `--ram-keep-gib`, `--draft-fallback`, `--draft-rule`,
`--draft-mtp-spec`, `--draft-mtp-min-p`. None removed. Every flag in P028x.json still parses.

Behaviour changes without a switch, on our path:
- After a sticky fatal CUDA error the engine prints `ERR fatal GPU error` and **exits**, and the server restarts it.
  A third death in 10 min stops the restarts (e1b27d54b; `exit_if_gpu_fatal`). Parked chat-cache conversations die with it.
- The server drops a trailing DONE after a NaN-stop ERR (9aea047ee).
- The server sends a new GEN key `pen_from` for continued legs (62e861c99). The engine parser must take it beside our
  `owner=` / `chat_drop=` / continuation keys.
- None of the decode kernel commits for CUDA changes arithmetic without a switch: dispatch counters (af6ba4c60), the copy
  grid, and the head column chunks. These are the only ones found; the exactness gate is the backstop.

Server-side defaults (serve/server.py, strata_control), new since v0.2.8:

| what | where | effect on P028x | pin |
|---|---|---|---|
| GDN stack | server.py:4022-4054 | sets GDN_TC=1, CONVL2=2 | config env `=0` |
| `vram_fit.fit_start` in `engine_args` (2a1042877, db4b445ba, 7a6e77a62) | server.py:3525; strata_control/vram_fit.py:279-326 | may lower `--kv-resident` from args (CUDA knob = kv_resident only; reserve never touched on CUDA) | `"user_args": ["--kv-resident", "32768"]` |
| drafting Auto = DFlash2 where the engine has it (13edeb7f8, d040f0b66) | server.py:3510; drafting.py:651-690 (choose_of/decide), 784-836 (apply) | inert today (our model_name fails the regex at drafting.py:251; no DFlash2 pack) | `"drafting": "mtp"` |
| on-demand picture reader, NVIDIA one GPU (166dcf0b1, 79dc46376) | server.py:9367-9400 | excluded by `--expert-cache-device1`; we run the CPU reader anyway | none |
| parallel stack (dd471d314, .9) | server.py:4000-4020 | needs `--batch`/`parallel` | none |

---

## 3. The all-cards split engine (sFNX, `strata-split-N`)

- It is a separate program, built only with `-DSTRATA_BUILD_SPLIT=ON` (docs/SPLIT_ENGINE.md). The server treats a run as
  split only when the exe's basename starts with `strata-split` (server.py:1094).
- Only `strata launch` (the Terminal) writes such a config ("0.2.10: the all-cards split engine is Terminal-only", 974074c54;
  auto by default since ac1965ede, rule 28f94d689).
- Our `serve/server.py --config configs/P028x.json` with `exe` = engine-r22p028x/strata can never start it.
  `start_engine_or_fallback` (server.py:9107) falls back to the config's `split_fallback` only for split configs.
- **Guards** (strata_control/split_engine.py:176-248 `decide`). Our cards fail at least three rules:
  - "the cards are not all the same model and size" (5080 16 GB vs 4060 Ti 8 GB);
  - NVIDIA tested archs (86, 120) on 2 cards only, and sm_89 is not tested (`TESTED_ARCHS`, :46);
  - "all the experts do not fit in the cards' memory": IQ3_S 46.84 GiB / 2 + overhead > 8 GiB.
  - Also: Linux, Qwen3.8 shapes, RAM check.
- Off switches if ever needed: `STRATA_SPLIT_ENGINE=0`, `--split-engine off`, `"split_engine": "off"`.
- The engine's own layer-split paths are separate (`--layer-split`). We pass none, so `multi_gpu` = false throughout.

---

## 4. (Folded into 0-2.) The pins above give a v0.2.10 build whose new defaults are all off.

Gate order suggestion for the port gap (same structure as gap 16):
1. The release with the pins = v0.2.8-pinned reference (T1 check).
2. Patched with every switch off = the release.
3. Each of our switches on, against P028x.
4. The new upstream defaults one at a time as candidates: lookup 12, QSA_FUSE_NR, IL_PAD, PDL (bitwise claims: exact7 +
   byte-identical logits); PCIE_START and GDN TC/CONVL2 (KL rule; GDN with 16K/64K cold prompts per item 7).

---

## 5. Rebase forecast: our 28 patches onto v0.2.10

Method: `git format-patch v0.2.8..r22-port028x`, then the 33 existing target files extracted from v0.2.10 with
`git archive`, then GNU `patch -p1` applied in order in the scratch tree (`port0210-scratch/tree2`, log `apply-log2.txt`,
rejects `rej2/`). "ok" = applied, maybe with an offset; "fuzz" = applied with fuzz (review); "FAIL" = rejected hunks.

### 5.1 Per patch

| # | commit | patch | result on v0.2.10 | upstream change that moved it / what to do |
|---|---|---|---|---|
| 1 | 660f986a9 | --side-stash | generate.cpp 8 ok (offsets up to 1.8K lines) | - |
| 2 | 83ee4a276 | --chat-cache | generate.cpp 6 ok | - |
| 3 | 80cdfcf9d | chat-cache root ckpt | 1 ok | - |
| 4 | 2587c288d | Web search switch | server.py 8 ok, app.js 5 ok, own files clean | server.py +876 lines, but none in our hunks |
| 5 | 8feadc5fd | web search date | clean (our file) | - |
| 6 | 463704af2 | ROUTER_Q8K | verify.hpp fuzz 1, verify.cpp 3 ok, expert_source.cpp 2 ok, **elementwise.cu FAIL 1** | context only: 1f8ca8de1 rewrote `copy_i32_from_mapped_kernel` right after `doorbell_publish_res`. Re-insert our block by hand. Buffers stay right for 12-row windows (`T * xk_stride_` at max_t; counters per group, G <= 2) |
| 7-9 | 5f7be6eec, 49a82c408, 2151970d7 | Q8K rounding / bsums / NaN | elementwise.cu FAIL | only because 6 failed (they edit its new block). Apply after 6 |
| 10 | 6418b007b | #619 nextn | clean | not merged upstream (no `nextn_predict_layers` in v0.2.10 native_dense.cpp): keep |
| 11 | 81ef92d15 | model_check | server.py 1 ok | - |
| 12 | e5b10ec9d | chat cache non-finite drop | 3 ok | upstream 9aea047ee touched the NaN-stop ERR/DONE: re-read the path after port |
| 13 | a500b94ef | `</think>` in a code fence | frontend.py 3 ok, **2 FAIL** | **semantic**: 209dcadb3 (v0.2.9, #4702/#4703) changed the fence state. A fence closes only with the same length, and an indented block is a quote. The snapshot is now 5 fields (`fence, line, ticks, _prev_blank, _indented`, frontend.py:1387-1393). Our `fhold_state = (fence, line, ticks)` must use upstream's snapshot. Upstream did not fix #2794 itself: keep ours |
| 14-15 | 2aad8a156, 0f3d17bde | Tavily / Exa fallback | clean (our file) | - |
| 16 | 04c5f1c7f | chat cache owner + chat_drop | server.py 1 ok, generate.cpp 8 ok | the GEN parser also gets `pen_from` (62e861c99): merge both |
| 17 | d6a33e297 | answer_room continuation (+ #652 engine half) | server.py 4 ok, test_server ok, generate.cpp 9 ok / **5 FAIL** | **semantic**, serve loop: the `lim` (tcap) declaration, `while (... produced_n < lim)`, the `emit` commit block, `consumed` up to emit, and the `drafted` condition. Upstream added `exit_if_gpu_fatal` next to `ver.commit`, the HIP-only `serve_stop_bound` just before it (generate.cpp:18490-18497), and changed the draft call to `req_df2 ? ... : mtp.draft_long(...)` (:18587). Port by hand. It is required before any switch |
| 18 | 455489c7e | GR_FORK | fused_gr.cu 2 ok + 2 fuzz, mtp.cpp ok, fused_gr.hpp ok, **verify.cpp init FAIL 1** | fused_gr.cu: `fused_gr_read_multi` was split into `fused_gr_read_multi_slice` plus a chunking wrapper. Our branch lands inside the slice before v3 (trial tree :3111 vs :3122), which is correct. verify.cpp:964-ish: context changed by the q8 activation `qcols` lines (03627326d) |
| 19 | bf8760cb7 | fork's own scratch | verify.hpp ok, verify.cpp 1 ok / **3 FAIL** | **semantic**: the head read is now a column-chunk loop (verify.cpp:2535 `for h0 ...`), passing `xn_ + h0*HC*N`. Ours must pass `grfk_` in every chunk (sequential on one stream; the counters reset themselves). In the 8-row build the wrapper's `>kFusedGrMaxT` path never runs (kFusedGrWideT = 8). Also re-add `grfk_` in init |
| 20 | 8f0efe5ea | patch guards | all ok (CMake, qsa_prompt_attn.hpp/.cu, fused_gr.cu, generate.cpp) | - |
| 21-22 | 0f8fa8f91, 73867a6a9 | guard fixes | clean (own files) | - |
| 23 | 91f7ef22c | PREFILL_V2 | CMake ok, moe_fused_iq.hpp ok, prefill.cpp 2 ok, moe_fused_iq.cu 6 ok, **moe_fused.cu FAIL 1, moe_fused_iq.cu FAIL 1** | context only: an include line, and the v2 mode block after `pick_ww`, where upstream added gfx12 IQ2_S code (02c367d5c / b9e3e2b86). The fused path is otherwise as before for CUDA (`d.s120`, HIP-only `q8d_f16`) |
| 24 | 06f3a67fc | SPEC_EXACT | mtp.hpp, verify.hpp, verify.cpp ok; sampler.hpp fuzz; mtp.cpp fuzz + 5 ok; **generate.cpp FAIL 4** | **semantic**: the serve and CLI lookup checks are now `(probabilistic \|\| !draft_on \|\| sbuf[0] == drafts[0])` with `probabilistic = use_mtp && !req_df2 && mtp.prob()` (generate.cpp:18232, 20182): put `mtp.ess() ? mtp.ess_top(0) : drafts[0]` back. `set_spec_window` goes next to the new `mtp_q_applies(...)` lines (:18465, :20240) and must stay off for `req_df2`. verify.cpp: our ess branch goes before the SPEC_PROB `T <= kVerifyMaxT` branch (:3598). Fine for 12-row windows (section 1.2) |
| 25 | d29791244 | COST_GATE | mtp.cpp ok, generate.cpp fuzz 1 / **2 FAIL** | **semantic**: the window-size if/else moved into `strata::spec::choose_window` (include/strata/spec/window_rule.hpp, called at generate.cpp:18217 / 20172). Either add our rules to `WindowRuleIn` or override T after the call, MTP source only (`!req_df2`, `!first_window`) |
| 26 | c7175fe64 | cost gate past its steps | mtp.cpp ok, CMake ok, **generate.cpp FAIL 2** | same as 25 |
| 27 | 06ebdaace | DRAFT_CUM | CMake, mtp.hpp, mtp.cpp ok; generate.cpp 4 ok + 3 fuzz / **4 FAIL** | same as 25. The `mtp.draft(...)` call is now `mtp.draft_long(...)`; keep `set_draft_cum` before it. Review the 3 fuzz hunks (`draft_cum_place` landed at :13467 / :20423 of the trial tree) |
| 28 | 8f7a48aab | v2 term = native_kernel's | moe_fused_iq.cu 4 ok | - |

Summary:
- **15 patches apply** (1-5, 10-12, 14-16, 20-22, 28).
- **6 are context-only rejects** (6-9, 18, 23).
- **7 need hand work** (13, 17, 19, 24-27).
- The hot spot is generate.cpp's serve and CLI decode loops (+2110 lines upstream; DFlash2 `req_df2`, `draft_long`,
  `choose_window`, `graph_fits`, `exit_if_gpu_fatal`).
- No file or env-name collision: none of our new files or `STRATA_*` names exist in v0.2.10.

### 5.2 Things upstream now does that one of our patches also does (reconcile, do not stack)

- **#652 "commit only what is handed out" (in our 17).** Upstream `strata::core::serve_stop_bound` (#4677, 243fdb213;
  include/strata/core/serve_stop_bound.hpp) does the same bound: through max_new and the first EOS.
  - It is **HIP only** (`#if STRATA_USE_HIP`). It shortens `a` itself, so the acceptance counters and the drafter's row
    change too, and it does not know our tcap / `</think>` lift.
  - On CUDA keep ours. If we ever build HIP, run one of the two, not both.
- **Think-fence (13)** next to upstream's fence-length and indented-quote rules (209dcadb3): the two are complementary.
  Ours must adopt their 5-field state.
- **GR_FORK (18-19)** next to upstream's v3 read, now faster (GR_R2 exact-T, the GR_V3_PF register blocking): a speed
  re-measure, not a merge. v3 + PF stays "another summation order" than the default read, like the fork.
- **COST_GATE / DRAFT_CUM (25-27)** next to upstream `STRATA_SPEC_COST` (unchanged since 0.2.7; default only in the sm_121
  table, src/core/nv_defaults.cpp:80) and the new `choose_window`. No upstream copy of our rules.
- **SPEC_EXACT (24)** next to upstream SPEC_PROB / gated proposal: unchanged (spec_prob.hpp has no diff).
  `gated_proposal` still needs `mtp.prob()` (generate.cpp:17159, 19976), which is false under our switch.
- **ROUTER_Q8K, PREFILL_V2, chat-cache, side-stash, #619, web search, model_check:** no upstream equivalent in v0.2.10.

---

## 6. Notes for later (DeepSeek-V4.1), confirmed with file refs

- **Vision tower in RAM between pictures** (21df2aa30, 11-01).
  - With `--serve` on a discrete GPU the tower waits in pinned host RAM (~1 GB) and takes its ~319-320 MiB of VRAM only
    for a picture turn, out of `--reserve-mib`. The expert split counts that room as experts' room.
  - It stays on the card if the reserve is below its size + 192 MiB, on shared-memory GPUs or Metal, or with
    `--vision-resident`.
  - Files: src/dsv41/ds4_vision.cu / .cuh, ds4_model.cu, ds4_main.cpp; docs/DEEPSEEK41.md:137-145.
  - Follow-ups:
    - d826b02d5: no room, so experts' tail slots are lent to the tower for the turn;
    - 79dc46376: no sticky CUDA error on a failed take;
    - e04ee998f: AMD too;
    - c5ab5d400: setup gives `--reserve-mib 900` with pictures on a discrete card, lazy tower kept.
  - Measured: A6000 as a 12 GB-like card, 370 vs 145 experts in VRAM, 20.7 vs 18.7 tok/s.
  - **Relevance:** our DS daily runs `--vision off`, so nothing changes unless pictures are turned on. Then the reserve must
    be >= ~512 MiB for the tower to leave the card.
- **ISTA DeepSeek-V4.1 Coder set.**
  - 192 of 384 routed experts kept per layer; router, experts and biases half as wide; other tensors = the 2.00 set's.
  - Repo `ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-Coder-GGUF` at revision 0b1d5da5: five shards in `IQ2_XXS/`. The
    Engram at the root is **the shared Engram** (same name, size and SHA-256 as the unpruned release's converted one), and
    the repo's own mmproj is accepted (06698c674, df8c28e87, 0e3b06f03).
  - Download 191 GB: 72 GB model + 111 GB Engram (shared) + 8 GB drafter.
  - Files:
    - data/dsv41/coder-set.json (pins);
    - data/dsv41/profile-coder.bin (its own expert profile from 519,422 tokens; c021f48d7);
    - docs/DEEPSEEK41.md:80-95;
    - README.md (the "ISTA-DAS Coder (half of the experts removed)" row).
  - Engine: 8dbdcf1b2 (a profile of another model's size is not read; router tests at 192 experts).
  - Setup and plan: 85dd08524, 89515548b, b1043775d.
  - Quality (DEEPSEEK41.md:90-92): KL 0.397 / top-1 76.4% / PPL 4.645 vs 2.00's 0.171 / 83.7% / 3.630.
  - Our strata-dsv41 fork (v026p343-slotram) would need these commits before it can use the set.

---

## 7. Method notes and scratch files (`results/r22/port0210-scratch/`)

- `log-028-0210.txt`, `log-028-029.txt`, `log-server.txt`, `log-defaults.txt`: commit subjects.
- `env-v0.2.8.txt`, `env-v0.2.9.txt`, `env-v0.2.10.txt`, `env-new-028-0210.txt`, `env-new-sites.txt`, `flags-*.txt`: the
  env and flag inventories.
- `generate-0210.cpp`, `fused_gr-0210.cu`, `prefill-0210.cpp`, `server-0210.py`, `server-028.py`, `drafting-0210.py`,
  `vram_fit-0210.py`: extracted copies.
- `lookup-verify.diff`, `lookup-gen.diff`: 03627326d's diff.
- `patches/` (our 28, format-patch), `tree/` + `rej/` (first pass), `tree2/` + `rej2/` + `apply-log2.txt` +
  `apply-summary.txt` (the forecast; FAIL counts there include patch's summary line, so actual = count - 1).
- Limits:
  - Kernel arithmetic changes without a switch were looked for in the decode/prompt kernel commit lists, and none was found
    for CUDA. The pinned-release exactness gate is the backstop.
  - "applies" in 5.1 is textual: the fuzz hunks and every generate.cpp hunk need review against the refactored loops.
