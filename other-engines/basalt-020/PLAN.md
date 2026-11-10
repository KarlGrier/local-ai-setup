# Basalt 0.2.0 settings test (Karl 11-01)

**Karl's brief (11-01):** "Basalt test, settings only, in the next free GPU gap: after 7a finishes, before 7d/7e. Tell me
before it starts. Budget: 1-2 hours of GPU with 8080 down." Everything lives in this folder; nothing is installed
system-wide; nothing is posted (`basalt-bench --community` writes its row to results/community-rows.json, a local copy).

## Layout

- src/: a worktree of ../basalt-pr90 (github.com/jesdga95/basalt) at tag v0.2.0 = main = f0bb833c (2026-11-01 13:49
  -0500). The clone was fetched 11-01 14:3x (049ba0bd..f0bb833c).
- models/: Qwen3.8-FN-GSQ-RCO-IQ3_S.basalt, `.basalt` format version 2, 87,643,882,460 bytes, LFS sha256
  a09867acc927928509baca0d6ef046fae176cb7af87b9b82a8d1e3c6775ff10a (hf/tree.json, 11-01; the v2 IQ3_S was uploaded
  11-01 13:54Z). scripts/get-pack.sh (user unit basalt020-pack, 25 MB/s, page cache dropped as it goes, stops under
  102 GB free; 183 GB free after at the start).
- venv/: the server's Python packages, copied from basalt-ab/venv (the uv cache no longer had numpy 2.5.3; 0.2.0's
  requirements.txt is unchanged since fb0944c7, the copied versions are the 10-21 set).
