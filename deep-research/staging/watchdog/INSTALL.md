# Stuck-run watchdog for the bench queue (staged 11-03, not installed)

Karl 11-03: "Yes to the watchdog: stop a run with no model call for 30 minutes, mark it faulted, and requeue it once.
If the same run hangs twice, stop and report instead of requeueing. Install it only when no LDR run is live."

Why: shop-7e-deep-p7dx/s2 made its last model call at 18:47 (LDR's research thread spun on a fetched page, RSS 13 GB)
and sat until the client's own limit at 22:35 (evidence: results/bench2/runs/shop-7e-deep-p7dx/s2.stuck-1103/).

## What it does

1. **tools/ldr-client.py** (`research --watchdog-min W`, or `$WATCHDOG_MIN`; off when neither is set). Every 3 s poll
   it checks for model-call activity. The idle clock restarts when:
   - this run's capture file `<capture_dir>/calls.jsonl` grows (without a capture dir: `logs/llm-calls.jsonl`), or
   - the proxy gate snapshot (`run/research-clock.json`, written about once a second) shows `inflight > 0` or `held > 0`.

   **Held time is not counted:** the gate closed for a pause (the runner's memory-relief restart, a Jan or user pause,
   the night pause), a test lock, or yielding to another client.

   **Strata not answering, with no call waiting, IS counted.** Strata's on-demand launcher stops it after 45 idle
   minutes, so a stuck run would otherwise look held forever. s2's samples show `strata=None` for hours, and the
   research clock counted 153 min as held.

   The clock uses CLOCK_MONOTONIC (it does not run while the PC is suspended), and one poll counts at most 2 min.

   When the clock reaches W minutes, the client:
   1. takes a snapshot of LDR's process from `run/ldr.pid` and /proc: RSS, threads, and the three busiest threads
      (CPU % over 1 s, state, wchan);
   2. sends LDR's `POST /api/terminate/<id>` and waits up to 120 s for a final status;
   3. removes the proxy mode file, so capture stops;
   4. writes `results/TAG/faulted.json` (reason, last call id/t0/end, idle and held minutes, gate snapshot, LDR
      process, terminate result, `stopped_by_api`), plus marks.json, samples.json, research.json and
      research-logs.json;
   5. exits **86**.
2. **tools/bench2.py** `run` passes `--watchdog-min $WATCHDOG_MIN` (default 30; 0 = off). On rc 86 it moves the files
   in as usual, writes `bench-fail.json` with `"faulted": "<reason>"`, and exits 86 without starting another question.
   Normal runs and other failures behave as before: bench2.py still ends with 0.
3. **tools/bench2-queue.sh** (the watchdog block). On rc 86 with no bench.json, the queue:
   1. stops LDR with `./run-ldr.sh stop`, so a thread that ignores the terminate goes too;
   2. moves the run folder aside with `mv RUNDIR RUNDIR.faulted-HHMMSS` (`-PID` is added on a name clash), never
      deleting it;
   3. appends `key <TAB> time <TAB> folder` to `results/bench2/watchdog-faults.tsv` (key = `set/profile/label/id`);
   4. logs it;
   5. on the first hang, continues: `next` picks the same question again because bench.json is missing, and the
      fresh-LDR-per-question restart gives it a new LDR;
   6. on the second hang of the same key, appends a NOTES.md line (`BENCH QUEUE STOPPED (watchdog ...)` with both
      folders), sends a critical desktop alert (notify-send, as the queue's other stops do) and **exits 0**. The unit
      has `Restart=on-failure`, so exit 0 keeps it stopped.

   If the unit is started again while the key still has 2 lines in the TSV, the queue refuses that question (log
   line and alert) and exits 0. To rerun it: delete its lines from the TSV and start the unit. To skip it: take it
   out of the plan.

## Files

| live file | staged copy | backup made by install.sh |
|---|---|---|
| tools/ldr-client.py | staging/watchdog/tools/ldr-client.py | tools/ldr-client.py.before-watchdog |
| tools/bench2.py | staging/watchdog/tools/bench2.py | tools/bench2.py.before-watchdog |
| tools/bench2-queue.sh | staging/watchdog/tools/bench2-queue.sh | tools/bench2-queue.sh.before-watchdog |

These are new at run time: `results/bench2/watchdog-faults.tsv` (on the first fault), `RUNDIR/faulted.json` and
`RUNDIR.faulted-*`. The install does not touch the LDR package, the systemd units, strata-proxy or run-ldr.sh.
The sha256 of the live files these were staged against is in `LIVE-SHA256-AT-STAGING.txt`; `check.sh pre` refuses if
any of them has changed since.

Tests (`tests/run_all.sh`; offline, scratch only, 31 tests):
- **test_watchdog.py**: firing at the limit; held reasons not counted; a held or in-flight call is not idle; Strata
  down counts; a stale snapshot counts; call-log fallback; the 2-min cap per poll; WATCHDOG_MIN parsing;
  last_record; proc_snapshot on a busy child; the exit codes agree across the three files.
- **test_client_loop.py**: the staged `research` end to end with a fake LDR, a fake proxy and a fake clock. Covers a
  normal run, s2's shape (fires 30 min after the last call, exit 86, the full faulted.json), a 60-min test lock
  delaying the fire by exactly 60 min, a call held for 3 h, and the option off.
- **test_bench2_rc.py**: the `--watchdog-min` pass-through, exit 86 with the files kept, and normal runs and
  ordinary failures unchanged.
- **test_queue.py**: the staged queue's whole loop in a sandbox. Every external path is replaced and asserted, so a
  changed script stops the test before it runs. Covers: hang once, requeued on a fresh LDR; second hang stops and
  reports; refusing after a restart; normal runs; other failures not counted; per-run counting.

## Install: only with no LDR run, Jan job, bench queue step, replay or grading live

Install inside a gap, while the queue is held: `tmp/bench2.hold` exists, the last line of `logs/bench2-queue.log` is
`hold file: waiting ...`, and `run/bench.lock` is free. `check.sh live` checks all of this. It also checks: no
`run/paid-run.json`, no active Jan job (`job` in run/research-control.json), nothing in flight or held at the proxy,
and no replay or grading unit. It does not look at queued Jan jobs (that needs jobs/); Jan jobs never use these
three files, and the queue itself waits for them.

1. `bash /home/USER/ai/deep-research/staging/watchdog/check.sh pre`: nothing live, live files unchanged, tests
   green.
2. `bash /home/USER/ai/deep-research/staging/watchdog/install.sh`: backups, new file + mv for each, then
   `check.sh post` (sha256 equal to staged, syntax, `--watchdog-min` present, tests, `bench2.py next` answers).
   ldr-client.py and bench2.py take effect from the next question, since each question is a new process.
3. **Restart the bench unit in the same gap.** The running queue is a bash script that keeps reading its old
   (replaced) copy, so the new loop starts only at the unit's next start. Do it while the queue waits on the hold
   file, never while a question runs (bench.lock held: with KillMode=process the run would continue without the
   loop that handles its rc). Use `systemctl --user restart deep-research-bench.service`, or `install.sh
   --restart-unit`, which re-checks `check.sh live` first. The new loop waits on the same hold file, so the gap is
   unchanged. If the unit is stopped, the new loop starts with it.

   If you skip step 3, the old loop treats rc 86 as "not completed (rc 86); retry in 10 min". That means unlimited
   retries and no second-hang stop, so don't leave it in that state.
4. Verify:
   - `readlink /proc/$(systemctl --user show -p MainPID --value deep-research-bench.service)/fd/255` shows
     `.../tools/bench2-queue.sh` without "(deleted)";
   - the log has a new `queue started (pid N)` followed by `hold file: waiting`;
   - after the gap, the first run's `client.out` minute lines end in `idle=N/30 min`, and its marks.json has
     `"watchdog": {"min": 30.0, ...}`.

**R (rollback):** in a gap, copy each `tools/<f>.before-watchdog` beside `<f>` and `mv` it over, then restart the unit
as in step 3. Leave the TSV and any faulted folders in place; they are records.

## Settings and limits

- `WATCHDOG_MIN` (default 30; 0 = off) is read by bench2.py from the queue's environment. Changing it means adding an
  `Environment=` line to the unit, which is not part of this install.
- `inflight` and `held` are proxy-wide. Another proxy client's call keeps the clock at 0, which errs on the safe side.
  During a bench run that is normally only this run's LDR.
- A single call stuck in flight for hours is not caught; the client's own `--max-minutes` limit (budget + 150)
  still is.
- Fire time: 30 min of unheld quiet after the last call, plus up to one 3 s poll. Then up to 2 min of terminate wait.
  In s2's case that would have been about 19:17 plus any held time, instead of 22:35.

## Open for Karl (not changed here)

- **Paid-search cap on a requeued run.** paid_budget counts the 30-per-run cap by the run name
  `<runs folder>/<qid>` (`~/.config/deep-research/paid-runs.json`), so a requeued attempt shares the faulted
  attempt's count. `shop-7e-deep-p7dx/s2` already has **13 of 30**. Its rerun (it is already moved aside to
  `s2.stuck-1103`, so the current queue picks it again after this gap, watchdog or not) gets at most 17 paid
  searches, unlike its p7d pair. Options:
  - a fresh cap per attempt: a new run name such as `.../s2.r2`, up to +30 searches per fault;
  - keep the shared cap, and the arm is not like-for-like for that question.
- **Pre-existing, not touched:** the search-failure stop ("three runs in a row FAILED on web searches - queue
  stopped") exits 1, and the unit has `Restart=on-failure` with `RestartSec=60`. systemd therefore starts the queue
  again a minute later and the failure count starts over. The watchdog's stops exit 0 for this reason.
