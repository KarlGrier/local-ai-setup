# Round 14 — summary

**Status (2026-10-07 03:00) — done. C\*14 (Strata v0.1.40.1 + 34 patches) is on 127.0.0.1:8080**, promoted 02:57
after all gates, the acceptance suite (11 pass / 0 fail), a 2-hour soak (440 requests, 0 errors, MemAvailable min
21.0 GB, soaked decode +1.8 % vs fresh) and a real rollback test (C\*13.1 answered, then C\*14 again). Rollback: stop
8080, `STRATA_CONFIG=configs/Cstar131.json ./switch-model.sh strata`. Nothing was posted (publish/ is for you).

**C\*14 = Strata v0.1.40.1 + 34 patches (from 53).** Against C\*13.1, A B B A:

| screen | C\*13.1 | C\*14 | |
|---|---|---|---|
| LDR | 138.7 tok/s | 143.4 | **+3.4 %** |
| decode | 138.5 | 144.4 | **+4.2 %** |
| full | 138.8 | 146.3 | **+5.4 %** |
| Round 12's general holdout (never run before) | 134.8 | 142.4 | **+5.7 %** |
| Round 12's LDR holdout (never run before) | 136.7 | 140.8 | **+3.0 %** |

Prompt reads equal (TTFT 32K / 64K / 120K ±0.1 %); total request time −2.7 … −4.4 %. Only short tool-call answers lose
(−4 … −10 %, one request per screen). Gates: acceptance suite 11 pass / 0 fail (teacher-forced NLL = C\*13.1's to the
digit), exact7, needles 12 × 6/6, Stop at 120K, follow-ups, stops, tool calls, round trips 3/3, browser 41 / 2 known.

**1. The release alone** (v0.1.40.1, my flags, none of our switches) vs C\*13.1: **−17.8 % LDR, −15.8 % decode, −16.3 %
full**, prompt reads equal. No existing default changed; nothing turns on `--remote-expert-opt` or a lower-precision
option (those stay opt-in). Its outputs = v0.1.39's on 6 of 7 exact tests; the 7th splits at token 958 — traced to the
new one-launch final mixer reading through my `STRATA_GR_V3=1`: rounding-level.

**2. Ledger pass, 53 → 34.** 11 rows upstream now carries (#550, #700, #454 + switches, #838, #931 ×4, #896 ×2); 1
dropped by your rule (dump-routing); then by measurement on v0.1.40.1: PR245 ×3 (equal to upstream's new kernels),
the n-gram prefetch (no gain on 0.1.40), our landing and helper rule (upstream computes the same), our Stop watcher ×2
(upstream's #879 does the same); the side mixer rewritten on 0.1.40's window; + the cost gate and B.3's new table.
Per patch on v0.1.40.1 (A B B A): helper-aware tier +5.3 %, exact sampling +3.5 %, B.2 +3.0 %, side mixer +2.5 %, B.3
+2.0 %, A.2 +1.4 %, B.1 +0.8 % (but +6.1 % over upstream's new read).

**3. Overlaps — winner:** landing and helper rule → **upstream's** (bit-identical 4/4, equal speed); HC read → **ours**
(+6.1 %); the fork's drafter kernels upstream took → upstream's (+0.6 %); grouped experts → upstream's (equal);
mixer branches → ours (−4.7 % per round); batched uploads → cannot act with a helper GPU; Stop during a long read →
upstream's #879 (equal).

**4. Cost-aware draft gate:** chi-square ALL PASS (two gate cases, negative control caught); **LDR +2.8 %, decode
+3.4 %** → kept. Its table is fitted to this drafter (re-fit for a new model).

**5. Calibration** (24 of 90 min): every value stays (nothing cleared +2 % beyond the noise). **B.3's table:** 17 of 80
cells re-derived → +0.2 % decode, −1.8 % per round, outputs identical.

**6. Session files** (report only): 40K chat save 0.20 s / restore 0.27 s (847 MB); 190K chat save 0.54 s / restore
1.08–1.24 s (3.1 GB), next turn TTFT 0.26–0.67 s vs a 9.8 / 47.6 s cold read. **Nothing lost**: with fixed expert
placement the continuation after a restore (same process or new) = the never-saved one; with the adaptive tier live
the 40K continuation drifts after ~10 tokens because residency differs by history (the two restores differ from each
other too).

**7. Fit planner:** IQ3_S fits at both margins (20 GB floor: 1.5 GiB spare; 8 GB serving margin: 13.5 spare); the Q4
needs a RAM budget (48 / 60 GiB). **A RAM budget beside the helper cache is still refused on v0.1.40.1** — v0.1.40 only
allows one with a layer split (the planner names it, unmeasured).

**8. Runbook's first real use:** stages 2 h 41 min unattended + ≈ 1.5 h by hand. Manual steps: the ledger pass
(expected), a dropped row's switch in model_check, the new gate missing from the runbook's switch list, the calibration
tables cut short (fixed), B.3's table pasted (by design), the Stop rows. DAY-ONE.md rewritten for this flow.

**9. publish/:** 7 branches on v0.1.40.1 (all compile; cost-gate new), the draft comments' status lines (6 obsolete:
merged upstream), the benchmark report's Round 14 section; privacy check CLEAN; nothing posted.

Full write-up: REPORT.md "Round 14"; notes NOTES.md "ROUND 14"; data results/r14/, bringup/out/r14*/.
