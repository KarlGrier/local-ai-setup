# Round 10 — summary (live; updated after every phase)

**Now (18:45 Sat):** **C\*12 passed everything:** both holdouts (+7.9 % / +8.4 % decode, −8 % total time, TTFT up to
−19 %), every gate, the 2-hour soak (414 requests, 0 errors, MemAvailable ≥ 22.2 GB, chat cache never over budget), no
slowdown soaked vs fresh, browser test 54/56 (the two known non-bugs), fallback OK. **Promotion at 19:00** (then the
real rollback test and a fresh 48-hour monitor) unless you say otherwise.

**I missed two releases:** Strata **v0.1.37 (10-02 12:26) and v0.1.38 (10-02 19:21)** — the watcher flagged them and I
didn't read its lines for ~25 h. v0.1.38 merges #453 and #413 (already in C\*12) and adds server security fixes
(DNS-rebinding Host check, cross-site refusal). Plan: finish C\*12 on the frozen v0.1.36 base (soak running), promote
if it passes, then port v0.1.38 and measure it on its own next — unless you'd rather wait with the promotion.

## Helper-GPU expert tier (Phase A) — counts (A.1, done 10:21)
Fresh server → an hour of LDR-shaped traffic (100 requests) → the screen again; today's code (counting build):

| | fresh screen | the hour | aged screen |
|---|---|---|---|
| (a) swaps whose incoming expert the helper already holds | **22.9 %** | **22.8 %** (0.93 M of 4.07 M) | **22.8 %** |
| … and swaps that push a helper-held expert back out | as many | as many (0.93 M) | as many |
| (b) experts held by both cards (of the helper's 3,300) | 637 → 968 | 800–1,070 (24–32 %) | 924 |
| (c) routed entries: 5080 / helper / CPU | 71.0 / 6.6 / 22.4 % | 71.5 / 6.5 / 22.0 % | 71.5 / 6.5 / 22.0 % |

- The 5080's tier swaps at its cap (~25 swaps per window) and keeps pulling hot experts the 4060 Ti already computes,
  then pushing them back — so ~28 % of the helper's slots sit idle and its share of the work drops from 11 % (first
  request) to 6.5 %. The CPU still computes 22 % of all routed entries.
