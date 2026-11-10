### C. Verification (Phase C, 13:14 →)

Candidate **C\*6** = Strata v0.1.24 + `patches/r6/0001–0012` (C\*5's 9 patches unchanged + 3 new) + the RTX 4060 Ti as a
helper GPU (`--expert-cache-device1 3300`), built from a clean clone (`work/r6/build-cstar6.sh`, sm_89 + sm_120).
Baseline = C\*5 exactly (`engine-cstar5/strata`, `configs/Cstar5.json`). Both with your chat settings (the configs'
shared-settings file: temperature 1.0, top_p 0.95, top_k 20, min_p 0.05). Every test server ran under the memory guard.

| build record | C\*5 (reference / rollback) | **C\*6** |
|---|---|---|
| source | v0.1.24 `3ce2523` + patches/r5 0001–0009, tree 455b7a68 | v0.1.24 `3ce2523` + patches/r6 0001–0012, tree d70695dc (= branch r6-cand) |
| engine sha256 | `3ee92c9a…` (sm_120) | `a56a444b…` (sm_89 + sm_120) |
| config sha256 | `3255d7b2…` configs/Cstar5.json | `b9bd8eb2…` configs/Cstar6.json (fallback configs/Cstar6-single.json `69ff0885…`) |
| sampling / template | 0.6/0.95/20/0.05 in the config + your shared settings (1.0/0.95/20; min_p 0.05 from the config); template unchanged since round 1 | identical (shared-settings file copied unchanged) |
| GPUs | RTX 5080 (4,560 cached experts) | RTX 5080 (4,560) + RTX 4060 Ti (3,300) |

**The promotion gate (fixed before the runs):** a reproducible improvement larger than the measured noise, no
unexplained material regression in any workload, no new correctness or stability failure, no required check missing.

**1. A/B speed** (`results/r6/ab-c5-c6.md`; 4 alternating pairs, fresh server and cold page cache each; the first C\*5
screen ran on a not-fresh C\*5 server because of my stop-script bug, so a 4th pair was added):

| | C\*5 (4 runs) | **C\*6 (4 runs)** | change |
|---|---|---|---|
| time to first token, 68–87-token prompts | 0.45–0.46 s | 0.45–0.47 s | = |
| 1K prompt | 0.97–1.00 s | 0.96–0.98 s | = |
| 32K prompt (uncached, cold page cache) | 10.01–10.03 s | 10.00–10.02 s | = |
| 64K prompt | 19.37–19.42 s | 19.35–19.42 s | = |
| 120K prompt | 36.55–36.59 s | 36.54–36.63 s | = |
| **decode, all 768+-token requests** | 89.3 / 90.1 / 90.6 / 89.7 tok/s (mean **89.9**) | 91.9 / 93.8 / 93.2 / 95.4 (mean **93.6**) | **+4.1 %**, no overlap |
| ms per generated token (ms per verify round ÷ tokens per round) | 11.19 / 11.13 / 11.03 / 11.15 | 10.88 / 10.66 / 10.72 / 10.50 | **−3.9 %** |
| long reasoning 8K, math | 100.1 / 102.0 / 102.1 / 100.6 (101.2) | 100.9 / 105.4 / 103.8 / 105.3 (103.9) | +2.6 % |
| long reasoning 8K, code | 82.6 / 82.7 / 83.4 / 83.6 (83.1) | 85.6 / 86.3 / 85.8 / 88.2 (86.5) | +4.1 % |
| decode after 32K / 64K / 120K (single sampled runs, ±7 %) | 83–89 / 80–84 / 84–97 | 86–98 / 83–92 / 93–98 | ≥ |
| draft acceptance | 0.63–0.66 | 0.63–0.66 | = |
| peak VRAM 5080 / min MemAvailable / peak RSS | 15,416 MiB / 29.0 GB / 57.3 GB | 15,418 MiB / 28.7 GB / 57.5 GB | = (4060 Ti ≥ 1,043 MiB free) |

Prompt time and decode are reported separately above; "uncached" = no conversation reuse (fresh server, first
request of that size). First start and cold filesystem cache: every screen starts a fresh engine (load 14–15 s) with
the model files evicted from the page cache; the launcher's warm-up prompt (9,657 tokens, 3.5 s) absorbs the first
start's kernel loading for your requests.

**2. Other workloads** (all on C\*6 unless marked):

| check | result |
|---|---|
| **web-replay chat** (a fixed 4-turn chat whose first turn carries saved kernel.org / endoflife.date tool results, replayed without live searches; `results/r6/webreplay.jsonl`) | 16/16 turns answered and checked OK in both arms, no tool calls, identical reuse (5,889 / 6,259 / 6,330 cached tokens); turn 1 (5.9K tokens, fresh server) TTFT 2.19–2.20 s C\*5 vs 2.23–2.24 s C\*6 (+2 %), later turns equal; decode per turn 97.0 vs 104.4 tok/s |
| teacher-forced accuracy (7 texts, clipped at 5 nats) | one GPU = C\*5 bit for bit; helper vs C\*5: short +0.0005 / −0.0001, long −0.017 … +0.117 (round-5 spread); vs llama.cpp mean −0.016 (C\*5 −0.039) |
| **harder needle set** (12 documents × 6 questions, 32K/64K/120K) | **72/72** (C\*5 and llama.cpp 72/72); first token 10 / 19 / 37 s |
| **quality set** (5 prompts, 1 run, 32K cap) | 5/5 finished, 89–93 tok/s; objective checks 27/29 as scored = 28/29 in fact (one regex false negative: the answer re-adds the VLAN-10 deny after the permit, i.e. keeps the restriction) — round 5's C\*5-era run 28/29 |
| chat-cache round trip (park / resume / edit, helper on, static placement) | exact: 0 of 1,536 tokens changed, all NLLs identical, drafter 0 of 385, session state identical |
| **sampler-distribution test** (9,000 requests + attribution runs) | no bias — see below |
| Stop during a 120K read | server idle 1.0 s after Stop, next request 0.69 s, back to the parked chat 0.36 s |
| overflow, context ceiling, two requests at once, idle CPU | all pass (HTTP 400 in 0.2 s; finish "length" at ~126K; both answered; 0.12 % of one core idle) |
| VRAM taken after start | **not testable within your 300 MiB floor** (a second process's CUDA context alone takes ~266 MiB of the ~500 MiB free; my guard stopped the one attempt that went to 32 MiB); round 5 verified the warm-up protection on the same code |
| **headless-Chrome browser test incl. the Web search switch** | **54 of 56 pass**; the 2 are round 5's non-bugs (a 110-token chat is not parked by design; `/favicon.ico` 404). Web: switch shown / off by default / on, answer with 3 tool cards and a cited URL, cards survive a reload, follow-up, Stop during a tool call 0.01 s, off |
| launcher fallback | 4060 Ti short of memory (another process holds 1 GiB) → `run-strata.sh` starts the 5080-alone config and serves; memory back → the helper config |

**The sampler test in detail.** 9,000 sampled requests through the measurement build with C\*6's flags, at the three
round-1 near-ties, drawn either as a plain first token (j0) or inside a speculative window after three accepted drafts
(j3). No sample ever fell outside the allowed set. Against Strata's own forced log-probabilities, arith and code
passed, but the science tie failed at j3 (p < 0.001). Attribution:
* The forced reference itself moves while the adaptive expert tier re-places experts. Within one run its three
  repeats flip the order of ',' and ';' (0.419 vs 0.393 in the first repeat, 0.376 vs 0.427 in the next two). The
  samples, however, were drawn over thousands of requests while the placement changed.
* With placement ON, the failing case moves around: C\*6 one GPU fails j0 (p < 0.001) and passes j3 (p 0.39); a
  v0.1.24 C\*5-era build passes both (p 0.42 / 0.58).
* **With placement frozen (`--adapt-swaps 0`) on C\*6 with the helper,** the reference is identical in every repeat, and
  the samples match it: **j0 p 0.34, j3 p 0.63.** So the sampler and the speculative accept rule are unbiased.
  A chi-square against a drifting reference is not a valid test when the adaptive tier is on. That is a lesson for
  the test, not a defect in C\*6.
