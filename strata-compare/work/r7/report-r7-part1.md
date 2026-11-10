### 1. Round 6 wrap-up: the 2-hour soak of C\*6 and the promotion

**Soak** (`work/r6/soak.sh 120`, label SOAK6-0929T1957, 19:57–21:57, C\*6 on 8080 through `switch-model.sh` with the
helper GPU, SearXNG, warm-up; round 5's big-chat traffic at your settings; memory guard and 1 s monitor attached):

| gate item | result |
|---|---|
| requests / errors | **333 requests, 0 errors** (81 returns to a big chat, 43 new chats with a pasted 32K/64K/120K document, 36 web-search chats + 20 web follow-ups, 40 follow-ups, 34 short chats, 29 Stop tests, 21 long-reasoning, 17 regenerates, 12 probes); Stop pressed 137 times |
| engine | no error, stall or watchdog line in this engine's log (only the six "upload no error" start-up lines) |
| server | 70 `fetch_page` refusals (a page outside the allow-list, 0.0 s each), as in rounds 5–6; nothing else |
| memory floors (guard, 0.2 s samples) | 0 samples under the floors; MemAvailable min **25.9 GiB**, 5080 min **476 MiB** free, 4060 Ti min 1,035 MiB free, swap 0 |
| leaks | engine RSS 50.4–60.5 GB, no growth (last 30 min max 58.8 GB) |
| chat cache | this engine's parked total peaked at **10,235 of 16,384 MiB**, never over budget (the summary script's "61,693 MiB" adds up the shared log of every C\*6 server since round 6 and is wrong; recomputed on this engine's part) |
| responsiveness | back to a parked big chat: median 0.83 s (max 4.1 s); to one the cache had dropped: median 10.9 s (read again); fresh 32K probe 9.95–10.03 s from start to end |

**Verdict: pass.** With the soak, no required check of round 6's gate is missing (A/B, accuracy, needles, quality,
web replay, chat-cache round trip, sampler, Stop/overflow/concurrency/idle CPU, launcher fallback, browser test; the
VRAM-grab test cannot run within your 300 MiB floor, as recorded in round 6).

**Promotion (22:22):** `run-strata.sh` and `switch-model.sh` now default to `configs/Cstar6.json` (round 6's prepared
`work/r6/*.new`; the old copies are in `work/r7/*.before-c6-promotion`). **Rollback test: pass** — 8080 went to C\*5
(engine `3ee92c9a…`, answered "17×3 = 51" in 18 s) and back to the default C\*6 (engine `a56a444b…`, both GPUs, "51",
19 s).

**Two things I fixed on the way:**
* **Round 6's rollback test would not have switched anything.** `switch-model.sh strata` keeps whatever Strata is
  running and does not compare configs, so `STRATA_CONFIG=configs/Cstar5.json ./switch-model.sh strata` with C\*6
  running just reports "already serving". The round-7 copy (`work/r7/rollback_test.sh`) stops 8080 before each switch.
  Keep this in mind for manual rollbacks too: **stop first** (`STRATA_PORT=8080 ./run-strata.sh stop`).
* **Round 6's browser test had changed your chat settings for C\*6.** It starts from a fresh browser profile (the
  page's default temperature 0.6) and clicks Apply with "use for other apps too" on, which wrote 0.6 into
  `configs/Cstar6.shared-settings.json` (15:43:43). Every round-6 client sent its own temperature, so no round-6 number
  changed, but a promoted C\*6 would have served other apps at 0.6. I restored your file (temperature 1.0, top_p 0.95,
  top_k 20, effort high) before the promotion; the promoted server announces "other apps use the Chat settings:
  temperature=1.0". Browser tests now run on a copy of the config (`configs/BR7.json`).
