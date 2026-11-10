# Basalt A/B (the user, 2026-10-20 evening; low priority, in gaps between Phase 4 runs, ~2-3 h GPU)

Folder: /home/USER/ai-speed-testing/basalt-ab (src/ = github.com/jesdga95/basalt at fb0944c7, 2026-10-20; hf/ = the
model card and file list; models/ = the pack; scripts/, logs/). Nothing from src/ has been built or run yet.

## 1. Safety review (10-20 22:0x-22:3x): nothing odd
- No prebuilt binaries (only two woff2 fonts and images); no long encoded blobs; web UI not minified, same-origin fetches.
- Build: no FetchContent / ExternalProject / downloads; execute_process only for `git rev-parse` (stamp) and a
  `python -c "import numpy"` probe; CUDA archs forced to 120.
- Engine (src/): no sockets; popen only for `nvidia-smi --query-gpu=power.limit` in basalt-bench; dlopen libnvidia-ml;
  `basalt serve` execs `python -m serve.server` from the source tree.
- Server (serve/): no outbound calls of its own, no update check, no analytics ("telemetry" = local NVML/psutil readings
  for its web page). An image in a request may be an http(s) URL (fetched) or a local file path (read) - the same as
  Strata's server. lan_addresses() only when bound beyond loopback (UDP connect sends nothing). --open opens a browser.
  Origin check on /v1 POSTs without an API key.
- Files outside its folder: extracted pack sections go to ~/.cache/basalt/<hash>/ unless BASALT_CACHE is set -> we set
  BASALT_CACHE and HOME to basalt-ab/home. No ~/.config, no key files.
- tools/convert/mtp_fetch.py downloads Qwen's BF16 MTP tensors from Hugging Face (conversion only; not run).
- Repo: MIT, created 10-06, 109 stars / 15 forks today; history = Strata's (Niko1221, 532 commits) + 832 by the author.

## Findings that change the plan
- **Blackwell only**: CMake refuses any arch but 120, and device.cu refuses a card that is not compute capability 12.0.
  The 4060 Ti is 8.9: Basalt cannot use it as the peer tier (or for `vision peer`). Arm (c) as asked cannot start.
  Proposal: (c') Basalt stock on the 5080 alone, plus (a') our 0.2.1 build on the 5080 alone (helper off), so the
  engine difference is separate from the helper card's.
- **The tuned MTP layer is published separately**: hf convert/mtp/rt/dense.bin (116 MB, sha256 dfe18647...), with
  dense-original.bin and dense-tuned.json. The pack is still needed for (c'); our own script will also extract the
  pack's mtp section and compare.
- **Two-stage output head (IQ3_S pack, Q6_K head), always on, no switch**: the top-64 rows are exact, the softmax tail
  comes from a 2-bit copy (rms ~0.7 logit; KLD +0.0017). With top-k 20 the sampled token comes from exact rows, so our
  sampling should be unaffected; full-vocabulary logits will not match Strata at rounding level - the check compares the
  top-64. Full exactness would need a one-line patch (skip q6k_vhead) for the check arm only.
- Speculative sampling: exact unless relaxed-drafting is set (engine flag or request field; default off). Check the
  pack's default sampling section after the download.

## Their table (hf model card): "Best measured, single stream, 400 W, RTX 5090 + RTX 5060 Ti peer"
IQ3_S 341 prose / 646 structured / 440 chat. basalt-bench's fixtures: conv ("B-tree vs LSM tree", 1200 tokens, T 0.6,
top-p 0.95, top-k 20), struct (a JSON array, 8192 tokens, greedy, ~7230 expected), prose ("essay on the Odyssey", 1200
tokens, T 0.6); thinking off; context sized to the fixtures (~9K); spec 0 unless given (MTP runs: --spec 7
--spec-min-p 0.5); relaxed drafting not set; "best" = the best of several runs. The card states no spec or sampling.

## Picture reader on the 4060 Ti (Strata 0.2.1)
Supported: the vision section's "cuda_device" (#408) runs the reader on a chosen card, "gpu": true. Our strata-vision is
the CPU build; it needs -DSTRATA_VISION_CUDA=ON (arch 89) and ~1-2 GB on the 4060 Ti, i.e. fewer helper experts than
3,300 (the decode cost to measure).

## Order
1. Pack download (scripts/get-pack.sh, started 22:23, 25 MB/s, page cache dropped as it goes).
2. Builds (Basalt; strata-vision CUDA; the MTP layer for our pack) in a gap - CPU only, <= 16 jobs.
3. GPU arms after the baselines (gaps between Phase 4 steps), one model server at a time, test lock held, 8080 stopped.

## The user's follow-ups (10-20 22:4x)
1. (c') Basalt on the 5080 alone and (a') our 0.2.1 build on the 5080 alone: OK.
2. Calibration arm on both engines at their table's settings: T 0.6 (top-p 0.95, top-k 20), thinking off, 1,200 tokens,
   spec 7 (--spec-min-p 0.5 as their bench), ~9K context; their three fixtures (conv, prose, struct) re-tokenized
   identically for both. Splits their number into settings / hardware / engine.
