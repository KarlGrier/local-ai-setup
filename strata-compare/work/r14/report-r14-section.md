

## Round 14 — catch-up to v0.1.40.1 with the runbook: the release alone, the ledger pass, overlaps, the cost-aware gate, calibration, session files, the fit planner → C\*14 (2026-10-06 07:28 → 2026-10-07)

Chronological notes: `NOTES.md` ("ROUND 14", "HANDOFF", "RESUME"). Phone summary: `results/round14-summary.md`. Scripts:
`work/r14/`; runbook runs `bringup/out/r14/` (the release alone + the first gates) and `bringup/out/r14f/` (the clean
clone of the final series). Raw results: `results/r14/`. Branches (local): r14-port (the first port, 40), r14-port2 /
r14-port3 / r14-port3g (the verdicts applied), **r14-final (C\*14's 34 commits = patches/r14c34f)**, r14-final-meas
(the twin, patches/r14-meas34f), r14-gate, pub14/\* (Step 9). Interrupted once on your request (17:45 → 22:38, the RAM
test: nothing was mid-run; the handoff note in NOTES.md), and once more for the display move (00:22 → 00:52).

**Result: C\*14 = Strata v0.1.40.1 + 34 patches (53 → 34). Against C\*13.1, A B B A: LDR +3.4 %, decode +4.2 %, full
+5.4 %, and on Round 12's two holdouts nobody had run: +5.7 % (general) and +3.0 % (LDR-shaped); prompt reads equal.**
Every gate passed (acceptance suite 11 / 0, exact7, needles 12 × 6/6, Stop at 120K, round trips, browser 41 / 2 known),
the 2-hour soak and the real rollback test: see "Soak, rollback test, promotion" at the end of this section.

### Step 1 — the release alone

**Base frozen at 07:29: v0.1.40.1 (82f46a8c, tree cc527a20)**, the newest release (v0.1.40 + 7 server / setup commits:
#1012 restart and admission fixes, #1058 / #804 tool calls in code fences or in the thinking, #997 / #890). Upstream
rewrote the history of every tag during the day; all 42 remote tags keep our trees (metadata only). The 48-hour monitor
had run 38 minutes (06:50 → 07:28): 3 samples, health ok, no requests of yours, memory and VRAM flat.

**Defaults and setup changes since v0.1.39** (full list: `results/r14/v040-defaults.md`):
* Engine options: no existing default changed; every new option is off (`--kv-grow`, `--adapt-async`,
  `--pipeline-windows`, `--batch-mtp`, `--lookup-chain`, `--mtp-q4`, `--mtp-draft-vocab`, …). **`--remote-expert-opt`
  stays off** (only setup adds it on 2+ GPUs, unchanged from v0.1.39; we do not use setup's configs). **The
  lower-precision options are all opt-in and off:** `--mtp-q4` (4-bit drafter), `--kv k8v4` / `q4_0`, `STRATA_HC_Q8`.
* 91 new `STRATA_*` switches. 18 are "arch defaults" for gfx1151 (Strix Halo) only. On CUDA these are new and **on by
  default**: #783 PR-a…k (QSA early exit, exact-T GDN gates, batched K/V + indexer appends, fused per-head norm + RoPE,
  multi-token HC read / write, 16-lane expert gate/up and two MMVQ rows a block, the drafter's catch-up skipping rejected
  rows, the shared expert forking after the doorbell), the fork's F7 (the final mixer read once per window, one-token
  windows commit themselves, multi-block argmax / top probability, the drafter's shared-expert branch and copy kernels),
  AVX-VNNI CPU rows (this Zen 5 has them), read-ahead at start.
* Server: session files (`--slot-save-path`), opt-in reasoning-loop recovery, "Connection: close" on every response,
  completed empty assistant turns skipped, JSON taken out of prose / fences in json mode, #553 / #879 / #931 / #454 /
  #700. Setup: MIN_ENGINE 0.1.40, k8v4 streams when chosen, Strix Halo detection, tips only.

**Its output vs v0.1.39's** (both stock, my flags, exact7's pinned runs): **6 of 7 bit-identical**; the 7th, sampled
math, splits at token 958 of 1,024. A bisect over the release's own off-switches (7 runs) pins it to one default,
**`STRATA_HEAD_MIX_MULTI`** (F7, fork 2ec7a80: the final mixer before the head reads the window's tokens in one
`fused_gr_read_multi` instead of `gr_read` per token) — `=0` alone restores v0.1.39's output. **Class: rounding-level**
(another summation order); the test that shows it: exact7's sampled-math pair. Every other new default leaves all seven
outputs bit-identical. The release repeats itself 7/7 and passes its server tests (452).

**The release alone vs C\*13.1** (A B B A, fresh server per arm; the release with my flags, none of our switches, no
chat cache):

| screen | C\*13.1 | v0.1.40.1 alone | change | ms per round | acceptance |
|---|---|---|---|---|---|
| LDR decode (tok/s) | 137.8 | 113.3 | **−17.8 %** | +19.0 % | 0.719 → 0.673 |
| decode screen | 136.8 | 115.2 | **−15.8 %** | +13.9 % | 0.707 → 0.654 |
| full screen | 138.7 | 116.1 | **−16.3 %** | +15.9 % | 0.699 → 0.667 |
| TTFT 32K / 64K / 120K | 7.79 / 15.54 / 29.98 s | 7.80 / 15.48 / 29.88 s | equal | | |

### Step 2 — ledger pass: 53 → 34

The runbook stopped at `clone` as Round 13 predicted (row 1 conflicts in generate.cpp) → manual step 1: in a worktree,
each row cherry-picked in ledger order onto v0.1.40.1 (now `bringup/lib/pick.sh` + `resolve.py`):

| outcome | rows (Round 13 numbers) |
|---|---|
| **upstream carries it → dropped (12)** | 18 #550 (identical diff), 19 #700 (identical), 20 #454, 22 their A/B switches, 38 #838, 40–43 #931 (the tokenizer's control list, longest first, like ours), 50–51 #896 (⊂ #651) |
| **conflicting, neither a fix nor ≥ 1 % → dropped (1)** | 9 dump-routing (measurement only) |
| **ported by hand** | 1 side stash (the chat cache sits on it), 5 web search, 10, 11, 12 exact sampling (optional drafter), 13, 15, **16 + 17 the side mixer rewritten on 0.1.40's window** (each branch now runs upstream's PR-b / d / f steps; switch off = upstream's exact launch order), 21 #652, 28–32 B.3, 33–34 B.1 (also covers 0.1.40's one-launch final mixer), 35 #567 (post-#931 form), 46 guards |
| applied unchanged | 2, 3, 4, 6, 7, 8, 14, 23–27, 36, 37, 39, 44, 45, 47 (#958: upstream fixed only the native half), 48 #619, 49 #648, 52, 53 |

The port compiled first try. Then the runbook's gates: **patched with every switch off = the release 7/7**, 8 guards
checked / 0 off, every switch gate PASS. One server test failed: row 53 (`model_check`) still set the OLD switch of
the dropped #700 rows → amended (it now only turns our web search off) → manual step 2.

**A served A B B A per patch, in the ledger's order of value** (each = the switches before it + this one; for an exact
patch the time per round is the signal: tokens per round moved ±1.5 % with nothing that touches acceptance changed):

