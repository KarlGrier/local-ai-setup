
**3. Soak — INCOMPLETE (stopped at 43 of 120 minutes on your request; pending).** C\*6 on 8080 as you use it
(`switch-model.sh`, warm-up, SearXNG, both GPUs), round 5's big-chat traffic, your settings, memory guard watching:
* **Traffic:** **133 requests from 16:37 to 17:20, 0 errors**, including:
  * 20 new chats with a pasted 32K/64K/120K document and 28 returns to an earlier big chat;
  * 17 web-search chats and 8 returns to them;
  * 16 follow-ups, 16 short chats, 6 long-reasoning requests and 4 regenerates;
  * Stop pressed 52 times.
* **Back to a big chat that was still parked:** median 0.66 s, max 3.6 s. Back to one the chat cache had dropped: median
  19.5 s (read again). The 32K probe read in 9.94–10.01 s, or 0.2–0.3 s once reused, with decode 82–97 tok/s.
* **Memory:**
  * MemAvailable never below 25.4 GB (round 5's soak minimum was 26.0 GB); engine RSS 50.4–60.5 GB.
  * The chat cache peaked at 10,466 of 16,384 MiB. The soak summary's "53,867 MiB" summed the shared engine log of all
    of today's C\*6 servers and is wrong.
  * 5080 VRAM 15,382–15,406 MiB used (≥ 476 MiB free); 4060 Ti ≥ 535 MiB free, while your desktop used more of it
    from ~17:00.
  * Swap 0.28 GiB, left over from before the round.
* **Engine log:** no engine errors. The 35 error lines in the soak's server log are all `fetch_page` refusals or failed
  page downloads, as in round 5 (`web_search` 146 ok).

### D. Files, state, what is left

**Running now:** C\*5 on http://127.0.0.1:8080 (`./switch-model.sh strata`, 17:21; verified: engine sha `3ee92c9a…`,
answers correctly) and SearXNG on 127.0.0.1:8888 (started with it). No queue, test server, soak, guard, monitor, tag
watcher or uptime monitor of mine is running. The launchers still default to C\*5 (not changed).

| what | where |
|---|---|
| candidate C\*6 config (+ its 5080-alone fallback) | `configs/Cstar6.json`, `configs/Cstar6-single.json` (+ `.shared-settings.json` copies of yours) |
| C\*6 engine / server + page | `engine-cstar6/strata` (sha256 `a56a444b…`, sm_89 + sm_120), `strata-cstar6/serve/` |
| rebuild C\*6 from scratch | `work/r6/build-cstar6.sh` (clean clone of v0.1.24, `git am patches/r6/0*.patch`, tree check) |
| patch series / PR drafts | `patches/r6/` (12), `pr-drafts/patches-r6/`, `pr-drafts/21–25` + README "Round 6 update" |
| launcher change for the promotion (prepared, NOT applied) | `work/r6/run-strata.sh.new`, `work/r6/switch-model.sh.new`; the helper-memory check with fallback IS already in `run-strata.sh` (only acts on configs that use a helper; old copy `work/r6/run-strata.sh.before-r6`) |
| remaining steps | `work/r6/soak.sh 120`, `work/r6/rollback_test.sh`, `work/r6/uptime_monitor.py` (passive: GET /health /status /metrics only; stop with `kill $(cat logs/r6/uptime/monitor.pid)`) |
| measurement build + tools | branch `r6-meas` (strata-r6), `r6-cand-meas` (strata-r6cm); `work/r6/` (guard.py, run.sh, srv.sh, screen.sh, route_parse.py, ceiling.py, predictor.py, cache_replay.py, cachewarm.cpp, …) |
| results | `results/r6/` (A/B table `ab-c5-c6.md`, route verification, microbench, ceilings, predictors, replay, TF, sampler, browser, round trip, web replay), `results/round6-summary.md`, day log `NOTES.md` "ROUND 6", `results/tuning-log.md` #71–79 |
