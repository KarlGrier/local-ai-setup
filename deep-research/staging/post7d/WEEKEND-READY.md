# Post-7d chain - ready for an unattended weekend (review 11-05 12:40 CST; desk work only)

Karl 11-05: "Post-7d chain: baseline -> item 8 -> C3c -> Phase 5, with rules frozen and drivers reviewed and ready, so
it runs unattended over the weekend. Put every decision you need from me in one list now, with your recommendation for
each." **The decisions are in section 9.** Nothing was started, stopped or switched; chain.sh and switch.sh (running)
were not touched; no GPU, LDR, search or API key was used.

## 0. State at review

- post7d-chain.service active (chain.sh pid 181246); step 1 done 11:13-11:14 (LDR fixes 0007 + 0008, runner changes,
  Pillow 13.0.0); the bench unit on queue-plan-p4s9.json since 11:14 (o01 running); step 2's switch.sh (pid 1321028)
  waits for p4s9 to finish.
- gap-series.service: gap-screen-rerun.sh holds the queue (tmp/bench2.hold set 11:17) and opens after o01; then
  gap-basalt-a, gap-basalt-b, gap-csample, gap-ud31, gap-ud31-dec (one per question; ud31-dec only if v3.1 says WANTED).
- 7d's four blind rounds are being graded today (results/bench2/blind-p7d*). Strata v0.2.11 is FLAGGED (no pause).
- Read-only checks today, all pass: plan_check.py on item8 / c3c / p5-holdout (staged bench2.py), modelprofile.py
  --check on the C3c profile, p5.py check-frozen + check-engine (P028x on 8080 and promoted), live tools/bench2.py =
  staging/post7d/tools/bench2.py.orig (so step 4 can install the p5 copy), no tools/bench2.py.before-p5,
  run/night-ok present, no tmp/bench2.stop.

## 1. Time line (expected; Jan jobs and long gaps push it)

| when | what | GPU |
|---|---|---|
| Thu 11:14 - ~14:05 | p4s9 o01 (171 min) | queue |
| ~14:05 - ~14:35 | gap: decode b screen rerun (~12-25 min with 8080 down) | gap |
| ~14:35 - ~17:25 | p4s9 o02 | queue |
| ~17:25 - ~19:45 / 21:30 | gap: Basalt a (2.0-3.9 h, deadline 4 h) | gap |
| -> ~22:35 / 00:20 | p4s9 o03 | queue |
| -> Fri ~00:10 / 03:00 | gap: Basalt b (~1.5 h, deadline 2.5 h); p4s9 finished; **switch -> item 8** | gap |
| Fri ~00:15 / 03:00 - ~09:00 / 13:50 | item 8: six 62-min runs (~64 min each) + gaps C-sample (0.2-1.3 h), UD3.1 (~2 h), UD3.1-dec (~1 h or skipped) after runs 1-3 | queue + gaps |
| -> Fri ~16:00 / 23:15 | **replays.sh** (queue stopped): merges + 10 report replays (40-55 min each) | replays |
| -> Sat ~00:30 / 08:00 | **switch -> C3c**: o01-o03 on flash-next-c3c (3 x ~172 min) | queue |
| -> Sun ~12:30 / 22:00 | **Phase 5** (66 runs with the o01 line, ~36-38.5 h) - only if GO-p5 is in by then | queue |

The gap series should be done after item 8's third run (5 remaining gaps, one per question), i.e. before the replays.
**GO-p5 is needed by Friday ~23:00** (the earliest C3c end) or the GPU idles from Saturday morning.

## 2. The remaining steps, end to end (what stops, what alerts)

| step | checks before it acts | on failure |
|---|---|---|
| 2 (running) p4s9 -> item8 | p4s9 finished (unit inactive + every run done + "queue finished (queue-plan-p4s9.json)"); waits while tmp/bench2.hold exists; kcheck; plan_check on live tools; unit rewrite (backup) + start; verify MainPID + first "running" line (45 min) | die = "NOT SWITCHED" in logs/post7d-switch.log + critical desktop notice, chain exits 1 (nothing else runs) |
| 3a replays.sh (queue stopped) | inputs (p8a-c o01/o03 + p4s9 o01-o03 finished), merges + `test_merge.py --verify`; before each replay: STOP-replays, Jan jobs, hold / open gap, strata-ensure, p5.py check-engine (P028x); kcheck after each | exit 1 -> switch.sh does not switch -> chain ends with a critical notice (see D8 for the go-on option) |
| 3b item8 -> c3c | `finished` again after the replays; hold; tmp/bench2.stop; unit still on item8; kcheck; installs profiles/flash-next-c3c.env (new file; refused if a different one is there); plan_check on live tools | as step 2 |
| 4 c3c -> p5-holdout | C3c finished AND GO-p5 = sha256 of the plan (waits silently for it); check-engine + check-frozen; tools/bench2.py <- staged p5 copy under run/bench.lock (only if live = .orig; backup .before-p5); swap-mark; plan_check | as step 2; **a change to tools/bench2.py before step 4 makes it refuse** (re-base the staged copy first) |
| queue, every run | watchdog (no model call 30 min -> requeue once; 2nd hang -> queue stops, NOTES + critical notice); 3 search-failed runs in a row -> stop + notice; Strata release = FLAG only | switch.sh keeps waiting (one "stopped early" notice) until the queue is started again |

