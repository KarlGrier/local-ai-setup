### 6. Files, state, and what is left

| what | where |
|---|---|
| **C\*7** (promoted, the launchers' default) | `configs/Cstar7.json` (+ `Cstar7-single.json` for the 5080 alone; your shared chat settings in `Cstar7.shared-settings.json`), engine `engine-cstar7/strata` (sha256 `886b6ab2…`, sm_89 + sm_120), server/page `strata-cstar7/serve/` |
| rebuild C\*7 from scratch | `work/r7/build-cstar7.sh` (clean clone of v0.1.27 `a790805`, `git am patches/r7/0*.patch`, tree check) |
| patch series | `patches/r7/` (13 = C\*6's 12 ported + 0013 the Stop fix); branch `r7-port` in `strata/` |
| upstream write-up of the Stop bug | `pr-drafts/26-stop-then-next-request.md` |
| rollback | `STRATA_PORT=8080 ./run-strata.sh stop && STRATA_CONFIG=configs/Cstar6.json ./switch-model.sh strata` (stop first: `switch-model.sh` keeps a running Strata whatever the config) |
| launchers before the promotions | `work/r7/*.before-c6-promotion`, `work/r7/*.before-c7-promotion` |
| measurement builds (never served) | `r7-meas` (teacher-forcing/force hooks, `engine-r7m`), `r7-oracle` (the oracle + NVTX + teacher-forcing, `engine-r7o`, `engine-r7o-trace`) |
| results | `results/r7/` (item-0 engine checks, A/B `ab-c6-c7.md`, `tf-compare.txt`, round trip, oracle tables, merged windows, agents), `results/round7-summary.md`, day log `NOTES.md` "ROUND 7" |
| round-7 scripts | `work/r7/` (queue, guard, run/srv/screen/with_server, soak, rollback test, promote-c6/c7, oracle_table, merge_windows, agents2, stop_repro, tagcheck …) |

**Running at the end of the round:** C\*7 on 127.0.0.1:8080 with SearXNG on 8888; the 48-hour passive uptime monitor
(section 7); the tag watcher. Nothing else of mine.

### Round 8 backlog (ranked by expected gain × confidence ÷ cost)

| # | item | expected | first step |
|---|---|---|---|
| 1 | **Batched draft-layer prompt pass with KV streaming** (extend 0.1.26's E-9 to the drafter's ring) | ≤ 0.69 s per long prompt: 6.6–7.2 % at 32K, 2.2 % at 112K (measured ceiling) | write the ring's K/V from the batched pass (the host copy + the ring slots); parity test against the per-token pass |
| 2 | Prompt: MMQ through a pointer table (no per-expert group copy) | ≤ 10 % of prompt GPU time | parity test of one layer |
| 3 | Prompt: underfilled MMQ (21 % of a 32K prompt at ~1.4 TFLOPS) | unknown, possibly large | MMQ tile occupancy per expert size |
| 4 | Deterministic draft-policy switch (upstream suggestion, PR draft 24) | exact A/B tests without `--suffix-draft 0` | – |
| 5 | CPU-cache warming with a predictor | ~2–3 % on the adaptive tier at 60 % recall (measured, item 1); only if a better predictor appears | – |
| 6 | Two conversations at once | see item 4's recommendation | – |
| – | dropped with numbers | next-layer PCIe staging (item 1: 0–3 % perfect, a loss at 60 % recall on the served tier) | – |