- home/: HOME for every Basalt step (0.2.0's cache is ~/.cache/basalt; BASALT_CACHE is gone).
- scripts/: build.sh, build_memguard.sh (a copy of strata-compare's, watching src/ only), watch.py, block.sh, pick.py,
  gap.sh, wait-7a.sh; results/, logs/.

## Review: b2fe96bf30 (PR #90) .. v0.2.0, under the 10-20 rules (basalt-ab/PLAN.md section 1): nothing odd

162 commits, 395 files (207 added, 181 changed, 7 removed), +42,103 / -23,517 lines.
- **Binaries:** one new binary file, data/profiles/qwen4exp-48x512.prof (196,628 bytes): the expert profile that
  moved out of the pack in v2 (header 1, 48 layers, 512 experts, then int16 pairs), read by the engine as data. No
  executables, no long encoded blobs.
- **Build:** no FetchContent / ExternalProject / file(DOWNLOAD); execute_process only for the git stamp and the numpy
  probe, as before; arch 120 forced; tests off by default.
- **Engine:** no new sockets; popen only in platform/system.cpp (the nvidia-smi power-limit query, as before);
  fork/exec / posix_spawnp in platform/process.cpp were already there (bench and probe start the engine, `basalt serve`
  execs Python); dlopen count unchanged (NVML). New file writes: a disk tier for conversations
  (--conversation-cache-disk-mib, default 0 = off; its folder is under ~/.cache/basalt) and --dump-* debug files.
- **Server:** no outbound calls of its own; the web page fetches only its own server ("health", its API); bind default
  127.0.0.1; LAN addresses printed only when bound wider. New: an idle sleep (--idle-sleep, default off) that
  checkpoints the engine's GPU state into host RAM through the CUDA driver (cuCheckpointProcess*, libcuda via ctypes) -
  not used here.
- **Downloads:** tools/convert/mtp_fetch.py as before (conversion only, not run); tools/migrations/basalt_v1_to_v2.py
  converts a v1 pack locally (not needed: we download v2).
- Every Basalt step still runs inside `unshare -rn` (no network at all), with HOME in this folder.

**Worth knowing (not a safety point):**
- The profile's name "qwen4exp-48x512" is the model's own GGUF architecture key (Qwen3.8-Flash-Next's
  general.architecture is "qwen4exp"; docs/model-file.md), not a sign of Qwen4 support.
- 0.2.0 defaults: --spec 8 (was 7 in the old card's runs), KV fp16 (the community preset forces int8), a
  thinking-loop safeguard on by default (256 repeats of one token inside the thinking end it), answer-room on.

## Precision shortcuts that are on by default (for a later quality gate)

1. **The int8 hyper-connection copy.** The GSQ-RCO pack stores the hc matrices (down, up, inject; per layer and for the
   head) as BF16. Decode reads an int8 copy instead: int8 codes with one fp16 scale per 32 inputs (scale = f16(absmax /
   127), codes clamped to +-127), stored in the v2 pack's hc8 section (docs/precision/index.md, "Hyper-connection (hc)
   matrices"; tools/convert/hc8.py; hc_fused.cu). Always on; no switch. The prompt path is a different computation
   (fp16 / BF16 GEMMs), so prompt and decode do not read the same hc numbers. In Strata the same idea is the opt-in
   STRATA_HC_REQ8 ("rounding level"), off by default and not set in any of our configs: our served P028x reads them
   unquantized. Their own gate (100 chunks against the Q8_0 base, decode path, exact head) gives KLD 0.15264 vs
   llama.cpp's 0.1526, so the copy is small on their numbers; ours has not checked it.
2. **The two-stage output head (our pack's head is Q6_K).** In every verify window all 248,320 rows are scored from a
   2-bit copy; only rows within 4 logits of the 64th-best approximate score are rescored exactly; every other row keeps
   its approximate logit (rms ~0.7). Not provably exact (that proof is for the new bit-plane Q8_0 head, which only the
   NVFP4 pack has). Their offline top-64 recall: 99.97 % at margin 4; their gate: KLD +0.0017 (1.1 %), PPL +0.2 %,
   top-1 unchanged. The per-call cap of 65,536 rescored rows (q6k_head.cu:354, VCAP) is unchanged since 10-21: rows past
   it are silently left at their approximate value, and which ones depends on atomic order. Our 10-21 HEADCHECK found
   2.2 % of verify rows with a true top-20 id not rescored where the cap bound (4 % of windows), argmax different on 12.
   With --spec 8 now the default (wider windows, more columns per call), the cap can bind more often than at spec 7.
   Always on for a sampled list of 64 or fewer (top_k 20 = ours). For a Q6_K head (ours) the exact re-run happens
   only for top_k 0 / > 64; logit_bias, penalties, grammar re-draws and scored (ppl) requests read the two-stage logits
   (corrected 11-02 from the code, EXACT-HEAD-NOTES.md; the docs' exact list is for a Q8_0 head). No switch.
3. Smaller, same class as ours: the MTP draft length factor is set from the pack, and verify kernels are not
   batch-invariant across widths (rounding-level token differences between window shapes); the CPU expert tier rounds
   differently from the GPU tiers and the adaptive tier moves experts (as Strata). --prefill-cpu-share changes which
   experts the CPU rounds (fixed per run).

**What a quality gate would have to check before any daily use:**
- (a) the head: count, over our own workloads at spec 8 and T 1.0 / top_k 20, the verify rows whose top-20 ids or fp32
  values differ from the exact Q6_K head (a HEADCHECK-style debug build, as 10-21) - and the windows where the 65,536 cap
  binds; for our lossless rule this has to be zero (or a fallback to the exact head when the cap binds);
- (b) the hc copy: teacher-forced decode-path logits against our served build and the Q8_0 base on our yardstick (mean,
  p90, KL > 1, changed top-1, text NLL; within the references' spread) - its ppl path reads the two-stage head on a Q6_K
  pack (corrected 11-02), so (b) needs the exact-head build (patches/exact-head.patch) to separate (a) and (b);
- (c) seeded sampling: spec 8 vs spec 0 texts and the exact-sampling chi-square / near-tie checks we run on Strata;
- (d) the thinking-loop safeguard (on by default) changes output whenever it fires: count how often on long thinking.

## The gap (scripts/gap.sh; about 1 h 15 min with 8080 down, deadline 115 min)

0. port_gap4.sh begin (hold, bench.lock, test lock, 8080 stopped) - started by Claude after wait-7a.sh returns and Karl
   has been told.
1. build.sh (offline, <= 16 jobs, memory guard; no compile during any LDR run).
2. watch.py beside all GPU steps: MemAvailable >= 12 GiB, 5080 free >= 300 MiB, the swap rule (VmSwap > 0; swap-in /
   swap-out streaks >= 4 MB after the first push-out), kcheck every 60 s; plus guard.py around each step.
3. GPU steps, each `unshare -rn bash block.sh ...`, the 5080 alone (CUDA_VISIBLE_DEVICES=0, PCI order):
   - printcmd (the preset's engine command: --max-context, --kv int8), probe (`basalt-probe -- --kv int8`);
   - `basalt-bench --community` x3 (cold: a fresh engine for the fixtures, the 16K and the 64K prompt) = the defaults;
   - the preset by hand with the probe's suggested flags x3 (the preset refuses flags; same max-context and KV);
   - lossless tries, one pass each, on top of the probe's flags: --spec 7 / 6 / 10, --vram-reserve-mib 400 / 256,
     --prefill auto:8192 / auto:32768, --kv fp16, --prefill-cpu-share 0.4 / 0.8 (unless the probe set it). Never
     --route-prior, --route-tail-skip or --relaxed-drafting (block.sh and pick.py refuse them);
   - pick.py best (the rule written before the gap: a one-pass gain > the base's 3-pass spread and >= 2 %, no other
     measure down by more than its spread; per family the largest win; families combined), then x3 if it differs;
   - the 9-workload speed screen (abrun.py: W1-W3, agent x2, research4 x4) through `basalt serve` at the best flags,
     131,072 context, KV int8, conversation cache off (gap 16's X arm form), 3 passes.
4. port_gap4.sh end: P028x back on 8080 (sha f4c4f654fb24 checked), queue released.

**Compared against** P028x in gap 16 (results/r22/gap16/bp90/report.md, cold, 3 passes): blend 198.4, 16K prompt
3,826.7, 64K prompt 4,382.5 tok/s (engine rates); the screen against gap 16's X arm (results/r22/gap16/speed/*.jsonl,
client-timed, as Basalt's server gives no engine log in our format).
