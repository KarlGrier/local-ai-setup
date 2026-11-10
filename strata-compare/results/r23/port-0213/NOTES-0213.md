# v0.2.13 groundwork (Karl 11-09) - desk and CPU only, through nogap-run; nothing replaces P028x

Karl 11-09: "v0.2.13 added Qwen4 groundwork. Desk and CPU work only, through nogap-run; nothing replaces P028x. ...
Don't interrupt this morning's post-Phase-5 gaps for any of this."

v0.2.13 = d2f096475: 212 commits after v0.2.12 and 813 files. The Qwen4 parts (compiled geometry, intake tool,
vendored ggml, the #5327 arena change) are all new in v0.2.13. A stock worktree is at **strata-v0213stock**
(detached, clean). The intake tool runs from it, never from our patched tree.

## 1. Qwen4 watch: upstream's intake verdict in the alert (DONE 11-09 07:22, tested 07:43)

- **The hook: work/qwen4-kit/intake_hook.py.** The HF watch (dayone.py, backup `dayone.py.before-intake`) calls it
  when it alerts on a Qwen4 repo with GGUF files. It runs `tools/qwen4_intake.py --hf REPO --rev SHA` (header-only
  range reads, no download) through work/r23/nogap-run.sh.
- **The alert:** the body starts with the verdict, e.g. `intake case B: n_embd 3072, n_head 32, ...`, cut to 72
  characters so it survives alert-push's 180-character limit. The NOTES line carries the full text: each set's case,
  every shape field with what the kernels were built for, up to 3 blockers, and the warnings.
- **No gap open:** the intake runs inline, in that alert.
- **A gap open:** the alert goes out at once, saying "intake after the open gap (2nd alert)". A transient user unit
  then runs the intake through nogap-run and sends a second alert, "Qwen4 intake verdict".
- **Not read:** a gated or private repo (no login, nothing worked around), and a repo without GGUF files.
- **Bug fixed on the way:** alert-push drops every word with a slash, so `unsloth/Qwen4-...` never reached the phone.
  The alert now writes `unsloth Qwen4-...`.
- **Tests (results/r23/port-0213/intake/light.log):**
  - upstream's tools/test_qwen4_intake.py: 32 tests, OK (1 skipped: the live-HF class);
  - intake_hook selftest: 19 / 19, including the runner through the real nogap-run and the gap-open path;
  - a synthetic dry poll of the real watcher: the gap-open path and the inline path both give the right alert text;
  - our files:

| input | verdict |
|---|---|
| ISTA IQ3_S (local, 2 shards) | case A, runs now on cuda, hip, sycl, metal |
| UD-IQ3_XXS, UD-IQ2_XS (v3.1 header stubs) | case A |
| UD-Q2_K_XL, UD-IQ3_XXS (pre-v3.1 header stubs) | case A |
| MTP drafters (stubs) | "a separate MTP drafter file, not a model" |
| DeepSeek UD-Q8_K_XL (local, 9 shards) | case C: architecture deepseek41 is strata-dsv41; tokenizer pre 'joyai-llm' |
| unsloth/Qwen3.8-Flash-Next-GGUF UD-IQ3_XXS folder, **--hf** at d96201194f10 | case A (headers 2.1 s) |

  The unsloth Flash-Next GGUFs themselves were deleted earlier (11-06), so their saved header stubs stood in. The
  `--hf` run shows the real watcher path works.

## 2. Shape readiness of our patches

Desk audit of the 29 commits (v0.2.11..r23-port0211), by a read-only helper: results/r23/port-0213/SHAPES-AUDIT.md
(12 findings, plus 4 places where upstream's own constant now comes from the geometry). The per-shape outcomes are
worked out by hand; the builds below confirm them.

| finding | our patch | Flash-Next value assumed | q4_mid / q4_big | q4_deep |
|---|---|---|---|---|
| F1 | 18 GR_FORK (fused_gr.cu:2823) | DG 4 x DS 20 tiling of n_embd x hc, static_assert at file scope | **build break**, even with the switch off | ok |
| F2 | 18/19 GR_FORK scratch | kGrForkScratchFloats = 26,368 (by hand) | out of bounds once F1 is generalised (needs 37,792 / 67,008) | ok |
| F3 | 18 gr_up_fork | hc_lr steps | ok | ok |
| F4 | 20 patch guard | checks n_embd / hc / hc_lr | ok, but cannot see F1 | ok |
| F5 | 23 PREFILL_V2 (moe_fused_iq.hpp:63) | kV2Embd 2560, kV2FF 640 vs v0.2.13's geometry-derived K | **build break** (CUDA) | ok |
| F6-F8 | 23 PREFILL_V2 (moe_fused_iq.cu:1309, 1544, 1561) | NFB 1280/2560, H row stride 10 x AB, down stride x 2560 | **wrong results** if only F5 is relaxed | ok |
| F9 | 20 patch_guard_test | test cases at 16 q-heads per KV head and n_embd 3072 | test fails (they are the compiled shape there) | ok |
| F10-F12 | 20, 1, 24 | qsa_interval; side stash cells x 144; vocab bound | ok | ok |

q4_deep (Flash-Next at 64 layers) is clean in all 29: no patch of ours pins the layer count.

### Proposed fixes (read the compiled geometry; Flash-Next code unchanged)

- **F5-F8, PREFILL_V2 (generalise, recommended):**
  - kV2Embd = kCompiledGeometry.n_embd, kV2FF = kCompiledGeometry.n_ff;
  - NFB = GU ? 2 * n_ff : n_embd;
  - H row stride = n_expert_used x AB;
  - down row stride x n_embd.
  This is the same set of literals upstream replaced in its own kernels in b273c8006. Check: the default build's SASS
  identical to the unfixed port's for these kernels.
- **F1/F2/F4, GR_FORK (Karl's choice; see "Decisions"):**
  - (a) **Flash-Next only for day one (recommended):** the fork's tiling and its static_assert under
    `if constexpr (fork_tiling_fits(kCompiledGeometry))`. At another shape the fork is compiled out, and the guard
    refuses STRATA_GR_FORK=1 with a plain line, so upstream's read runs.
  - (b) **Generalise:** DS = ceil(n_embd x hc / (DG x 128)) with the padding rows masked, and the scratch computed from
    the geometry and rounded to 256 (Flash-Next keeps 20 x 4 and 26,368). Bits against upstream's read and speed at q4
    shapes are untested, so (b) needs the shape gap's parity and speed rows.
- **F9:** the guard test takes its "wrong shape" values as compiled + 1 / x 2, so they never equal the compiled shape.
- **F11:** the side stash's q4_0 bytes `cells * 144` (head_dim 256's q4_0 row) becomes
  `cells * kv_q4_bytes_per_head(head_dim)`. geometry_checks pins head_dim = 256, so it is cosmetic today.
- **F12:** `static_assert(kCompiledGeometry.n_vocab <= 262144)` beside the sampler's bound, or the guard as it is if the
  load check does not enforce n_vocab (open).
- **Test only:** our v2 block in prefill_fused_iq_test against upstream's new `--edge` cases: `std::min(20, E - 1)` and
  `ZERO >= 0`, as upstream does.

The served config turns every one of our switches on (SPEC_EXACT, ROUTER_Q8K, GR_FORK, COST_GATE, DRAFT_CUM,
PREFILL_V2). So on a new-shape day-one engine, (a) means GR_FORK falls back to upstream's read: correct, but slower
on the hyper-connection read until (b) is tested.

## 3. Port notes for v0.2.13

- **GDN_TC / CONVL2: our values stay the same.**
  - `apply_gdn_defaults_cuda(true)` (generate.cpp:3886) sets STRATA_GDN_TC=1 and STRATA_GDN_CONVL2=2 on every Linux CUDA
    start, before the engine reads them. It does **not** look at STRATA_DEFAULTS=026, so the 026 pin does not stop it.
  - A value the user set wins (arch_defaults.cpp:233, =0 included). Our port configs (P0211x, P0211x-h) pin both to 0
    explicitly. P028x has no pins, but runs a v0.2.8 engine without the default.
  - **So the v0.2.13 port config must keep the explicit =0 pins**: the 026 pin alone would leave them on.
- **HC_Q8: our values stay the same.**
  - The engine now turns STRATA_HC_Q8 on by default on CUDA when the GGUF carries the hyper-connection projections as
    Q8_0 (generate.cpp:4439, `gguf_carries_q8_hc`).
  - Our ISTA IQ3_S carries all 192 (blk.*.hc_{attn,ffn}_{down,up}) as **BF16** (header read 11-09), so it stays off.
  - A UD config on v0.2.13 would get it on, which is a rounding-level change. Pin STRATA_HC_Q8=0 in any UD config
    until gated.
- **The parallel stack (new in v0.2.13):** `apply_parallel_defaults_cuda` acts only with 2 or more batch slots. Ours run
  1 (no --batch), so nothing changes.
- **STRATA_MANIFEST cannot confirm all three.** At v0.2.13 it records HC_Q8 (path "dense"/"hc_q8") but not GDN_TC or
  CONVL2. Proposed: a 2-line diagnostic in our port (`M.path("prefill", "gdn-tc" / "gdn-convl2", ...)`, written only
  with STRATA_MANIFEST set, output-neutral). The confirmation itself (one manifest per arm start) needs an engine
  start, so it goes into the shape gap below.
- **Retired switches:** STRATA_GR_Q32_PL (64fac3177), STRATA_DF2_GATE and STRATA_DF2_ROW_MS (e62f3c1ff) are in none of
  our configs, launchers or scripts.
  - GR_Q32_PL was upstream's own arm, in fused_gr.cu at v0.2.11, beside our GR_FORK hunks. Expect a context conflict
    there.
- **ggml move:** none of our 29 patches touches ggml sources. v0.2.13 builds from third_party/strata-ggml by default,
  so our build script drops -DSTRATA_GGML_DIR. Our 4 CMake hunks move:
  - patch_guard.cpp -> cmake/strata_gpu_engine.cmake:289;
  - patch_guard_test -> strata_gpu_engine.cmake:1048;
  - prefill_fused_v2_test -> cmake/backends/cuda.cmake:285;
  - cost_gate_test / draft_cum_test -> cmake/backends/cpu.cmake.
  Our `experts_native` v2 dispatch hunk must be redone by hand (b273c8006 rewrote its context).
- **#5327, STRATA_ARENA_FILE_CACHE (recommend pinning =0 in the port config):**
  - v0.2.11: an expert-arena shortfall (MemAvailable below the arena after the 20 s wait) reads the experts from the
    file.
  - v0.2.13 on Linux: if free pages + droppable file cache + free huge pages cover it, it loads the arena anyway
    (warning on stdout too), evicting the cache as it reads.
  - Normal starts are unchanged.
  - Here the shortfall case is an 8080 start beside something still exiting, or a gap start. Loading anyway can leave
    MemAvailable near zero, under our 12 GB guard floor (the guard then stops the engine) or into swap. The file read
    is slower but keeps the floor.
  - Pinning =0 keeps v0.2.11's behaviour, as the port rule does for new defaults. Adopting it would be a gate decision.

## Karl's decisions (11-09) - FIXED for the port

> "1. GR_FORK: (a). Flash-Next only on day one, compiled out at other shapes so upstream's read runs. Generalise later,
> once the real Qwen4 shape is known, if its measured gain on Flash-Next makes it worth it. Yes to generalising
> PREFILL_V2 the way upstream fixed its kernels.
> 2. Pin STRATA_ARENA_FILE_CACHE=0 in the port config: yes."

So the port carries:
- GR_FORK option (a), the fork compiled out at other shapes, with the guard refusing it;
- PREFILL_V2 generalised (F5-F8, as b273c8006);
- F9 / F11 / F12 as proposed;
- STRATA_ARENA_FILE_CACHE=0 and the explicit GDN_TC / CONVL2 =0 pins in configs/P0213x.json (made from P0211x.json);
- the 2-line STRATA_MANIFEST diagnostic for GDN_TC / CONVL2.

## Decisions asked (11-09, answered above)

1. GR_FORK at new shapes: (a) Flash-Next only for day one (recommended), or (b) generalise now and test it in the
   shape gap.
2. STRATA_ARENA_FILE_CACHE=0 in the v0.2.13 port config (recommended), or adopt #5327's load-anyway.

## Still to do (after the post-Phase-5 chain, under nogap-run)

- The branch r23-port0213 (v0.2.13 + the 29 from r23-port0211, cherry-picked in order).
- Builds: work/r23/build-port0213.sh `engine`, then `geo q4_mid`, `geo q4_big`, `geo q4_deep` (ninja -k 0; the error
  list per shape in results/r23/port-0213/geo-<shape>.txt).
- The shape gap plan (not queued).

## Port state and the shape list (2026-11-09 13:55)

**Branch r23-port0213 = v0.2.13 (d2f096475) + 34 commits**, head 43ef724a1:
- the 29 from r23-port0211, each with "changed lines identical". Five conflicts were resolved: 13, 20, 23, 26 and 27
  (see NOTES.md 11-09 12:32);
- 30 = the mismatch guard (019b04dd2 -> 081a6966d);
- A 8845ede61, B b9518356c, C 622df2ff6, D 43ef724a1.

Author and committer are KarlGrier noreply on every commit, with no Claude lines. The test config is configs/P0213x.json.

**Builds** (work/r23/build-port0213.sh, nice 19, 2 jobs):

| build | before the fixes (29 commits) | after (34) |
|---|---|---|
| engine, flash_next | rc 0 | rc 0: engine-r23p0213/strata 420a0efbd202 |
| tests | rc 0 | rc 0 |
| geo q4_mid | **rc 1**: fused_gr.cu 2846 "down geometry", 2849 "fork scratch", moe_fused_iq.cu 1342 "kV2Embd / kV2FF" (results/r23/port-0213/asis/geo-q4_mid.txt) | rc 0, 0 errors: engine-r23p0213-q4_mid 0f4569a86f60 |
| geo q4_big | (not built) | rc 0, 0 errors: engine-r23p0213-q4_big fefc372a4426 |
| geo q4_deep | (not built) | rc 0, 0 errors: engine-r23p0213-q4_deep 0c09d51ed2a0 |

The per-shape engines are for the shape gap only and are never served. Note on the after-fix geo builds: they first
returned 1 because of a bug in my own report step (an empty error list under `set -e` / pipefail). It is fixed in
build-port0213.sh, and the three builds were then recorded with RESUME=1, with nothing left to compile.

**CPU tests** (GPUs hidden, flash_next build-tests): cost_gate_test, draft_cum_test, spec_prob_test (72 cases),
gated_proposal_test (266 checks), gguf_geometry_test and patch_guard_test on the real ISTA headers all pass, with 0
failures. The new F9 offset cases are among them. The serve parser tests pass. test_server has 1 failure,
test_hip_ordinal, which stock v0.2.13 fails too.

**Our patches that assumed Flash-Next sizes, and where they stand** (details in SHAPES-AUDIT.md):

| finding | patch | assumed | now |
|---|---|---|---|
| F1 / F2 | GR_FORK (18, 19) | n_embd 2560, 4 streams, low rank 320 (tiling, scratch 26,368) | built for that shape only (A): off elsewhere, with the guard's reason; q4_deep keeps it |
| F4 | gr_fork guard (20) | the fork's compiled shape | + "not built for this shape" (A) |
| F5-F8 | PREFILL_V2 (23) | K 2560 / 640, 1280 / 2560 items, 10 x AB H stride, 2560 down stride | from the compiled geometry (B); kV2Shape gates other shapes |
| F9 | patch_guard_test (20, 23) | synthetic cases = Flash-Next values | offsets from the compiled shape (C) |
| F10 | side_mixer guard's 4 | qsa_interval | shape-free (no change) |
| F11 | side stash / chat cache (1, 2) | q4_0 row = 144 B | kv_q4_bytes_per_head (C) |
| F12 | SPEC_EXACT (24) | vocab <= 262,144 | the guard refuses above it (C) |
| R1-R4 | constants upstream now derives | - | follow upstream after the rebase |

## The shape gap (PLANNED, not queued; needs Karl's go)

**Purpose.** Show that our patched v0.2.13 port runs at upstream's synthetic shapes. Nothing is switched, and P028x stays
served.

**At the desk, before the gap** (no GPU; under nogap-run; disk about 25 GB):
1. One synthetic model per shape, written with `tools/q4geo_synth.py --shape S --layers 4 --tokenizer-from <ISTA shard 1>
   --header H.hpp --out models/q4geo/S-4l.gguf`, upstream's way (its install gate uses q4_lite with few layers).
   - Estimated sizes, 4 layers, ud-q4k: q4_mid ~5 GB, q4_big ~14 GB, q4_deep ~3 GB.
   - Full-layer files would be ~64 / ~216 / ~50 GB.
2. One engine per shape from its header: `-DSTRATA_GEOMETRY_FILE=H.hpp`, giving engine-r23p0213-S-4l (about 10 min each).
   The kernels' shapes equal the full builds'; only the layer count differs.
3. `patch_guard_test S-4l.gguf` on each 4-layer build (CPU).

**In the gap** (8080 down; about 45-60 min):
1. Upstream's geometry parity programs from each full-shape build (build-q4_mid / -q4_big / -q4_deep):
   - gguf_geometry_test, prefill_fused_iq_test (+ `--v2` and `--edge`), prefill_fused_moe_test;
   - native_dense / expert / grouped_parity, gdn_parity;
   - gr_parity and gr_multi_parity (+ STRATA_GR_FORK=1 at q4_deep only);
   - qsa_parity, qsa_prompt_attn_parity, router_top10_parity, shared_expert_parity, verify_parity, spec_verify_parity.

   Each runs with a timeout. The record is PASS / SKIP (77) / FAIL. The same programs from the flash_next build go first,
   as the reference row.
2. A smoke start per shape: engine-r23p0213-S-4l on S-4l.gguf with `--no-ple`, following upstream's gate step 5. It sends
   one chat request at T 1.0 / 0.95 / 20 / min-p 0.05 and checks:
   - the start, a finite answer, and no fatal or stall line;
   - the guard lines: gr_fork OFF with the reason at q4_mid / q4_big and available at q4_deep; prefill_v2 per kV2Shape;
   - STRATA_MANIFEST's gdn_tc / gdn_convl2 lines.
3. A kernel check after each part, and port_gap4 begin / end as in every gap.

**Verdict.** It is informational, with no switch: per shape, "builds, its parity programs pass, it loads and answers".
Any FAIL is listed with its program.

**After it:** the synthetic files can be deleted (about 25 GB). They are listed for Karl's OK; nothing is deleted
without it. Then ADAPT_FETCH's gap is queued (Karl 11-09).

**Karl 11-09 ~14:15: the shape gap GO, as planned** (desk prep first, then the gap at the next clean boundary; information
only).
- Afterwards, delete the synthetic models without asking. Keep the generator script and its exact command so they can
  be remade.
- Keep the per-shape engine builds only if they are small; otherwise delete them too.
- Then queue ADAPT_FETCH's gap.
- **Priority rule:** if the Qwen4 watch finds open Flash weights before ADAPT_FETCH's gap runs, hold that gap and do the
  day-one work first. Qwen4 is rumoured for Tuesday night or Wednesday, so the shape gap should be done before then.

**Shape gap: what changed from the plan, and the review (11-09 15:2x)**
- The helper's choices, accepted by Claude:
  - the synthetic files use the **fused-iq recipe**, not ud-q4k: IQ3_S / IQ4_NL plus IQ4_XS / IQ4_NL experts, so
    PREFILL_V2's generalised kernels and PF_FUSED actually run (ud-q4k has no IQ3_XXS / IQ4_NL, so v2 would be off);
  - **--small-ple, with the smoke started PLE on**, upstream's install gate's way, and **once more with --no-ple only if
    the PLE-on start fails**;
  - **no STRATA_GR_FORK=1 parity runs**: gr_parity compares the fused read bit for bit with the single-token read,
    which never forks, so the fork would fail it by design. q4_deep's smoke runs P0213x's GR_FORK=1 instead;
  - **a CLI probe per shape** for the guard lines (a served start drops the engine's stdout up to READY).
- Peak disk is ~34 GB (the real 248,320-token vocabulary). The 4-layer engines are 0.22 GB each, so cleanup keeps them.
- **One fresh reviewer: 3 must-fix items, all fixed** (gap-shape0213.sh, backup .before-review1109; the mock test
  still passes):
  1. A served start cut by `timeout` before 8081 listened left the guard, server.py and the monitor holding the test
     lock, so strata-ensure would refuse and 8080 would not come back. Now `test_cleanup` runs after every served run
     (and in the signal handler), and a `lock_sweep` before port_gap4 end kills or names anything of this gap still
     running or holding the lock.
  2. A hung nvidia-smi could hold 8080 down with no alert. Now every query runs under a 20 s timeout and a failure is
     taken as "not clear", and a watchdog sends one critical alert if the gap is still open 20 min past its deadline.
  3. Any argument other than `--dry-run` / `--mock` used to run the real gap. Now it refuses.
- Minor items also fixed:
  - the served start needs 6 min left, and a cut is reported as a cut;
  - patch_guard_test runs inside the deadline;
  - begin's cap is MAXM + 25 and SG_MAX_MIN is capped at 90;
  - a second instance refuses;
  - the research-queue hold is removed only if it is ours;
  - the tree is re-checked after begin's wait;
  - the engines-left path exits 2;
  - the signal handler says whether 8080 listens;
  - cleanup --go needs a DONE result (or SG_FORCE=1).
- Not changed: the derived-config check stays a blacklist (today's config is clean: every model path under models/q4geo,
  port 8081, no served path); the shared-lock race between two gap drivers is port_gap4's (queue no other gap until
  this one ends).

## Upstream test bugs found in the shape gap (11-09); issue draft ISSUE-DRAFT-geometry-tests-1109.md (not posted)
- **src/kernels/gr_parity.cpp** (identical to v0.2.13) hard-codes Flash-Next's N 2560 / HC 4 / LR 320 in
  fused_multi_lds_parity and in its real-dimension section, while the fused read is compiled for the build's shape.
  - q4_big: it read past its buffers, an **NVRM Xid 31 MMU fault** (15:56:43; harmless, Karl 11-09).
  - q4_mid: 6 wrong results.
  - **Fixed on our branch, test only:** commit 66d4f9b65, sizes from kCompiledGeometry. The builds were re-recorded at
    that head with RESUME=1 (ninja recompiled gr_parity only; the engines are unchanged).
- **tests/core/gguf_geometry_test.cpp** (identical to v0.2.13) builds its fixture from Flash-Next's keys. At q4_mid /
  q4_big the unchanged fixture already mismatches, so 4 refusal cases name the wrong key. **Not fixed**: recorded as
  upstream's.
- **Our own smoke-config bug:** shape_rules.py dropped --spec, and a native pack needs --spec T >= 2. Fixed: --spec 2
  (backup shape_rules.py.before-spec1109).
- **The rerun** (Karl 11-09; unit shape-gap0213 from 16:28):
  - SG_STEPS = q4_mid parity, q4_big parity, the three smokes, q4_deep parity. The first run's flash_next row (84 pass /
    1 skip / 0 fail) is in shape-gap-prev-1109-162804.
  - **Any new kernel error stops at once and brings P028x back** (new in the driver, mock-tested; backup
    .before-rerun1109).

## SHAPE GAP RESULT (11-09; information only, nothing switched; P028x stays served)

There were three runs, each kept in its own folder:
- **Run 1** (15:38-16:03, stopped by Claude after the Xid 31; results/r23/port-0213/shape-gap-prev-1109-162804/):
  flash_next only.
- **The rerun** (16:28-17:02, 8080 down 32 min; shape-gap-prev-1109-170359/): the q4 parity rows.
- **The smoke follow-up** (17:04-17:08, 8080 down 2 min; shape-gap/).

No kernel error in the rerun or the follow-up; the kernel check after each passed.

| shape | build | parity programs (ctest GEO + 3 direct) | smoke: loads and answers | guards / manifest / env |
|---|---|---|---|---|
| flash_next (ref) | rc 0 | 84 pass / 1 skip / 0 fail (run 1) | - | - |
| q4_mid | full rc 0, 4-layer rc 0 | 83 / 1 / 1: gguf_geometry_test (upstream) | yes | as expected; GDN pins 0 / 0; env OK |
| q4_big | full rc 0, 4-layer rc 0 | 83 / 1 / 1: gguf_geometry_test (upstream) | yes | as expected; 0 / 0; OK |
| q4_deep | full rc 0, 4-layer rc 0 | 83 / 1 / 1: gguf_geometry_test (upstream) | yes | as expected; 0 / 0; OK |

- **gr_parity passes at all three q4 shapes** with the test-only fix 66d4f9b65. Before it: the Xid 31 at q4_big and 6
  wrong results at q4_mid.
- **The guards:** gr_fork OFF with "built for Flash-Next's 2560 / 4 / 320 only" at q4_mid and q4_big, available at
  q4_deep; prefill_v2 per kV2Shape.
- **The smoke's two fixes of our own config:**
  - --spec 2: a native pack needs T >= 2;
  - the 5080's cache at half the expert pairs: with 4 layers it took them all, and the engine exited "CUDA1 experts: no
    unclaimed experts remain".
  - The helper then took 460 / 919 / 919 experts, so the 4060 Ti's kernels ran at the new shapes too.
  - Each smoke answered one chat: 32 tokens, finish length, random weights.
- **What it shows:** our patched v0.2.13 port builds, passes upstream's geometry parity programs (bar upstream's own
  shape-unaware gguf_geometry_test) and loads and answers at q4_mid, q4_big and q4_deep. GR_FORK is Flash-Next-only as
  decided, and PREFILL_V2 is generalised.
- **Cleanup (Karl's OK):** 37.67 GB freed: the synthetic models, their packs and every per-shape build directory.
  - Kept: the engine copies (0.22 GB each; engine-r23p0213-{q4_mid,q4_big,q4_deep}[-4l]),
    work/r23/shape-gap/q4geo-commands.txt and geo/*.hpp, so the models can be remade.
- **Issue draft (not posted):** ISSUE-DRAFT-geometry-tests-1109.md.
