### Item 0 — the review of Strata v0.1.25, v0.1.26 and v0.1.27 (code reading)

v0.1.24 → v0.1.27 is 35 commits (72 files, +6,877 / −369 lines). The tag watcher found **v0.1.27** (22:58 CEST, 15:58
here) at its first check of this round, so it is included. What matters for this PC and config:

| release | change | on our config (IQ3_S, KV streaming `--kv-resident 32768`, helper GPU, Linux, RTX 5080) |
|---|---|---|
| 0.1.25 | prompt path: the per-layer expert **grouping tables in mapped pinned memory** instead of `cudaMemcpyAsync` behind the expert stream (+3.9 % at 32K, +4.5 % at 128K upstream; bit-identical; `STRATA_GROUP_COPY=1` = old) | **applies** |
| 0.1.25 | prompt path: **fused hyper-connection kernels** F-1 (the read without its FP32 copy) and F-2 (a half's write fused with the next half's norm), bit-identical, +4.0 % / +3.3 % upstream; `STRATA_GR_UNFUSED=1` = old | **applies** |
| 0.1.25 | `--kv k8v4` (INT8 K + Q4_0 V) | skipped as you asked (refused with `--kv-resident`) |
| 0.1.25 | AMD HIP backend (gfx1100), Turing (RTX 20) port, hipBLASLt tables | not our hardware; the Turing port touches our v5 kernel's file (below) |
| 0.1.26 | **E-9: the draft layer's prompt pass in batches** (0.9 → 0.07 s of a 32K prompt upstream; `STRATA_MTP_BATCH=0` = old) | **skipped on our config** — confirmed in the code (below) |
| 0.1.26 | low-RAM mode (`--mmap-experts` with native packs) | skipped as you asked |
| 0.1.26 | request-sized prompt chunks (`request_chunk`, lend checks) | applies (small prompts; no effect on ≥ 8K chunks) |
| 0.1.27 | **draft vocabulary with all Chinese/Japanese/Korean tokens** (40,525 → 106,299 ids; upstream: CJK answers +15–38 % decode, English −1–2 %) | installed only by `setup.py` (which we do not run): measured separately |
| 0.1.27 | server: only template-written image markers are images (#150); a config's `env` reaches the engine | applies (harmless for us) |
| 0.1.27 | PLE reader error paths (cancel queued reads on a failed read) | applies (robustness only) |

**Porting the promoted build's 12 patches** (branch `r7-port`, `patches/r7/`): 11 applied unchanged. Patch 0009 (our
"GR v5" multi-token hyper-connection read, decode) conflicted with upstream's Turing change in the same function
(`fused_gr_read_multi`: upstream now cuts a window into slices when a card's shared-memory opt-in is too small). Merged:
our v5 path stays the default and falls back to upstream's chunked kernel on a card that cannot hold the window (our
cards: capacity 9 tokens ≥ 8); `STRATA_GR_OLD=1` still selects upstream's kernels.

**"Fused hyper-connection kernels" vs our v5 kernels: they do not overlap in code.** Upstream's F-1/F-2 are in the
*prompt* path (`src/prefill/`); our v5 is the *decode* verify window's read (`src/kernels/cuda/fused_gr.cu`). The decode
path already had F-2's idea (the previous half's write is applied inside the next read). So "combine" = keep both; each
is measured on its own path with its switch (results below).

**E-9 is skipped with KV streaming — confirmed in the code.** `Prefill::draft_kv` returns false (→ the old per-token
`MtpDrafter::prefill`) when the drafter's K/V state is not fully resident (`st.kv_mode != 0`); with `--kv-resident` the
drafter keeps its K/V as a ring over a host copy (`kv_mode` 2, `mtp.cpp`), which is also what the chat cache parks.
So on our config every prompt, at any length, takes the old pass. Its measured share of prompt time is below (the
ceiling for extending E-9 to the ring: backlog, not built).