3. Output head: an exact-head patched Basalt build (debug only) that also runs the plain Q6_K head at every verify
   position and counts positions where the exact top 20 is not inside the two-stage head's exactly rescored rows
   (equivalently: the two-stage top-20 ids or logits differ from exact). Also check whether Basalt's sampler normalizes
   over the full vocabulary before top-p / min-p (the approximate tail would then move the cutoff). Their own number:
   top-64 recall 99.97 % at margin 4 (3,614 inputs). If never / essentially never on our workloads: exact under our
   top-k 20, and a candidate speed trick for Strata (same check there).
4. Decision rule: Basalt (c') >= 15 % faster than (a') on the user's normal text (T 1.0, thinking on) AND passes the
   quality checks -> up to ~half a day on the helper card, but first report which route is cheaper and wait for the pick:
   (a) sm_89 peer tier back into Basalt (only the arch list + startup check cut, or Blackwell-only instructions in the
   peer kernels?) vs (b) Basalt's speed parts (tuned MTP, kernels, head trick) into our Strata build. Start neither
   before the pick.

## 10-21 morning
- Pack: sha256 OK 10-20 23:20 (models/Qwen3.8-FN-GSQ-RCO-IQ3_S.basalt).
- Python: venv/ made offline from the local uv cache (no network namespace). Pinned versions except markupsafe 3.0.4
  (3.0.3 pinned) and regex 2026.9.29 (2026.9.10 pinned): the cached ones.
