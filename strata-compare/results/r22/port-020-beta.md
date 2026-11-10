# 0.2.0 port (code work, 2026-10-19): our series on v0.2.0-beta

Branch `r22-port020` in worktree `strata-r22port`, from tag v0.2.0-beta (3d1fb480; engine 0.1.45.3). 0.2.0 final is
not out yet (tag check: v0.2.0-beta newest); when it lands, the branch is rebased onto it. No build, no GPU so far.
**Not promoted to 8080:** that waits for the phase 3 checkpoint and the user's OK. Port tests run on their own port in
queue gaps (`work/r22/port_gap.sh begin/end`: after each gap C*18t is back on 8080, checked by its binary's SHA-256,
the chat-cache parking policy off, the switch-back logged in deep-research NOTES.md).

## The series: 32 commits -> 25 carried + 1 new, 7 dropped
```
1 resolved 788a4754 side stash (2 hunks: ckpt pool, admit-merge-first)
2 resolved 918891d0 chat cache (1 hunk: side stash condition; chat cache off with STRATA_CKPT_POOL)
3 resolved 68cf3132 web app chats (1 hunk: upstream's sampling-default line kept)
4 clean  ef2045f7 serve: --chat-cache keeps the shared-prefix checkpoint with the session when it parks
5 resolved accb8357 web search switch (server: after upstream's --offline checks, web search off with --offline; app.js: upstream's 1.0 defaults + web:false)
6 clean  261e689a web search: tell the model today's date (in web_search's description); www. and the bare h
7 clean  65a75f52 web app: two tabs keep each other's chats
8 resolved 893b563b exact spec sampling (1 hunk: also off on upstream's merged first window)
9 resolved 84e174de commit only what a window hands out (#652; 1 hunk + emit = all on upstream's merged first window)
10 resolved a6628bc6 router Q8_K (2 hunks: next to upstream's cpu_jobs / PcieModel and its balance stamps)
11 clean  a977a929 round 11 A.2: the Q8_K rounding is ggml's nearest_int bit for bit (magic-number add), also
12 clean  2e4fb5c8 round 11 A.2: bsums sum the stored int8 values, as ggml does
13 clean  63ae8ac3 round 11 A.2: a NaN product rounds as x86's default NaN does (0)
14 DROPPED 76043ac5 QSA split attention (#1888): upstream 1a2f95c3 has it, same STRATA_QSA_SPLIT_ATTN=1 switch (its sums in another order: rounding-level vs ours)
15 resolved 6556ff74 GR fork read (1 hunk: after upstream's HC_PERSIST call, HIP-only)
16 clean  b09e40a8 round 11 B.1 on v0.1.39: the fork read gets its own scratch - 0.1.39's batched PLE writes 
17 DROPPED 5b014b63 incremental tokenising (#567): upstream f13a870d (#1852 + #567, with IncrementalPrompts tests)
18 DROPPED 275de3be round 11: STRATA_PROMPT_ENCODER_OLD=1 = the full prompt encode (A/B switch for t - goes with #567 (upstream has it)
19 DROPPED ea248fd2 round 11 G: #567's tests call the renamed _encode_rendered (0.1.39 has its own e - goes with #567 (upstream has it)
20 DROPPED 81cdb523 round 13 P1.2: #567's IncrementalPrompts tests with #931 - the reference is a fu - goes with #567 (upstream has it)
21 clean  57cf16b9 round 13 P2.3: patch guards - every local engine patch's assumptions about the model check
22 clean  3c8688dd #619 (code only; its docs conflict with 0.1.39's MODELS.md): read qwen4exp.nextn_predict_l
23 clean  5b2c9841 round 13 P2.3: the gr_fork guard does not check the GGUF's hc weight type (the pack stores
24 clean  4a964f93 round 13 P3.4: serve/model_check.py - the server's fixed template strings checked against 
25 clean  57ec961e round 12 B (A1): STRATA_COST_GATE=FILE - a cost-aware draft length: draft d joins the wind
26 DROPPED 0ca1293e side mixer (#1889): upstream ffc30b8d (same STRATA_SIDE_MIXER=1/2; bitwise; =2 now the sm_120 default)
27 clean  9d89df00 round 15: the B.3 guard (mmvq_il) goes with B.3 - on v0.1.40.2 STRATA_MMVQ_IL is upstream'
28 DROPPED cbf7ed3f side mixer branches read F4's interleaved copy, qkv first: in upstream ffc30b8d's description and code
29 clean  113e4f0f chat cache: dropped with v0.1.43's non-finite guard (#879) - after a non-finite window the
30 clean  d9e2c3a5 reasoning: a </think> inside a code fence of the reasoning is quoted text - held until the
31 clean  9455a366 web search: a Tavily fallback when SearXNG fails or returns fewer than 3 results (local; d
32 clean  a2ec5ac1 web search: the fallback after SearXNG is Exa (Lite), then Tavily (local; each dormant unt
```
New on the branch: 64ce1d05 chat cache owner tag + chat_drop (memory proposal A; GEN keys owner= / chat_drop=, server
fields strata_owner / strata_chat_drop, unit test test_chat_cache_owner_keys).

