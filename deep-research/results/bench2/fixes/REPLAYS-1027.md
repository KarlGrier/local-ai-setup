# The six fixes + the consistency pass: per-fix replays (10-27)

Karl's bundled testing: replays per fix, then one combined full rerun and one stage 3.

**How the replays ran:**
- Only the report stage's checks ran (`tools/fix-replay.py`, through strata-proxy on P021m, holding run/bench.lock).
- They read saved reports:
  - the code-tool rerun's own report and evidence store (results/bench2/codetool/run-full);
  - for Fix 1, also Karl's 10-24 report (the agreed test case; its own source list as the only evidence);
  - for Fix 3, a copy of the rerun report with three planted errors (planted/PLANTED.md).
- Four rounds, each changing the code after looking at the results.
- The kernel check was clean after every round.
- Outputs: replays/<label>/ (report.md with the marks, the checks' JSON files, calls.json); log replays.log.

All of it sits behind `LDR_DEEP_FIX` (all, or a list of version, inline, arith, cite, baseline, budget, consist); without
it a run is unchanged.

| fix | final result | what changed on the way |
|---|---|---|
| **1 version** (+ the code tool pinned to the question's version) | 10-24 report: **16** settings flagged as not options of Strata v0.2.4's DeepSeek engine - the Qwen-engine flags `--host-core`, the PLE flags, `STRATA_IO_*`, `STRATA_SPLIT_UNIFORM`, ... plus `--chunk-prestage` (not found). Rerun report: `--experts` (main-branch docs only), `STRATA_SPLIT_UNIFORM`, `--prompt-cache` flagged - the grader's in-plan pair among them; `-DSTRATA_NATIVE_EXPERTS` and `--set` debatable. | round 1 flagged 1 and 1: without knowing which folder is the engine, another engine's flags in the same repo read as "this version". Now: the engine's folders are asked twice (only the folders both answers name; one answer took in the Qwen engine's src/program), and each name's hits are reported inside vs outside them. Round 2's folder list was cut by a 200-entry cap (src/dsv41 never shown) - fixed. |
| **2 inline** | the critic's points are marked where they stand ("[Check: ...]", 8 placed, none lost); an unsupported citation's mark carries the checker's note; blind-open.py strips every mark (that also removed a stray "**" the old citation flags left) | - |
| **3 arith** | rerun report: **0** false alarms in 82 checks (17 written-out equations + 64 model-listed calculations, 1 "units unclear"); planted copy: **3 of 3** errors caught (+33 %, 10x, ~250x) | round 1: 30 false alarms (unit handling); round 2: 15 (the model mixed unit words with manual factors); round 3: 0 false alarms but only 1 of 3 planted errors (the model's list skipped them). Now written-out equations ("1,357 × 9.4 MB = 12.8 GB", chains) are checked with no model at all (units, label words, bold, bits, GB/s); the model's list (plain-number formulas) covers the rest; 10 % tolerance (15 % for "≈"). The agents also get a `calculate` tool. |
| **4 cite** | offline over all 44 saved measurement reports: **1** citation outside its run's evidence ([36497] in a p4s3 o01 run; not in an Answer); the rerun report: none | regex classes in code (`[0-9]`) and the math interval "[0, 1]" were taken for citations at first - code, math and [0, 1] excluded |
| **5 baseline** | the setup check also judges recommendations ("already set": `--ssd-cache 70`, `--dspark none`, `--experts 6`, `--gpus 0,1`) and gains (like with like); 35 marks on the rerun report, most substantive (it also caught the DSpark claim of answer key K4, the "lossless" plan with a non-exact step, a GDDR6/GDDR7 slip) | round 1 judged the 10-24 question (v0.2.4, 22.6 tok/s) against today's profile (v0.2.6, 28.3 tok/s) and "corrected" right statements; now the task's own description wins and the profile counts only for the hardware when the task is about another state. Some noise remains on this old-state question (a few marks against the profile's current prompt chunk). |
| **6 budget** | a 25-min report-stage replay with every check: done in 20.4 min (4.6 min left), the citation check cut to 32 key claims by the plan | the critic's reply was cut at the plan's output cap and dropped whole -> cut JSON lists now keep their complete items (critic, setup check, the new checks); the time estimates were updated to the measured times |
| **consistency** | 14 contradiction pairs in the rerun report - answer key K1 (layer-major needs one GPU) caught and resolved, K4 (DSpark) not; others real (27/13 vs 22/18 split, 18.8 vs 9.4 MB per expert, lossless vs "not exact") | - |

**Also built, as Karl asked:** effort drops by the retry ladder are logged ("EFFORT LOWERED ...") and counted in
stats.json and summary.json (`effort_drops`); the code tool's GitHub API use is capped per run with the core and search
limits tracked apart (the "6 left" of 10-27 was the search minute; the hourly core limit never went below 39), commit
lists and default branches come from git, and API answers are cached for the run.

**Not yet measured:** the strategy side (the whole-run deadline, the calculator tool, the version pin in the lead's
prompt) - the smoke run with all fixes and then the combined full rerun measure those.
