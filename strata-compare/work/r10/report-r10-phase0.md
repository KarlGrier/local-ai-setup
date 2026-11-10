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
