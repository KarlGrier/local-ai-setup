# v0.1.39 → v0.1.40.1: every default and setup change (Round 14 step 1)

Source: `git diff v0.1.39 v0.1.40.1` (307 + 7 commits, 278 files), the `Options` struct, every new `STRATA_*` read
(results/r14/v040-env-reads.txt, 91 new names, none removed), `arch_defaults.cpp`, setup.py, serve/server.py.
"Here" = this PC: CUDA, RTX 5080 (sm_120) + RTX 4060 Ti (sm_89), Ryzen 9 9950X3D (AVX-512, AVX-VNNI, AMD), Linux,
THP `madvise`, IQ3_S file, my config (configs/Cstar131.json).

## Engine options (`Options` struct, generate.cpp)

No existing default changed. New, all off / empty by default:

| option | default | what |
|---|---|---|
| `--kv-grow` | off | elastic K/V (VMM), off with a warning under --batch / --vram-elastic / --peer-device |
| `--host-core first\|last` | "" | the host thread's core (fork 5137b33) |
| `--vram-reserve-later-mib` | −1 | reserve on later cards of a layer split |
| `--batch-mtp` | off | MTP inside --batch slots |
| `--spec-follow`, `--window-hashes` | "" | test tools (fork) |
| `--adapt-async` | 0 | asynchronous adaptive tier |
| `--session-min-free-mib` | 4096 | session files' RAM floor |
| `--prompt-cache-tail` | off | tail checkpoint kind |
| `--pipeline-windows` | 0 | layer split: pipelined verify windows |
| `--lookup-chain`, `--lookup-chain-min` | 0, 3 | prompt lookup chained after the MTP drafts |
| `--mtp-hnorm stream` | off | |
| **`--mtp-q4 all\|proj\|head`** | "" | **4-bit drafter projections / head — lower precision, off, not used** |
| `--mtp-draft-vocab FILE` | "" | another draft vocabulary |
| `--remote-expert-opt` | **off** (unchanged) | only setup adds it, on 2+ GPUs, as in v0.1.39 |
| `--kv k8v4` | not chosen | now streams with --kv-resident; my config stays `--kv int8` |

## New STRATA_* switches that are ON by default here (CUDA)

| switch (off value) | origin | what | effect on my outputs (stock exact7) |
|---|---|---|---|
| `STRATA_HEAD_MIX_MULTI` (=0) | F7, fork 2ec7a80 | the final mixer for the window's tokens in one `fused_gr_read_multi` (also the drafter's) | **rounding-level: sampled math differs from token 958; the only output change** |
| `STRATA_NO_MULTI_GR` (=1 = off) | #783 PR-g | multi-token HC read/write, exact-T GR | none (7/7) |
| `STRATA_NO_BATCH_KV_STEP` (=1) | #783 PR-d | window K/V + indexer append in one launch | none |
| `STRATA_NO_NORM_ROPE` (=1) | #783 PR-f | per-head RMSNorm + RoPE in one launch | none |
| `STRATA_NO_SUB16_GU` (=1) | #783 PR-h | 16-lane sub-warp expert gate/up (n_embd 2560) | none (and bypassed by PR245 in our build) |
| `STRATA_NO_MMVQ_ROWS2` (=1) | #783 PR-h | two rows per block in the dense MMVQ | none |
| `STRATA_ONE_TOKEN_COMMIT` (=0) | F7, fork 235784c | a one-token window commits itself | none |
| `STRATA_MULTI_BLOCK_ARGMAX` (=0) | F7, fork fbb8bfa | head argmax / draft top-prob over many blocks a row | none |
| `STRATA_MTP_SHARED_BRANCH` (=0) | F7, fork d3d48b1 | the drafter's shared expert on a branch | none |
| `STRATA_QSA_EARLY_EXIT` (=0) | #783 PR-a | QSA block-score early exit | none |
| `STRATA_SH_FORK_LATE` (=0) | #783 PR-j | the shared expert forks after the doorbell when CPU experts are in the window | none |
| `STRATA_MTP_CATCHUP_ALL` (=1 = old) | #783 PR-i | the drafter's catch-up skips rejected rows | none |
| `STRATA_NO_AVXVNNI` (=1) | b211ba1 | AVX-VNNI forms of the CPU i-quant / IQ4_NL rows (Zen 5 has AVX-VNNI) | none |
| `STRATA_MTP_PRIORITY` (=0) | | drafter stream priority | none (timing) |
| `STRATA_S2_SWIGLU_Q8` (=0) | #783 PR-k | S2 (Q2_0) experts only | inert (IQ3_S) |
| `STRATA_TOPK_STREAM` (=0) | #743 | Turing prefill only | inert |
| `STRATA_READ_AHEAD` (=0), `STRATA_FILL_AHEAD` (=0) | #699-like | start-up read-ahead / profile fill advice | load only |
| `STRATA_IQ256_GATHER` auto | a733617 | gathered IQ decode on Intel P-cores | off here (AMD) |
| `STRATA_LFUSE_GATE/PAIR`, `STRATA_PF_BK64`, `STRATA_WMMA_BF16` | | sub-switches of opt-in paths | inert |

