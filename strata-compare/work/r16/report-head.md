
## Round 16 — catch-up to v0.1.41: the port, v0.1.41's CPU prompt-read share (kept off), C\*16 promoted for the server fixes, a Q4 speed check (2026-10-08 14:05 → 23:10)

Chronological notes: `NOTES.md` ("ROUND 16"). Phone summary: `results/round16-summary.md`. Scripts: `work/r16/`; runbook runs
`bringup/out/r16` (the release alone, upstream's defaults), `r16z` (the port's gates, the share off), `r16q4` (the Q4 build).
Raw results: `results/r16/`, `results/runs.jsonl`. Branches (local): r16-port (= patches/r16p27), r16-meas (+ r16-meas27).
Configs: `configs/Cstar16.json` (+ `Cstar16-single`, `R16RT`, `BR16`), `configs/r16-q4.json`. Ledger: `patches/LEDGER.md`
(C\*16; C\*15's is `LEDGER-r15.md`).

### Result

* **C\*16 = Strata v0.1.41 + our 27 patches is on 8080** (promoted 22:24). It computes exactly what C\*15 computes (exact7
  7/7 = C\*15's hashes) at the same speed: **LDR +0.4 %, decode −1.4 %, full +0.5 %, prompts 0.4–0.8 % faster** (A B B A).
  Not ≥ 1 % faster; promoted under your rule because **it carries v0.1.41's server fixes that reach your Open WebUI → 8080
  path**: a frozen engine is ended and restarted (#1317 part 2), malformed / oversized request bodies are answered 400 / 413,
  and `<function= NAME>` tool calls are parsed. Every gate, the acceptance suite (11 pass / 0 fail), a 2-hour soak (439
  requests, 0 errors) and a real rollback test passed. Rollback: stop 8080, `STRATA_CONFIG=configs/Cstar15.json ./switch-model.sh strata`.
* **The 2–3 % gap to C\*14 has not closed** (C\*16 vs C\*14: LDR −2.4 %, decode −3.5 %, full −1.7 %; ms per verify round
  +2.7…3.5 %).
* **v0.1.41's new CPU prompt-read share is ON by default on your two-card config.** It reads short prompts and every chat
  turn's new text 16–17 % faster (512 tokens: 581 vs 694 ms). It passed the long-text NLL check, but it reads those prompts
  with timing-dependent rounding, so it failed the acceptance suite's chat-cache round trip (1/3), and it's **off in C\*16
  (`STRATA_PREFILL_CPU_SHARE=0`) by your rule.** `STRATA_STAGE_PIN` stays off (opt-in in v0.1.41).
* **Q4 check (UD-Q4_K_XL, the 5080 + 66 GiB RAM, your 6 GiB floor): 68.7 tok/s on the decode screen, 64.0 on LDR (about half of
  IQ3_S's 138.8 / 138.3), 32K prompt in 11.7 s (7.7), 120K in 34.4 s (29.7), needle at 120K 6/6.** Saved as
  configs/r16-q4.json; not promoted.
* Upstream released nothing newer during the round (v0.1.41 = main all day). Nothing was fetched or downloaded.