Alerts are desktop notices and NOTES.md lines only: when nobody is at the PC, a stop costs the rest of the weekend.
Not alerting: a run that fails the same way every time is retried every 10 min without limit (bench2-queue.sh);
gap-series exit 3 (kernel check failed) leaves the gap OPEN and the hold set by design - everything waits for Karl.

## 3. Gaps vs replays - how they cannot collide (and the fix)

- A gap opens only through port_gap4.sh begin: it sets tmp/bench2.hold, then waits until run/bench.lock is free, then
  takes the test lock and stops 8080. fix-replay.py holds run/bench.lock from just before the report stage's first
  model call to its end, so a gap can never open in the middle of a replay's model work.
- gap-series.sh starts the next driver only after a question started since the previous gap; with the bench unit
  inactive and the chain active (the replays) that is false, so normally no gap starts during the replays. But its wait
  ends after 4 h anyway (line 46: 1440 x 10 s, no check after the loop) and starts the driver - which would then set the
  hold and open between two replays.
- **What was broken in replays.sh, fixed (new file + mv, 12:15; the old copy scratch/weekend/replays.sh.before-weekend):**
  1. A race: the hold could be set after replays.sh's check but before fix-replay took the lock (strata-ensure, the
     engine check, imports, run_store: tens of seconds) -> 8080 stopped under a starting replay; strata-ensure would also
     have failed twice and stopped the chain. Now ready() waits while the hold exists OR a gap is open (port-gap.lockpid),
     a Strata / engine check that fails while a hold appeared waits for the gap instead of stopping, and the hold is
     checked once more right before fix-replay starts. The rest of the window is watched: a gap that opened while a
     replay ran (lockpid seen at a 5-s poll, or a new "phase 4 gap BEGIN" NOTES line) makes it VOID - folder to
     staging/post7d/item8/void/, rerun once after the gap; a second collision stops the chain.
  2. No time limit: fix-replay has no watchdog, so a hang (a model call, a code-tool clone) waited for ever without an
     alert. Now `timeout` REPLAY_MAX_MIN = 180 min per replay (write replays took 22-50 min) -> stop + alert.
  3. A kernel check after every replay (was: only at the end); the relief restarts inside each replay's window and
     the free disk go into replays-summary.txt / the log.
  4. Optional (D8): with staging/post7d/REPLAYS-GO-ON present, a replay that fails on its own (not Strata, engine,
     kernel or a gap) is set aside to item8/failed/ and the rest go on; the script ends 0 with a critical notice and a
     NOTES line, so C3c's runs (which do not use the replays) still start. Two failures in a row stop in either mode.
  Test: scratch/weekend/test_replays.sh (sandbox, stubs; 18/18 pass: normal, both collision kinds, double collision,
  hold during checks, ensure failing during a gap, failure with / without GO-ON, two in a row, hang -> timeout,
  relief count, unfinished folder, STOP file, source-only). The main body (inputs, merges, verify, the 10 labels and
  their order) is unchanged.

## 4. Phase 5: the plan for Karl's calls, and GO-p5

- **Found:** the o01 line with the 8 GB text (adopted 11-04: README section 4, NOTES 11-04 10:43) is NOT in the staged
  plan (p5.json include_o01 false, no FROZEN-p5-o01.txt) - and p5.py's include_o01 would put it INTO the open totals,
  not on its own line.
