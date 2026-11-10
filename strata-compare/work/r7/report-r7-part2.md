### 2. Item 0 — Strata v0.1.25, v0.1.26, v0.1.27: review, port, measurement on its own, C\*7

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

**Measured on its own (engine level, `strata generate --stats`, same flags as C\*6, cold page cache, guarded;
`results/r7/item0-engine.txt`).** C\*6 = engine-cstar6; R7c = v0.1.27 + the same 12 patches (engine-r7c).

| check | C\*6 | R7c (v0.1.27 port) |
|---|---|---|
| greedy decode, exact (`--adapt-swaps 0 --suffix-draft 0`), math / code, 1,024 tokens | output `8b1157e8` / `0db2777b` | **identical outputs**, same rounds and window sizes |
| ms per verify round, math (2 runs) / code (2 runs) | 32.36, 31.83 / 24.37, 24.31 | 31.88, 31.78 / 24.30, 24.43 (=) |
| 32K prompt, cold, first start (2 runs) | 9.95, 9.93 s | **9.66, 9.61 s (−3.0 %)** |
| 112K prompt (2 runs) | 33.55, 33.61 s | **32.38, 32.37 s (−3.5 %)** |

Where the prompt gain comes from (upstream's own A/B switches, same binary):

| R7c with … | 32K prompt | reading |
|---|---|---|
| (default) | 9.66, 9.61 s | |
| `STRATA_GR_UNFUSED=1` (0.1.25's fused norms off) | 9.95, 9.95 s | = C\*6: **the fused hyper-connection norms are the whole gain** |
| `STRATA_GROUP_COPY=1` (grouping tables copied again) | 9.62, 9.61 s | no effect on this config |
| `STRATA_MTP_BATCH=0` (0.1.26's batched draft pass off) | 9.66, 9.62 s (112K: 32.38 s) | = default: **the batched pass is not used with KV streaming (runtime confirmation)** |

**The old draft-layer prompt pass (the ceiling for extending 0.1.26's batching to KV streaming):** 694 ms at 32K and
697 ms at 112K (it only covers the drafter's window), 7.5 ms for a ~140-token prompt; `STRATA_PREFILL_TIMING` books it as
"after each chunk (the draft layer) 694 ms" of 10.55 s. So **at most 0.69 s per long prompt: 6.6–7.2 % at 32K, 2.2 % at
112K** (upstream's batched pass took 0.9 s → 0.07 s on an RTX 5070). Backlog, not built.

**Our v5 decode kernels vs upstream's on the new base** (`STRATA_GR_OLD=1` = upstream's multi-token read): per generated
token 12.57 vs 12.47 ms (math, +0.8 %) and 13.04 vs 12.49 ms (code, +4.4 %) without v5 → **v5 still helps; kept together
with upstream's fused prompt-path norms** (they do not overlap).

**0.1.27's CJK draft vocabulary** (installed only by `setup.py`; measured with a separate MTP folder of symlinks + the
new file): on English text, compared on the same output trajectory, math 126.8 → 124.2 and 124.5 → 121.8 tok/s
(−2.1 / −2.2 %), code 109.1 → 108.5 / 106.8 (−0.5 / −2.1 %) — upstream's "English −1–2 %" holds here. **The candidate keeps
the English-era vocabulary.** If you chat in Chinese, Japanese or Korean, the new file is worth it (+15–38 % upstream).

**Served A/B, C\*6 vs the port** (`results/r7/ab-c6-c7.md`; round 6's screens, 4 alternating pairs, fresh guarded
server and cold page cache each, your settings T 1.0):

| | C\*6 (4 runs) | **v0.1.27 port (4 runs)** | change |
|---|---|---|---|
| 32K prompt (uncached) | 10.00–10.02 s | **9.64–9.66 s** | **−3.6 %**, no overlap |
| 64K prompt | 19.36–19.43 s | **18.65–18.71 s** | **−3.7 %** |
| 120K prompt | 36.55–36.68 s | **35.19–35.33 s** | **−3.7 %** |
| 1K prompt / short prompts | 0.97–1.00 / 0.45–0.47 s | 0.96–0.97 / 0.45–0.48 s | = |
| decode, all 768+-token requests | 94.8 / 93.4 / 93.8 / 94.5 (94.1) | 93.8 / 95.4 / 93.3 / 92.2 (93.7) | = (sampling noise; greedy is bit-identical) |
| long reasoning 8K math / code | 103.3–105.2 / 86.9–88.5 | 103.1–105.2 / 84.9–90.5 | = |
| VRAM / MemAvailable / RSS | 15,418 MiB / ≥ 29.1 GB / 57.5 GB | same | = |
| correctness (5 prompts) / chat-switch test | all right / 0 errors | all right / 0 errors | = |

**The new base wins** (a reproducible gain beyond the noise, no regression), so it went through your checks:

| check | result |
|---|---|
| accuracy (teacher-forced, 7 texts, one GPU and with the helper) | **bit-identical to C\*6**: 1,536 / 1,536 NLL values equal on every text in both setups (`results/r7/tf-compare.txt`) |
| harder needle set (12 documents × 6 questions, 32K/64K/120K) | **72/72** |
| chat-cache round trip (park / resume / edit, helper on, static expert set) | **exact**: 0 argmax changes, all NLLs identical, drafter 0 of 385, state equal except stale cells |
| headless-Chrome browser test incl. Web search | first run **53/56 — found a real bug** (below); after the fix **54/56** = round 6's two known non-bugs |
| Stop during a 120K read, then the next requests (round 5's stop120k) | unfixed: **fails** (going back to the parked chat errors); fixed: **7/7** |
| launcher fallback (4060 Ti short of memory → 5080 alone) | pass |
| 2-hour soak | see below |

**A bug in upstream 0.1.26+, found by the browser test and fixed (patch 0013).** After you press Stop while a long
prompt is being read, the next request whose prompt goes through the batched prompt path — continuing that chat, or
going back to a parked chat — failed with `ERR cancelled`; the engine then exited and the server restarted it (a minute,
and every parked chat was lost). Cause: the serve loop keeps one error string for its whole life, a Stop leaves
"cancelled" in it, and 0.1.26's new draft-layer hook fails a prompt chunk whenever that string is non-empty (0.1.24's
hook ignored it). Fix: the hook gets its own error string (both serve and CLI paths); no arithmetic change — after the fix
greedy output, the 32K prompt time and the teacher-forced NLLs are unchanged. C\*6 does not have the bug (its stop120k:
7/7). Write-up for upstream: `pr-drafts/26-stop-then-next-request.md`.

My mistakes in this item, caught: the first round trip used a config without `--adapt-swaps 0` (the test needs a static
expert set) — invalid, re-run; my own quick reproduction script for the bug did not trigger it (its follow-up prompts
never took the batched path), so the evidence is the browser test and stop120k, which did.
