**11-05 12:40: see WEEKEND-READY.md** (review for the unattended weekend: time line, the replays.sh fix, phase5/apply-p5.sh, Karl's decisions D1-D9; rules frozen in results/bench2/RULES-item8.md, RULES-c3c.md, RULES-p5.md).

# After 7d: LDR fixes, a fresh baseline, item 8, C3c, Phase 5 (staged 11-04, updated 10:45 with Karl's answers)

NOTHING installed, switched or started. Karl 11-04: "After 7d, with no LDR run live: install the subagent step fix
and the memory fixes, then run a fresh baseline with the fix as item 8's and C3c's comparison side." Options: the
recommendations below, unless one spends paid searches beyond the caps, deletes anything or changes the served build.
**P028x (f4c4f654fb24) stays the served build throughout** (replays.sh checks it before every replay).

## Order (chain.sh; every step waits while tmp/bench2.hold exists, i.e. never collides with a phase-4 gap)

| step | trigger | what | GPU |
|---|---|---|---|
| 1 | "queue finished (queue-plan-7d.json)" + unit inactive + every 7d run done | **install-ldr-fixes.sh**, then the unit on **queue-plan-p4s9.json** | ~8.7 h |
| 2 | p4s9 finished | **queue-plan-item8.json** | ~6.4 h |
| 3 | item 8 finished | **replays.sh**, then **queue-plan-c3c.json** | ~8 h + ~8.7 h |
| 4 | C3c finished AND `GO-p5` = sha256 of the Phase 5 plan | tools/bench2.py with the p5 sets, **queue-plan-p5-holdout.json** | ~35 h |

7d's end slides to ~midday 11-05 (gaps between its 7 remaining runs). Expected: install ~12:00 11-05, p4s9 to ~21:00,
item 8 to ~03:30 11-06, replays to ~11:30, C3c to ~20:30 11-06; Phase 5 after 7d's grading, the adoption calls and
GO-p5 (~35 h). Gaps between runs push all of this.

## 1. install-ldr-fixes.sh (between 7d and p4s9; `--check` is read-only)

From the ldr-study helper (MEMORY.md section 5, PAPERS.md section 8), snapshot in `ldr-fixes/` (PATCH-SHA256.txt):
**0007-memwatch** (memory records + gc / malloc_trim after a research or a big page), **0008-subagent-steps** (item
"steps": recursion limit 3 x calls + 10, the salvage), **runner-fresh-ldr** (a Jan job gets a fresh LDR above 1.0 GB).
NOT 0009. Plus `tools/bench2-queue.sh`: plan item **`fix:steps`** -> LDR_DEEP_FIX `...,steps` (run-ldr.sh already stamps
it "fix:steps"; every plan from p4s9 on names it; Phase 5's baseline arm stays pristine).
Steps: refuses if the study's patches changed after the snapshot or a live file is not the patches' original -> waits
for no hold / no Jan job, holds run/bench.lock -> stops the runner and LDR -> backups `*.before-ldrfix` + `ldr-fixes/UNDO.sh`
-> 0007 -> 0008 (dry-run first; result compared with orig + patches built in scratch) -> runner patch -> queue ->
`patches/ldr/make-patches.sh` (apply.sh status must be "patched") -> tests on the installed package (Memwatch 5,
Step 3, Runner 1 = 9) -> runner started again; LDR left stopped (the queue's next question starts it). Any failure
after the first copy: UNDO.sh, runner restarted, exit 1 (no switch). One NOTES line.
Checked 11-04: 0007 -> 0008 and the runner patch apply to copies of today's live files; the result equals the
study's site/ where 0009 does not also edit; the 8 Memwatch + Step tests pass on a copy with 0007 + 0008 only (no 0009);
the Runner test passes on the patched copy; `--check` rc 0. Jan's runner jobs do not name "steps" (not asked).

## 2. queue-plan-p4s9.json - the fresh baseline

p4s8's setup + the fix: o01-o03, deep, medium / xhigh, items setup critic code fixes read claims **fix:steps**,
171 / 47 min, SearXNG only, a fresh LDR per question. What uses it: C3c's runs (o01-o03 in-run reports), item 8's long
side and C3c's current-size side (replays of p4s9's evidence, o01-o03; o02 also for item 8's later stage 3).

## 3. Item 8, C3c, replays (as recommended, Karl 11-04)

- **queue-plan-item8.json:** o01, o03 x three 62-min runs (p8a / p8b / p8c; Fix 6: 3 x 40.3 = the 171-min run's
  120 min of research), fix:steps, SearXNG only. o02 = stage 3, later.
- **replays.sh** (queue stopped): merge + `test_merge.py --verify`; `fix-replay.py write --fix all,read,claims --setup
  --critic --budget-left 3045`: r-p8m-fn vs r-p4s9-fn (item 8, o01 / o03); r-p4s9-c3c vs r-p4s9-fn (C3c's report
  half, o01-o03); r-p8m-c3c vs r-p4s9-c3c (item 8's retry at C3c sizes, ON).
- **queue-plan-c3c.json:** o01-o03 on `profiles/flash-next-c3c.env` (flash-next.env + four sizes; installed by the
  switch), fix:steps, vs p4s9. Hard five not added (tied 5/5 at the ceiling).

## 4. Phase 5 (behind GO-p5)

`queue-plan-p5-holdout.json` (p5.py's plan + fix:steps on the final arm; `phase5/p5.json`: P028x, p4s8's items +
fix:steps). Adoption calls (setup, paid route, profile, engine) wait for 7d's blind grading; then edit the plan, and
`sha256sum results/bench2/queue-plan-p5-holdout.json > staging/post7d/GO-p5` with Karl's OK. Recommendations:
- **o01 with the 8 GB text: yes, as its own line** (+3.4 h) - Karl's real hardware question, corrected as he asked
  10-28; kept out of the holdout totals because phase 4 was tuned on it.
- **Checkables at 47 min** - under Fix 6, 47 whole-run minutes = the 30 min of research every earlier stage had; a
  30-min budget leaves ~17 min of research.

Paid search: 0 in steps 1-3; Phase 5 0 as staged (<= 90 with route 7d, ~275 with 7b) - inside the caps (Tavily 201 /
1,000 and Exa $1.01 / $10 used in November; 7d adds <= 210).

## Between 7d and step 1 (grading, not GPU)

7d's four blind rounds (PLAN-7D section 6) with `staging/item7d/tools/relief_counts.py` (the live copy lacks
shop-7e); each SUMMARY.md carries the step-bug line (PLAN-7D.md section 9); paid_tracker for November.

## Start (Karl)

```
systemd-run --user --unit=post7d-chain --description="post-7d bench plan chain" /bin/bash /home/USER/ai/deep-research/staging/post7d/chain.sh
```
Confirm: `systemctl --user is-active post7d-chain`, its MainPID, and "waiting for queue-plan-7d.json to finish" in
logs/post7d-switch.log. Stop a wait: `touch staging/post7d/STOP-switch`.

## Files

switch.sh, chain.sh, install-ldr-fixes.sh, replays.sh, ldr-fixes/ (patch snapshot), tests/test_ldr_fixes_installed.py
(post-install copy of the study's tests), tools/ (bench2.py + bench2-queue.sh staged with .orig, plan_check.py),
profiles/flash-next-c3c.env, phase5/p5.json, LIVE-SHA256-AT-STAGING.txt, scratch/ (check logs).