- **Staged:** staging/post7d/phase5/apply-p5.sh `none|7d|7dx|7b [--no-o01] [--c3c] [--check]` builds the plan from
  phase5/queue-plan-p5-holdout.base.json (the 11-04 plan; `none --no-o01` reproduces it byte for byte, sha256
  8349bafad5a6...), adds the o01 pair last (baseline + final, set p5-o01, outside p5.py's lines), puts the route /
  profile on the final (deep) steps only, freezes results/bench2/FROZEN-p5-o01.txt + questions-p5-o01.jsonl (chmod 444,
  sha256 602db37242ff checked) when o01 is in, runs check-frozen and plan_check, installs the plan (new file + mv,
  backup) and prints the GO-p5 command. It never writes GO-p5. `--check` builds in scratch against a mirror: all six
  variants pass (none / 7d / 7dx / 7b with o01: 66 runs, ~38.5 GPU h; without o01: 64 runs, ~35.1 h).
- To start Phase 5 (after D1-D6): `bash staging/post7d/phase5/apply-p5.sh <route>` then
  `sha256sum /home/USER/ai/deep-research/results/bench2/queue-plan-p5-holdout.json > /home/USER/ai/deep-research/staging/post7d/GO-p5`.
- Grading tool: staging/post7d/tools/relief_counts.py reads every set's deep and baseline folders (the item7d copy
  misses holdout / p5-harder / p5-o01); same rows as the item7d copy on p4s8 + p7d.

## 5. Disk (floor 100 GB)

180 GB free now. The chain writes little: an open run ~100 MB (p4s8: 279 MB for 3), a replay ~2 MB, Phase 5 < 1 GB,
logs/ is 760 MB in all. The big writer is the gap series' UD3.1 gap (Fri ~04:00-06:00): ~54.8 GB splice + ~8 GB packs ->
~117 GB left; it refuses itself below 100 GB (exit 1, skipped). Margin after it ~15-20 GB; nothing else large is
scheduled (ud31-download inactive). replays.sh logs the free space per replay; nothing in the chain checks the floor.

## 6. Watchdog, fetch guard, memwatch (installed)