- Build: scripts/build.sh (cmake + ninja inside `unshare -rn`, i.e. no network; HOME/BASALT_CACHE = basalt-ab/home;
  CUDA 13.3, arch 120; 16 jobs, strata-compare's build memory guard) runs in strata-compare's gap 5 after h08
  (work/r22/gap5.sh), with the 0.2.2 port build and the CUDA picture reader (sm_89) for item 5.
- GPU arms still after stage 1.

## The user, 10-21 ~07:00: run the GPU tests at the end of gap 5 (~09:45), then P021 back and stage 1; results to the
## user as soon as they are in (before stage 1 ends)
Block: strata-compare work/r22/gap5b.sh (called by gap5.sh before its switch-back); Basalt part scripts/basalt_block.sh.
- MTP findings (no GPU): our strata-v0115/mtp/rt/dense.bin (sha c724dc0b...) IS Basalt's dense-original.bin, and our
  experts.bin IS theirs (09398406...); dense.txt identical. Their tuned dense.bin (dfe18647...) is a drop-in file:
  models/mtp-basalt/rt-tuned (hard links to ours + their dense.bin). Draft vocabulary differs: ours 40,525 ids, theirs
  106,299 (both plain int32 lists; Strata takes theirs with --mtp-draft-vocab) -> arm b7v.
- Our own reader (scripts/packsec.py) on the pack: 18 sections; mtp/dense == the published dense.bin byte for byte;
  mtp/experts == ours; mtp/draft_vocab = their 106,299-id list; vision/mmproj == our mmproj-BF16 (b1a82259...).
  meta.sampling = T 1.0 / top-p 0.95 / top-k 20 / min-p 0.0, presence 0; no relaxed-drafting key in the pack.
- Our arms (configs/basalt-ab/*.json, from r22p021-ar0 = P021's engine and flags, no reader, answer_room off so both
  engines think to the same cap): a (two cards, spec 4), a1 (5080 alone, STRATA_ROUTE_TAIL_SKIP=0), b4/b5/b7 (two
  cards + tuned dense), b7v (+ their draft vocab), a1s7 (5080 alone, spec 7: calibration); vcpu / vgpu (pictures:
  the CPU reader vs the CUDA sm_89 reader on the 4060 Ti, helper slots 3300 -> 2800).
- Client: scripts/abrun.py (same requests to either server, streamed, client-timed; nonce line defeats prefix reuse):
  normal = W1 longreason math (cap 3072), W2 longreason code (3072), W3 o07 report call 662 (~19K prompt, 2048),
  W4 32K prompts x2 (prefill); T 1.0 / 0.95 / 20 / min-p 0.05, thinking on, effort medium; 2 reps.
  calib = Basalt's fixtures (T 0.6, thinking off, 1,200 tokens; struct greedy 8,192).
- Lossless: logit dumps teacher-forced on tf-corpus (scripts/strata_dump.py, logitcmp.py): ours two cards vs 5080
  alone = the rounding reference; Basalt (stock head, and the exact-head debug build) vs ours.
- Pictures: a screenshot (serving-110-stages.png, 2770x1662) and a synthetic 12 MP photo (results/pictures/
  large-4032x3024.jpg; the repo has no real photo); first-read time CPU vs 4060 Ti; decode W1/W2 vcpu vs vgpu.

## 10-21 results (gap 5, 09:27-10:04; results/summary.txt, results/table-*.md via the gap log)
- Normal text, 5080 alone, decode tok/s (client, mean of 2; accepted %): W1 ours a1 147.6 (72, spec 4) vs Basalt c1
  156.8 (75, spec 7) +6 %; W2 139.5 (75) vs 135.4 (69) -3 %; W3 126.7 (80) vs 129.8 (78) +2 %. Mean +2 %: the 15 % rule
  is NOT met. Prompt reading: W3 26.7K 4,250 vs 4,928 tok/s (+16 %), 32K 4,325 vs 4,930 (+14 %) - engine side.
- Calibration (their fixtures, T 0.6, thinking off, spec 7, 5080 alone): conv ours 123.5 (66 %) / Basalt 126.4 (74 %) /
  basalt-bench 126.4 +- 4.1 / their card 440; struct 174.2 (96 %) / 194.5 (97 %) / 199.9 +- 4.5 / 646 (both 7,230
  tokens); prose 115.3 (50 %) / 130.3 (68 %) / 123.8 +- 3.0 / 341. Our client and their tool agree; their table is the
  5090 + 5060 Ti machine (~3x). Struct +12 % at equal acceptance = engine; prose/conv add higher acceptance.
- Tuned MTP layer on ours (both cards; a = ours spec 4): W1/W2/W3 a 175.1/153.8/152.3, b4 178.3/155.5/152.3,
  b5 166.4/149.5/149.5, b7 182.9/152.2/152.5, b7v (their draft vocab, x1) 165.7/147.5/152.1 - a wash (a's own W1 runs:
  191 and 159). Nothing to adopt.
- Lossless: seeded T 1.0 spec 7 vs spec 0 NOT identical (split at char 36 and 242; the request seed does reach the
  engine). HEADCHECK over 10,185 verify rows (2,142 windows, W1-W3): 222 rows (2.2 %) had a true top-20 id not exactly
  rescored and a different sampled top-20 (209 as a set), argmax differs 12, |logit error| up to 5.95; 85 windows (4 %)
  hit the 65,536-row cap. Teacher-forced at spec 0 (windows of 1): two-stage == exact head, bit-identical, 511/511 rows.
  So the two-stage head is lossy where the per-window cap binds: not a trick to port as is (a variant falling back to the
  exact head at the cap would be exact; speed unmeasured).
- Our side of the logit comparison did not run: strata --dump-logits only writes from the per-token loop, which a native
  pack never runs (0-byte dumps, rc 0). Needs a debug dump in the verify loop (follow mode) - next gap if wanted.
- Pictures (P021 + reader): cold first answer token 4.5 s CPU reader -> 3.2 s on the 4060 Ti; second picture 3.4 -> 3.3;
  repeats 2.6/1.9 -> 2.0/1.8. Decode -1 to -2 % (helper experts 3,300 -> 2,800 MiB). CPU reader RSS 1.1 GB.
- Memory: Basalt 4,499 expert slots (8.58 GiB) on the 5080, 748 MiB free, 45.8 GiB pinned RAM; ours 4,433 (8.46 GiB).
- Isolation: every Basalt step ran inside unshare -rn; no leftovers; kernel log clean.

## 10-21 round 2 (gap 6 10:36-11:10, gap 6b 11:15-11:17; results/r2/)
- Basalt lossless tuning (exact head, seeded tune set, >2 % rule): its defaults stay best (spec 7, 15 pool workers + host,
  reserve 700, pcie-frac 0.55, shared cache). Exact head: seeded spec 7 vs spec 0 still split at chars 36 / 242 =
  window-shape rounding, not the head. Head trick (fbt vs fb): decode +0.7 %, prompt 0 %.
- Normal text, 5080 alone, decode mean W1-W3 / prompt 32K: stock defaults s0 125.4 / 3,914 (needed --vram-reserve-mib 800:
  upstream's 700 left 275 MiB with the 106K draft head, guard floor 300); stock + our settings s1 127.8 / 4,251; ours
  a1r 137.7 / 4,228; Basalt best lossless fb 132.9 / 4,920; Basalt two-stage fbt 133.8 / 4,924.
  -> our settings +1.9 % / +8.6 %, our code +7.8 % / -0.6 %; Basalt's tech (vs stock) +6.0 % / +25.7 %;
  Basalt vs ours -3.5 % / +16.4 % (W3 prompt +17.9 %). Combined estimate: decode 138-146, prompt 32K 4,920-5,300.
- Struct greedy spec 7: stock+settings 182.0 (5.91 drafts/window), ours 169.5 (3.00), Basalt 192.7 (5.74): our patch
  series caps greedy windows (sent to the draft-length port).
- 4K screenshot (3840x2160) on P021's CPU reader: 3.9 s to the first answer token, 6.1 s total; repeat 1.7 / 3.7 s.
- PLE: our build already reads the 26.8 GiB table from SSD (--ple-io direct default, ~90 MB row cache): no RAM to gain.
- Code diff: notes-r2-codediff.md (fork base v0.1.39).