Bisect (results/r14/s1-bisect.txt): all of the above off → v0.1.39's exact7 hash a10f2135; HEAD_MIX_MULTI alone
decides it.

## Opt-in only (off here): gfx1151 arch defaults and the rest

arch_defaults (applied only when the device is gfx1151): GDN_HEAD, GDN_PP=2, GDN_CONVL2, GDN_NOY, CVEC_FUSE, HCD_EXACT,
PF_PAD, Q8_PACKED, Q6_PACKED, MMVF_ROWS, ATTN_LANECELL, EXPERT_V2, TSUM, LFUSE, GDN_SPLIT, QFUSE, PLE_BATCH, SH_STREAM.
Other opt-ins: ADAPT_LAG (=2), DISJOINT_ADAPT, DMA_BATCH (1/2), EXCHANGE_ROTATE, KV_PREFETCH, PREFILL_EQUAL,
DEFERRED_REGISTER, FILE_RELEASE (Windows), IQ3S_MT1, Q2_BITPLANE, DENSE_MMQ (HIP), HIP_*, PF_* (gfx11), WMMA_GEMM,
PA_FAST, HC_Q8 / HC_Q8_INJECT (**Q8 activations for the HC read: lower precision, not used**), HC_UPMIX, MMQ_RESIDENT_SORT_NE,
CACHE_MESSAGE_BOUNDARY, OWNED_PRICE, KV_GROW*, BATCH_MTP, MTP_FULL_HEAD, MTP_TOP2, LOOKUP_CHAIN_FIXED, test hooks.

## Server (serve/server.py, frontend.py)

Session files (`--slot-save-path DIR` / config `slot_save_path`; POST /slots/0?action=save|restore), reasoning-loop
recovery (`reasoning_loop_recovery`, default false), `return_progress`, `strata_checkpoint: false`, "Connection: close"
on every response, completed empty assistant turns skipped (`STRATA_KEEP_EMPTY_TURNS=1` restores), JSON extracted from
prose / code fences in json_object mode, json_schema unions, tool_choice "required" / named, namespace__name mapping,
a tool call in a code fence or in the thinking is text unless it was an act (#1058, #804), #1012 restart / admission
fixes, #553 image sources (/v1/responses refuses another origin's file image), #879 Stop during the prompt read, #931
control-token text, #454 stop strings, #700 tool tags, Claude Code's billing stamp pinned (cache reuse).

## Setup (setup.py)

MIN_ENGINE 0.1.40 (#848 split + resident, #711 K8V4 streaming); `kv_streaming_wanted` / `low_ram_wanted` as functions
(k8v4 streams when chosen); Strix Halo (gfx1151) recognised, UD-IQ4_XS recommended there; bench-data tips (tips only:
RESIDENT_HEADROOM, --conversation-cache-mib for several agents, CPU vision on small cards); 200K context step never the
recommendation; the shared Chat settings file is not a model config; --rollback-engine; the user's --expert-profile kept
on update; pack rebuilds pass --force. **The --remote-expert-opt rule (2+ GPUs) is unchanged from v0.1.39** and no
setup path picks a lower-precision KV or drafter by itself.
