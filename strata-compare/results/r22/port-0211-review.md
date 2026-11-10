# Strata v0.2.11 review (no port now) - read-only, 2026-11-05

Karl 11-05: "Same handling: review read-only and flag; no port now; nothing pauses". Scope as in port-0210-review.md: what
v0.2.10 -> v0.2.11 changes on OUR path (Qwen3.8-Flash-Next IQ3_S, native pack, CUDA, RTX 5080 sm_120 = CUDA0, RTX 4060 Ti
sm_89 = `--expert-cache-device1 3300` helper, `strata --serve` via serve/server.py, configs/P028x.json served, configs/P0210x.json
= the port base's config), and how the port base (branch r22-port0210 @ fdd2fffa8 = v0.2.10 + our 28) lands on it.
Only the git fetch (refs) and read-only `gh` used the network. Nothing was built, run, checked out or edited outside this file
and the scratch folder.

- Upstream: v0.2.11 = c3b3f5035 (11-05 12:54 +0100; app/Terminal 0.2.11, Control and engines 0.1.57; the Qwen engine packages
  built from 0bdcef468). 205 commits v0.2.10..v0.2.11 (162 non-merge), 327 files, +21,381 / -1,178.
  - The all-cards split engine (src/split): 28 commits, +2,874 lines. It cannot start for us (port-0210-review section 3).
  - The main engine (src/core, src/program, src/prefill, src/kernels, include): 23 commits, 25 files, +1,560 / -77. Most of it
    is tests and the layer split's spill walk.
  - serve/: 22 commits. The rest is app, Control, launcher, setup, catalog, Mac and packaging.
- File:line refs are `v0.2.11:` unless marked. "served" = strata-r22p028x, "port base" = strata-r22p0210 (both read, not
  touched). Scratch: `work/r22/scratch-0211/` (section 4).

---

## 0. Summary

1. **Engine path: almost nothing changes.**
   - Three new engine defaults could reach our path. All three are keyed on `qwen_defaults_026()`, so our
     `STRATA_DEFAULTS=026` keeps them off:
     - the PCIe share rule (ceiling 0.95, pool factor k);
     - the 32768 chunk ceiling for a bare `--prefill auto`;
     - `STRATA_MMQ_KQ=1`.
     The second and third are not reachable anyway. We pass `auto:16384`, and our pack has no K-quant routed experts.
   - The only numerics change without a switch is the Q5_0 expert dot (aa678f10d). Our file has no Q5_0 tensor.
   - No change to: MTP, verify, the sampler, GR / GR_FORK, the fused MoE prompt kernels, the GDN kernels (kernels.cu,
     gdn_tc.cuh), the QSA CUDA kernels, the CPU pool kernels, the helper tier, or the serve decode loop. (`git diff --stat`
     of those files is empty.)
2. **Serve layer: the real content for us.**
   - Karl's #3961 fix (note d): a run that ends without its done event becomes an error and restarts the engine.
   - Two new server-process defaults: a 60 s stream write timeout, and a non-blocking console.
   - A tool-parser fix that names our #4701.
   - A Pillow decoder whitelist. Our server venv runs Pillow 12.3.0, which is inside GHSA-78g4-xqwv-q3g8's range.
   - `/?q=` no longer auto-sends (#4221, a security fix).
   - A new "short of VRAM: start again with no drafter" retry. Our `"drafting": "mtp"` key already blocks it.
3. **Rebase forecast.** A three-way trivial merge of v0.2.11 into r22-port0210: 10 files changed on both sides, 9 merge
   cleanly (textually), and **1 conflict**: serve/web/app.js, our web-search patch against #4221 (section 1.4).
4. **Karl's notes** (section 2):
   - (a) The v3.1 sets are in the catalog, but the parity tests are kernel tests on synthetic weights with no recorded
     numbers and no card named. Nothing in them is numerically comparable with gap-ud31. Two comparability flags for the gap:
     - upstream's run config for UD-* files sets `STRATA_HC_Q8=1`, and our U arm does not;
     - the Q5_0 fix matters for UD-IQ2_XS (layer 4), not for UD-IQ3_XXS.
     UD-IQ1_S is refused because its layer 18 has gate IQ2_S and up IQ2_XXS, and the pack format holds one gate/up type per
     layer.
   - (b) Both halves are confirmed. A reason exists, in a header comment of the same commit: the IQ3_S-type sets' "suite lost
     3 agent tasks with it, UD-Q4 did not". It gives no numbers, and no issue or PR covers it. It is a different engine with
     different dense numerics and a different measure, so it neither confirms nor contradicts our NLL result.
   - (c) None. No v0.2.11 change to the default fused prompt path's numerics on our configuration.
   - (d) Confirmed, with a nuance. The stream part of c30aa647 is tagged #3961; #4463 is its activity-lease part. Two
     follow-ups (a8767488c, 74f390538) belong with it. The served tree and the port base both have the old behaviour.
     The item text is in 2(d).

### Pins and keys for the next port (additions to P0210x.json's 14 pins; "=" is the off value the code reads)

Engine (config `env`). The first two are already off under `STRATA_DEFAULTS=026`; pin them explicitly, as was done for
GR_V3_PF:

| variable | value | keeps |
|---|---|---|
| `STRATA_PCIE_SHARE_MAX` | `0.60` | PcieAuto's ceiling of 0.60 (the new default is 0.95 on a discrete card; include/strata/core/pcie_share_rule.hpp:46-49, generate.cpp:2698-2705, used at :2743 and :12550) |
| `STRATA_PCIE_K_RULE` | `0` | k = 1.85 at every pool rate (the new rule falls to 0.8 at 12 GB/s; pcie_share_rule.hpp:18-22, :40-43) |
| `STRATA_NV_CHUNK` | `0` | optional, a no-op for us: the 32768 ceiling applies only to a bare `--prefill auto` (generate.cpp:3543, :3881) |
| `STRATA_NV_KQ_DEFAULT` | `0` | optional, a no-op for us: read only for K-quant routed experts (src/core/nv_defaults.cpp:117-127; src/prefill/moe_mmq.cu:49) |

Server process (the launcher's environment, NOT the config `env`: server.py reads `os.environ` itself, :321 and :9843;
the config `env` only reaches the engine child). By the 11-02 rule ("everything else new stays pinned OFF unless gated")
pin them. They are serve robustness fixes with no numerics, so accepting them after the serve test is the alternative:

| variable | value | keeps |
|---|---|---|
| `STRATA_STREAM_WRITE_TIMEOUT_S` | `0` | a client that stops reading holds the engine's turn as before. The new default is 60 s, then a disconnect and the engine is stopped (c08fd2ecc, #4271) |
| `STRATA_BLOCKING_CONSOLE` | `1` | the server's `print` blocks as before. The new default queues it and drops the oldest text past 1 MiB / 4000 chunks (b776e1cd0, serve/nonblocking_out.py). The engine log is not affected: the engine's stderr goes straight to its log file (server.py:1211) |

Config keys: keep both of P0210x's.
- `"drafting": "mtp"`: it now also blocks v0.2.11's no-drafter retry. `nodraft_retry_args` returns None unless drafting is
  Auto (server.py:3747-3760; fc5dac23c).
- `"user_args": ["--kv-resident", "32768"]`: `vram_fit.fit_start` is unchanged. The vram_fit.py diff only adds
  `engine_stop_reason`.

---

## 1. Flagged items

### 1.1 Engine: new defaults and changes on or near our path

| commit | what | reaches P028x / P0210x? | default | 026? | bitwise? | action |
|---|---|---|---|---|---|---|
| 213f1a390 (+ e364620c5 switches) | PcieAuto follows the CPU pool on a discrete card. Ceiling 0.60 -> 0.95; k falls from 1.85 at R >= 30 GB/s of expert bytes to 0.8 at R <= 12 (pcie_share_rule.hpp). The same functions feed the "new" start share (generate.cpp:12550, which we pin `STRATA_PCIE_START=old`) and the layer-split stages (:12641) | yes, in principle: we pass no `--pcie-frac`, so PcieAuto refines our share (pcie-frac adopted 10-23) | on (discrete CUDA) | **yes**: `pcie_share_ceiling` / `pcie_k_rule_default` return the old rule under 026 | no: it changes which experts the CPU computes (like PCIE_START) | pin `STRATA_PCIE_SHARE_MAX=0.60`, `STRATA_PCIE_K_RULE=0`. Upstream: "a strong pool unchanged ... the shares stay below 0.60". Only a gap would show whether ours moves |
| 213f1a390 | `STRATA_PCIE_AUTO_SPLIT` on for a CUDA layer split (generate.cpp:2447-2456) | no (no layer split; the helper does not set `multi_gpu`) | on | yes | - | none |
| aa1202551 (+ 1fef27e83 docs) | a bare `--prefill auto` on NVIDIA cc 8.0+ takes a 32768 ceiling (include/strata/core/nv_chunk.hpp; generate.cpp:3874-3897). The RAM guard now steps 32768 -> 16384 -> 8192 (:9678-9708) | **no**: `auto:16384` makes `prefill_auto_bare` false (:3542-3543); the guard runs only when a default raised the ceiling | on | yes (`nv_chunk_ceiling(..., defaults026)` = 0) | KL ~1e-4 vs 8192 (DETAILS.md:1309) | optional `STRATA_NV_CHUNK=0` |
| 52ac4e733 (e2f7c4744) | `STRATA_MMQ_KQ=1` on NVIDIA cc 8.0+: K-quant routed experts (Q4_K/Q5_K/Q5_1/Q6_K) read the prompt on MMQ (nv_defaults.cpp:117-144, generate.cpp:3860-3868) | **no**: our routed experts are types 18/20/21/22/23/42 (IQ3_XXS, IQ4_NL, IQ3_S, IQ2_S, IQ4_XS, Q2_0; checked from the GGUF header). The K-quants are only dense / shared-expert tensors, and the variable is read only in the MoE MMQ path (moe_mmq.cu:49, mmq_kq_loader.cpp:110). We also run fused | on | yes | KL 0.024-0.035 (upstream) | optional `STRATA_NV_KQ_DEFAULT=0` |
| 62853e78d | FP16 weight cache on when the engine runs `--batch` >= 2 on Linux CUDA (generate.cpp:8180; gemm.cu:1413-1431) | no (no `--batch`) | on with batch | - | claimed bit-exact now (gemm_w16_parity) | none |
| aa678f10d | **Q5_0 expert dot**: the -16 offset uses the sum of the quantized activations (iq_kernels.cu:438-470). No switch | no: our file has no Q5_0 tensor anywhere (GGUF header). See 2(a) for v3.1 | always | - | changes Q5_0 results | none for us |
| fc5dac23c, ee0b367fb, 31a735153 | the layer split's spill walk (trim, fewer cards, KV window down, head to host, loan keeps 16). The MTP-drop rule was refactored (generate.cpp:7029-7078) | no: every step needs `multi_gpu` / `stages`. The single-card MTP drop is unchanged in substance (`STRATA_MTP_KEEP=1` pinned). Two single-card loan/spill conditions lost `!multi_gpu && stages.empty()` (:7941, :7988), but still need `!o.vram_reserve_given` (we pass `--vram-reserve-mib`) and no `STRATA_SPILL_OFF` (pinned 1) | - | some | - | none |
| 8b98b6f1c, 938b76eb3 / a1e6ef324, c2d44e93a, edb7c4819 | Strix Halo probe, gfx12 staging ring (prefill.cpp:402-425 inside `#if defined(STRATA_USE_HIP)`), gfx12 defaults | no (HIP only) | - | - | - | none |
| a1c7f0505 | named DFlash2 + `--batch` on one card | no | - | - | - | none |

New `"STRATA_*"` names in src/include/serve, v0.2.10 -> v0.2.11 (9): `STRATA_BLOCKING_CONSOLE`, `STRATA_GFX12_RING`,
`STRATA_NV_CHUNK`, `STRATA_NV_KQ_DEFAULT`, `STRATA_PCIE_K_RULE`, `STRATA_PCIE_SHARE_MAX`, `STRATA_PF_OWN_PROBE_OFF`,
`STRATA_SPLIT_EARLY_OFF`, `STRATA_STREAM_WRITE_TIMEOUT_S` (scratch `env-new-0210-0211.txt`). Each is covered above.
- No engine flag was added or removed.
- No Qwen4 support (no commit or diff line).
- The split engine's new defaults (FNX_PF_ROWS 8192, FNX_PF_HCSPLIT 2, FNX_PFX_ATTN_I8 / FNX_PFX_GDN_TC by file type,
  8 AMD lanes, DFlash2 in the split) are not reachable.

### 1.2 Serve layer (arrives with server.py / frontend.py at the port)

| commit | what | for us |
|---|---|---|
| c30aa6475 + a8767488c + 74f390538 (#3961) | a run with no done event becomes an error and the engine restarts | **port item**, see 2(d) |
| c08fd2ecc (#4271 part 1) | a stream write with no progress for 60 s is a disconnect. The engine is stopped and the turn given back (server.py:321, :8538-8540) | new default (pin table). Jan / LDR read continuously, so it should not fire |
| b776e1cd0 (#4479, #2481) | server stdout/stderr go through a bounded queue (serve/nonblocking_out.py) | new default (pin table). Engine log untouched |
| fc5dac23c (server half) | an Auto start that dies for VRAM starts again once with no drafter (server.py:1278-1290, :3747) | blocked by `"drafting": "mtp"` |
| 3bbf0f399 (#5040, **#4701**, ours) | tool parser: streamed arguments keep a file that lists the closing tags (`_close_verdict` "hold", frontend.py:794-800, :1864-1870) | take. It merged cleanly next to our think-fence patch |
| 8181522f1 (GHSA-78g4-xqwv-q3g8) | `PICTURE_FORMATS` whitelist in `Image.open` (serve/ds_pictures.py:26, server.py vision path); Pillow 13.0.0 in requirements.txt | **our vision path opens pictures with Pillow** (served server.py:2894-2917), and `.venv` has **Pillow 12.3.0**, inside the advisory's 11.1.0-12.3.0 range. The whitelist arrives with the port. A Pillow upgrade is a separate, Karl-approved venv change |
| app.js part of 50c2db690 (#4221) | `/?q=` only fills the box, never sends ("any page can link here, and a send would go out with the API key and the MCP tools saved in this browser") | take upstream's behaviour. This is the one merge conflict (1.4) |
| b3c633868 (#5044 half) | engine stdout read with `errors="replace"` | take |
| 0d922698f (#4792), f1fd753de (#4738), 3f6960f1f (#3443) | failed-start cleanup race, control-line wake-up, ConvCacheLog lock | take (robustness) |
| bae1e1d4d, 65cff54c0, 39851463b, daf4ac087, 66385404f | `--batch` slot picking and framing, replicas | not reachable |

### 1.3 Anything else worth gating

- **PcieAuto under the new rule.** This is the one engine default that could move our decode if 026 were ever dropped.
  If upstream's figures (2 workers 31 -> 63 tok/s) tempt a test, it needs its own gap with the KL rule (not bitwise).
- **#4879 (upstream, open):** a locally built sm_120 engine gave degraded IQ-quant output with distro nvcc 13.2; the
  prebuilt was fine. We build with CUDA 13.3, and setup.py already flags 13.2 (`CUDA_SM120_SUSPECT = (13, 2)`). No action.
  It is a reminder to keep the nvcc version in every build record.
- DETAILS.md:1309 now says chunks above 8192 on CUDA "change the rounding slightly" (first-token KL vs 8192 about 1e-4,
  UD-Q4_K_XL, A6000). Before, it said "not bit-exact". Our served `auto:16384` is such a chunk. It is a docs change, not a
  code change.

### 1.4 Rebase forecast (r22-port0210 onto v0.2.11)

Method: `git merge-tree --trivial-merge v0.2.10 r22-port0210 v0.2.11`. It prints to stdout and writes no objects or refs
(scratch `merge-tree-trivial.txt`).
- Files changed on both sides (10): CMakeLists.txt, include/strata/kernels/qsa_prompt_attn.hpp,
  src/kernels/cuda/qsa_prompt_attn.cu, src/prefill/prefill.cpp, src/program/generate.cpp, serve/server.py, serve/frontend.py,
  serve/test_server.py, serve/test_tool_corpus.py, serve/web/app.js.
- **9 merge cleanly.** The generate.cpp hunks upstream touched are start-up / PCIe / split code. Our hunks are in the serve
  and CLI decode loops, which v0.2.11 did not change.
- **1 conflict: serve/web/app.js** (around app.js:1605). Our patch 4 (web search) chains `loadHealth().then(loadMcp).then(loadWeb)`
  and auto-sends `/?q=`. Upstream (#4221) never auto-sends. Resolution: upstream's block plus our `.then(loadWeb)`.
- Caveat: this is textual only. The semantic checks are 2(d) (our run paths must keep ending in one done) and the usual
  gates.

---

## 2. Karl's four notes

### (a) Unsloth v3.1 sets in the catalog, with CUDA parity tests

**Catalog.**
- 9ed3c7789 (11-05 07:23) adds UD-IQ1_M, UD-Q2_0, UD-IQ2_XS, UD-Q2_K_XL, UD-IQ3_XXS, UD-Q3_K_XL and UD-IQ4_XS-v31, at Hub
  revision `d96201194f10` (setup.py:428-435, `UNSLOTH_V31_REVISION`, `UNSLOTH_V31_ENGINE = (0, 1, 57)`).
- MODELS entries: setup.py:488-509 (UD-IQ2_XS :494-496, UD-IQ3_XXS :500-502).
- Pins: `UNSLOTH_V31_SHARDS` setup.py:611-650.
- strata_control/models.py:41-42; data/gguf_fingerprints.json:337-353 (UD-IQ2_XS), :379-396 (UD-IQ3_XXS).
- Wording: 199fbc7a4. Strix plan fix (UD-IQ2_XS first launch failed on a 64 GB Strix Halo): 86ffdbeb1.
- **The UD-IQ3_XXS pins equal ours.** All 4 shards' sizes and SHA-256 match `work/qwen4-kit/unsloth-v31/dl/tree.json`
  (checked, scratch `pincmp.py`), so it is the same files as gap-ud31's U arm.

**The parity tests** (5d56ff8c0, c1d5e4d5e, 14a4636b8, 7faeb8c26, aa678f10d; CMakeLists.txt:2497, :2704-2717, :2737-2753):

| test (ctest names) | what is compared | to what | tolerance | inputs |
|---|---|---|---|---|
| `native_expert_parity_v31_<gu>_<dn>` and `_new_<gu>_<dn>` = `native_expert_parity --synthetic GU/DN` (gu iq1_m, iq2_xxs, iq2_xs, iq2_s, q2_0, iq3_xxs, iq4_xs; dn q2_0, iq4_nl, q5_0, q8_0) | one routed expert (gate, up, SwiGLU, down) at H 2560 / FF 640, 3 tokens. (b) the CPU pool path (ggml-cpu vec_dot, its quantized activations); (c) the GPU `native_expert_grouped` (q8_1 activations), with the decode-once and per-entry kernels | (a) a double-precision SwiGLU expert on ggml's `to_float` of the same blocks (native_expert_parity.cpp:9-14, :66-105) | relative L1 error < 3e-2 for both (b) and (c); GPU < 1.8e-2 for a Q5_0 down (:509-510). The (c) twins bitwise. Prompt dequantizers vs `to_float` rel < 1e-6, their FP16 = fp16(f32) bit for bit. Q8_0 bitwise | weights N(0,1) x 0.02 x (0.5 + (r mod 7)/7), quantized by `ggml_quantize_chunk` (imatrix of ones where needed; :609-630); activations N(0,1); fixed seeds |
| `native_dense_parity` | dense MMVQ decode, 1/2/3/4/8 columns; prompt dequantizers f32 / f16 / bf16 | a double product of `to_float` weights x FP32 activations | rel L1 < 2e-2 (4e-2 for Q4_0 / Q5_0, whose dense MMVQ keeps the unrounded activation sum: 14a4636b8, native_dense_parity.cpp:114). Multi-column = single bitwise. f32 dequant 1e-6 | Q2_0 ... Q6_K, IQ4_NL, IQ4_XS at 2560 and 640 |
| `native_dense_types_parity` | the same through `native_mmvq` at real shapes | same | rel L1 < 2e-2; ncols 1..4 bitwise; zero in -> zero out | Q5_0, Q6_K, Q5_K, Q4_K, Q3_K, Q8_0, IQ4_NL, IQ4_XS, Q2_0 |
| `prefill_mmq_v31_test` | the prompt MMQ products: gate/up 1280 x 2560, down 2560 x 640 | a double product | rel <= 0.04 and max_abs/rms <= 0.35 (prefill_mmq_v31_test.cpp:146). By its own header, "a screen for layout, stride, expert-bound and row-id errors, not a bit-exactness test" | Q5_0 only in a `STRATA_ORCA_Q4KS_MMQ` build |
| `native_grouped_parity` | Q5_0 down added; v1 vs new launches | - | - | - |

**What UD-IQ3_XXS and UD-IQ2_XS exercise** (from upstream's header fixture tests/fixtures/unsloth_v31/headers.json.gz):
- **UD-IQ3_XXS** routed experts (gate/up / down, layers): IQ2_S / IQ4_NL 23, IQ3_XXS / IQ4_NL 21, IQ2_S / Q2_0 3,
  IQ4_XS / IQ4_NL 1. Dense: Q6_K 250, Q8_0 248, F32 557, BF16 24, IQ4_NL 1. **No Q5_0.** This matches gap-ud31's splice dry
  run (52 IQ2_S + 42 IQ3_XXS + 2 IQ4_XS gate/up tensors; 45 IQ4_NL + 3 Q2_0 downs).
- **UD-IQ2_XS**: IQ2_S / IQ4_NL 21, IQ2_S / Q2_0 18, IQ2_XXS / Q2_0 5, IQ2_XXS / IQ4_NL 3, **IQ2_S / Q5_0 1 (blk.4)**.
  Dense: Q6_K 85, Q8_0 410, F32 388, BF16 195, IQ4_XS 1, IQ4_NL 1. It holds no IQ2_XS-typed experts despite the name.

**Results: none recorded.**
- No ctest output, number or card for any v3.1 set is in the tree, the docs or the commit bodies. The tests print their
  values when run.
- The only figures: before aa678f10d, a Q5_0 down gave a whole-expert error of 2.1e-2 .. 3.1e-2, against "1.2e-2 for every
  other down type". After it, 1.2e-2, and "the GPU now agrees with the CPU path". No card is named for these either.
- There is no end-to-end quality figure (KL, PPL, suite) for the v3.1 sets in v0.2.11.

**What is comparable with gap-ud31** (work/r23/gap-ud31.sh, ud31_rules.py; not run):
- **Nothing numerically.** Upstream measures kernel-implementation error on synthetic weights against ggml's own reading
  of the same blocks. Our gap measures:
  - model-level text NLL (long11, ~31,408 positions, band 0.1365 nats/token);
  - KL against R (UD-Q4_K_XL);
  - repeatability (exact7 U2 vs U1);
  - speed.
  A pass upstream means "the kernels compute the quant correctly", not "the quant is good".
- **Comparable facts:** the same four files, and the same type pairs. Upstream's tests support that a WORSE or "further from
  R" verdict for U would come from the quant, not from a decode or dequant kernel bug. That holds for v0.2.11's kernels.
  Those are the same as v0.2.10's for these types; v0.2.8 -> v0.2.10 was not re-checked here.
- **Not covered upstream:** our U arm reads prompts through the fused int8 experts (`STRATA_PF_FUSED=1`). The v3.1 tests do
  not exercise them (prefill_mmq_v31_test is MMQ; prefill_fused_iq_test is unchanged in v0.2.11).
- **Flag 1, `STRATA_HC_Q8`.** Upstream's setup writes `STRATA_HC_Q8=1` on CUDA for every UD-* file
  (`unsloth_default_env`, setup.py:4312-4334, since 0.1.44: "the GGUF's own Q8_0 hyper-connection projections, closer to
  the file and faster"). It also writes `--compat-bf16` (setup.py:723) and `STRATA_ROUTE_TAIL_SKIP=0` outside the budget
  mode.
  - UD-IQ3_XXS's hc_attn/ffn_down/up and output_hc_down/up are Q8_0 (fixture).
  - Our U arm has `--compat-bf16` and TAIL_SKIP=0, **but not HC_Q8**. So U is not upstream's "as shipped" run config in the
    verify read's HC projections.
  - Our engine has the switch: served src/core/native_dense.cpp:45-80, "S23 experiment ... the hyper-connection projections'
    Q8_0 bytes for the verify read". So GAPS-README's "The engine cannot read them otherwise" holds for the pack and prompt
    path, not for the verify read.
  - Karl's call, and it must be decided before the gap because the rules are frozen: keep U as written and note it, or add
    `STRATA_HC_Q8=1` (cfgcheck and the scorer's head would need it named: the offline head reads BF16 from dense.bin, while
    the engine's verify rows would read Q8_0).
- **Flag 2, Q5_0.**
  - The v0.2.11 fix is not in our engine: the old dot is at served iq_kernels.cu:464 and port base :466.
  - It does not touch UD-IQ3_XXS (no Q5_0).
  - A P028x test of UD-IQ2_XS (layer 4 down), UD-IQ4_XS-v31 (33 layers) or UD-Q3_K_XL (20 layers; CMakeLists.txt:2706)
    would carry the older, larger GPU decode error on those layers. The CPU pool path already used the quantized sum. Port
    aa678f10d first, or say so in the result.
- If Karl wants a like-for-like kernel check, upstream's `native_expert_parity --synthetic iq2_s/iq4_nl iq3_xxs/iq4_nl
  iq2_s/q2_0 iq4_xs/iq4_nl` could be built and run against our tree later (a build plus GPU step; not now).

**UD-IQ1_S refused.**
- Text: setup.py:3436-3441 (`SUPPORTED_GGUFS`, `UNSUPPORTED_WHY["UD-IQ1_S"]` = "UD-IQ1_S mixes two expert formats in one
  layer, which Strata cannot load; UD-IQ1_M is the 1-bit choice"). Tested in tools/test_setup_unsloth_v31.py:253-265.
- Mechanism: tools/iq_pack.py:452-453 refuses `"layer %d: gate and up differ in type"`, because native_experts.txt carries
  one `gu_type` per layer (iq_pack.py:13). That rule has been there since f2a08d4b2 (09-24).
- The fixture shows it: UD-IQ1_S's **layer 18 has gate IQ2_S and up IQ2_XXS**, the only such layer. The other 47 layers are
  IQ2_XXS/IQ2_XXS 35 or IQ2_S/IQ2_S 12, all with Q2_0 downs. No tensor in the set is IQ1_S-typed; the name is Unsloth's
  label.

### (b) 6983b09bb: GDN tensor-core prompt path by file type in the split engine; the main engine

**Split half: confirmed.**
- The file type is decided at src/split/src/gguf.cpp:114-122. `iq_experts_` is true if any tensor is IQ2_S, IQ3_XXS, IQ3_S
  or Q2_0. Our ISTA IQ3_S file qualifies, and so does UD-IQ3_XXS. UD-Q4_K_XL does not.
- engine.cu:63 calls `gdn_tc_set_default(!m_.g.iq_experts())` (moved there from model.cpp by fcd1493c1).
- kernels.cu:1935-1936 and :2029-2030: `FNX_PFX_GDN_TC` unset (-1) means the file decides; 0/1 overrides.
- Test: tests/split/test_split_hcsplit.py:7, :76-94. It asserts the ISTA IQ3_S type set gives off and UD-Q4_K_XL gives on.
- The same commit and f95411b84 set the opposite for the int8 prompt attention (engine.cu:62).
- In the split engine, an IQ3_S-type file also has its dense matrices, routers, embeddings and projections dequantized and
  re-written as Q8_0 at load (gguf.cpp:114-117). Its numerics are not the main engine's.

**Main half: confirmed, with a precision.**
- The **engine** default is off: src/prefill/kernels.cu:3040 (unset = off) and :2904 (CONVL2 unset = 0). Neither file
  changed in v0.2.11.
- **serve/server.py** turns both on for every Linux CUDA `qwen4exp` config, with `env.setdefault` and no file-type test:
  server.py:4293-4318 (`GDN_STACK_CUDA = {"STRATA_GDN_TC": "1", "STRATA_GDN_CONVL2": "2"}`), called from `child_env` at
  :4342.
- So "the main engine defaults it on" holds for any server start without our pin. Upstream qualified that default on
  **Qwen3.8 IQ3_S** itself (server.py:4294-4295, "QUAL-GDN": KL mean 0.0019 / max 0.0125, 61-task suite 55 vs 54, l620).

**The reason.**
- The commit message gives none. The same commit's header comment does, at src/split/src/kernels.hpp:120-121: "the
  tensor-core scan is OFF for the IQ3_S-type sets (**their suite lost 3 agent tasks with it, UD-Q4 did not**) and ON for the
  others".
- It gives no counts out of 61, no CI and no run count. The ATTN_I8 sibling in f95411b84 does give counts: UD-Q4_K_XL 57/61
  off vs 55/61 on, agent-A8 and A10.
- The chain:
  - 082af9c19 (11-02 16:05): the split's own port of gdn_tc.cuh, opt-in;
  - 1bf5e13e7 (11-02 17:23): on by default;
  - 838b2e0de (11-03 02:00): ATTN_I8 back off, "GDN_TC stays on";
  - 6983b09bb (11-03 08:26, "owner 11-03, do all 5"): off for IQ3_S-type files.
- For scale: the same 61-task suite moves by a few tasks between configurations. 9149835c6 has the split at 57/61 vs the
  layer split's 54/61 on IQ3_S; QUAL-GDN has 55 vs 54.
- `gh` (read-only): no issue or PR on it. Searched "GDN_TC", "FNX_PFX_GDN_TC", "gdn_tc", "GDN tensor", "tensor-core GDN" and
  "GDN IQ3_S" across issues and PRs. The hits (#3779, #4876, #3904, #5037 speed only, #4741) are not about this choice.

**How it relates to our finding.**
- Ours (results/r23/gdn-nll/decision.txt, stock v0.2.10 main engine, our IQ3_S file):
  - GDN on vs off: d = **-0.1844** nats/token, lower NLL, outside the band 0.1365 + margin 0.0373.
  - KL mean 0.180, also outside.
  - Both rounding references are lower too: PF_FUSED=0 d -0.1241, CPU share 0.4 d -0.0999. The same holds in
    nll-many/gap/decision.txt.
  - So every prompt variant scores lower NLL than the default fused path.
- Upstream's split-engine rule points the other way on "quality", but it is weak evidence about our path:
  - another engine and another port of the scan;
  - Q8_0-re-quantized dense weights;
  - agent-task counts, unquantified;
  - and it contradicts upstream's own main-engine qualification on the same file family.
  It neither confirms nor contradicts our NLL result. It is a hint that upstream also saw the IQ3_S + GDN TC pair behave
  differently from UD-Q4.
- Nothing in v0.2.11 touches our main engine's GDN or prompt path (2(c)). work/r23/gap-decpath.sh is not on disk yet; it is
  first in work/r23/gap-series.sh:12 `STEPS`. Upstream gives it nothing to compare against: v0.2.11 has no decode-path change
  on our configuration.

### (c) v0.2.11 changes to the default fused prompt path's numerics

**None on our configuration.**
- `STRATA_PF_FUSED`: no diff in the fused MoE kernels (moe_fused.cu, moe_fused_iq.cu), src/prefill/kernels.cu (GDN conv /
  scan) or gdn_tc.cuh. qsa_prompt_attn.cu adds only a HIP helper (`#if defined(__HIPCC__)`, :2443-2451).
- prefill.cpp: the only hunk is the gfx12 staging-ring depth, inside `#if defined(STRATA_USE_HIP)` (:402-425), and it is
  bit-identical by its own note.
- gemm.cu (accumulation of the dense GEMMs): the FP16 weight-cache default applies only with `--batch` >= 2 (:1413-1431,
  generate.cpp:8180). Without batch it stays off as in v0.2.10.
- Chunking: the NVIDIA 32768 ceiling and the stepping RAM guard apply only to a bare `--prefill auto` and not under 026.
  We run `auto:16384` with 026, so our chunks are unchanged.
- CPU share (`STRATA_PREFILL_CPU_SHARE` 0.4 / MAX 1792): no change.
- Q5_0 dot: decode experts, not in our file.
- The only related text is a docs edit (DETAILS.md:1309): chunks above 8192 on CUDA "change the rounding slightly"
  (first-token KL about 1e-4 vs 8192, UD-Q4_K_XL / A6000). Our served chunk is 16384. Upstream's figure is a first-token KL
  on another file, so it is not comparable with our 0.1365 nats/token NLL band, but it is small.

### (d) Serve fix c30aa647 ("a stream that ends without its end event is an error that restarts the engine")

**The issue tag.** c30aa6475 (11-04 11:00) bundles four changes, tagged "(#4463 #4352 #3961)":
1. a server started by running serve.py holds the shared activity lease (#4463, `main` -> `_main`, server.py:9828-9856);
2. `strata update` defaults to the checkout's engine store (strata_cli/update_cmd.py);
3. the server's own picture encoder is released when its engine died (#4352, `_release_orphan_encoder`, :5116);
4. **the stream part, which is #3961**: "a new agent request answers empty in 0.2 s (200, 1 chunk, no finish_reason) while
   the engine never logs it; /health stays ok". It was reported on an RTX 5080, engine 0.1.48.

**What it changes** (with its two follow-ups the same day):
- `openai_chunks` tracks `answered_done` (server.py:7149, :7183). If the run ends with no done event and was not cancelled
  (:7198-7206), it prints "[strata] a request ended without an answer and without a finish reason; it is answered as an
  error" and raises `EngineDied("the engine ended the request without an answer")`.
  - The client gets a 503 (non-streamed) or an SSE error object plus `[DONE]` (streamed), instead of an empty 200 that
    looked like an answer.
  - Both stream and non-stream `/v1/chat/completions` go through `openai_chunks` (:8638-8643). `/v1/messages`
    (`anthropic_events`) and `/v1/responses` have no such check in v0.2.11.
- c30aa6475 then killed the engine: `StrataEngine.end_for_restart`, :2965, sets `ended` and kills the process, so
  `ensure_loaded` restarts it on the next request.
- **a8767488c** (13:18) narrows that: `Service.end_engine_if_unchanged(born)` (:5452-5468).
  - It ends the engine only if it is still the process the request ran on (`engine.gen` noted per event).
  - Only if the turn can be taken without waiting (`fifo.acquire(blocking=False)`).
  - Never with batch slots.
  - So a request admitted after the lost one is never killed.
- **74f390538** (13:34): `EngineDied.restarts` plus `died_note` (:432-441). The message says "; the next request restarts
  it" only when the engine really was ended. It is used at all five EngineDied handlers (OpenAI non-stream and stream,
  Responses non-stream and stream, Anthropic stream).
- Tests: serve/test_server.py (+81, +65, +33 lines across the three commits).

**Does ours have the old behaviour? Yes, both.**
- served strata-r22p028x/serve/server.py `openai_chunks` (:6244-6312): the event loop ends at `yield last` with no
  done-check. There is no `answered_done`, `end_for_restart`, `end_engine_if_unchanged` or `died_note` anywhere in the file.
- port base strata-r22p0210/serve/server.py `openai_chunks` (:6849-6917): the same.
- The pieces the fix needs already exist in both: `StrataEngine.gen` (served :1200, port base :1312), `Service.fifo`
  (:4016 / :4529), `batch_slots_on` (:3888 / :4401), `EngineDied` (:395 / :425).
- Our own run paths already end every admitted run with exactly one done (served: `Service.run`, :5818 on cancel and :5873
  at the end, including our continuation fix; `run_with_mcp`, :6078). So the new check fires only on a real loss.

**The item for the next port's list** (wording for PORT-V0210-PLAN.md's "Next port's list"):

> **Serve fix #3961 (v0.2.11 c30aa6475 + a8767488c + 74f390538):** a /v1/chat/completions run that ends without its done
> event is answered as an error (503, or an SSE error plus [DONE]) instead of an empty 200, and the engine is ended so the
> next request restarts it: only the engine process the request ran on (`gen`), only if nobody holds the turn
> (`fifo.acquire(blocking=False)`), never with batch slots, and the message says "the next request restarts it" only then
> (`EngineDied.restarts`, `died_note` at the five handlers). Our served and port-base server.py have the old behaviour (no
> check in `openai_chunks`). Port the `openai_chunks` hunk, `StrataEngine.end_for_restart`, `Service.end_engine_if_unchanged`,
> `EngineDied.restarts` / `died_note` and the three commits' serve/test_server.py tests. If the next port is a merge of
> v0.2.11, they arrive with server.py (the merge is clean there), and the item becomes "check they survived". Checks at the
> port: our serve tests and upstream's three new tests pass; `Service.run` (with the continuation fix) and `run_with_mcp` /
> web search still yield exactly one done per admitted run (a cancel included); a restart caused by it drops the engine's
> parked chat-cache conversations (as `exit_if_gpu_fatal` does), which is acceptable for a lost run. Optional from the same
> commit: the activity lease (#4463) only matters with `strata update`, which we do not use. The orphan-encoder release
> (#4352) does not apply: our picture reader runs on the CPU (`"gpu": false`).

---

## 3. Notes for later (no action)

- The split engine (FNX_*) keeps growing: DFlash2 in the split, 8 AMD lanes, the HC split. It still cannot start for us:
  the server needs an exe named `strata-split-*`, and our cards are mismatched and do not hold all experts.
- DFlash2 named by the person now runs with `--batch N` (drafting.py `blocked_by(named=...)`). That is irrelevant with
  `"drafting": "mtp"`.

---

## 4. Method and scratch (`work/r22/scratch-0211/`)

- `log-0210-0211.txt` (commit subjects), `diffstat.txt`, `generate.diff`, `server.diff`, `native_expert_parity.diff`.
- Extracted copies: `generate-0211.cpp`, `server-0211.py`, `setup-0211.py`, `native_expert_parity-0211.cpp`,
  `native_dense_parity-0211.cpp`, `prefill_mmq_v31_test-0211.cpp`.
- `env-v0.2.10.txt`, `env-v0.2.11.txt`, `env-new-0210-0211.txt`: the `"STRATA_*"` inventories (src, include, serve).
- `merge-tree-trivial.txt`, `ours-files.txt`, `up-files.txt`: the rebase forecast.
- `gguf_types.py`: our GGUF's tensor types, read from the header only (`python3 -I`).
- `fixture/headers.json.gz` (upstream's fixture, copied out with `git show`) and `fixture_types.py`: the v3.1 sets'
  per-layer types.
- `pincmp.py`: upstream pins vs our tree.json.
- Fetch: `git fetch origin --tags` updated the refs. The old v0.1.x tags were rejected ("would clobber"), as expected after
  upstream's 10-06 history rewrite. v0.2.11 arrived.
- `gh`: read-only `issue list/view` and `pr list` on Niko1221/Strata (#3961, #4463, #4879, #5037; the GDN searches).
- Limits:
  - The rebase forecast is textual.
  - "No change" for a kernel means its file has no diff v0.2.10..v0.2.11.
  - v0.2.8 -> v0.2.10 was not re-reviewed (port-0210-review.md covers it).
