### Phase C — combine, verify, promote

**C\*9 = Strata v0.1.30 + `patches/r8c/0001–0014`**: C\*8's 12 patches, plus 0013 (PR245 grouped experts) and 0014
(the prompt's MMQ reads streamed experts in place). Clean clone (`work/r8/build-cstar9.sh`), engine
`a7efa8fe5a0b48f6…`, tree `680b1f38`. `configs/Cstar9.json` = C\*8's flags. Every build's hashes are in
`results/r8/builds.md`.

**Two problems caught on the way, both mine:**
1. **Prompts 6 % slower.** The first C\*9 read long prompts 5.5–6.2 % slower than C\*8. My track-2 kernel edit had
   turned 1,152 read-only global weight loads into generic loads in every MMQ launch (SASS), and track 2's own A/B
   had only compared it on vs off inside the patched binary. Fixed (offsets relative to the restrict pointer; the
   loads are back), then re-measured against C\*8: −3 % prompt time. Phase C restarted on the fixed build.
2. **16 chat slots fail the memory floor.** With many big pasted chats (the needle test), 16 slots let the chat cache
   fill its whole 16 GiB: MemAvailable reached the 20 GB guard floor and the guard stopped the server during the 12th
   question. Reverted to 6 slots; the needles then passed 72/72.

**Gates**
| gate | result |
|---|---|
| (a) exact, CLI, fixed cache, C\*9 vs C\*8: greedy math / code, sampled math / code (seed, T 1.0), 2K / 32K / 112K prompts | **bit-identical on all 7** |
| SASS of the clean build | C\*8's loads plus 32 read-only 64-bit loads for the offsets (iq4_nl, iq3_s instances) |
| teacher-forced NLL, 7 texts × helper / one GPU, vs C\*8's twin | first pass 12/14 bit-identical; 2 differed mid-text (see "An open point"); **with the adaptive tier off: identical in 12 of 12** |
| PR245 kernels under compute-sanitizer (parity harness, both cards) | racecheck 0 hazards, memcheck 0 errors, initcheck 0 errors (no uninitialized reads); output deterministic |
| chat-cache round trip (park → resume, resume + edit) | **exact** (1,536/1,536 NLL equal, drafter guesses equal) |
| needles (12 documents × 6 questions, 32K–120K) | **72/72**; TTFT 9.1–9.4 / 17.8–17.9 / 33.6–33.9 s (C\*8: 9.4–9.6 / 18.3–18.4 / 34.7–34.8) |
| Stop during a 120K read, next request, back to the chat | **7/7** |
| browser test (copy of the config) | **54/56**: the 2 known non-bugs; the live web-search checks pass again (SearXNG recovered) |
| fallback to the 5080 alone, then back to the helper | pass |

**A/B vs C\*8** (fresh guarded server and cold page cache each, your settings; `results/r8/phaseC-ab.md`):
| | C\*8 | **C\*9** | change |
|---|---|---|---|
| full screens ABBA: decode, all 768+-token answers | 105.3 / 105.9 tok/s | **110.8 / 110.1** | **+4.4 %** |
| ms per verify round (1.95–2.01 tokens per round) | 18.49 / 18.68 | 18.10 / 17.76 | −3.5 % |
| TTFT 32K / 64K / 120K | 9.52 / 18.43 / 34.78 s | **9.26 / 17.89 / 33.75** | **−2.8 / −2.9 / −3.0 %** |
| TTFT 1K, short prompts | 1.00, 0.46 s | 0.98–1.00, 0.45 | = |
| decode screens ABBA: decode | 108.2 / 105.4 | **109.9 / 112.7** | +4.0 % |
| **fresh holdout ABBA** (8 new requests incl. a 28K document): decode | 98.4 / 99.5 | **103.9 / 103.6** | **+4.8 %** |
| holdout: TTFT 28K document / all 8 requests | 10.47 / 172.5 s | **10.19 / 164.8** | **−2.8 % / −4.5 %** |
| memory (peak GPU, lowest MemAvailable, RSS) | 15,418 MiB, 28.5, 57.5 GB | the same | = |

**An open point: rare tier-on differences.** On the first teacher-forced pass, 2 of 14 texts differed from C\*8,
starting mid-text: token 181 of 1,536 at 64K on one GPU, and token 1,224 at 28K with the helper.
- **Not the prompt change:** every earlier token was bit-identical, so the prompt state was the same.
- **Mechanism (source):** the adaptive tier makes a swapped-in expert GPU-resident only when a non-blocking event query
  says its copy has landed. So the round in which an expert moves from CPU to GPU depends on timing, and CPU and GPU
  round the same expert differently (the engine's own note says so). C\*8 has the same mechanism, and PR245 only
  changes the timing; its arithmetic is bitwise the same.
- **Repeats:** with the tier off, C\*9 = C\*8 every time. With it on, 0 differences in the next 47 C\*9 runs and 0 in 31
  C\*8 runs, so I could not show it happening on C\*8.
- **Size:** −0.034 ± 0.012 nats (clipped) on the worst text. C\*8's own tier on vs off moves the same text by
  +0.010 ± 0.012, and the raw shift is about twice C\*8's on/off shift.
- **My read:** rounding-level, not a math change. You may weigh it differently.

**Soak (2 h, 8080, your settings, big-chat traffic): pass.**
- 361 requests, 0 errors, Stop pressed 139 times.
- Back to a kept big chat: median 0.82 s. A dropped one: 10.2 s.
- New 64K / 120K paste: 17.7 / 31.6 s (C\*8's soak: 18.2 / 32.5).
- MemAvailable ≥ 25.0 GB; engine RSS 50.4–60.8 GB with no growth; swap 0.
- Chat cache peak 10,584 of 16,384 MiB, never over budget.
- Fresh 32K probe 9.18–9.27 s throughout (C\*8's soak: 9.43–9.53).
- The summary script's "whole engine log" line read every Phase C run in that log file. Recomputed for the soak's
  own engine, it gives the numbers above.

**Promotion (06:37):** the launchers default to `configs/Cstar9.json`. Rollback test passed: stop 8080 → C\*8 answers
→ stop → C\*9 answers, a different process each time. **C\*9 is on 8080**, and a fresh 48-hour passive uptime monitor
runs (`logs/r8/uptime/`).
