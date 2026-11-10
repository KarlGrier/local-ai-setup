# Maya catch-up list: Project Maya v1.1.17 -> v1.1.28 against Strata v0.2.6 (proposed next round)

10-25 evening, during the DS4.1 tuning round. **Code reading only**:
- a read-only, no-login clone of mw00/project-maya at `ext/project-maya` (no checkout, read with `git show`; tags to v1.1.28 = 6afa525, 10-25);
- Strata v0.2.6 read from `strata-v024` (tags);
- about a dozen unauthenticated GitHub API GETs for PR texts;
- nothing built or run. Three read-only reading passes (prompt path; decode / memory / multi-GPU; everything else + loading + GLM + build).
- Checked by hand: the pin lines in both engines, the Engram file's header, both cards' PCIe links (sysfs), the 5080-alone screen's reference, the 132 GB / 121.2 GB expert totals (engine start log).

Strata's DeepSeek engine is Maya v1.1.17 imported unmodified (Strata bbd0a2c6; verified earlier, partD section d). Since then Strata
has diverged (+6.8k lines, incl. its own RAM store) and Maya has grown ~11k lines in `src/ds4`, so anything taken over is a
hand port.

## What shapes the list

- **Our prompts are bound by the SSD, not the GPUs.** P20K reads ~177 GB from disk in ~38 s (~4.7 GB/s; the engine's own
  measured disk rate is 4.55 GB/s; more readers / store threads were slower). Maya's GPU-compute prompt changes (tensor-core
  attention, wider slabs, leaner tiles, FAT_ROWS) are therefore worth ~0-3 % here today. Only changes that cut bytes read
  per prompt move it: whole chunks skipped (#343) or fewer, larger chunks (BORROW). This is also why the X post's Maya
  1.4-2.2x prompt figures don't carry over: they come from machines whose experts sit in RAM or VRAM.
- **The 4060 Ti runs at PCIe 4.0 x4** (sysfs: 16 GT/s x4; the card can do x8), the 5080 at PCIe 5.0 x16.
- **Routed experts are 132 GB** (15,360 x ~8.6 MB). In the 10/30 split the CPU lane holds 14,044 of them (121.2 GB); VRAM
  holds 415 (4060 Ti) + 901 (5080).
- **The 4060 Ti's share of the 10/30 split is worth only ~1.3 % decode today:** the 5080 alone screened at -1.3 % decode
  (P4K -44.5 %, P20K -69.5 %) against the 4060 Ti-first 10/30 config (10-24 18:13).

## The catch-up list (Maya changes not in Strata v0.2.6), ranked for this PC

Exactness: exact = bit-identical; rounding-level = summing order / precision only, inside our KL references; lossy = beyond.
Gains are estimates from code reading and Maya's own numbers, scaled to our SSD-bound box. They are not measured.

| # | Maya change | What it does | Applies here? | Exactness | Gain estimate (ours) | Port effort | First check |
|---|---|---|---|---|---|---|---|
| 1 | **Prompt skip across a 2-GPU layer split** (#343, 7644743, v1.1.26) | Mode-1 skip (layers 21-39 run only the last 2,668 rows; earlier rows run layer 20 KV-only) on a split, if layer 20 and every later layer share one GPU, no tensor parallel, no Engram layer >= 20 | **Yes, as-is**: 4060 Ti first, 10/30 puts 10-39 on the 5080; Engram layers are 1 and 14. 5080-first splits don't qualify | rounding-level if the KL gate passes (Maya: last-row KL 1.9e-5 to 5.4e-7). Mode 2 / `DS4_YOCO_KEEP` < 2,668 = lossy, excluded | P20K **+35-45 %** (~177 -> ~121 GB read), 32K +40-55 %, 64K +55-70 %; P4K/P8K ~0-5 % (one chunk) | ~0.5 d code (Strata's one-GPU skip is line-for-line Maya's; only the gate `s:8181` differs, Maya's diff is 28 lines) + ~1 d tests | Tonight's prompt-skip end test (see below), then the split KL + liveness checks |
| 2 | **`DS4_BORROW`** (v1.1.18; on 2 GPUs only with `DS4_BORROW=1`) | Lends the prompt-chunk buffers to experts between prompts (~3.7 GB -> ~+430 VRAM experts), and allows 16K/32K chunks | Yes | rounding-level | decode **+6-9 %**; P20K +20-50 % (2 chunks instead of 3); with #1 ~+90-100 % | 2-4 d | 4060 Ti VRAM room; swap-cache checks after the port |
| 3 | **`DS4_IQ_Q8K`** (v1.1.18, Maya default on) | GPU expert kernels round activations as Q8_K like the CPU lane (Strata's GPU path uses q8_1 per 32) | Yes | rounding-level once; afterwards VRAM vs CPU placement differs only in summing order (Maya: 96/96 tokens equal across placements vs 50/96) | 0 speed; repeatability across placements and A/Bs | 0.5-1 d | KL gate; prerequisite for #4 and #7 |
| 4 | **Helper GPU, `MAYA_DS4_HELPER`** (#415, cad9ca4, merged v1.1.28) | A GPU outside the layer split holds a static pool of the most-routed leftover experts; the main GPU keeps every layer; per token ~1.6 MB over the link | Only as 5080 = all 40 layers, 4060 Ti = helper (it replaces our split). Fits: ~750-920 experts on the 5080 + ~800 on the 4060 Ti (vs 1,316 now) | rounding-level, repeatable (static pool) | decode **+5-12 %** vs 10/30 (model; the old +18-27 % was against the 22/18 split). **Prompts lose** unless the 5080-alone path gets better (screened -44.5 / -69.5 %) | 4-7 d | Zero-code first: 5080 alone on v0.2.6 with `--prefill-chunk` 4096/8192 |
| 5 | Wider attention slabs (v1.1.26, `chunk_dims`) | Slab size picked from 3 % of free VRAM (5080: 16/32 MB vs Strata's fixed 8/16) | Yes (4060 Ti stays ~8/16) | rounding-level at most (cuBLAS shapes); check bit-identity first | 0-3 % now (+5-10 % only if compute binds); costs ~120 MB VRAM = ~-0.4 % decode | 1-3 h | 20K profile: does compute wait for reads? |
| 6 | Leaner expert tiles + FP16 rows + router 8 rows (v1.1.21, 3453271) | Smaller output staging in the tensor-core expert kernel; FP16 activations read 8 at a time; router weights read once per 8 tokens | Yes (prompt path) | exact (same bits by construction) | 0-2 % now, +3-8 % if compute binds | 1-1.5 d | Bit-identical `score.tsv` |
| 7 | **#476 in-place pulls + landing** (95f200d, v1.1.28; with v1.1.27's lane) | The GPU pulls missed experts straight from pinned RAM and keeps them in 32 "recent slots"; the "~2x decode" | Gated to one GPU (1b60249). Forced on 2 GPUs, 5080 layers only, untested by Maya. Its 2x came from DSpark windows + a weak 6-core lane + copy-all, none of which we have | rounding-level per expert, but nondeterministic run to run (Maya: two runs differ on greedy answers) | -3 to +8 % | 1-2 d (a fixed-count, deterministic version of Strata's `DS4_STORE_ZC`) to 5-8 d (the lane) | Zero-code: `DS4_STORE_ZC=1` on the 5080 alone; locks ~70 GB, so stressapptest first |
| 8 | Recent slots (#344, `DS4_RECENT`) | LRU slots for CPU-lane hits, 2 fills a layer a tick | Possible | placement only | 0-3 % | 1-2 d | A cache-policy A/B against our decay 0.8 |
| 9 | Tensor-core prompt attention, `DS4_ATTN_MMA` (#369, e9b5df4, v1.1.24, Maya default on) | `mma.sync m16n8k16` BF16-split sparse attention (arch >= 8.0: sm_89 and sm_120 allowed; tested on sm_86 only) | Yes | rounding-level (~1e-5 relative; 1 of 6 greedy outputs byte-identical) | 0-2 % now (attention ~16 % of GPU time), +3-8 % if compute binds | 0.5-1 d | Profile + KL gate |
| 10 | PCIe lane, staging form (`MAYA_DS4_STREAM`, #312/#329, v1.1.18/25) | Some missed experts staged and computed on the GPU beside the CPU lane, split by measured cost | 5080 only (the x4 link never pays) | nondeterministic (KL 1.8e-2 between starts) | <= 0 to +3 % (lost on 2x4090) | 4-7 d | **Not recommended** |
| 11 | `DS4_FAT_ROWS` (v1.1.26; #446 fix in v1.1.27) | Busy experts decoded to FP16 once, then cuBLAS GEMM | **Only for experts that already sit in VRAM** (streamed experts excluded since v1.1.27) | rounding-level | <= 1 %; costs ~75 MB VRAM (-0.2-0.3 % decode) | ~1 d | **Not recommended** |

**Not for us / nothing to port:**
- **#452 IQ1_M AVX2 rows:** Strata's AVX-512 rows are faster on Zen 5; take only its subnormal test cases.
- **Not applicable to our setup:** host-free layers (need all 384 experts of a layer in VRAM); tensor parallel (#344/#377/#408); `MAYA_DS4_DRAFT_DEV` (#412); the DSpark verify speedups (we run without DSpark).
- **Low value:** `DS4_INDEX_TC` (int8 indexer, last bits differ, 1.7 % of GPU time).
- **Lossy, excluded:** `RAM_SKIP_W`, `DISK_SKIP_AUTO`, skip mode 2.
- **Doesn't fit:** `DS4_ENGRAM_RAM` (the 111 GB Engram table exceeds our RAM).
- **No effect here:** Windows and AMD items, setup and dashboard, the 512K/1M context menus (#442).

**Already in Strata v0.2.6:** #360 (copies continue during the routing wait = Strata's flow pump; v0.2.6's `DS4_MISS_SPLIT` is a different, CPU-lane overlap), `Q8_BATCH` (#382), the copy-all rule (da99ae7; never triggers here, it needs ~130 GB free), conversation slots (#356), checkpoint take-back (#394, but see below), one-GPU skip, Stop, cold prefetch, `DSPARK_CUM`, the newer GGUF formats.

**Correctness differences:**
- **Follow-up re-reads:** Maya avoids our bug twice over.
  - Its engine pins the anchor unconditionally: v1.1.28 `ds4_main.cpp`:927 `if (!continued) m.pin();`.
  - Strata made this conditional on slots on 10-24 (fa3252ad, v0.2.6 `:835`).
  - Maya's thinking budget is enforced inside the engine (#363), so there is no second pass to move the checkpoints.
  - Our TOP fix #1 is exactly Maya's line (added to partD's TOP item).
- **`--no-expert-cache` determinism (`prof_load`, v1.1.18):** Strata orders a prompt's expert slots by the drifting profile even with placement frozen. This matters only for frozen-placement runs, such as tonight's continuation exact replay. If its pairs differ, check this before blaming the continuation.

## Tie-in with tonight's prompt-skip end test (and a harness fix)

- **The bug:** the teacher-forced checks could not have run as written. With `DS4_SCORE_PREFIX` set, the engine joins all segments of an ids file into one stream. Ours had 8 x 12,256 tokens against scorearm's `--max-context 16384`, so every check would have stopped on "the context is full".
  - This would have hit the rounding check on what ships, the v0.2.6 rounding gate (where "did not pass" would have made v0.2.6 lose by default), the prompt-skip check and 5 vs 6 experts.
- **The fix (10-25 ~21:05; tested offline against a stand-in engine; no restart needed):** `skipcheck.py` now runs the engine once per segment and merges the scores.
  - A skip-on run byte-identical to its base is now reported as "not tested" instead of a pass.
- **What the result tells us for #1:**
  - **PASS:** mode 1 is rounding-level on this pack. The split port shares that math line for line; what remains is control flow (hangs, stream order), not silent drift.
  - **FAIL:** first rerun with `DS4_LAYER_MAJOR=0`. The one-GPU check at chunk 1024 likely takes the layer-major path, while the split uses the chunk-major flow. If it still fails, don't port.
  - **NOT TESTED:** the skip didn't engage on that path. Rerun with `DS4_LAYER_MAJOR=0`.
- **The split port's own checks:**
  1. Skip 0 on the split is bit-identical to v0.2.6.
  2. A KL gate on the split: skip 1 vs 0, with split-config rounding references, at 12K and 20K prefixes.
  3. Liveness:
     - prompts of 3,692, 8,193, 19,052 and 20-40K tokens;
     - Stop during a skipped prompt;
     - a slot or checkpoint restore after one.
  4. P4K, P20K, P40K and W1-W3 decode.

## Item 2: does Maya load our files? Yes, since v1.1.27, so a head-to-head is possible

- **Loading:** v1.1.27 (da99ae7) loads ISTA's GSQ-RCO IQ2_XXS set and the separate IQ4_NL Engram file without conversion. It handles IQ2_XS experts, Q5_K dense and embedding, I32/I64 hash tensors and the separate Engram GGUF.
  - It loads through `tools/ds4/pack_gguf.py` (stdlib only), which writes a pack folder of offsets into the original GGUFs.
  - Our Engram file's header says `deepseek41-engram` (read by hand), which Maya accepts.
  - PR #453 is not needed. It is still open and conflicts with v1.1.28.
- **Caveats:**
  - `--shards` must be explicit: the model folder also holds the Q8_K_XL and dspark GGUFs.
  - No DSpark.
  - Maya writes into its pack folder, so use Maya's own pack, not a copy of Strata's.

**Head-to-head plan (after the round, needs your go to build):**
1. **Review first** (~2-3 h): the v1.1.28 code that will run, meaning `src/ds4`, `serve/`, `tools/ds4/pack_gguf.py`, `CMakeLists.txt`/`cmake/` and the ggml patch. Look for network, file and shell access.
   - Known so far: the only configure-time fetch is llama.cpp at 3cf03257, which is skipped with `-DSTRATA_GGML_DIR`. Our checkout is that exact pin. Use a copy so nothing touches ours.
   - The server's update check runs only when the dashboard asks; `MAYA_UPDATE_CHECK=0` turns it off.
   - `maya.py`/`setup.sh` pip-install and download, so they are not used.
2. **Offline build in a gap:**
   - Source: `git archive v1.1.28` into a new folder.
   - `unshare -rn` (network-isolated; works here without root) around cmake configure + build.
   - Flags: `-DSTRATA_ENABLE_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="89;120" -DSTRATA_BUILD_TESTS=OFF`, CUDA 13.3, `--target maya-ds4`.
   - Python wheels its server needs that our env lacks (likely jsonschema) are fetched before isolating.
3. **Pack:** `pack_gguf.py --shards <4 backbone shards + the Engram file>` under `unshare -rn`, into Maya's own folder.
4. **Runs:** each arm is the whole thing (server + client + guards) inside one `unshare -rn` namespace on its own 127.0.0.1. The test lock, kernel checks, swap guard, memory floors and drive log apply as usual.
   - **S:** Strata, our tuned ship config on the engine that wins tonight.
   - **M1:** Maya with Strata's arithmetic:
     - `MAYA_DS4_PROMPT_SKIP=0 DS4_FAT_ROWS=0 DS4_ATTN_MMA=0 DS4_ATTN_SLAB_MB=8 DS4_W16_MB=16 MAYA_DS4_STREAM=0 DS4_IQ_Q8K=0`;
     - lossy switches unset (`DS4_YOCO_KEEP`, `DISK_SKIP_W`, `RAM_SKIP_W`, `DS4_INDEX_TC`);
     - slot keep off, `--prefill-chunk 8192`, the same split and card order, 6 experts, no DSpark;
     - this isolates engine and kernel differences.
   - **M2:** Maya's own defaults minus anything lossy or nondeterministic: skip mode 1, FAT_ROWS, ATTN_MMA, auto slabs and Q8K on; STREAM off.
   - **Memory:** Maya has no RAM store. Its CPU-lane experts are read through the page cache, and copy-all never fits (it needs ~130 GB). Start without `DS4_COPY_GB`. The 10-25 04:48 "page allocation failure" came from a 66 GB copy plus page-cache reads.
   - **Measurements:** S/M/S A/B/A, 3 passes, fresh engines: W1-W3 decode, P4K/P20K, and the chat follow-up (`ckpt_client`, Jan's format). Maya's follow-up should read only the new text, which is a live check of our TOP fix.
   - **Quality:** Maya has no teacher-forced `--score` mode (it is Strata's addition). M2's rounding-level changes are checked either by porting Strata's `score()` (~40 lines) into the local build, or by greedy agreement plus our suite on the winner.
   - **Estimate:** review 2-3 h, build 20-30 min (CPU, in a gap), pack minutes, runs ~3-4 h of GPU, quality ~1 h.
5. **Decision:**
   - **Port:** Maya within noise or behind on decode and prompts. Port the list above into Strata; our RAM store and fixes stay.
   - **Switch:** Maya ahead beyond noise on decode and prompts, with no quality loss, and our clients still work: Jan's tool calls (DSML; Maya's open bug #482 swallows a call after a partial closing tag), deep research, `/v1/responses`, and a numeric effort, since Maya maps "medium" to 75, not 62.

## Item 3: GLM-5.3-Flash on Maya: your file should work, no new quant needed

- **Your file:** Unsloth `GLM-5.3-Flash-GGUF` UD-Q2_K_XL (arch `glm5next`).
  - Experts: IQ2_XS/IQ3_XXS gate-up, IQ3_XXS/IQ4_XS down.
  - Dense: Q5_K/Q6_K/Q8_0.
  - NextN block: Q2_K/Q3_K.
- **How it would load:** through Maya's GLM engine (`--gguf-dir`, marked "experimental" for non-Maya quants) plus an offline pack index built from the same file (`tools/iq_pack.py --compat-bf16`: index files, ~1 GB `dense.bin`, tokenizer). The experts stay in the GGUFs and no download is needed. Its GPU and CPU kernels cover all of the file's types. Static reading only, not run.
- **Caveats:**
  - `--compat-bf16` rounds a few small projections to BF16, which is rounding-level against llama.cpp.
  - MTP drafting with the NextN Q2_K/Q3_K experts is likely unusable (no GPU kernel case). Run without drafting, as the llama.cpp setup already does.
  - The GLM RAM tier is pinned memory, so the stressapptest rule applies above 60 GiB.
  - `iq_pack.py` is Maya code: review it and run it network-isolated.
  - The GLM project's `configs/model.json` names an older HF snapshot (621d456e) that no longer has shard 00001. Shards 2-4 are the same blobs. Not changed; your call.

## Proposed next round (for the round report, beside the follow-up re-read fix)

1. **Follow-up re-read fix** (partD TOP; Maya's line + `extends`): ~1 h code, CPU build in a gap, ~1.5 h tests.
2. **Maya head-to-head** (S / M1 / M2, above): decides port vs switch.
3. **If porting**, in this order:
   - #343 skip across the split, gated by tonight's skip check;
   - `DS4_IQ_Q8K`;
   - BORROW;
   - slabs + tiles/router/FP16 rows + ATTN_MMA, only if a 20K profile shows compute binding;
   - helper GPU, only after the zero-code 5080-alone check.
4. **Not proposed:** PCIe lane (staging form), FAT_ROWS, #476 landing (unless the zero-code `DS4_STORE_ZC` check surprises).

## Re-rank after #343 (10-26): long prompts are no longer drive-bound - what speeds up the 4060 Ti's part

Measured (h2h S1, ship config without #343, DS4_FLOW_STATS): a 20K prompt (19.7K tokens, 38.3 s) streams 76 GB of
experts to the **4060 Ti** (layers 0-9: 40 GB from the drive at ~1 GB/s, 36 GB from RAM - all over its PCIe 4.0 x4
link) and its compute **waits 9.4 s for reads**; the 5080 streams 244 GB (3.5 GB/s from the drive) and waits 12.7 s.
With #343 the 5080 runs layers 21-39 on the last 2,668 rows only, and B's 20K prompt took ~33 s at 110 GB read: the
4060 Ti, which still runs its 10 layers on every row, now sets the pace. Maya M1 (no skip) read 136 GB yet ran 15 %
faster than Strata+#343 (~4.9 GB/s effective vs ~3.4) - neither BORROW nor bigger chunks was on in Maya's runs.

Ranked by what they would do for the 4060 Ti's part (estimates; P20K = 20K prompts, assuming the 4060 Ti stays the pace):

| # | Change | What it does for the 4060 Ti | Estimate | Exactness | Note |
|---|---|---|---|---|---|
| 1 | Fewer layers on the 4060 Ti (8/32, zero code) | ~20 % less of its streamed bytes and compute moved to the 5080 | P20K +10-20 % while the 5080 does not become the pace; decode -0-2 % (fewer VRAM experts a 5080 layer) | rounding-level (placement) | screened this round (Karl, 10-26) |
| 2 | Its reads: a larger share of the drive / earlier prefetch for the slower pipeline (Strata-side; Maya's flow is the same idea) | its file reads run at ~1 GB/s while the 5080's run at 3.5 GB/s; 9.4 s of waits | P20K +10-15 % if the waits halve | exact (scheduling only) | code reading first: the read scheduler, the early-queue size per device (2,880 queued, ~190 unpicked) |
| 3 | Tensor-core prompt attention (DS4_ATTN_MMA) | its attention over 20K rows (layers 0-9, compress ratio 4 / 128) on tensor cores | +5-8 % if attention is ~16 % of its time | rounding-level (~1e-5) - KL gate | sm_89 allowed; Maya tested sm_86 only |
| 4 | Leaner expert tiles + FP16 rows + router rows (v1.1.21) | its streamed experts' kernel and router | +3-6 % | exact (bit-identical by construction) | 1-1.5 d |
| 5 | Wider attention slabs (v1.1.26) | none on an 8 GB card (stays 8/16 MB) | ~0 % for the 4060 Ti; +2-3 % on the 5080 only if it becomes the pace again | rounding-level | costs ~120 MB VRAM on the 5080 |
| 6 | DS4_FAT_ROWS | only experts already in VRAM (418 of 3,840 on the 4060 Ti) | <= 1 % | rounding-level | not recommended |
| - | #360 (copies during the routing wait) | already in Strata v0.2.6 (the flow pump) | - | - | nothing to port |

BORROW stays the next round's main item (more VRAM experts on both cards = fewer bytes over the x4 link; 16K/32K chunks =
fewer passes). First step of the next round's prompt work: a per-GPU profile of one 20K prompt with #343 (nsys or the
engine's stage times) so these estimates are replaced by measured shares of attention / experts / waits on the 4060 Ti.
