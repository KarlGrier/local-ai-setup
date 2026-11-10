# Basalt 0.2.0: exact output head behind BASALT_EXACT_HEAD (11-02)

Patch: `patches/exact-head.patch` (sha256 72134e23476982f203beae5e754e332c0c8d1df491dd866119c418ea9916d39d), against
v0.2.0 = f0bb833c. 7 files: 1 new header, 6 small edits. `git apply --check` and `patch -p1 --dry-run` pass against the
tag. **Nothing was built or run.** `src/` is untouched (`git status` clean). The work copies are in `patches/work/{orig,new}/`.

Our pack's head is **Q6_K**: meta says `output.weight` Q6_K, 2560 x 248,320, 521,472,000 bytes. The engine log
of the 11-02 runs agrees ("native head: Q6_K"). So the shortcut that matters here is `q6k_vhead`.

## 1. Where the two-stage head decides tokens or logits (v0.2.0 line numbers)

The output head is computed in exactly one place: `Verifier::WindowRecorder::head()`,
src/core/verify/record_head.cpp:22-147. It is captured into every verify-window graph: solo `exec_[T]` /
`exec_nr_[T]`, the batch graphs `exec_bm_`, every T from 1 to 8. All of them are captured before READY
(serve/verify.cpp:162-166, `warm_graphs`). The batched prompt path (src/prefill/*) has no head.

Decode, spec decode, the plain step (`--spec 1` is still a 1-token window), prompt parts read through windows,
batch slots and scored requests all launch these graphs. Inside head():

| Line | Head | When |
|---|---|---|
| 118-120 | **q6k_vhead**: all 248,320 rows from the 2-bit copy (198.7 MB) on int8 MMA. Rows within 4 (VDELTA) of the 64th-best (VKEEP) approximate score are rescored exactly, up to VCAP = 65,536 rows per call over all T columns (q6k_head.cu:350-356, 580-587, 609). Every other row keeps its approximate logit. | Q6_K head, copy packed (native_head.cpp:103-116), scratch allocated (lifecycle.cpp:249-250): **always on our pack** |
| 121-122 | q6k_head_mmvq: every row exact. It is bitwise the same as native_mmvq type 14. | Q6_K with no 2-bit copy (the allocation failed) |
| 82-95, 125-127 | q80p_vhead with device word k (head_keep_d_). k = 0 means every row exact. | Q8_0 bit-plane head only (NVFP4 pack) |
| 140-143 | greedy argmax over head_logits_, inside the graph | gives `out[]` for greedy requests and prompt windows |

The exact re-run and the keep word:

- `head_keep()` / `set_head_keep()` (sampling.cpp:41-60) do something only when `head_keep_d_` exists. It is
  allocated for a Q8_0 head alone (lifecycle.cpp:251-254). **For a Q6_K head the keep value is ignored**: q6k_vhead has
  no k (its K is fixed at 64), and `head_screened_` stays false.
- So on our pack `copy_logits` (ppl rows, logit hash, top-k log: sampling.cpp:138-144) and `resample_row` (grammar
  re-draw: sampling.cpp:104-108) run **no** exact pass. They read the two-stage logits, approximate tail included.
- The only exact pass is `exact_head_rows` (sampling.cpp:71-93): q6k_head_mmvq over the same columns. It is called only
  for a *sampled* request whose list is wider than 64 entries (execution.cpp:155 and 385; batch_execution.cpp:289-297).
  That means top_k 0 or above 64, or a sampled request that sends no top_k (request_parse.cpp:21-23: an absent
  top_k means the whole vocabulary).
- Correction to REPORT.md section 4 (taken from the docs' Q8_0 table): on the IQ3_S pack, logit_bias, penalties,
  grammar refusals, ppl scoring and batch slots all use the two-stage head. This fits the docs' own gate table,
  where the two-stage head adds about 0.0017 KLD.
- The head split by vocabulary is off whenever a Q6_K copy exists (head_split.cpp:73).

The MTP drafter has its own two-stage *draft* head (core/mtp/head.cpp:156-165, forward.cpp:329-339, head_proxy.cuh:17-20):
- It uses its own 2-bit copy of the draft vocabulary's rows. Rows within 5 of the best are rescored, at most 64.
- It decides draft tokens only. Verification decides the output, so it is not an output-head shortcut.
- The patch leaves it alone, so acceptance can move only through the verified tokens.

`basalt generate --no-capture` uses NativeHead::run, which is native_mmvq and already exact
(generate/token_path.cpp:141-146). Generate's normal path uses a Verifier (generate/decode.cpp:78), so the patch covers it.

What our runs hit (stock build, Q6_K):

| Run | Sampling | Head |
|---|---|---|
| bench conv, prose (bench_main.cpp:448-464) | T 0.6, top_p 0.95, top_k 20 | q6k_vhead in every window |
| bench struct | T 0 (greedy), top_k 20 | q6k_vhead, plus the graph's argmax |
| bench pp16384 / pp65536 (bench_main.cpp:915-921) | greedy, 32 / 1 new tokens | batched prompt (no head), then windows with q6k_vhead |
| bench --quality (ppl=) | greedy | q6k_vhead; the gate scores the approximate tail |
| `basalt serve`, our client (T 1.0 / 0.95 / 20 / min-p 0.05) | sampled, list of 20 | q6k_vhead in every window; no exact pass |
| a sampled request with top_k 0 / >64 / absent | wide | q6k_vhead, then the exact re-run |

## 2. The change

`BASALT_EXACT_HEAD` is read once, at the first window capture (before READY), in include/basalt/core/exact_head.hpp.

| Value | Effect |
|---|---|
| `=1` | record_head.cpp skips the q6k_vhead branch. The next branch, **q6k_head_mmvq**, takes the head (see below). |
| `=1` | `head_keep()` returns 0 first thing. For a Q8_0 head, q80p_vhead with k = 0 scores every row exactly, as logit_bias / penalty / batch windows already do. Returning 0 where stock returns 1 is safe: batch windows always run with 0, and `head_screened_` then stays false, so no second pass and no peer screen. For a Q6_K head it changes nothing. |
| `=1` | `exact_head_rows` returns early (the window is already exact). No redundant second pass for top_k 0 requests. |
| any other value | Default heads, but windows are counted (a control run). |
| unset | Every edited condition evaluates as in stock, the counters return at once, and nothing is printed: same outputs, same logs. |

Why the `=1` path is exact: q6k_head_mmvq is the engine's own exact kernel. It is the same kernel, on the same q8_1
columns, that the stock wide-list path (top_k 0) and the no-copy fallback use. It is bitwise equal to native_mmvq
(q6k_head.hpp:1-4). The xq_ input does not depend on the head.

Kept the same on purpose:
- The 2-bit copy stays allocated. VRAM, the expert-cache size, the "no head split" decision and the scratch arena
  are identical between arms. Only the kernel changes.
- No kernel was added or changed. The drafter, prefill and hc paths are untouched.

Proof that the exact path ran (counters):
- `head_rec_two_` (new Verifier member) is set when a graph records q6k_vhead.
- Each launched window that runs the head (solo: execution.cpp; batch: two places in batch_execution.cpp) is counted.
  It counts as two-stage if `head_screened_ || head_rec_two_`.
- `Runtime::shutdown()` prints the counts at QUIT, stdin EOF, or the server's SIGTERM-to-QUIT.

## 3. What could go wrong

- **Capture.** q6k_head_mmvq's first use calls cudaFuncSetAttribute and an occupancy query inside the capture. q6k_vhead
  does the same, and stock already captures this kernel at this spot (the no-copy fallback), so this is expected to
  work. A failure would show as `verify: end capture/instantiate` errors.
- **PDL.** The kernel is a plain launch, not PDL. Expect the "programmatic dependent launches" count per captured
  window to fall by 3 (201 -> 198, 274 -> 271) if that count is per launch_pdl call. This is not verified.
- **Rare token differences between =1 and unset are expected, not a bug.**
  - Two-stage top-64 recall is 99.97 % (docs).
  - VCAP is per call over all T columns. Struct's p99 is 12,790 rows per column, x 8 columns > 65,536, so the cap
    binds in some T = 8 windows.
  - Which rows the cap drops depends on atomic order, so the stock head can differ from run to run there.
  - Draft acceptance can move slightly with the tokens.
- **No report on a crash, `kill -9`, or the generate CLI** (that path prints the start note only).
- **The variable must be in the engine's environment.** basalt-bench and the HTTP server pass their environment to the
  engine child (posix_spawnp / execv with environ). Setting it after the start has no effect.
- **The cost is slightly overstated** for an exact-only engine. That engine would free the 198.7 MB copy, about 96
  more expert slots at ~2.06 MB per slot (+2 %).
- **The Q8_0 branch is untested here.** It is the same mechanism as upstream's logit_bias path.

## 4. Build (written down, not run; in a gap only, never during an LDR run)

```sh
B=/home/USER/ai-speed-testing/basalt-020
git -C /home/USER/ai-speed-testing/basalt-pr90 worktree add --detach $B/src-exacthead f0bb833c49a4290fcc28529df98ed9021ac0717f
git -C $B/src-exacthead apply --check $B/patches/exact-head.patch && git -C $B/src-exacthead apply $B/patches/exact-head.patch
git -C $B/src-exacthead status --short        # 6 M + 1 ?? (include/basalt/core/exact_head.hpp)
setsid nohup $B/scripts/build_memguard.sh 7200 > /dev/null 2>&1 < /dev/null &   # its glob basalt-020/src* covers src-exacthead
export HOME=$B/home
unshare -rn nice -n 5 cmake -G Ninja -S $B/src-exacthead -B $B/src-exacthead/build -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc -DPython3_EXECUTABLE=$B/venv/bin/python > $B/logs/build-exacthead-configure.log 2>&1
unshare -rn nice -n 5 cmake --build $B/src-exacthead/build -j ${BUILD_JOBS:-16} > $B/logs/build-exacthead.log 2>&1
echo "basalt f0bb833c + patches/exact-head.patch (72134e23), built $(date '+%F %T') (CUDA 13.3, arch 120, offline)" > $B/src-exacthead/bin/SOURCE
sha256sum $B/src-exacthead/bin/basalt $B/src-exacthead/bin/basalt-bench $B/src-exacthead/bin/basalt-probe > $B/src-exacthead/bin/SHA256
```

- These are the same flags as scripts/build.sh. Its "src is clean" check does not apply to this tree.
- basalt-bench built there runs src-exacthead/bin/basalt by default (BASALT_BENCH_ENGINE).
- Run with the usual guards: hold tmp/gpu-test.lock, start engines with `8>&- 9>&-`, keep the same HOME and flags for both arms.

## 5. Verification after building (same patched binary, the variable is the only difference)

1. **Logs.** With `=1`:
   - Before READY: `basalt exact-head: BASALT_EXACT_HEAD=1: every verify window records the exact output head ...`
   - At QUIT: `basalt serve: exact-head: N verify windows ran the head: 0 two-stage, N exact`.
   - Control `BASALT_EXACT_HEAD=0`: `N two-stage, 0 exact`.
   - Unset: no `exact-head` line at all.
   - The expert-cache lines (`expert cache auto ... -> N slots`, `expert cache N slots`) must match between arms.
   - In basalt-bench, use `--logs DIR` and grep `engine*.log`.
2. **Tokens.** Make two wrapper scripts (`env -u BASALT_EXACT_HEAD .../basalt "$@"` and
   `BASALT_EXACT_HEAD=1 exec .../basalt "$@"`) and run `tools/greedy_identity.py REF NEW --model PACK -- --expert-cache 4790`.
   Its pinned base is `--adapt-swaps 0 --peer-adapt-swaps 0`. Expect GREEDY IDENTICAL; a rare difference, see section 3.
3. **The path changed.** Run the same greedy GEN with `--exp concur9_logit_hash=1`, `=1` vs unset. The `T` lines should
   match and the `LH -1 pos hash` lines should differ (the tail rows are now exact).
4. **Bitwise exact against the engine's own exact pass.**
   - Arm A: `=1`, `GEN 300 temperature=0 <ids>`.
   - Arm B: unset, the same ids with `temperature=0.00001 top_k=0 seed=1`. This is the stock wide-list path: q6k_vhead,
     then exact_head_rows.
   - Both with the logit hash and pinned tiers. Up to the first token difference, every position's LH must be equal.
5. **Optional quality.** Run `--quality 20 --kld-base FILE`, `=1` vs unset. Mean KLD should drop by about 0.0017
   (docs, 100 chunks). This is noisy: the PCIe share stays dynamic.
6. **Speed.**
   - Run `basalt-bench --community --logs DIR` in arms ABAB x3, a fresh engine each.
   - Expect per-window verify ms (draft log `W` lines, by T) to rise by about 0.35-0.55 ms at every T. The exact head
     reads 521.5 MB per window, against 198.7 MB plus rescored rows.
   - Expected decode: about 1.5-2.5 % slower (blend ~212-214 vs 217). Prefill unchanged within noise.

## 6. Hyper-connection copy: BF16 vs int8 bytes per decode window (estimate only; that path is not changed)

**Sizes.** From the pack (hc8 table plus meta), hc_fused.cu and verify/hc8.cpp. 48 layers x {attn, ffn} x
{down 320x10240, up 10240x320, inject 4x10240}, plus the head's down and up. Each is read once per window by
hc_fused_read: the weight tiles go into shared memory once for all T <= 8 columns (hc_fused.cu:33-60).

| Matrix | int8 codes + fp16 scales | BF16 |
|---|---|---|
| down | 3,481,600 B | 6,553,600 B |
| up (scales padded to 16 per row, which the TMA reads) | 3,604,480 B | 6,553,600 B |
| inject | 43,520 B | 81,920 B |
| **main model, per window** | **691.5 MB** | **1,279.3 MB** |
| MTP drafter, per draft step | 21.3 MB | 39.5 MB |

The difference is **587.7 MB per window** for the main model and 18.1 MB per draft step.

**Time.** At 828 GB/s the extra read costs 0.71 ms per window. At 80 % of that it is 0.89 ms, and at 70 % 1.01 ms.
- If hc were read per token (spec off, one token per window): 0.71-1.01 ms on a 4.6 ms step, **+15-22 %**.
- With MTP, as measured: our three by-hand runs average 1,899 windows per 9,410 tokens (4.95 tokens per window), 43.2 s
  of decode, 4.59 ms per token.
  - Main-model hc: +1.35 / 1.69 / 1.93 s, that is **+3.1 / 3.9 / 4.5 %**, or +0.14-0.21 ms per token. The blend
    drops from 218 to about 211-209 tok/s.
  - MTP hc (8,387 draft steps): +0.18-0.26 s, +0.4-0.6 %.
  - **Total about +3.5-5 %, roughly 207-211 tok/s.**
  - Our client's workloads accept fewer drafts per window, so the share there is likely larger (~5-7 %, assuming ~2.5
    tokens per window).

**Where the estimate could be wrong:**
- **L2 (64 MB).** It cannot hide the main-model reads. The per-window set is 0.69 or 1.28 GB, each matrix is used once,
  and the expert cache and the head stream through L2 every window. The only prefetch is the next norm, 40 KB
  (record_layer.cpp:207, 293). The drafter's set (21 MB int8, 39 MB BF16) may partly survive between back-to-back draft
  steps, so its share is anywhere from 0 to the full figure.
- **Not purely bandwidth-bound.** These are 3-7 MB reads of ~10 µs each, on the critical path between layers. Launch
  latency and ramp-up make both formats slower than bandwidth alone, and the fixed part does not scale with bytes. On
  the other hand, BF16 would skip the dequantization. I assume no overlap: each read needs the previous block's output.
- **Draft columns.** hc is read once per window, not per draft column (T-templated kernels). Windows with many columns
  amortize it; spec-off decode does not.
- **The prompt path is unaffected.** Prefill already uses BF16 / dequantized-to-BF16 hc in compute-bound GEMMs
  (index.md row "hc matrices", prefill/projection.cpp). Only the few prompt tokens read through windows would pay.
- **There is no BF16 decode kernel to measure against.** `hc8_enabled()` is hard-coded true (hc_fused.cu:1332), and
  hc_fused_read exits without the 8-bit copies. Measuring it would need a new kernel, not a flag.
