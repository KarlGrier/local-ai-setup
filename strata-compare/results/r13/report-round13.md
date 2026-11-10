## Round 13 — readiness for a new model: bugs, the patch ledger and guards → C\*13.1, inspector and fit planner, runbook and two rehearsals, the acceptance suite, upstream prep (2026-10-05 17:33 → 2026-10-06 06:50)

Chronological notes: `NOTES.md` ("ROUND 13"). Phone summary: `results/round13-summary.md`. Scripts: `work/r13/`
(round jobs) and `bringup/` (what a new model needs: inspector, planner, runbook, acceptance suite, harness copies).
Raw results: `results/r13/`, `bringup/out/`. Branch r13-fix (= C\*13.1's 53 patches, `patches/r13c39/`), r13-meas
(+ 4 measurement commits, never served), r13-t773 (#773 trial), 9 `pub/*` branches (Part 6, local only).

**Base = C\*13** (engine-cstar13 0839b20b…, v0.1.39 + 37 patches). **One promotion: C\*13.1 = v0.1.39 + 53 patches**
(engine-cstar131 732bcd6a…, tree c9d5cb88), promoted 10-05 22:45 after all gates, a 2-hour soak and a real rollback test;
**C\*13.1 is on 8080.** It computes what C\*13 computes: exact7 7/7 = C\*13's hashes with the same switches; LDR and
decode screens +0.3 % (noise). Upstream released **v0.1.40 at 10-06 01:33** (307 commits) and **v0.1.40.1 at 04:53**
(a re-cut on another line); the watcher only logged them. Their one security fix (#553: /v1/responses reading a local
file as an image for a foreign page that `cors_origins` admits) cannot be reached on this server (every foreign-origin
/v1 POST is refused; no `cors_origins`, vision off) → not ported (your rule); it comes with the day-one base. A merge
preview of our series into v0.1.40: 57 conflict hunks in 14 files, a good part of them from transplants v0.1.40 already
carries (#550, #454, #700, #838's sites, #931, #651 ⊃ #896, #748).

### Part 1 — known bugs and loading safeguards

| item | finding | action | result |
|---|---|---|---|
| 1. #838 (q8_1 scale / sum stored without the #606 clamp) | upstream's 2 sites (the shared expert's fused SwiGLU — on by default; gfx906's fused gate/up) **plus a 3rd in our tree: PR245's `native_gus_kernel`, every decode window**. The q8_0-style stores (fp16 scale only) overflow only past \|x\| > 8.3 M — listed, not changed | #838 + our site (finite blocks bit for bit) + a fixture (`check_gus_finite`) | C\*13's kernels: **619 / 700 (x 1e3) and 700 / 700 (x 1e4) blocks stored inf**; fixed: 0 differ from the old kernels, 0 non-finite, both cards; exact7 7/7 |
| found on the way | upstream's own native_grouped_parity: **1,229 failures on C\*13** — PR245's kernels take one group per grid row, 0.1.38+ launches the PCIe call with 4 rows striding over up to 16 groups | grid-stride loop | 0 failures; C\*13 never hit it (`--pcie-frac 0`), a config with pcie-frac > 0 would have |
| 2. #931 (control-token text in a message becomes a real control token) | **reproduced on C\*13** with synthetic documents: copying a line that contains control text **3/20** exact, a forged turn inside a document marked untrusted **followed 30/30**; 1,739 / 1,739 prompts with control text carried forged control ids | ported (3 commits; our #567 encoder rebased onto #537's plain spans; d55679c's test reference) + `STRATA_CONTROL_LITERALS_OLD=1` | **copy 20/20, forged 0/30**, plain 0/30, no warning 30/30; **ids 0 differences on prompts without control text** (389 prompts / 851,570 tokens; #567's own check 0 in 28,545,945); stop test 9/9; server tests = C\*13's. **llama.cpp has the same bug** (copy 0/20, forged 30/30 in Part 5) |
| 3. crash recovery | kill -9 mid-answer, SIGSEGV mid-prompt, kill -9 idle: the client gets what was sent + an error event; **the next request restarts the engine and answers in 12.2 s**; lost: the request in flight and the chat cache (a cached turn 0.35 → 2.7 s) | **no gap → #788 / #748 not ported** | both PRs' own tests fail on 0.1.39's server code; #788's BrokenPipe seen once at shutdown (harmless). v0.1.40 carries #748 |
| 4. loading safeguards | each trial-merged alone, built, exact7 | **#958, #648, #896 taken; #619's code taken** (its only conflict: docs) | 7/7 identical each alone and together |
| 5. iq_multi_parity on CUDA 13.3.73 | #538: 13.2.78 miscompiles IQ3_S / IQ2_S on sm_120 | – | **all checks pass on both cards** (IQ3_S ref rel ≤ 6.8e-8, IQ2_S ≤ 5.7e-5) |
| 6. Cstar13.json's settings | neither key set | – | **repeat_stop_tokens = 256** (default), **reasoning_budget_tokens = 0 (no budget)** |

### Part 2 — the patch ledger and guards → C\*13.1

- **patches/LEDGER.md**: 53 rows, one per commit (what, files, switch, class, gate command, gain, upstream PR, model
  assumptions). **Totals: exact 16, rounding-level 2 (B.1, B.2), distribution-preserving 1 (exact sampling), fixes 15,
  serve / UI 7, measurement / test 12.** Upstream PRs carried: 12 (#550, #567, #652, #454, #700, #838, #931, #958, #619,
  #648, #896, PR245) + 6 ideas from fork Eddoursul.
- **Model-number audit:** our patches read upstream's constants almost everywhere. Bound to this model in our own code:
  B.1's scratch (26,368 floats; 52,736 = 2×; tied to N / HC / LR by static_assert), B.3's row classes (speed only), A.2's
  n_embd % 256; 40,525 and 248,320 are read from files. **Upstream itself hard-codes the embedding vocabulary 248,320** —
  a new vocabulary needs upstream.
- **Guards:** 8 startup guards cover the 12 rows whose assumptions go beyond upstream's own checks; a mismatch logs one
  line (`strata patch guards: …`) and turns that patch off, upstream's path runs. Unit test: 12 synthetic mismatches /
  12. **Negative test: each guard forced = the switch off by hand, hash for hash.** The server checks its 54 fixed
  template-string uses against the model's tokenizer and template at start (`serve/model_check.py`). One false positive
  found and removed (the hc weights' GGUF type).
- **One-command exactness test per patch:** `bringup/patchtest.sh NAME` (pair / tf / chi2 by class).
- **Inactive patches:** side-stash and dump-routing are inert without their flags but entangled with active patches —
  kept, documented. Nothing moved out.
- **C\*13.1** (clean clone): exact7 7/7 = C\*13; needles 72/72; Stop at 120K 7/7; #652, stops, #931, tool calls, repeat
  3/3, round trips, browser 41 + 2 known non-bugs; **screens vs C\*13: LDR +0.3 %, decode +0.3 %**; **soak 423 requests,
  0 errors** (back to a big chat median 0.74 s, MemAvailable min 22.6 GB, RSS flat 63–64 GB, soaked decode −1.3 %);
  **promoted 22:45; rollback test: 8080 → C\*13 (0839b20b, answered) → C\*13.1 (732bcd6a, answered).** Rollback any time:
  stop 8080, `STRATA_CONFIG=configs/Cstar13.json ./switch-model.sh strata`.

### Part 3 — inspector and fit planner (predictions vs reality)

- `bringup/inspect_model.py` (headers only, 0.2 s, works on 16 MB partial downloads): tensor roles, trunk vs MTP,
  tokenizer / template / control tokens, n-gram table; upstream's fixed geometry and formats and each guard's assumption,
  constants parsed from the engine tree. **IQ3_S: RUNS. UD-Q4_K_XL: RUNS (+ `-DSTRATA_MMQ_KQUANTS=ON`). Signal
  AP-Q4_K_XL: NEEDS UPSTREAM — token_embd Q6_K.** Synthetic headers (hidden 3072, a 2-layer MTP block, undeclared nextn
  tensors, a Q4_0 embedding) each NEEDS UPSTREAM with the exact constant named; a declared 1-layer nextn RUNS.
- `bringup/fitplan.py`:

| prediction | planner | reality | |
|---|---|---|---|
| 5080 slots, IQ3_S (3 configs, Part 3) | 4,655 / 2,580 / 3,233 | 4,559 / 2,646 / 3,226 | +2.1 / −2.5 / +0.2 % |
| 5080 slots, IQ3_S (Rehearsal A) | 4,653 | 4,551 | +2.2 % |
| 5080 slots, UD-Q4_K_XL (Rehearsal B) | 2,682 | 2,722 | −1.5 % |
| helper maximum, IQ3_S | 3,583 | 3,500 ran, 3,600 refused (Round 11) | ✓ |
| RAM, IQ3_S | 60.5 GiB | C\*13's soak peak 60.2 GiB | ✓ |
| RAM, Q4: experts 71.7 GiB vs room 62 GiB | does not fit | the budget mode's 48 GiB ran at MemAvailable ≥ 35 GiB | ✓ |
| Q4 starting config (first version) | helper + `--resident-budget-gib 48` | **refused by the engine** (no RAM budget beside a helper cache) | ✗ → fixed |

### Part 4 — the runbook and two rehearsals

`bringup/RUNBOOK.md` + `bringup/runbook.sh RUN STAGE…` (clone inspect fitplan pack build stock patched patches calib
b3table screens accept soak promote) + `bringup/DAY-ONE.md` (one page).

**Rehearsal A — the same model from a clean v0.1.39 clone (unattended): reproduces C\*13.1.** Clone trees = r13-fix /
r13-meas / v0.1.39; a fresh pack byte-identical to C\*13's; stock (v0.1.39 as released + my flags) exact7; **patched with
every switch off = stock 7/7; each switch's gate PASS in order of value** (adapt_helper, qsa_split_attn tf −0.0008 /
−0.0006, gr_fork tf +0.0008 / −0.0026, spec_exact chi-square, router_q8k, mmvq_il, side_mixer, adapt_land); **all on:
exact7 7/7 = C\*13**; calibration (24 of 90 min) kept every value (helper 3,300 vs 3,475 −0.2 %, reserve 713 vs 613
−1.0 %, resident KV 32K vs 16K −3.0 %, prompt chunk 16K vs 32K ±1.4 %, draft floor 0.5 vs 0.4 −3.1 %); **B.3's table
re-derived: 80 cells, 0 differ**, parity bitwise; **suite 11 pass / 0 fail**; **screens vs the promoted C\*13.1: LDR
+1.4 %, decode −0.6 % (noise)**.
**Time: 2 h 33 min unattended (clone 23:48 → suite 02:20) + 37 min for a screens re-run = 3 h 10 min.** Manual steps:
(1) the v0.1.15 tree's llama.cpp link is relative → the first try stopped at build (fixed: absolute link); (2) two table
scripts imported a Round 11 module (fixed); (3) generated configs lacked the shared chat settings (the first screens
compared T 0.6 against T 1.0; fixed, re-run); (4) by design: reading the calibration and screen tables. With (1)–(3)
fixed, a repeat needs only (4).

**Rehearsal B — Unsloth UD-Q4_K_XL (4 shards, K-quant experts): what the runbook got wrong.**
1. **The planner wrote a RAM budget beside the helper cache; v0.1.39 refuses that** ("--resident-cpu-experts does not
   support layer splits or remote expert caches"; v0.1.40 still refuses it next to a helper cache). With the helper,
   the only placement that keeps the 20 GB floor is `--mmap-experts`.
2. **Both GPUs + `--mmap-experts`: 15.4 tok/s** (x-math greedy; 2.43 GB of experts copied out of the page cache per
   round — the round is that copy). **One GPU + `--resident-budget-gib 48`: 31–33 tok/s (2.1×)**; it needs 100 MiB more
   VRAM reserve (the page-locked, GPU-mapped RAM copy; the memory guard stopped the first try at 276 MiB free). The
   planner now starts there and names the both-GPU placement as the alternative. **The helper GPU cannot help a file
   whose experts do not fit in RAM, on v0.1.39 or v0.1.40.**
3. **The exactness gate assumed a repeatable stock. On this file stock v0.1.39 does not repeat itself** in any placement
   that reads experts from the files, adaptive swaps off: both GPUs mmap stock vs stock 5/7, one GPU mmap 2 of 3 alike,
   one GPU budget 2 of 3 alike (x-math); the runs split late at near-ties (tokens 475–927; once at token 5 of the 112K
   item) and land on the same alternatives whichever build. **Fix:** stock runs twice; experts read from files → the
   patched-off check is `bringup/lib/repeat_gate.py` (the first differing token of patched-off vs stock must come no
   earlier than half of stock vs stock's — negative control: B.1/B.2's rounding change diverges at tokens 3–98 → FAIL)
   and every exact switch is gated by teacher-forced NLL (TF noise of two identical arms: −0.0001 / 0.0000 nats, bound
   0.005).
4. **Results on the tuned placement (one GPU + `--resident-budget-gib 48`):** stock 7/7 outputs (MemAvailable ≥ 35 GiB,
   5080 ≥ 372 MiB free); patched-off: repeat gate PASS (poff = stock 7/7; poff2 split at tokens 928 / 521 — the
   variation once more); guards 8 checked, 0 off; **switch gates all PASS** — TF noise −0.0001 / 0.0000, qsa_split_attn
   −0.0011 / −0.0026, gr_fork −0.0001 / +0.0006, exact sampling chi-square ALL PASS, router_q8k 0 / 0, mmvq_il −0.0001 /
   0, side mixer −0.0011 / 0, landing −0.0008 / −0.0003 (bound 0.005; the two exact switches above the one noise sample
   are 5× under the bound — adaptive swaps can place experts differently between the TF arms); **calibration (44 of 60
   min) keeps every value**: the candidate's own old arm varies decode 45.8–47.6 tok/s and TTFT 32K 15.6–21.4 s between
   pairs, so resident KV 16K (+4.1 % decode) and a 32K prompt chunk (TTFT 32K −17 %) do not clear +2 % beyond it —
   worth a repeated A/B on day one; draft floor 0.4 −4.8 % (acceptance −10 %); **B.3 table 0 of 80 differ.**

   | decode screen (A B B A) | decode tok/s | ms / round | acceptance | long reasoning math / code | TTFT 32K | screen total |
   |---|---|---|---|---|---|---|
   | untuned: stock, both GPUs, `--mmap-experts` (the planner's first config) | 26.8 | 74.0 | 0.648 | 30.9 / 26.0 | 16.5 s | 419 s |
   | stock, one GPU + RAM budget (the tuned placement) | 44.7 | 43.9 | 0.646 | 53.3 / 41.4 | 18.1 s | 257 s |
   | **tuned: + 53 patches + calibration** | **47.4** | 44.1 | 0.697 | 53.8 / 45.8 | 15.5 s | 246 s |

   **Tuned vs untuned +77 %: the placement +67 %, patches + calibration +6.1 %** (nearly all acceptance, from exact
   sampling; the round is the CPU experts, 44 ms vs ~15 on IQ3_S with the helper, so the helper-aware tier has nothing to
   act on). Swap in use rose 2.5 → 4.6 GiB in the budget placement (MemAvailable ≥ 33.8 GiB).
5. **#773 (Linux unbuffered file tier):** acts only with a RAM budget (its own 2nd commit), so it was tried alone on the
   tuned one-GPU budget config, A B B A: decode −1.4 %, total −2.8 % — **no effect, and its log says why: with the 48 GiB
   copy built, 36.1 GiB is still available, so the file cache can keep the other 23.7 GiB of experts and #773's rule
   picks the buffered path, the same as without it.** Not taken; it matters on smaller-RAM PCs. #699 not tried (startup
   read-ahead; cold start only).

**Time for Rehearsal B: 2 h 18 min for the run that went through (03:56 planner → 06:14 screens), 3 h 17 min from the
first start** (02:57 refused at stock; 03:05 stopped at patched; a 25-minute bisect), well inside the 6 hours.

**No-drafter start (#708 reference):** `--mtp` removed → the server stops after the full 15 s load: "strata serve: needs
--spec T, --mtp DIR and --prefill CHUNK"; no chat cache (it lives in the served engine). #708 not ported (the server
fails clearly; a model without a drafter needs upstream's change or `generate` mode).

### Part 5 — the acceptance suite against llama.cpp

`bringup/acceptance.sh LABEL CONFIG TWIN [GGUF]` — one command, one table; the same GGUF in both engines; identical
token ids wherever numbers are compared. **On C\*13.1: 11 pass, 0 fail, 2 reported; Rehearsal A's clean-clone build
the same.**

| row | Strata (C\*13.1) | llama.cpp (same IQ3_S file) | criterion | result |
|---|---|---|---|---|
| tokenizer + template ids (9 conversations) | ids identical 9/9 | template text identical 9/9 | ids identical | PASS |
| TF NLL short (math / corpus, 1,536 tokens) | 0.2909 / 0.3865 | 0.2879 / 0.3872 | \|Δ\| ≤ 0.01 per text | PASS |
| TF NLL long, 7 texts 16K–112K, clipped at 5 | mean 2.0459 | mean 2.0524 (Rehearsal A's run: 1.9758) | \|mean Δ\| < 2 se between texts | PASS |
| TF NLL long, unclipped | 3.5119 | 3.5276 | −0.016 ± 0.076 | reported |
| needles (6 documents × 6 questions, 32K–123K) | 36/36 (Rehearsal A 35/36) | 36/36 | ≥ llama.cpp − 1 and ≥ 90 % | PASS |
| chat-cache round trip (park → resume → edit) | 3/3 identical | – | first difference: none | PASS |
| exact-sampling chi-square (real kernels) | ALL PASS | – | ALL PASS | PASS |
| near-tie frequencies vs Strata's own probabilities (6 cases × 200) | min p 0.039 (Rehearsal A 0.096), none outside | – | every p ≥ 0.01 | PASS |
| the same vs llama.cpp's probabilities | min p 0.004 | – | – | reported (different logits at a near tie) |
| stops (split across tokens and chunks) | ALL PASS | 5 pass, 4 fail | Strata ALL PASS | PASS |
| tool calls (prose naming the tag first) | 6/6 parsed | 6/6 parsed | every call parsed | PASS |
| every boundary split (parser, stop matcher) | 0 differ in 4,235 | – | 0 differ | PASS |
| control-token text in documents (copy / forged / plain) | 20/20 · 0/30 · 0/30 | **0/20 · 30/30 · 0/30** | copy ≥ 19/20, forged ≤ 1/30 | PASS |

**Run time: one clean unattended pass 57 min 12 s** (Rehearsal A). **llama.cpp's long-text NLL is not repeatable:** the
same scorer, flags, file and card gave 2.0524 and 1.9758; its NLL files differ from the first token of every long text,
**mean |d| 0.109 per text (max 0.255) — as large as Strata vs llama.cpp (0.062 / 0.108)**; Strata's 9 NLL files were
bit-identical in both runs. The long-TF row's criterion (mean shift vs the spread between texts) was right not to read
one llama.cpp run as exact.
**5.2 KV precision (llama.cpp):** f16 − q8_0 on the 9 texts: short +0.0012 ± 0.0013, long clipped +0.035 ± 0.057 (f16
the worse side); inside llama.cpp's ubatch spread (0.104 mean |d|) and its run-to-run spread (0.109) → **int8 KV cleared,
nothing changed.**
**5.3 STRATA_IQ_MT_MIN=1 (report only):** pinned 16K-prompt runs repeat 6/6 with the default and 6/6 with MT_MIN=1
(different outputs, ~7 % faster in those CLI runs); Round 12's drift did not reproduce.

### Part 6 — prepared for upstream (nothing published)

`publish/README.md` lists every item for your decision: (a) the benchmark report in COMMUNITY_BENCHMARKS.md's format
(runs.csv, prompt-reads.csv, the helper slot sweep, `--remote-expert-opt` part by part); (b) 12 draft comments (#550,
#652, #454, #700, #567, #903's equal-chunks checkpoint problem, #838, #931, #958/#619/#648/#896, #788/#748, #911, PR245);
(c) 9 local branches on v0.1.39, one per change of our own, exact ones first (A.2, B.3, the n-gram prefetch, landing, the
helper-aware tier, the side mixer), then exact sampling, B.1, B.2 — each with its measurements, **all 9 compile**, author
`strata-compare <noreply@localhost>`, no session links; (d) `publish/privacy_check.py`: **CLEAN** (17 files, 9
branches). Added after Rehearsal B: `comments/issue-file-tier-repeat.md` — a draft new issue (check for an existing one
first): greedy output not repeatable when experts are read from the GGUF; the RAM budget refused beside a helper cache;
the budget's ~100 MiB of VRAM that the reserve does not count.

### Day one
The one-page checklist is `bringup/DAY-ONE.md` (also at the end of `results/round13-summary.md`).

### Machine state at the end
C\*13.1 on 127.0.0.1:8080 (engine 732bcd6a, configs/Cstar131.json; answered; 5080 506 MiB free, MemAvailable 38 GB);
SearXNG 8888 up. Queue runner and release watcher stopped; a fresh 48-hour passive monitor writes
logs/r13/uptime-c131/. Disk 744 GB free. Rollback: stop 8080, `STRATA_CONFIG=configs/Cstar13.json ./switch-model.sh
strata`.