- Aging changes nothing: the state settles inside the first long answer (decode 113.9 fresh vs 114.0 aged).
- The host waits for the helper only 0.3 % of decode time.
- **The fix works (A.2, LDR screen ABBA): never pull in an expert the helper holds → 121.1 vs 114.8 tok/s (+5.4 %),
  total time −4.5 %**, prompts unchanged; counting them at half weight (the fork's rule) gives +2.5 %. **Decode screens
  agree: +2.5 %, ms per round −4.5 %, total time −4.1 %.** **Gates passed on v0.1.36** (accuracy within the usual spread, needles 12/12, repeat 3/3) → Phase E candidate; an aged A/B
  comes at the end of Phase A part 2; **A.2 on v0.1.36: 0 helper-held experts pulled in, CPU share 22 → 17 %; the host now waits for the helper ~3 % of
  decode time (was 0.3 %).** **A.3 (the helper's set following the conversation): dropped** — its experts do move (up to
  4,675 per request, ≤ 2 ms waiting) but the CPU share falls only another 0.5–0.9 points; LDR +0.2 %, decode +0.7 % with
  total time +1.3 % (noise).
- **Personal profile (A.4, replay of your own routing traces):** the replay reproduces the engine's placement on 99.92 % of
  entries. With the A.2 fix, the CPU's share falls from 22 % to 17 % of entries (the helper's rises from 6 % to 17–18 %).
  A profile learned from half of your traffic and tested on the other half lowers the CPU share by only another 0.1–0.2
  points (16.99 → 16.91 %, 16.46 → 16.23 %), so it is likely below the 1 % bar. A served A/B (v0.1.36's learned profile vs
  make_profile.py's vs the shipped one) will decide.
- **Learned profile (#477, your note): not kept — it loses.** It puts the hottest experts on the helper at start and A.2
  keeps them there: the helper computes 37 % of entries and becomes the bottleneck — research-style decode **−4.2 %**,
  decode screens −0.9 %. The make_profile.py profile: +1.0 % / −0.8 % (noise). The shipped profile stays.

## Q4 fair retest (D.3, your addition included)
- 56 GiB RAM budget (the largest step keeping ~20 GB free), 32K, the 5080 alone. **Q4 decodes at about half IQ3_S's speed
  (math 60 vs 125 tok/s, code 49 vs 104), TTFT 1.5–1.9× longer**, and reads 4–5 GB from NVMe plus ~48 GB through the file
  tier per long answer.
- **Q4 is the better model on long texts: NLL −0.25 / −0.22 / −0.08 at 16K / 24K / 28K** (corpus equal).
- **Draft acceptance on the same texts is the same** (0.857 / 0.576 / 0.543 / 0.615 vs IQ3_S 0.839 / 0.585 / 0.553 / 0.618).
  Details: results/r10/q4-retest.md.
- **Signal AP-Q4_K_XL: stopped, as you said.** The packer accepted it; **the engine rejects its token embedding, which is
  Q8_0** (token_embd.weight, 2,560 × 248,320): the native embedding path has no Q8_0 dequantizer. No budget steps or
  prompts were run.

## Repeatability (side findings)
- **With exact sampling off, served and CLI runs repeat bit for bit given the same history** (C\*11 served, no warm-up:
  3/3). My test's warm-up request was unseeded, so each fresh server started the measured request in a different tier
  state; that, not the engine, made earlier served repeats differ.
- **With exact sampling on (C\*11's setting), sampled text varies run to run**: upstream's draft policy picks lookup vs
  MTP windows from measured times, and exact sampling's draws depend on the drafts offered. The output distribution is
  unaffected. Round 9's "served runs repeat" holds only with exact sampling off; the repeatability gate runs that way.

## Upstream PR transplants (Phase B) — done (18:52)
- **#453 (drafter's ring K/V batched): keep → Phase E.** Main model state bit-identical after 32K / 64K / 120K prompts;
  drafter acceptance on fixed long texts unchanged (1,800 vs 1,807 accepted drafts, −0.4 %); **TTFT −0.6 s per long
  prompt: −7.1 % at 32K, −3.7 % at 64K, −1.8 % at 120K**; decode and total time unchanged.
- **#413 (faster DeltaNet recurrence on 64–95-SM cards): keep → Phase E.** Exact (7/7, own parity test bit for bit);
  **TTFT −1.4 % at 32K, −1.1 % at 64K, −1.3 % at 120K**; decode unchanged.
- **#443 GR "down max4": dropped** — same bits as upstream's default read but 16–30 % slower than our v3 read at 1–4
  tokens. (v5 is faster than v3 at 5–8 tokens: tested in Phase D.1.) **MMVQ_WARP1: dropped** — not exact, and at our
  2–4-token windows it saves ~0.2 % of a window on the 5080.
- **B.4 (skip the empty PCIe call, #363's idea): dropped** — exact, but no served gain (LDR −0.3 %, decode +0.5 %): the
  0.33 ms it removes runs while the window waits for the CPU anyway. #439 doesn't apply over our prompt patch; #454: no request ever sent "stop".

## Eddoursul fork vs ours — stage table (Phase C)
- **Its second GPU doesn't work on this machine:** it computes part of every layer (and 45 % of the output head) on the
  4060 Ti and waits 35–40 ms per window over the Gen4 ×4 link → served decode −64…−70 %, TTFT 32K 22.0 s vs 9.2 s,
  prompts 2.5–5.4× slower.
- **On the 5080 alone (ms per window, math / code), the fork is faster where it matters:** QSA mixer −0.89 / −0.79, HC
  reads −0.86 / −0.52, GDN mixer −0.64 / −0.39, plan wait −0.22, head −0.14 / −0.06, draft round −0.22. Its CPU path is
  much slower (+5–7 ms), so overall it is still slower than ours (107 / 100 vs 128 / 104 tok/s).
- **Prompts, fork alone vs our base:** 4K +4.5 %, 8K −1.2 %, 32K −7.7 %, 120K −5.3 % (before our fused / #453 / #413 gains).
- **Ports so far:** **34a35db + b063c13 (the GDN gates / gate projection and the QSA indexer / queries on side branches):
  exact, −1.5…−1.7 % per verify round on both screen types → Phase E candidate.** 2ec7a80 not ported (on our build it
  would change rounding for ≤ 0.5 %). 962b99c's idea (shared expert on a branch) built, being measured.
- **Port list** (your order, mapped to those stages): 34a35db, 962b99c, aa209f7, 81e276d, b063c13, 2ec7a80 / d9ce223,
  the draft-round trio, b67a291, fd23d91 — the critical-path stages add up to ~2–2.6 ms of a ~16–19 ms window.

## Phase 0 — done (08:51)
- **v0.1.35 port** (C\*11's 16 patches on v0.1.35, all applied without a conflict, identical patch content):
  - fixed-computation hashes **7/7 identical to C\*11**
  - teacher-forced twin **14/14 texts bit-identical to C\*11's**
  - chat-cache round trip: identical NLL on all 1,536 tokens, state hashes equal
  - upstream's server tests: **91/91** (all 7 server test modules: 149 run, 0 failures)
  - Stop during a 120K read 7/7; round trip with exact sampling off: 0 of 385 drafter guesses changed
  - **ABBA vs C\*11: decode 115.8 → 115.4 tok/s (−0.4 %, noise), prompts equal → the v0.1.35 port is the base.**
- **Speed vs server uptime (0.4): no slowdown.** Over 3–10.6 h of your real traffic C\*7 did not slow down (2-hour bins
  108.5 / 106.0 / 111.8 / 111.2 tok/s); Round 9's 2-hour soak: the same 32K probe has no significant trend.
  Figure: results/r10/uptime-drift.png.
- **LDR-shaped screen + holdout (0.3) built and frozen:** 42 research topics, real search results and pages fetched
  through our own SearXNG (not LDR's), turned into query-planning, JSON triage, tool-call, source-analysis,
  long-synthesis and prefix-reusing follow-up requests. Screen 12 requests (prompts 143–37K tokens, median ~8K),
  holdout 12 (other topics, read-only until Phase E), aging pool 60 (median 3.8K, like your 4K).
- **Profile of the base as served (0.2):** a decode window is 16–21 ms. On your LDR-shaped traffic the GPU waits for
  the CPU **5.1 ms of a 21.4 ms window (24 %)** — twice as long as on plain math text (1.9 ms) — because LDR's experts
  miss the 5080's cache more; the first layers are the most exposed. The host's wait for the 4060 Ti helper is only
  0.3–0.6 % of decode time. The empty PCIe expert call costs ~0.3 ms per window (built a switch to drop it: B.4).
  Stage tables: results/r10/stages-base.md, nsys10-ldr.txt.
- **LDR screen baseline:** 114.5 / 114.7 tok/s on two runs — repeatable to 0.2 %, so it is Phase A's main screen.
- **#454 (stop sequences):** the server's logs don't record request bodies, so they can't show whether any request
  sent `stop`. Per your rule, not ported.

## Start of round
- **48-hour uptime monitor stopped** after 4 h 40 min: 19 samples, all idle, health ok, **none of your requests**.
  Archived in logs/r10/uptime-c11-r9end/.
- **Release watcher restarted** (every 40 min). It found **v0.1.35** at once (tagged 02:44 today): Windows AMD fixes,
  a low-RAM resident mode on Windows, `messages` sent as a JSON string, draft counts in /metrics, setup fixes. No new
  network code.

## v0.1.36 (your note, ~12:00) — done: same output and speed as C\*11 → the new base
- **Same output as C\*11:** 7/7 fixed-computation hashes (cluster kernels on, their default on the 5080, and off);
  teacher-forced twin bitwise identical on 14/14 texts; chat-cache round trip identical (as before); Stop 120K 3/3.
- **Same speed (ABBA vs C\*11):** decode screens 116.6 vs 116.6 tok/s, TTFT 32K / 64K / 120K within ±0.2 %; LDR screen
  decode +0.4 %, total time −0.5 % (noise). It is the round's base from here; C\*11 stays the rollback target.
- Ported: patches 1–11 and 13–16 applied cleanly (exact sampling merged into sampler.cu without a conflict; checked:
  only upstream's 154 lines differ). The prompt-MMQ patch was merged by hand into v0.1.36's new structure, and v0.1.36's
  fused prompt path now reads streamed experts where our pointer mode puts them.
- Will measure: same output as C\*11, TF twin, round trip, Stop 120K, ABBA (full + LDR screens); cluster kernels (same
  output; decode at short context and after 32K / 120K vs `STRATA_QSA_CLUSTER=0`); `STRATA_PF_FUSED=1` vs our MMQ path
  at 1K / 4K / 32K / 120K + its TF gate; whether `--prefill auto:16384` takes 16K with or without it.
- **Cluster kernels: kept on (default).** Exact; with the same tokens in both arms, ms per round −2.8 % at 112K, −1.3 % at
  32K, 0 at short context (the served screen was too noisy to show it).
- **Fused prompt experts (`STRATA_PF_FUSED=1`): a winner, to confirm on the holdout in Phase E.** On the research-style
  screen TTFT is −3.7 % (< 4K), −3.7 % (4–16K), −3.3 % (≥ 16K) with decode unchanged; the prompt-size screen agrees
  (−5.9 % at 4K, −3.5 % at 32K, −3.4 % at 120K). Gates passed: against upstream's FP16 prompt path it is **about half as
  far off as our MMQ path** (mean distance 0.045 vs 0.107 helper, 0.037 vs 0.092 one GPU), needles 12/12, repeat 3/3.
- **16K prompt chunk (only possible with fused):** a further −1.9 % TTFT on 4–16K prompts, −2.9 / −3.7 % at 32K / 120K, no
  decode cost on real traffic. **Gates passed** (accuracy identical to fused 8K on 6 of 7 texts, needles 12/12) →
  Phase E candidate together with fused. This also answers D.2.
- `--expert-profile-save` goes into A.4 (learned vs make_profile.py vs shipped, incl. what the helper holds at start).

## Your additions (received ~09:30) — queued
- **Q4 retest:** draft acceptance for Q4 and IQ3_S on the *same* texts (the server's force mode on four human-written
  texts, the drafter's guesses scored against the text), plus the served acceptance.
- **Fork:** prompt times and the prompt-stage profile at 4K / 8K / 32K / 120K next to ours, with and without its
  second GPU.
- **Signal AP-Q4_K_XL** right after the Q4 retest (≤ 2 h, no tuning): packed in the workspace; if a tensor format is
  rejected I report which and stop; else budget stepping, then the same prompts on Signal and on C\*11 (acceptance,
  tokens per round, output tokens per answer, decode tok/s, time per finished answer).

## Phases
| phase | status |
|---|---|
| 0 update + baselines | **done** — v0.1.35 port = base (same output and speed as C\*11) |
| v0.1.36 port | **done** — base from now on; cluster kernels on; fused prompt experts → Phase E candidate |
| A helper expert tier | **done** — A.2 → Phase E (+5.4 % fresh, +5.3 % aged, gates passed); A.3, learned profile, decay 0.8/0.9 dropped |
| B upstream PR transplants | **done** — #453, #413 → Phase E; #443, B.4 dropped; #439 / #454 not ported |
| C Eddoursul fork | **done** — measured; ports 34a35db + b063c13 (−1.5…−1.7 %/round) and 962b99c's idea (~0.9 %) → E; 2ec7a80 not ported |
| D settings + Q4 retest | **done** — D.1 dropped; D.2 = 16K chunk with fused (→ E); Q4: half speed, better long-text NLL, same acceptance; Signal: engine rejects Q8_0 embedding |
| E integrate + verify | **running** (from 14:40): C\*12 build, gates, holdout A/Bs |
