## Round 10 — v0.1.35 → v0.1.36, the helper tier, upstream PRs, the Eddoursul fork, settings / Q4 → C\*12 (2026-10-02 07:25 → 2026-10-03)

Chronological notes: `NOTES.md` ("ROUND 10"). Phone summary: `results/round10-summary.md`. Build records: `results/r10/builds.md`. Patches: `patches/r10c/` (C\*12). PR drafts 36–40 (`pr-drafts/`).

Base: **v0.1.35** from the start of the round (Phase 0), replaced by **v0.1.36** at noon on 10-02 (your note; ported and measured on its own at the phase boundary after Phase A part 1). Every later track is a branch off the v0.1.36 port.

### Start of round
- **The 48-hour uptime monitor** (started at the end of Round 9, 02:46) was stopped after 4 h 40 min: 19 samples, all
  idle, health ok, one server process throughout (C\*11, engine e22354d1…); **none of your requests** (the 3 logged ones
  were Round 9's rollback test); MemAvailable ~37 GiB, 490 MiB free on the 5080, engine memory flat. At 07:16 something
  else briefly used ~260 MiB of the 4060 Ti (back by 07:25). Archived: logs/r10/uptime-c11-r9end/.
- **Release watcher restarted** (every 40 min; logs/r10/tagwatch.log). It found **v0.1.35** (tagged 02:44 today) at its
  first look. The base check now reads the newest vX.Y.Z tag from the watcher's full ref snapshot and compares it with
  the base tag directly at every look.

### Phase 0.1 — Strata v0.1.35, ported and measured on its own

v0.1.35 is a bug-fix release (13 commits, 19 files): the soft resident mode keeps what fits (#467; Windows trimming is
Windows-only), the prompt-chunk pick per split stage with a warning naming the small card (#448; layer split only),
`messages` sent as a JSON string (#460), draft counts in /metrics (#457), setup / calibrate / docs. No new network code.

**Port:** branch v35-c11 = v0.1.35 + C\*11's 16 commits, all applied without a conflict; `git range-diff` shows all 16
unchanged, and the +/- lines of the two series are identical. Measurement twin v35-c11-meas (+ the 4 MEASUREMENT commits).

| gate | result |
|---|---|
| upstream's server unit tests | **test_server 91/91**; all 7 server test modules 149 run, 0 failures, 9 skipped |
| 7 fixed-computation hashes vs C\*11 | **7/7 identical** |
| teacher-forced twin, 7 texts × helper / one GPU | **14/14 bit-identical to C\*11's twin** |
| chat-cache round trip (direct ×2, park → resume, resume + edit) | NLL 1536/1536 identical, argmax unchanged, state hashes equal (only "stale" differs, as always); with exact sampling off the drafter's guesses also 0 of 385 changed |
| Stop during a 120K read | **7/7** (idle 1.5 s after the close; next request 0.67 s; back to the chat 0.35 s) |
| ABBA vs C\*11 (full screens) | decode 115.8 → **115.4 tok/s (−0.4 %, noise)**; ms per round 17.94 → 17.95; TTFT 32K / 64K / 120K 9.25 / 17.84 / 33.72 → 9.24 / 17.85 / 33.75 s |

→ **the v0.1.35 port is Round 10's base** (frozen at 08:28; every Phase A–D track is a branch off it).

### Phase 0.2 — the base as served (sampled, your settings)

Two tools: upstream's own GPU stage stamps (`STRATA_VERIFY_PROFILE=1`, each stage includes a ~2 µs stamp) with its
per-request decode timing, and nsys traces of the NVTX build (served windows 150–269, untraced by stamps).

| | math (1,200 tokens) | LDR synthesis after a 24K prompt |
|---|---|---|
| window (nsys) | 16.49 ms (mean 2.6 tokens) | **21.36 ms** (mean 3.4 tokens) |
| GPU working | 12.97 ms | 14.58 ms |
| **GPU waiting for the CPU** | **1.89 ms** | **5.12 ms (24 %)** |
| idle gaps between kernels | 0.23 ms | 0.22 ms |
| the CPU pool's interval per layer / GPU work inside it | 90 µs / 63 % | 185 µs / 47 % |
| between windows (commit + MTP draft + host) | – | 2.41 ms (draft 2.26) |
| host waits for the 4060 Ti helper (engine) | 0.3 % of decode | 0.3–0.6 % |

Stage table (stamps, ms per window; results/r10/stages-base.md):

| stage | math | code | LDR synthesis |
|---|---|---|---|
| hyper-connection reads (both) | 3.12 | 2.69 | 3.02 |
| router / ring / hits | 0.68 | 0.68 | 0.71 |
| shared expert + its inputs | 0.94 | 0.86 | 0.93 |
| routed experts on the 5080 | 2.68 | 2.02 | 2.43 |
| PCIe stage (empty at --pcie-frac 0) | 0.34 | 0.30 | 0.33 |
| **wait for the CPU** | 3.44 | 2.54 | **4.75** |
| CPU rows + combine | 0.41 | 0.37 | 0.45 |
| GDN mixer (36 layers) | 2.97 | 2.71 | 2.95 |
| QSA mixer (12 layers) | 1.72 | 1.61 | 2.23 |
| head | 0.81 | 0.73 | 0.80 |
| draft round (MTP layer, host clock) | 1.55 | 1.20 | 1.84 |
| window (host clock) | 18.91 | 15.95 | 20.69 |

Kernel table (nsys, LDR, per window): flag waits 5.12 ms, dense GEMVs (native_mmvq_multi) 3.75, PR245's GPU experts 4.32
(gate/up 2.35 + down 1.97), v3 hyper-connection reads 2.73, attention 0.69, GDN 0.67, head 0.29.

**What it says:** on your LDR-shaped traffic the GPU waits for the CPU a quarter of the window — twice as long as on
plain text — because more of LDR's experts miss the 5080's cache; the first layers are the most exposed. That is what
Phase A's helper-tier work targets. The empty PCIe call costs 0.17–0.20 ms of kernels and ~0.3 ms of stream time per
window (B.4).

### Phase 0.3 — the LDR-shaped screen and its holdout

Built from the shape of Round 8's log of your traffic (529 requests, mostly Local Deep Research): prompts from 143 to
~37K tokens, median ~4K; 94 % of the time in decode, 70 % of it in answers of 8K+ tokens on 16K+ prompts; 15 % of
requests reuse a cached prefix. Contents are my own, in the way a deep-research tool talks to a model: 42 research
topics, each searched twice through our own SearXNG (8888 — not LDR's 8889/8890), the result pages fetched with the
server's own fetcher and frozen (work/r10/ldr/corpus/). Request kinds: search-query planning, JSON triage of results, an
OpenAI tools turn (the model picks its next call), source analysis with citations, long synthesis reports, and a
follow-up that reuses the synthesis's prefix.

| set | requests | prompt tokens (min / median / max) | use |
|---|---|---|---|
| screen (6 topics) | 12 | 143 / ~8K / 37K | Phase A–D decisions |
| holdout (6 other topics) | 12 | 141 / ~9K / 35K | read-only until Phase E |
| aging / profile pool (30 topics) | 60 | 135 / 3.8K / 33K | an hour of LDR-shaped traffic; A.4's routing traces |

On the base, two runs: **114.5 / 114.7 tok/s** (0.2 % apart), 2.29 tokens per round (the syntheses quote their sources,
so lookup windows land more often than on the general screens' 2.07), TTFT 0.93 / 2.71 / 6.12 s for prompts < 4K /
4–16K / ≥ 16K, 434 s per run. A separate general holdout for Phase E was also written and frozen now
(work/r10/holdout.py, sha256 21a10af2…).

### Phase 0.4 — decode speed vs server uptime: no drift

| source | data | trend |
|---|---|---|
| C\*7's monitor, your requests (answers ≥ 768 tokens) | 329 answers at 3.0–10.6 h uptime; 2-hour bins 108.5 / 106.0 / 111.8 / 111.2 tok/s | +0.95 ± 0.30 tok/s per hour with prompt and answer length as covariates (the afternoon's topics as much as anything) |
| Round 9's 2-hour soak of C\*11 | the same 32K probe every 10 min (12 runs) | −1.84 ± 1.76 tok/s per hour (not significant; the first, fresh one was the fastest) |

Engine memory was flat in both. Nothing here asks for a periodic restart. Figure: results/r10/uptime-drift.png.

### v0.1.36 (your note at noon on 10-02) — ported, measured on its own, the new base

v0.1.36 (15 commits): `--expert-profile-save` (#477), cluster decode kernels on sm_90+ (QSA top-k and the greedy argmax
on 8-CTA clusters), fused int8 prompt experts (#136; default for Q2_0 packs, opt-in `STRATA_PF_FUSED=1` for native IQ
packs like ours), a cancelled prompt logged with what it read (#471), the draft-head hint (#474), `update.sh` (#475; not
run). Security read: no new network code in the engine or server; the engine writes a file only with
`--expert-profile-save` to the path given.

**Port (branch v36-c11):** 15 of C\*11's 16 patches applied cleanly (exact sampling auto-merged in sampler.cu; checked:
only upstream's lines differ). The prompt-MMQ pointer patch conflicted (v0.1.36 moved the MMQ path into an `else` of
the new fused branch) and was re-applied by hand; **one interaction fixed:** in our pointer mode a streamed expert ends
at its ring slot's tail, so v0.1.36's fused branch now reads streamed blobs through the same `slot_blob()` (otherwise
`STRATA_PF_FUSED=1` would read the wrong bytes in our build).

| gate | result |
|---|---|
| upstream's server tests | test_server 100/100; all 7 modules 158 run, 0 failures, 9 skipped |
| 7 fixed-computation hashes vs C\*11 | **7/7** (cluster kernels on — their default on the 5080 — and off) |
| teacher-forced twin, 7 texts × helper / one GPU | **14/14 bit-identical** to C\*11's |
| chat-cache round trip | identical (as before) |
| Stop 120K | 3/3 |
| ABBA vs C\*11, full screens | decode 116.6 vs 116.6 tok/s; TTFT 32K / 64K / 120K within ±0.2 % |
| ABBA vs C\*11, LDR screen | decode +0.4 %, total time −0.5 % (noise) |

→ **the v0.1.36 port replaced the v0.1.35 port as the round's base**; Phase B, A parts 2–3, C and D were rebased onto it
(one conflict, #407 vs #477 in the adaptive tier's decay: both kept).

**Cluster kernels: kept on (default).** Same output on and off. Served screens could not resolve them (sampled answers
swing ±10 %); a fixed-computation pair (same tokens in both arms, 3 + 3 runs) did: **ms per verify round −2.8 % at a 112K
context** (22.20 → 21.58), −1.3 % at 32K, 0 at short context — as upstream's per-call numbers predict.

**`STRATA_PF_FUSED=1` (fused IQ prompt experts): → C\*12.** TTFT on the prompt-size screen 1K +1.7 %, 4K −5.9 %, 32K −3.5 %,
120K −3.4 %; decode unchanged; the 7 output hashes unchanged. Its teacher-forced NLL against our MMQ path looked worse
on long texts (+0.08 helper / +0.05 one GPU, borderline) — but **against upstream's FP16 prompt path (`STRATA_PREFILL_MMQ=0`)
the fused path is about half as far off as MMQ: mean |diff| 0.045 vs 0.107 (helper), 0.037 vs 0.092 (one GPU)**; the
apparent loss was MMQ's own offset from FP16 on those texts. The fused kernel keeps MMQ's precision class (int8 per 32
values, finer fp32 scales). Needles 12/12, repeat 3/3. **On the LDR screen (3 arms): TTFT −3.7 % (< 4K), −3.7 % (4–16K),
−3.3 % (≥ 16K) vs MMQ, decode equal.**

**`--prefill auto:16384` (D.2): takes 16K only with the fused path** (borrows 3,555 of 4,559 cache slots; with MMQ it stays
at 8K). Over fused 8K: a further TTFT −1.9 % on 4–16K prompts, −2.9 / −3.7 % at 32K / 120K, no decode cost on the LDR mix;
TF identical to fused 8K on 6 of 7 long texts, needles 12/12. **→ C\*12.**

### Phase A — the helper GPU's expert tier

**A.1 counts** (counting build; a fresh server → an hour of LDR-shaped traffic → the screen again; v0.1.35):

| | fresh screen | the hour | aged screen |
|---|---|---|---|
| (a) swaps whose incoming expert the helper already holds | **22.9 %** | **22.8 %** (0.93 M of 4.07 M) | **22.8 %** |
| … and swaps that push a helper-held expert back out | as many | as many | as many |
| (b) experts held by both cards (of the helper's 3,300) | 637 → 968 | 800–1,070 (24–32 %) | 924 |
| (c) routed entries: 5080 / helper / CPU | 71.0 / 6.6 / 22.4 % | 71.5 / 6.5 / 22.0 % | 71.5 / 6.5 / 22.0 % |

The 5080's tier swaps at its cap and keeps pulling hot experts the 4060 Ti already computes, then pushing them back; a
quarter of the helper's slots sit idle. The host waits for the helper only 0.3 % of decode. Aging changes nothing.

**A.2 — `STRATA_ADAPT_HELPER=1`: the tier skips helper-held candidates → C\*12.** (`=2`, half weight as in the fork's
7105fcc: weaker.)

| A/B (ABBA, your settings) | `=1` vs off |
|---|---|
| LDR screen, fresh (v0.1.35) | **121.1 vs 114.8 tok/s (+5.4 %)**, ms per round −4.6 %, total time −4.5 % (`=2`: +2.5 %) |
| decode screens (v0.1.35) | +2.5 %, ms per round −4.5 % (`=2`: +1.9 %) |
| aged server (v0.1.36; an hour of traffic first) | **+5.3 %** (115.7 → 121.9), ms per round −4.5 %, total time −4.9 % |
| over the hour of traffic itself | +5.2 %, ms per round −5.4 % |

Counts with `=1` (v0.1.36): 0 helper-held experts pulled in, 0 held by both; entries 5080 ~65 %, **helper 18 % (was 6.5 %),
CPU 17 % (was 22 %)**; the host now waits for the helper ~3 % of decode. **Gates:** TF on 9 texts (helper) — short within
±0.0003, long mean +0.016 (sd 0.038), the usual spread; needles 12/12; repeat 3/3 (CLI, tier live, exact sampling off).

**A.3 — the helper's set following the conversation (`STRATA_HELPER_ADAPT`): dropped.** Its experts do move (212–4,675 per
request, ≤ 2 ms waiting for the copies) but the CPU share falls only another 0.5–0.9 points; LDR +0.2 %, decode +0.7 % with
total time +1.3 %. It also lets the main tier pull helper-held experts again (~5 % of swaps: A.2's table is built once).
(Its counting build first failed: a brace I left in a hand-resolved cherry-pick; fixed and re-run.)

**A.4 — personal expert profile.** Routing traces of your own chat- and research-like prompts (two halves) + Round 6's
cache replay (validated: 99.92 % of entries placed as the engine placed them). With A.2, a profile from one half tested on
the other lowers the CPU share by only 0.1–0.2 points. **#477's learned profile (your note) — not kept, it loses:** it
ranks the hottest experts right after the 5080's resident set, so at the next start the helper holds them and A.2 keeps
them there: **the helper computed 37 % of entries and LDR decode fell 4.2 %** (decode screens −0.9 %). make_profile.py's
profile: +1.0 % / −0.8 % (noise). The shipped profile stays. Read with A.2 (6.5 → 18 %: +5.4 %), the helper's useful share
on this machine lies between 18 % and 37 % (backlog).

**A.5 — #407's `--adapt-decay`: 0.7 stays.** 0.8: LDR +0.4 %, decode +0.1 %; 0.9: +0.7 % / +0.6 % (ms per round ±0.2 %:
noise). `--adapt-tuned` does nothing here: the engine logs that the cache holds 19 % of the experts, outside its 20–60 % band.

### Phase B — open upstream PRs, each behind its switch

| PR | what | result | verdict |
|---|---|---|---|
| **#453** (efd79ba) | the draft layer's batched K/V for a KV-streaming ring | main state **bit-identical** after 32K / 64K / 120K prompts (all hashes but the drafter's); drafter acceptance on fixed long texts past 32K 1,800 vs 1,807 accepted drafts; **TTFT −0.6 s per long prompt: −7.1 % (32K), −3.7 % (64K), −1.8 % (120K)**; decode unchanged | **→ C\*12** |
| **#413** (c4436ec) | DeltaNet recurrence, a key head per thread | own parity test bit for bit (T 1…4,099) on the 84-SM 5080; recurrence 1.23×; served **TTFT −1.4 % (32K), −1.1 % (64K), −1.3 % (120K)**, exact (7/7) | **→ C\*12** |
| #443 (fcc9062) | `STRATA_GR_DOWN_MAX4`, `STRATA_MMVQ_WARP1` | max4 = upstream's default read bit for bit, **16–30 % slower than our v3 read at 1–4 tokens**; WARP1 changes bits (1 ulp) and at our 2–4-token windows saves ≈ 0.2 % per window on the 5080 (−8…−17 % on the 4060 Ti, which runs no dense GEMVs) | dropped, no served A/B |
| B.4 (#363's idea) | skip the empty PCIe call at `--pcie-frac 0` | exact; **no served gain** (LDR −0.3 %, decode +0.5 %): its 0.33 ms per window runs while the window waits for the CPU | dropped |
| #439 | — | does not apply over the prompt-MMQ pointer patch | not ported |
| #454 | — | no request in your logs ever sent "stop" | not ported |

### Phase C — Eddoursul's fork (branch custom 3a19944; measurement arm only, never on 8080)

Security read of its diff: no network code (no sockets / HTTP / process spawning), file writes only in opt-in debug
outputs and the packer. Built in its own worktree for both cards. **Its auto-sizing left 281 MiB free on the 5080 served
(216 MiB in the CLI) — below your 300 MiB floor; the guard stopped it.** It reserves nothing for its draft head; with
`--vram-reserve-mib 900` it keeps ~470 MiB free (ours ~494) at the cost of ~100 of its 4,776 slots.

**With its second GPU it is 3× slower here.** Its `--second-gpu` computes a share of every layer (and 45 % of the output
head) on the 4060 Ti with a per-layer round trip; built for a 3090 + 5070 Ti, on our Gen4 ×4 link it waits **35–40 ms per
window**: fixed text 45–48 tok/s vs our 117–144; served decode −64…−70 %, TTFT 32K 22.0 s vs 9.2 s, prompts 2.5–5.4× slower.

**Stage table, both on the 5080 alone** (CLI, same prompts, ms per verify window; results/r10/fork-stages-1gpu.md):

| stage | ours, math | fork, math | ours, code | fork, code |
|---|---|---|---|---|
| router / ring / hits | 0.44 | 0.74 | 0.45 | 0.68 |
| wait for the pool's plan | 0.25 | 0.03 | 0.25 | 0.03 |
| shared expert + expert inputs | 0.94 | 0.10 (+1.68 on a branch) | 0.87 | 0.08 (+1.38) |
| routed experts (VRAM) | 2.74 | 3.03 | 2.15 | 2.50 |
| PCIe stage | 0.33 | 0.03 | 0.31 | 0.03 |
| wait for the CPU | 5.16 | 12.41 | 3.69 | 8.88 |
| CPU rows + combine | 0.41 | 0.27 | 0.37 | 0.26 |
| **GDN mixer** | 3.03 | **2.39** | 2.75 | **2.36** |
| **QSA mixer** | 1.73 | **0.84** | 1.62 | **0.83** |
| **hyper-connection reads** | 3.18 | **2.32** | 2.74 | **2.23** |
| head | 0.75 | 0.61 | 0.67 | 0.61 |
| window total | 18.98 | 22.85 | 15.95 | 18.55 |
| decode tok/s | 127.6 | 107.3 | 103.8 | 99.5 |

Its mixers and reads are faster (~2–2.6 ms of the window on the critical path); its CPU path is far slower (pool 14.0
vs 8.6 ms per token), so overall it is slower than ours. **Your prompt-profile addition** (results/r10/fork-prompt-profile.md):

| prompt | ours (base, MMQ) | fork + 4060 Ti | fork, 5080 alone |
|---|---|---|---|
| 4K (4,118 tokens) | 1.65 s | 8.91 s (+440 %) | 1.73 s (+4.5 %) |
| 8K | 2.60 s | 9.87 s (+280 %) | 2.57 s (−1.2 %) |
| 32K | 9.53 s | 23.38 s (+146 %) | 8.79 s (−7.7 %) |
| 120K | 33.69 s | 83.60 s (+148 %) | 31.91 s (−5.3 %) |

(C\*12's prompt changes take ours below the fork alone: TTFT 32K 7.88 s, 120K 30.05 s.)

**Ports** (your order, the gap each explains; re-implemented on 0.1.36's window — the fork's commits do not apply):

| fork commit | port | result | verdict |
|---|---|---|---|
| 34a35db (GDN gates + QSA indexer beside the projections) | `STRATA_SIDE_MIXER=1` | exact; LDR ms per round −1.7 % (decode screens +0.2 %) | → C\*12 |
| b063c13 (gate projection, queries on a second branch) | `STRATA_SIDE_MIXER=2` | exact; decode screens −1.6 % over =1 (LDR 0.0 %) | → C\*12 |
| 962b99c (shared expert on a branch) | `STRATA_SIDE_SHARED=1` (the idea; 0.1.36 has no such branch) | exact; per generated token −0.9 % on both screens | → C\*12 |
| aa209f7, 81e276d | — | the fork's router is slower than ours (+0.23…+0.30 ms); "fewer QSA launches" — ours is batched already | not ported |
| 2ec7a80 (final mixer in one fused read) | — | on our build the fused read uses v3 rounding: a (b) change for ≤ 0.1 ms per window | not ported (backlog) |
| d9ce223, 22b46b6 / d3d48b1 / 235784c, b67a291, fd23d91 | — | not reached this round (drafter-side / kernel re-implementations; listed in the backlog with their gaps) | backlog |

### Phase D — settings, Q4, Signal

**D.1 — `--spec 8 --mtp-max-t 4` × `--suffix-draft` 3 / 8 / 16 (with v3 up to 4 tokens, v5 above): dropped.** Decode
screens +0.9 / −0.8 / +0.7 % (noise); copy-heavy screen s8×3 +3.4 % on the first pair, then pooled over 4 runs per arm
+0.7 % (ms per round +3.5 %); LDR screen s8×3 −0.9 % (ms per round +1.1 %). `--spec 4 --suffix-draft 3` stay.

**D.2 — `--prefill auto:16384`:** with our MMQ path the engine still picks 8K (borrows 2,408 slots); with the fused prompt
experts it takes 16K (borrows 3,555). → C\*12 with fused (above).

**D.3 — Q4 fair retest** (≤ 2 h, no tuning; a separate `-DSTRATA_MMQ_KQUANTS=ON` build, `--vram-reserve-mib 1000`, 32K, no
chat cache, the 5080 alone; RAM budget stepped 24 → 56 GiB, the last step before ~20 GB MemAvailable;
results/r10/q4-retest.md):

| | Q4 run 1 | IQ3_S | Q4 run 2 |
|---|---|---|---|
| decode, math (tok/s) | 59.7 | 124.8 | 60.2 |
| decode, code (tok/s) | 49.7 | 103.8 | 48.8 |
| TTFT 8K / 32K (s) | 4.34 / 12.50 | 2.33 / 8.17 | 4.11 / 12.23 |
| NVMe / file tier per math answer | 4.3 / 48 GB | 0.1 / 0 GB | 4.0 / 48 GB |
| swap-in pages (math) | 96 K | 0.1 K | 33 K |

**NLL Q4 − IQ3_S (one GPU, 4 human-written texts): corpus −0.007, 16K −0.248, 24K −0.221, 28K −0.078** — Q4 is the better
model on long texts. **Your addition, draft acceptance on the same forced texts (Q4 / IQ3_S):** 0.857 / 0.839, 0.576 /
0.585, 0.543 / 0.553, 0.615 / 0.618 (first-draft hits equal) — acceptance is not Q4's gap; the size of its experts is.

**Signal AP-Q4_K_XL (your addition): stopped at the engine, as instructed.** The packer accepted it (1,079 tensors, 302
native, 460 converted: 96 exact, 364 rounded; tokenizer identical to the IQ3_S pack's). **The engine rejects its token
embedding: `token_embd.weight` is Q8_0 (2,560 × 248,320)** — the native embedding path dequantizes only i-quants and BF16
("native embedding: token_embd.weight is absent, of another shape, or of a type without a GPU dequantizer"). No budget
steps or prompts were run (PR draft 40).

### Side findings

- **Sampled text with exact sampling does not repeat run to run** (C\*11 included): upstream's draft policy picks lookup
  vs MTP windows from measured times, and exact sampling's draws depend on the drafts offered. The output distribution is
  unaffected (the policy never sees a position's draw). **Correction to Round 9:** "deterministic landing makes served
  runs repeatable" holds with exact sampling off (CLI and served, given the same history); the repeatability gate now runs
  that way (PR draft 39).
- **Served repeat checks need a seeded (or no) warm-up:** an unseeded warm-up request put each fresh server's adaptive tier
  in a different state, so even greedy served output differed; without it C\*11's served output repeated 3/3.
- **Queue runner:** it logs every command's exit code as 0 (`$?` is read after a `$(date)` substitution); one failed build
  (A.3's counting build) hid behind it until its run failed. Checked the whole log: the only one. To fix at the next
  restart (not edited while running).
- **My process slips:** Phase C's measurements finished at 04:43 and the queue then sat at its hold until 09:50 (I had set
  no waiter) — 5 hours idle with C\*11 on 8080. And a few NOTES time stamps I first wrote ahead of the clock were corrected
  from the commits and the batch log.

### Phase E — C\*12: integrated and verified

**C\*12** = Strata v0.1.36 (36fa455) + `patches/r10c/0001–0025`: C\*11's 16 patches ported to 0.1.36, **0017 A.2** (helper-aware
tier), **0018 #453**, **0019–0022 #413** (+ its tests), **0023–0025 the verify-window branches** (fork ideas). Built from a
clean clone by `work/r10/build-cstar12.sh` (tree checked against the branch; engine-cstar12 **21fccd4f…**, sm_89 + sm_120).
Config `configs/Cstar12.json` = C\*11's flags + `--prefill auto:16384`, env + `STRATA_ADAPT_HELPER=1 STRATA_PF_FUSED=1
STRATA_SIDE_MIXER=2 STRATA_SIDE_SHARED=1` (C\*11's `STRATA_SPEC_EXACT=1 STRATA_GR_V3=1 STRATA_ADAPT_LAND=2` kept); the cluster
kernels are 0.1.36's default. Fallback `configs/Cstar12-single.json` (the 5080 alone). Not in C\*12: A.3, #477's learned
profile, decay 0.8 / 0.9, B.4, #443, D.1, 2ec7a80.

| gate | result |
|---|---|
| upstream's server tests (on the clean clone) | 158 run, OK (9 skipped) |
| start checks | C12: 570 MiB free on the 5080 after load (530 after a request), 892 MiB on the 4060 Ti; chunk 16,384; answered. Fallback: answered |
| every new switch off (incl. #453's) | **7/7 = C\*11** |
| teacher-forced, 9 texts × helper / one GPU | short texts within ±0.0003 / bitwise; long texts vs the FP16 prompt path: **mean \|diff\| 0.042 / 0.037 (C\*11: 0.107 / 0.092)**, signed +0.005 / +0.016 — closer to the exact computation than C\*11 |
| needles 32K / 64K / 120K | **12/12** runs 6/6 |
| chat-cache round trip | NLL 1,536/1,536 identical, 0 argmax changes, state hashes equal but `stale` |
| Stop during a 120K read | **7/7** (closed at 20.2 s, idle 3.5 s later, chat resumed from the cache) |
| repeat (CLI, tier live, exact sampling off) | 3/3 |
| browser test on a copy of the config (BR12) | 54/56 — the two known non-bugs (110-token chat below the park threshold; favicon 404); all web checks pass |
| fallback (1 GiB of the 4060 Ti taken) | Cstar12-single started and answered; after release the helper was used |

**Speed — C\*12 vs C\*11 (ABBA, fresh servers, your settings):**

| screen | decode | ms per round | TTFT | total time |
|---|---|---|---|---|
| **fresh general holdout** (never run before Phase E) | **110.1 → 118.8 tok/s (+7.9 %)** | – | 30K document **8.69 → 7.30 s (−16 %)**; short −11 % | **−8.3 %** |
| **LDR holdout** (never run before Phase E) | **113.0 → 122.5 (+8.4 %)** | **−8.5 %** | < 4K −6.8 %, **4–16K −18.7 %, ≥ 16K −14.0 %** | **−7.7 %** |
| full screens | **117.3 → 125.1 (+6.6 %)** | −8.5 % | **32K 9.25 → 7.88 s (−14.8 %), 64K −12.5 %, 120K 33.78 → 30.05 s (−11.0 %)** | −6.6 % |

Runs per arm within 0.3 % of each other (TTFT within 0.02 s). Every request kind of the LDR holdout is faster (+4.6 … +9.3 %).

**Soak, rollback, promotion:**
- **2-hour soak on 8080 (your traffic shape: big pasted documents overflowing the chat cache, going back, Stop,
  regenerate, web search, long reasoning, a 32K probe every 10 min): 414 requests, 0 errors**, Stop 151×; back to a kept
  big chat median 0.77 s (n = 97); re-read after an LRU drop median 7.96 s (C\*11: 9.71); new 32K / 64K / 120K pastes max
  7.85 / 15.63 / 29.94 s (C\*11: 9.24 / 17.85 / 33.70); **MemAvailable min 22.2 GB** (floor 20); engine RSS 50.5–64.2 GB with no
  growth after the cache filled; chat cache peak 12,273 of 12,288 MiB, never over; 32K probe decode 111–128 tok/s, no trend.
- Web replay on the soaked server: 4/4 turns, all content checks pass, the same prefix reuse as Rounds 8–9.
- **Soaked vs fresh decode screen: 123.2 vs 122.6 tok/s (+0.6 %), ms per round −1.2 %** — no slowdown after 2 h.
- **Promoted at 19:00 on 10-03** (`work/r10/promote-c12.sh`): the launchers default to `configs/Cstar12.json`; **real rollback
  test passed** (8080 → C\*11, both GPUs, answered → back to C\*12, both GPUs, answered). Rollback: stop 8080, then
  `STRATA_CONFIG=configs/Cstar11.json ./switch-model.sh strata`. A fresh 48-hour passive monitor runs (logs/r10/uptime/).

**After the promotion — v0.1.37 / v0.1.38:** both were released during the round (10-02 12:26 and 19:21) and I missed the
watcher's flags for ~25 hours (see Side findings). v0.1.38 merges #453 and #413 (both in C\*12 already), adds #407,
#443's opt-in read, prompt-path work and **server security fixes (a Host-header check against DNS rebinding; cross-site
browser requests refused without an API key)**. A dry-run port: 9 of C\*12's patches conflict (generate.cpp ×6,
server.py, prefill.cpp — our MMQ pointer mode vs upstream's new one-launch gather — and iq_kernels.cu). Porting it and
measuring it on its own is the next step (C\*12's base stayed frozen at v0.1.36 for this build phase, per your rule).

### Ranked backlog (lossless only; expected effect on this machine)

| # | item | expected | cost / risk | first step |
|---|---|---|---|---|
| 1 | **The helper's share sweet spot** (A.2 at 18 % gains 5.4 %; a learned profile at 37 % loses 4.2 %) | 1–3 % decode | low (settings / a ranking rule) | sweep helper slots or the share of hot experts it starts with, LDR screen |
| 2 | **#413-style speedups for the remaining critical-path mixer time**: fd23d91 (QSA decode attention split among blocks, (b)), b67a291 (projection rows per warp, IQ3_S decoded once, bitwise) | 1–3 % per round | medium (kernel ports onto 0.1.36) | port b67a291 behind a switch; mmvq_roofline on both cards |
| 3 | **The draft round** (22b46b6 / d3d48b1 / 235784c: front once, draft kernels in the main forms, a one-token window commits itself) | ~1 % (draft round 1.36 vs 1.14 ms) | medium (0.1.36's drafter differs: exact sampling, coupled drafts) | 235784c first (smallest) |
| 4 | **The CPU path** stays the critical path on research traffic (wait for the CPU 3.6–5 ms per window even with A.2) | large if reachable | high | profile the pool per layer on the LDR screen with A.2 on |
| 5 | A Q8_0 token-embedding dequantizer (lets Signal-type GGUFs load; PR draft 40) | enables a comparison | low | one dequantizer, or a BF16 one-tensor `--embd-gguf` from the GGUF |
| 6 | A fixed-cost draft-policy mode (repeatable sampled text with exact sampling; PR draft 39) | 0 % (test convenience) | low | cost table per window size from the screens |
| 7 | 2ec7a80 (the head's final mixer in one fused read) | ≤ 0.5 % | (b) on our build (v3 rounding) | measure with a plain-rounding fused call |
| 8 | Keep A.3's idea only with `helper_has` updated on every move | ≤ 0.5 % | low | — |
| 9 | Fix the queue runner's exit codes | – | trivial | capture `$?` before the `$(date)` |
