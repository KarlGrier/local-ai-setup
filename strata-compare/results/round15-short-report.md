# Round 15 — short report (2026-10-07 07:29 → 2026-10-08 11:25)

**Outcome: C\*15 (Strata v0.1.40.2 + 27 of our patches) is on 127.0.0.1:8080.** Rollback: stop 8080, then
`STRATA_CONFIG=configs/Cstar14.json ./switch-model.sh strata`. Full write-up: REPORT.md "Round 15".

## What was done
1. **Port**: C\*14's 34 patches moved onto v0.1.40.2 → 27 (B.3 dropped: upstream's F4 is the same code; 2 others
   upstream carries). All switch gates and guards passed; with our switches off it equals the release.
2. **Stand-ins for a 300B Qwen4 Flash**: Q8_0 of Flash-Next (119.5 GiB of experts ≈ 300B at IQ3_S) and a splice of
   UD-Q5_K_XL's experts into IQ3_S (91.6 GiB ≈ 300B at IQ3_XXS; UD-Q5_K_XL itself does not load).
3. **Every placement measured** (steps 1–3), **file-tier options** (step 4), **settings** (step 5, 2 h per file),
   an **all-in-RAM estimate** (step 6), **quality** (step 7), then the **catch-up and promotion** (step 8).

## Results — a 300B-class model on this PC (served, your settings, 6 GiB RAM floor)

| size (stand-in) | best setup | research answers | short answers | 120K prompt |
|---|---|---|---|---|
| IQ3_S size (Q8_0) | 5080 + 4060 Ti peer tier + 71 GiB RAM | ~14 tok/s | ~18 tok/s | ~50 s |
| IQ3_XXS size (splice) | layer split, saved config (64K cap) | ~43 tok/s | ~51 tok/s | not allowed (64K takes ~2 min) |
| IQ3_XXS size (splice) | 5080 + 72 GiB RAM | ~33 tok/s | ~40 tok/s | 39 s |

For scale: today's Flash-Next on IQ3_S (C\*14/C\*15) runs ~140 tok/s.

- **With every expert in RAM (estimate, not measured):** ~32 tok/s at IQ3_S size (~123 GiB RAM), ~46 at IQ3_XXS size (~101 GiB).
- **Biggest lever found:** forcing direct SSD reads (`STRATA_UNBUFFERED_LOAD=1`): +48 % (Q8_0), +15 % (splice).
- **Quality (long documents, vs IQ3_S):** Q8_0 −0.27 nats, UD-Q4_K_XL −0.21, splice −0.17; short texts equal.
- **What the runbook/planner got wrong:** old format list; no check against the engine's own file reader; RAM sized
  from probes and not at your 6 GiB margin; v0.1.40.2's read rule picked the page cache.

## Step 8 — C\*15
- Upstream's new drafting (STRATA_SPEC_PROB) lost to our exact sampling → kept C\*14's flags.
- **vs C\*14: 2.3–3.1 % slower, identical outputs.** Your 1-hour search (each changed default reverted) found no cause.
- Promoted anyway for the server fixes: Stop during a long prompt read (#1182), refused requests answer at once
  (#1059), hung engine start times out (#1317), restart fixes.
- Gates passed; acceptance suite 11 pass / 0 fail; 2-hour soak 440 requests, 0 errors; rollback test passed.

## Issues to know
- **Upstream released v0.1.40.3, v0.1.40.4 and v0.1.41 during the round** — I reported them late. v0.1.41 also
  disables a buffer-pinning default that corrupted decode after long prompts.
- The layer split gave broken answers after a 120K prompt once; not reproduced in 8 fresh sessions (cause unknown).
- Took ~28 h vs ~18 h planned. My slips are listed in the full report.

## Files
REPORT.md "Round 15" · results/round15-summary.md · configs/r15-q8.json, r15-q5s-C.json, r15-q5s-B.json, Cstar15.json ·
patches/LEDGER.md · 48-h monitor: logs/r15/uptime-c15/ · stand-in models: models/r15 (395 GB, yours to delete).