| patch | screen | decode | per round | verdict |
|---|---|---|---|---|
| helper-aware tier | LDR | **+5.3 %** | −4.5 % | keeps its place (step 3: as upstream's switch) |
| B.2 split attention | LDR | **+3.0 %** | −4.6 % | kept |
| B.1 fork HC read | LDR | +0.8 % | −2.2 % | kept (step 3: +6.1 % over upstream's new read) |
| exact sampling | decode | **+3.5 %** | +2.5 % (acceptance +8.5 %) | kept |
| A.2 Q8_K rows | LDR | **+1.4 %** | −1.0 % | kept |
| B.3 interleaved MMVQ | LDR | **+2.0 %** | −3.1 % | kept |
| side mixer =2 | decode | **+2.5 %** | −4.7 % | kept |
| PR245 (vs #783 PR-h) | decode | +1.6 % | **−0.1 %** | equal → upstream's; **dropped** with its #838 site and stride fix |
| n-gram prefetch | decode | +1.0 % | **+0.3 %** | no gain on 0.1.40's PLE path → **dropped** |

**Patch count: 53 → 34** (12 carried upstream, 1 by your rule, PR245 ×3 and the prefetch by their A/B, landing and the
helper rule by step 3, the Stop watcher ×2 by upstream's #879; rows 16 + 17 merged into one; + the cost gate and B.3's
new table). Ledger: `patches/LEDGER.md` (Round 13's: `patches/LEDGER-r13.md`).

### Step 3 — overlaps (ours vs upstream's on the same build)

| | identity (adaptive tier live, seed 11) | served A B B A | winner |
|---|---|---|---|
| landing: ours `ADAPT_LAND=2` vs `STRATA_ADAPT_LAG=2` (#764) | **4/4 bit-identical** | decode −1.1 % (per round −2.1 %) | equal → **upstream's** |
| helper rule: ours `ADAPT_HELPER=1` vs `STRATA_DISJOINT_ADAPT=1` (#731) | **4/4 bit-identical** | LDR −0.5 % (per round +0.4 %) | equal → **upstream's** |
| hyper-connection read: B.1 (fork) vs 0.1.40's multi-token read | – | **upstream's −6.1 %** (per round +6.0 %) | **ours** |
| drafter / head kernels from the fork (F7: upstream's only) on vs off | – | +0.6 % with them | **upstream's (on)** |
| grouped expert kernels: PR245 vs #783 PR-h (step 2) | – | per round −0.1 % | equal → **upstream's** |
| mixer branches: our side mixer vs 0.1.40's window (step 2) | – | per round −4.7 % with ours | **ours** |
| batched uploads (#807 / F12) | – | cannot act here: forced to one copy each with a helper GPU, no PCIe share at `--pcie-frac 0`; ours was #550, now upstream's | – |
| Stop during a long prompt read: our watcher vs #879 | – | the release alone: read stopped at the next chunk, idle 3.5 s after the close (ours: 3.0 s, the same chunk rule) | equal → **upstream's** |

### Step 4 — the cost-aware draft gate

Round 12's r12-gate rebased (one include conflict). **Chi-square on the gate build's kernels: ALL PASS**, including
both gate cases (p 0.47 / 0.61 first token, 0.25 / 0.28 first two) and the negative control caught (χ² 35,465).
**Served A B B A, gate off vs on: LDR +2.8 %, decode +3.4 %** (tokens per round +10–12 %, time per round +7–8 %, TTFT
equal) → **kept**. Its table is Round 12's (`configs/r12-cost-gate.txt`), fitted to this drafter on v0.1.39's window
costs — noted in the ledger; a new drafter or model needs a refit. With the gate on, `--spec-min-p` no longer sets the
window. Greedy outputs regroup (rounding-level): all-on exact7 2/7 = C\*13 (without the gate the all-on pins were
C\*13's own hashes).

### Step 5 — calibration (24 of 90 minutes) and B.3's table

| value | old → alternative | decode | per round | verdict |
|---|---|---|---|---|
| helper slots | 3300 → 3475 | +2.2 % | +1.4 % | keep (the unchanged arms alone spread 2.6 %) |
| VRAM reserve | 713 → 613 MiB | −1.6 % | −1.8 % | keep |
| resident KV | 32K → 16K | +1.2 % | −0.7 % | keep |
| prompt chunk | 16K → 32K | +0.5 % | −3.9 % | keep (TTFT 32K +1.3 %, 120K −1.4 %) |
| draft floor | 0.5 → 0.4 | +0.5 % | +0.7 % | keep (the gate sets windows now) |

**Every value stays.** **B.3's rows-a-warp table re-derived: 17 of 80 cells differ** (all toward the rows-a-warp
kernels: v0.1.40's native_mmvq changed underneath) → a new commit; exact7 7/7 = the build before it, B.3's pair gate
PASS, decode A B B A +0.2 % (per round −1.8 %).

### Step 6 — session files (report only)

My config + `slot_save_path`; greedy turns; "parked" = another chat in between (ours stays in our RAM chat cache).

| | 40K chat (40,025 tokens) | 190K chat (189,795 tokens; `--max-context 262144`) |
|---|---|---|
| file / save | 847 MB / 0.20 s | 3.13 GB / 0.54 s |
| restore (same process, after another chat) | 0.27 s | 1.08 s |
| restore in a new process | 0.27 s | 1.24 s |
| next turn after a restore | TTFT 0.26–0.31 s (27 tokens read) | TTFT 0.67 s |
| the same turn without save / restore | 0.17 s | 0.20 s |
| cold first read | 9.8 s | 47.6 s |
| **anything lost?** | greedy continuation identical to the never-saved one **with fixed expert placement** (same process, new process, control: all 3 identical); with the adaptive tier live the continuations diverge after ~10 tokens — and the two restores also differ from each other, i.e. residency, not the file | identical (same process, new process) |

### Step 7 — fit planner, two margins

| file | RAM needed | room at the 20 GB test floor | room at an 8 GB serving margin |
|---|---|---|---|
| IQ3_S (ours) | 60.5 GiB | 62.0 → fits (1.5 spare) | 74.0 → fits (13.5 spare) |
| UD-Q4_K_XL | 85.4 GiB | 62.0 → no: one GPU + `--resident-budget-gib 48` | 74.0 → no: budget 60 GiB |

**The rule stands: a RAM budget cannot be combined with the helper cache.** v0.1.40's "resident variant on several
GPUs" (#642 / #848) is a RAM budget with a **layer split** — v0.1.39 refused "layer splits or remote expert caches",
v0.1.40.1 refuses only "remote expert caches" (confirmed by a start on the stock build). So a too-big-for-RAM file can
use the 4060 Ti only as a layer-split stage beside a budget; the planner now names that as an unmeasured third option.

### Step 8 — C\*14: clean clone, acceptance suite, gates, the comparison with C\*13.1

**C\*14 = v0.1.40.1 + patches/r14c34f** (branch r14-final, tree f5722e94; engine-cstar14 sha256 9e163314…, built by the
runbook from a clean clone; strata-cstar14 at r14-final; `configs/Cstar14.json` = C\*13.1's flags with
`STRATA_ADAPT_LAG=2` and `STRATA_DISJOINT_ADAPT=1` in place of our two dropped switches, and
`STRATA_COST_GATE=configs/r12-cost-gate.txt`; `Cstar14-single.json` = the one-GPU fallback). The final series differs
from the fully gated 35/36-commit one only in serve/server.py (our Stop-watcher rows dropped for upstream's #879): the
clean re-clone built, its server tests pass, and C\*14's exact7 = the 36-commit candidate's 7/7.

* **Runbook gates (clean clone):** the release reproduces itself 7/7 and Round 14's first stock run 7/7; patched with
  every switch off = the release 7/7; `strata patch guards: 6 checked, 0 off`; switch gates: B.2 TF −0.0008 / −0.0006,
  B.1 TF +0.0008 / −0.0026 (bound 0.005), exact sampling chi-square ALL PASS, the cost gate's chi-square ALL PASS, side
  mixer / B.3 / A.2 pairs identical.
* **Acceptance suite vs llama.cpp (57 min): 11 pass, 0 fail, 2 reported** — ids 9/9; teacher-forced NLL short 0.2909 /
  0.3865, long clipped 2.0459 (llama.cpp 2.0440), unclipped 3.5119 (**C\*13.1's values to the digit**: the gate does not
  act on fixed windows); needles 36/36; round trips 3/3; samplers PASS; stops ALL PASS (llama.cpp 5 of 9); tool calls
  6/6; 4,235 boundary splits 0 differ; control-token text 20/20 · 0/30 · 0/30 (llama.cpp 0/20 · 30/30) — the last
  three through upstream's own #454 / #700 / #931 now.
* **Gate set (results/r14/s8-gates-c14.txt): ALL PASS** — exact7 7/7 = the gated candidate; needles 12 × 6/6
  (32K / 64K / 120K); Stop at 120K 7/7 (read stopped at the next chunk, idle 3.5 s after the close, back to the earlier
  chat from the chat cache in 0.35 s); #652 follow-ups 14/14 + 5/5; stop strings ALL PASS; tool tags 5/6 with every call
  parsed (the miss: the model wrote "the web_search tool" instead of the tag, as in Round 13); #931 probe 20/20 · 0/30 ·
  0/30; repeat 3/3; round trips 3/3 identical; browser 41 / 2 = Round 10's two known non-bugs.

**C\*14 vs C\*13.1 (A B B A, fresh server per arm; 22:38 → 00:22; both holdouts' sha256 checked first):**

| screen | C\*13.1 | C\*14 | decode | ms / round | tokens / round | acceptance | TTFT | total time |
|---|---|---|---|---|---|---|---|---|
| LDR (12 requests) | 138.7 | 143.4 | **+3.4 %** | +6.9 % | +10.5 % | −3.1 % | +0.2…+0.5 % | −2.7 % |
| decode | 138.5 | 144.4 | **+4.2 %** | +5.9 % | +10.4 % | −5.3 % | 32K −0.2 % | −2.7 % |
| full | 138.8 | 146.3 | **+5.4 %** | +6.2 % | +12.0 % | −3.7 % | 32K / 64K / 120K ±0.1 % | −2.9 % |
| general holdout (Round 12, never run before) | 134.8 | 142.4 | **+5.7 %** | – | – | – | 27K doc equal; short −3.7 % | −4.4 % |
| LDR holdout (Round 12, never run before) | 136.7 | 140.8 | **+3.0 %** | +6.8 % | +10.0 % | −2.3 % | equal | −3.2 % |

Long reasoning math / code: +3.8 / +6.6 % (decode screen), +6.6 / +8.7 % (full). The one shape that loses is the
short tool-call answer (LDR −4.4 %, LDR holdout −9.9 %: one request per screen, two runs per arm; a long window
does not pay for a short answer). Most of the gain is the cost-aware gate (longer windows: tokens per round +10–12 %, time per round
+6–7 %); the rest is B.3's new table and v0.1.40's own kernels under our patches. These screens ran with the desktop on
the RTX 5080 (after the RAM test; it cost the 5080 ~90 cache slots, both arms alike); the soak ran with it on the iGPU.

### Step 9 — publish/ refreshed (nothing posted)

* **Branches:** 7 `pub14/*` on v0.1.40.1 (side-mixer, b3-mmvq-il with its re-derived table, a2-router-q8k, spec-exact,
  cost-gate (new, stacked on spec-exact, with its measurements file), b1-gr-fork, b2-split-attn), rebuilt from the
  ported series; **all 7 compile**; author `strata-compare <noreply@localhost>`. Retired: ple-prefetch (no gain on
  0.1.40), adapt-land and adapt-helper (upstream's #764 / #731 compute the same). The round 13 `pub/*` branches stay.
* **Draft comments:** each now opens with a status line — obsolete: #550, #454, #700, #838, #931 (merged), #903
  (taken opt-in, per segment); #748's half of pr-788-748 and #896's part of pr-958-… obsolete; #567, #652, #911,
  #958 / #619 / #648, PR245 (if it stays open) and the file-tier issue still relevant.
* **Benchmark report:** a "Round 14" section with v0.1.40.1's numbers (the release alone with this config, C\*14 vs
  C\*13.1, the cost gate). `privacy_check.py` (now also over pub14/\*): **CLEAN**. `publish/README.md` has the Round 14
  table; nothing was posted, pushed or sent.

### The runbook's first real use — time and manual steps

| part | wall clock | how |
|---|---|---|
| clone → stop at the series (as Round 13 predicted) | 07:31:57, 1 s | unattended |
| **manual 1: the ledger pass** — 53 rows cherry-picked in ledger order, 12 drops (upstream), 1 drop (your rule), the side mixer rewritten | 07:37 → ~08:00 (≈ 25 min) | by hand (now bringup/lib/pick.sh + resolve.py) |
| first runbook run r14: inspect, fitplan, pack, build (release, then patched + twin), stock, patched, patches | 35.5 min of stages | unattended |
| manual 2: one server test failed (a dropped row's switch inside model_check) → amended | ≈ 5 min | by hand |
| the verdicts of steps 2–5 applied (the series rebuilt five times: 40 → 36 → 34 → 35 → 36 → 34) | ≈ 30 min over the day | by hand, between measurements |
| manual 3: the new gate missing from the runbook's list of our switches → stopped at build, fixed, restarted | ≈ 2 min | by hand |
| final runbook run r14f: clone → patches, calib (24 of 90 min), b3table, 2 × clone + build, accept | 125.3 min of stages | unattended |
| manual 4–6: calibration tables read (the stage had cut them: fixed); B.3's table pasted (the runbook's design); the Stop rows dropped for #879 | ≈ 25 min | by hand |
| **total** | **runbook stages 2 h 41 min unattended + ≈ 1.5 h by hand** | from the release tag to an accepted C\*14 |

The round's own experiments around it (the release-alone screens and bisect, 9 per-patch A B B A, the overlaps, the
gate, session files) took most of the day's wall clock (07:31 → 17:19, then the screens and the soak after the RAM
test). Runbook fixes made: the identity on `am --abort`; llama.cpp linked before the series (the release alone can be
built while the series is resolved: `RB_BUILDS=stock`, `RB_STOCK_REF`); caches in `RB_CACHE`; `RB_SWITCH_ENV` /
`RB_PATCH_ORDER`; a `cost_gate` patchtest row; the calibration tables kept whole; the inspector and the negative test
follow the tree's guards; the planner's serving margin; the release watcher counts four-part tags. My own slips (none
cost a measurement): a first screen overlapped one minute of a build (aborted and rerun from scratch); a `pkill -f` that
matched its own shell; a `sed` delimiter that released a queue hold early (the acceptance run it started was stopped
after 17 s and redone). **Day one:** `bringup/DAY-ONE.md` is rewritten for this flow (a new release, the ledger pass,
the per-patch A B B A, the gate's refit).