- Watchdog (11-03): every bench run (not the replays - hence section 3's limit); held time does not count.
- Fetch guard (patch 0006, 11-03): 16 MiB / 400,000-tag caps on every deep run's pages (not the baseline profile).
- Memwatch (patch 0007, 11-05 11:14): logs/ldr-mem.jsonl, malloc_trim after each research; fresh LDR per question.
- Step fix (0008, fix:steps): every plan from p4s9 on names it; Jan's deep jobs get it too (runner).

## 7. Paid search

November (paid_tracker.py, counters only): Tavily 365 of 1,000 (tests + research stop at 750: 385 to go), Exa
$1.168 of $10. Steps 1-3: none (SearXNG only). Phase 5: none as staged; with 7d or 7dx <= 30 per final open run
(4 with o01: <= 120) and ~0 on the lead-only checkables (the rule pays only after a subagent searched or from search
101); with 7b ~300+ (every final run pays its first searches: ~120 open + ~29 x 6-8 checkable) -> ~670-700 of the 750
line that Karl's own research shares. paid_budget enforces 30 per test run; a watchdog requeue keeps the run's
remaining cap (as s2 p7dx: 13 + 30 = 43 only after Karl's rename, 11-04).

## 8. Files changed / added (11-05)

- staging/post7d/replays.sh - replaced (section 3); old copy scratch/weekend/replays.sh.before-weekend; test
  scratch/weekend/test_replays.sh.
- staging/post7d/phase5/apply-p5.sh, phase5/queue-plan-p5-holdout.base.json (new; section 4).
- staging/post7d/tools/relief_counts.py (new; section 4).
- results/bench2/RULES-item8.md, RULES-c3c.md, RULES-p5.md (frozen 11-05, before any result).
- Not changed: chain.sh, switch.sh (running; no change needed for steps 3-4), plans in results/bench2, live tools/,
  LDR package, units, gap-series.sh (its 4-h fallback is handled on our side).

## 9. Decisions for Karl (recommendation; what happens without an answer)

| # | decision | recommendation | no answer |
|---|---|---|---|
| D1 | **GO-p5** on the final plan | after 7d's grading and D2-D6: apply-p5.sh, then write GO-p5, by **Fri ~23:00** | the chain waits after C3c (~Sat 01:00-08:00); GPU idle for the rest of the weekend |
| D2 | **Phase 5 paid route** (from 7d's grading) | blind-p7d a gain (p7d > p4s8, wrong claims not worse) -> **7d**; and blind-p7dx a gain too -> **7dx** (o06 is a product question); blind-p7d a gain but p7b ahead in blind-p7d-p7b -> still **7d** (7b ~300 Tavily, near the 750 line your research shares) unless you accept that; blind-p7d tie / mixed / worse -> **none** | none (as staged) |
| D3 | **o01 with the 8 GB text** (adopted 11-04, missing from the plan) | in, own line, last (+3.4 h); apply-p5.sh freezes FROZEN-p5-o01.txt | in, if apply-p5.sh runs with defaults |
| D4 | **Phase 5 model profile** | **flash-next**: C3c's runs end Sat morning and are graded after; waiting for them = no Phase 5 this weekend; C3c adopted later -> Phase 5 then measured the build before C3c | flash-next |
| D5 | **Engine** | **P028x** until Phase 5 ends; v0.2.11 stays flagged (a switch makes the replays and step 4 refuse) | P028x |
| D6 | **Final items** | p4s8's (setup critic code fixes read claims) + fix:steps, medium / xhigh, 171 / 47 min | as staged |
| D7 | **Item 8 in Phase 5** | no: the queue cannot run merged short runs; item 8's grading decides stage 3 later | no |
| D8 | **REPLAYS-GO-ON** | yes: `touch staging/post7d/REPLAYS-GO-ON` - a replay failing on its own is set aside and C3c still starts | one failed replay stops the chain on Friday (no C3c, no Phase 5) |
| D9 | **Rules' OPEN points** (RULES-*.md) | a gain within grader noise (<= 1.5 of 34) counts as mixed; C3c split -> ask, candidate = the half that gained; a C3c run hitting its client stop or the 121.8K limit counts as worse; Phase 5 sanity regression = fewer correct or more wrong commitments -> flagged; Phase 5 Q3 / Q5 / Q6 / Q7 as RULES-p5.md section 4 | written as recommended, marked unconfirmed |

Grading of item 8 and C3c (blind-i8s2, blind-i8c3c, blind-c3c-rep, blind-c3c) needs a session but holds no GPU step.

## 10. Helper slips

Three read-only `cd` in Bash calls (into strata-compare, results/bench2 and deep-research, while reading or checking);
nothing was written by them.

## 11. Karl's answers 11-05 (implemented 14:5x)

- **GO-p5 armed** (coordinator): route none, o01 in, plan sha256 3e1d0589fcc7... (phase5/CHOICE.txt).
- **D8** "yes. If one replay fails on its own, C3c starts anyway. If a second replay fails, stop the chain and alert
  me. Give the failed replay one retry at the end of the chain, if it needs no decision from me."
  - staging/post7d/REPLAYS-GO-ON written. replays.sh (replaced again by new file + mv; the 12:15 copy is
    scratch/weekend/replays.sh.before-d8): the first failure is set aside and the chain goes on; the SECOND failure, in
    a row or not, stops the chain (NOTES line + critical alert, exit 1). Each failure (and a double gap collision)
    is an event in staging/post7d/item8/failed-replays.tsv: label, why, folder, whether a retry needs a decision, the
    sha256 of fix-replay.py, the LDR deep package and the evidence.
  - staging/post7d/retry-failed-replay.sh (one-shot, NOT started): waits until post7d-chain AND the bench unit are
    inactive (after Phase 5's queue, or after a stop), then retries each recorded label ONCE through replays.sh's own
    replay() (Jan jobs, holds / open gaps, run/bench.lock, Strata, engine, time limit, VOID, kcheck). Needs a decision
    instead (item8/RETRY-NEEDS-DECISION.txt): evidence gone or changed, fix-replay.py or the deep package changed, the
    label folder in use, an interrupted earlier retry, or a stop (engine not P028x, kernel check). NOTES line + alert.
    Log logs/post7d-retry.log; STOP: touch staging/post7d/STOP-retry. Start (Karl):
    `systemd-run --user --unit=post7d-retry --description="post-7d: one retry of each failed replay after the chain (Karl 11-05 D8)" /bin/bash /home/USER/ai/deep-research/staging/post7d/retry-failed-replay.sh`
    Confirm: `systemctl --user is-active post7d-retry` and the log's line "waiting for the chain to end".
  - Tests (sandbox, stubs): scratch/weekend/test_replays.sh 24/24, test_retry.sh 15/15.
- **D9** "OK as recommended, provided each point was set before any result it governs." The RULES files were written
  12:21-12:22; no item 8, C3c or Phase 5 run, merge or replay existed then or at 14:5x. Each of the 7 OPEN (D9) points
  now carries "11-05 Karl: the OPEN (D9) points confirmed as recommended (set before any result)."