Static checks only (no build allowed while the queue runs): 221 Python files compile; serve/web/app.js parses (gjs,
checked against upstream's file and a broken one); C++ untouched by a compiler yet.

## The sm_120 defaults against our config (C*18t's env)
| new default on a 12.0 card | ours | effect on our setup |
|---|---|---|
| STRATA_SIDE_MIXER=2 | we set =2 (our #1889, now upstream's ffc30b8d) | same |
| STRATA_PF_FUSED (80+ SMs; the 5080 has 84) | we set =1 (every covered format, any card) | same as before |
| STRATA_ATTN_DAILY=1 (bitwise) | we set STRATA_QSA_SPLIT_ATTN=1 | the split path runs first where it applies (int8 KV, sm_80+): Daily only on the fallback |
| STRATA_GR_UP75=1, STRATA_GR_DOWN_TG=1 (and per-token HC down blocks), bitwise | we set STRATA_GR_FORK=1 (+ GR_V3=1) | our fork read bypasses launch_multi: these kernels never run (GR_V3 is moot under GR_FORK, as before) |
| STRATA_GU_SWIGLU=1 (gate/up + SwiGLU + q8_1 in one launch, bitwise) | ROUTER_Q8K is the CPU pool's rows | independent: applies to the 5080's routed experts (the 4060 Ti, sm_89, keeps its defaults) |
No conflict: every switch's own variable still wins. Upstream's split attention sums in another order than ours did
(rounding level), so the ported build is not expected to be bitwise C*18t; judged by the usual quality checks.
To measure on the ported build (A B B A): GR_FORK=1 vs unset (upstream's sm_120 hyper-connection kernels) and
QSA_SPLIT_ATTN=1 vs unset (Daily attention) - keep whichever is faster within the quality gates.

## Conflicts resolved (8 commits)
* side stash / chat cache: next to upstream's STRATA_CKPT_POOL and STRATA_ADMIT_MERGE_FIRST; side stash and chat cache
  stay off with the checkpoint pool (it reuses a checkpoint's storage).
* exact speculative sampling and "commit only what a window hands out" (#652): upstream's merged first window holds
  prompt tokens - no ESS on it, and all its prompt tokens are committed.
* router Q8_K: next to upstream's PcieModel / balance stamps (keeps upstream's pin-exhausted hint).
* GR fork read: after upstream's HIP-only HC_PERSIST call.
* web app: upstream's 1.0 sampling defaults + our several chats / web switch; web search off with --offline.

## Gap plan (queue held with port_gap.sh; times from the ETA of 10-19)
* Gap 1 (~3.5 h, after o08 deep medium): build; C++ unit/parity tests + serve/test_server.py; the ported config
  (configs/r22port.json, a copy of Cstar18t.json with the port's exe) on its own port: quality checks vs C*18t
  (identity gate, exact7, needles), decode + 32K prompt A B B A; work/r22/chatcache_checks.py (resumed = fresh,
  ckpt=0 = plain, the research drop) with STRATA_STATE_HASH=1.
* Gap 2 (~3 h, after the hard medium five): strata tune auto (thorough, small differences off, on a copy) + A B B A on
  its disagreements; GR_FORK and QSA_SPLIT_ATTN on/off A B B A; the pictures step (--vision cpu: identity with the
  reader loaded, decode A B B A, MemAvailable through a research-style report).

## Gap 1 armed (10-19 16:17)
`work/r22/gap1.sh` (started detached; log logs/r22/gap1.out, summary results/r22/gap1/summary.txt) opened the gap's hold
at 16:17 and waits for o08 deep medium to finish; then build (work/r22/build-port.sh: our llama.cpp checkout is at
3cf03257 = 0.2.0's pinned ggml, nothing downloaded), quality (exact7 vs C*18t for information + exact7 repeat 7/7,
needles, Stop at 120K, probes, repeat3), chat-cache checks on configs/r22portRT.json (fixed computation: --adapt-swaps
0, --suffix-draft 0, prompt share 0, STATE_HASH=1), decode screen A B B A vs C*18t, serve/ unittest, C++ ctest; then
port_gap.sh end. A failed build ends the gap at once; a kernel error stops everything with the gap left open.
Configs: configs/r22port.json = C*18t's flags/env with engine-r22port and the port's serve/, port 8081, no fallback.
Checked: every C*18t flag still exists in 0.2.0's engine; 0.2.0's server adds --layer-split only for a config "gpu"
list (ours selects the cards by CUDA_VISIBLE_DEVICES, so no split, as before).
* 19:41: the gap's lock holder was exclusive and with_server.sh waits for a shared hold, so the needles step waited
  18:52-19:41; switched to a shared hold in place (port_gap.sh fixed). exact7: 2/7 vs C*18t (the p2000 / 32K prompt
  outputs equal; decode outputs differ - 0.2.0's attention order, and the expert cache has 4551 slots vs 4510, which
  alone changes decode outputs, r21), 7/7 against itself (deterministic).
* Gap 1 results so far (19:41-20:01): needles 72/72 (TTFT 32K 7.5 s, 64K 15.2 s, 120K 29.4 s; C*18's gate on 10-15:
  7.8 / 15.4 / 29.9 - another day, not A B B A); Stop at 120K all PASS (prompt read 4,292 tok/s); #652 follow-ups
  plain 14/14, think 4/5 (C*18 the same); stop strings: the same one known failure as C*18 (anthropic multi-token
  stream); tool tags: every call parsed (no malformed call), the model named the tag in its prose 2/6 (C*18 4/6:
  wording at T 1.0); copy 20/20, forged 0/30, plain 0/30; repeat3 3/3; chat cache ALL PASS (resumed = fresh greedy
  and seeded, STATE_HASH equal; ckpt=0 = plain; the research drop keeps the untagged chat).
  Decode screen A B B A (results/r22/gap1/dec.md): decode 150.3 vs C*18t 154.4 tok/s (-2.6 %; ms per verify round
  +5.7 %, tokens per round +2.9 %), long reasoning math +0.7 %, code -3.4 %, TTFT 32K 7.63 vs 7.69 s (-0.8 %).
* Gap 2 gets the full screen A B B A as well (TTFT 32K / 64K / 120K + 768 decoded each, long reasoning at 8,192,
  correctness, chat switch; ~6.5 min per arm), on the port's best variant after the GR_FORK / QSA_SPLIT_ATTN A B B A.
* Gap 1 end (20:00-20:12): serve.test_server 342 tests OK; serve/test_*.py 889 OK (18 skipped). C++: 147 tests,
  139 pass, 8 fail - none in or fed by a file our 26 commits change (they touch generate.cpp, verify/mtp/expert_source,
  native_dense, patch_guard, the CUDA elementwise / fused_gr / qsa_prompt_attn / sampler kernels, iq_pack.py,
  CMakeLists' patch_guard lines):
  - ple_parity, expert_parity, pool_test: model files at fixed relative paths (a Q2_0 gguf, pack/full/experts.bin) that
    this machine does not have (test data);
  - native_hadamard_test, tq_cpu_parity, tq_cpu_parity_avx2: "this ggml has no trellis types" - they need the agention
    llama.cpp fork; we build with upstream ggml at 0.2.0's pinned commit (Gyro trellis, unused here);
  - ggml_tq_overlay: cmake/ggml_tq_overlay_test.cmake uses IN_LIST in script mode without policy CMP0057 -> a CMake
    error on CMake 3.28 (upstream script);
  - isa_guard_check: upstream's own tq_rows_avx512 (src/kernels/cpu/tq_avx512.cpp) flagged as wide-ISA code outside
    the allowed translation units (upstream's guard list or flags).
  Gap 2 adds the same ctest on pristine v0.2.0-beta (build-tests only) to confirm the 8 fail there too.
  20:12:50 switched back to C*18t (SHA e428a826c5fb checked), parking policy off, queue released: h02 (hard, deep
  medium) started 20:12:55. kcheck clean.

## Gap 2 armed (10-19 21:07-21:13)
port_gap.sh begin (21:06:57, now with a shared hold) waits for h08; work/r22/gap2.sh (log logs/r22/gap2.out, summary
results/r22/gap2/summary.txt) then runs: 1 pristine v0.2.0-beta ctest (worktree tmp/r22/pristine020) to compare gap 1's
8 C++ failures; 2 decode screen A B B A port vs configs/r22port-nofork.json (GR_FORK and GR_V3 unset: GR_V3 alone
would take the old v3 read, not 0.2.0's sm_120 kernels) and vs r22port-noqsa.json (QSA_SPLIT_ATTN unset -> ATTN_DAILY);
3 full screen A B B A vs C*18t; 4 strata tune auto on configs/r22port-tune.json (thorough, coding, --no-save, no small
differences; its own lock file tmp/r22/tune-gpu.lock, since the tuner locks exclusively; work/r22/floor_watch.sh stops
its process group below 17 GB free); 5 work/r22/gap2_pictures.sh; then port_gap.sh end.
Pictures: mmproj-Qwen3.8-Flash-Next-BF16.gguf downloaded 21:10 into models/vision-r22/ from ISTA-DASLab's repo at
0.2.0's pinned revision ed59f920..., size 907,543,008 and SHA-256 b1a82259... as setup.py pins them. Configs
r22port-vision.json / r22portRT-vision.json = the vision section setup writes for --vision cpu (strata-vision, the
mmproj, the text model vocab-only, 300 image tokens, 16 threads) + the engine's --vision. Steps: reader build (CPU,
native), identity (11 replies on the twin, reader off vs on), a screenshot sent as Jan sends it (time to first answer
token / end, answer judged by hand, reader RSS), decode A B B A off vs on, full screen on and off for RAM (a
long-context stand-in; a real research report with the reader comes at the phase 4 switch if wanted). The Jan side
(Vision on in the provider's model) waits for promotion: Jan talks to 8080, which stays C*18t.
* Gap 2 results 21:15-22:05:
  - pristine v0.2.0-beta ctest: the same 8 of 147 fail (ple_parity, ggml_tq_overlay, native_hadamard_test,
    tq_cpu_parity, tq_cpu_parity_avx2, expert_parity, pool_test, isa_guard_check); none only in the port.
  - decode screen A B B A (results/r22/gap2/dec-nofork.md, dec-noqsa.md): GR_FORK + GR_V3 unset (0.2.0's sm_120 HC
    kernels) decode -4.0 % vs the port (long reasoning code -4.4 %): keep GR_FORK=1. QSA_SPLIT_ATTN unset (ATTN_DAILY)
    decode -1.0 %, long reasoning -2.2 / -2.3 % (ms per round -1.4 %): no gain, keep QSA_SPLIT_ATTN=1. The port's config
    stays as it is.
  - full screen A B B A vs C*18t (results/r22/gap2/full.md): decode 155.3 vs 155.5 tok/s (-0.1 %; ms per verify round
    +6.7 %, tokens per round +6.6 %, acceptance +3.1 %), long reasoning math -2.0 % / code +1.8 %, TTFT 32K 7.67 vs
    7.73 s, 64K 15.28 vs 15.40, 120K 29.57 vs 29.76 (each -0.6 to -0.7 %), all requests 208.9 vs 209.5 s (-0.3 %).
    min MemAvailable 28.3 vs 28.4 GiB, max tree RSS 58.6-58.7 GiB both. With gap 1's decode screen (-2.6 %): decode
    is level to ~3 % slower (each step slower, more tokens accepted per step), prompt reading ~0.7 % faster.
  - 22:04:53 tuner started (status: 6 runs planned, ~15 min estimated).
* Tuner (22:04-22:19, 16 runs, 14.5 min of its 2 h budget; results/r22/gap2/tune.json): "default_confirmed /
  already_fastest" - our settings were the fastest it found; nothing to change (--no-save, nothing saved). Its base:
  decode 143.6 tok/s (its own short runs; noise 1.6 %, drift 1.5 %), prompt 3,708 tok/s (4,338 long), RSS peak 52.1 GB,
  min MemAvailable 37.1 GB. Tried (answers exact): --kv-resident 65536 0.98-0.99x, --trim-stage-weights ~1.00x,
  --host-core last ~1.00x, --kv-grow ~1.00x; per request spec-min-p 0.7 0.97x, spec-min-p 0.5 (ours) and aux CPUs 1
  ~1.03x, both below the control's 1.04x (not won), aux CPUs 0 0.97x. Skipped by the user's choice (answers may change):
  faster expert-cache re-balancing, faster decay; skipped as not this PC: pin by need. The floor watch's lowest: 37.1 GB.
* Pictures (22:19-22:45; results/r22/gap2/pictures/):
  - reader built (CPU, native) in ~10 s: engine-r22port/strata-vision sha256 4829c210f71d...; mmproj SHA re-checked.
  - identity (twin, reader off vs on): 8/11 replies identical; greedy-4, seeded-0 and seeded-4 differ. The engine's
    --vision keeps a 1.5 MB image-position table on the GPU (generate.cpp: (max_context + 64) x 3 int32), and the
    expert cache came out 2 slots smaller (4,589 -> 4,587, engine logs); decode outputs follow the slot count (round
    21: c18r-e7 2/7 at another count). Likely that, not the CPU reader; to confirm: the same check with the expert
    cache pinned to one size in both arms (~5 min, next gap).
  - screenshot (docs/terminal-previews/serving-110-stages.png, 2770x1662, sent as Jan sends it, effort medium): first
    answer token 4.5 s, done 7.8 s (cold: the picture encoded on the CPU); again 1.2 s / 3.6 s (317 of 322 prompt
    tokens cached). Judged against the picture: what it is, its layout and most numbers right; answer 1 misread two
    ("1 requested" for 8, "4 decoding" for 5), answer 2 three (pre-admit 2 for 5, "1 requested", first output 20 for
    0). 300 image tokens (setup's CPU default) for a screenshot this size: small digits get misread.
  - decode A B B A, reader off vs on: decode -2.3 %, long reasoning math +4.5 % / code -3.0 %, TTFT 32K +0.1 % - mixed
    signs inside the screen's noise: no measurable speed cost.
  - RAM: the reader process 960 MiB idle, 1,115 MiB after a picture; per guard, max tree RSS +0.9 GiB (decode screen
    51.4 -> 52.3, full screen 58.6 -> 59.6) and min MemAvailable -0.9 GiB (35.6 -> 34.7; full screen 28.3 -> 27.4).
  - too tight for research runs with the reader always loaded until proposal A: o08's report stage reached 16.7 GB
    with relief at 18 (and relief only now at 20); ~1 GB more would have crossed the 16 GB floor. Options (no lower
    floor): 0.2.0's "elastic": true in the vision section - the reader starts with the first picture and stops after
    elastic_idle_s (120 s) without one; on an engine without --vram-elastic (ours) it just starts and stops, no VRAM
    give-back (server.py _vision_up / _vision_idle_down; to test: first-picture latency, the stop, RSS freed);
    proposal A at phase 4 (research conversations dropped at report start) should leave room for 1 GB; or the runner
    could stop the reader during research jobs.
* 22:45:46 switched back to C*18t (SHA checked), policy off; hard xhigh h02 started 22:45:58. kcheck clean.

## 0.2.1 port (10-20): branch r22-port021, gap 3 (03:08-04:19), results/r22/gap3/
v0.2.1.1 (10-20 05:21, final) is a Windows long-path / Docker hotfix: src/ and serve/ unchanged, CMake version string only
(0.1.46.1). The 0.2.1 port stands; no rebuild.
v0.2.1 tagged 10-20 03:04 (final; v0.2.0-beta + 107 commits; engine 0.1.46). Our 26 commits cherry-picked without
conflicts (worktree strata-r22p021; upstream touched only server.py, expert_source.cpp, generate.cpp of our files:
HIP queue priming, iGPU defaults, two-card batch groups, experts.bin io prefetch, user_args / "mtp": false - none
applies to our config). Same pinned ggml (3cf03257). Release-notes items for us: a hand-set --vram-reserve-mib is kept
(ours 713); the draft-layer VRAM count is setup/app-side only; experts.bin prefetch did not switch on (no "file tier"
line: our experts are in the RAM arena).
* Quality: exact7 7/7 identical to the 0.2.0 port (r22p-e7) and 7/7 repeat; needles 72/72 (TTFT 7.5 / 15.2 / 29.5 s);
  Stop at 120K all PASS; follow-ups 14/14 + 4/5; stop strings the same known case; tool tags 4/6 named (all calls
  parsed); copy 20/20, forged 0/30, plain 0/30; repeat3 3/3 (430bf6cb, = 0.2.0 port). Chat cache ALL PASS.
* Speed A B B A vs C*18t: decode screen decode -1.7 % (ms per round +9.5 %, tokens per round +7.6 %), TTFT 32K
  -0.9 %; full screen decode -2.0 %, long reasoning -0.3 / -2.2 %, TTFT 32K / 64K / 120K -0.7 / -0.8 / -0.7 %. Same
  picture as 0.2.0.
* Pictures: the reader rebuilt from 0.2.1's tools/vision is byte-identical (4829c210...). Identity with the expert
  cache pinned (4,551 slots both arms): 11/11 identical - gap 2's 8/11 was the 2-slot difference --vision makes, not
  the reader. Elastic reader: NOT engaged - 0.2.1's server needs the config's "vram_elastic": true for an elastic
  reader (server.py: "the vision section's elastic needs vram_elastic"), which also has the expert cache give up
  elastic_mib (2 GiB default) of VRAM during picture turns - pointless for a CPU reader. Picture answered 3.6 s to
  the first token, 6.1 s in all (reader already loaded). Options if wanted: a local server patch letting a CPU
  reader be elastic without vram_elastic; with the 12 GB floor (10-19 evening) the always-loaded reader (~1 GB)
  fits anyway.
* Unit tests: serve/ 895 OK (18 skipped); C++ 148 tests, the same 8 fail (upstream / test data / ggml fork).
* 04:19:52 switched back to C*18t (SHA checked), policy off. kcheck clean.

## Gap 4 (10-20 11:45-12:13): gap 3's decode loss, answered (results/r22/gap4/)

* **Arms:** A = C*18t; B = the 0.2.1 port with answer_room off (the same work as A); C = B with 0.2's RTX 50 defaults
  off (STRATA_SM120_PERF set, MMVQ_IL_120=0, MMVQ_IL_WIDE=0).
* **Order:** A B C C B A A B C C B A, 135 s each. Every arm exited cleanly; MemAvailable never fell below 34 GiB.

| | A C*18t | B 0.2.1, answer_room off | C = B, RTX 50 defaults off |
|---|---|---|---|
| decode (tok/s, mean of 4) | 153.2 | 154.6 (+0.9 % vs A) | 153.9 (-0.5 % vs B) |
| ms per verify round | 18.08 | 18.03 | 18.20 |
| acceptance | 0.715 | 0.723 | 0.723 |
| long reasoning math / code (tok/s) | 160.9 / 153.3 | 163.1 / 154.7 | 160.3 / 156.3 |
| TTFT 32K (s) | 7.70 | 7.65 | 7.64 |

* **The decode loss was not real.** With the same work in both arms, 0.2.1 decodes at parity with C*18t: +0.9 %, inside
  the per-arm spread of 150-156 tok/s.
  * Gap 3's -1.7 / -2.0 % came from answer_room: 0.2.1 stopped thinking at 3,072 tokens and then answered, while
    C*18t thought to the cap, so the two arms did different work.
* **The RTX 50 defaults change nothing measurable here** (C vs B -0.5 %), so they stay on as shipped. Step 2 was skipped
  (C vs B under 1 %).
* **Afterwards:** switched back to C*18t (e428a826c5fb) at 12:13:52 with the parking policy off; kcheck clean.
