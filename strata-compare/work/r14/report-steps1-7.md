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
