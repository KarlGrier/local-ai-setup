# Boot resume (staged 11-05 21:40, Claude) - NOT installed, NOT enabled, NOT started

Karl 11-05: *"After a reboot, resume the chain and series only at the next clean boundary. Never resume mid-gap or
mid-question: restart the interrupted question from the start, and rerun an interrupted gap from the beginning. Make
sure 8080 comes back, and alert me that a reboot happened."*

Files: `boot-resume.sh` (the logic), `boot-resume.service` (user unit, `WantedBy=default.target`), tests in
`scratch/bootresume/` (`test.sh`, stubs in `bin/`, last run `test-run.log`: **58 / 58 pass**). No existing script was
edited.

## Why a record is needed

post7d-chain, gap-series, post7d-retry and weekend-watch are transient units (systemd-run). A reboot drops them, and
nothing on disk says whether one was running, was stopped by hand, or had ended. So `boot-resume.service` runs all the
time as a **recorder**. Every 30 s it writes `run/boot-resume/units.txt`: the boot id, the time, and every active
transient user service with its Description, Environment, ExecStart and CollectMode. It writes nothing while the user
manager is stopping, or while a unit is `deactivating`, so a shutdown cannot record "nothing ran". The next boot
resumes from that record. The logs are what decide *where* each unit resumes.

## What it does at boot (once per boot)

The resume runs only when the record's boot id is not the current boot. The record must also be fresh: it must belong
to the boot that just ended and be no more than 20 min older than that boot's last journal entry. A second start in the
same boot only records.

1. **Alert.** One line in both NOTES.md files (deep-research and strata-compare) saying that a reboot happened and what
   was interrupted:
   - the question (the last `: running` line with no `<id>: rc` line after it),
   - an open gap (`port-gap.lockpid`) or a gap waiting in begin (the hold),
   - the series step that was interrupted,
   - the bench unit's plan,
   - the units that were active,
   - whether the previous boot shut down cleanly (from the journal).

   A second NOTES line gives the outcome. One `notify-send -u critical` goes out once a notification server is on the
   session bus (it retries for 24 h). `staging/post7d/STOP-boot-resume` turns everything off: alert only.
2. **Kernel check.** It waits up to 5 min for kwatch. kwatch must be active and its pid file must be newer than the boot
   and match its MainPID (a pid from before the boot can be reused). Then it runs `bringup/lib/kcheck.sh boot-resume`.
   It also greps the **previous boot's** kernel log with kwatch.sh's own `PAT`, from kwatch's last start on, which
   skips the boot-time "NMI watchdog: Enabled" line. If either check fails, nothing is cleaned and nothing is resumed;
   after his check, Karl or Claude runs `boot-resume.sh resume`.
3. **Leftovers, then 8080.** This step runs only when no gap driver, series, port_gap4, replays or fix-replay process is
   alive (a /proc scan, no `pgrep -f`) and nobody holds `tmp/gpu-test.lock`:
   - It removes leftovers written before the boot: `tmp/port-gap.lockpid`, `tmp/port-test-server.pid` (port_gap4 end
     would otherwise kill whatever process reuses that pid), `tmp/gap-keep-hold` and `tmp/gap-waiting-jan`.
   - Then it runs `strata-ensure.sh "boot resume"` (3 tries, 5 min apart) and checks the engine sha `f4c4f654fb24`
     (P028x, port_gap4's engine_sha) and the chat-cache policy.
   - Only then is a stale `tmp/bench2.hold` removed. It must be a "phase 4 gap:" hold written before the boot; any
     other hold is left alone and nothing is resumed.

   If 8080 or its checks fail, the hold stays, so the queue stays held. The research queue (enabled) comes back by
   itself and reruns an interrupted question from the start (bench2.py moves the old files to `failed-attempt-*`; that
   attempt is not counted as a queue failure, because it has no bench-fail.json).
4. **Restarts.** Each unit is restarted only if it is in the record, with its recorded description, environment and
   `--collect`. Nothing that is active is started again.
   - **Chain:** `CHAIN_STEPS` = the steps from the bench unit's `BENCH2_PLAN` on (7d→1, p4s9→2, item8→3, c3c→4,
     p5-holdout→done). switch.sh then waits for its FROM to finish again, so it resumes at the next clean boundary.
   - **Series:** the remaining steps come from gap-series.log after the last `series start`: done = `exit 0` or a
     "skipped" refusal; a step with "one retry" pending goes into `SERIES_RETRIED`; a `starting` line with no exit line
     = interrupted, and that step goes first. A transient `boot-resume-series` waits for a timestamped `: running` line
     *after the boot*. If the queue and the chain are both idle for 3 min, it counts as nothing left, as in
     gap-series.sh. Then it starts `gap-series` from a copy of the live gap-series.sh in which only the STEPS line is
     changed (`results/r23/run-copies/gap-series-boot-*.sh`). `GAP19_T0` = the last "hold released" before that
     question, so the series' own `started_after_gap` is true at once (tested on the real function). The driver takes
     a fresh snapshot, and its begin waits for that question to finish.
   - **Retry and watcher:** started as recorded. The retry is held back if the chain was supposed to resume and did
     not, because it would take a stopped chain for the chain's end.
   - Any other transient unit (e.g. a `series-restart-after-*` waiter) is listed and not restarted.

## Per case

| reboot during | what happens |
|---|---|
| a question (no gap) | Nothing is cleaned. The queue reruns the question from the start. The chain resumes at its step. The series' next step waits for a question after the boot, so it lands after the rerun question. |
| a gap (hold + lockpid, 8080 down) | The lockpid, test-server pid and keep marker are removed. 8080 comes back and is checked, then the hold is removed. The queue goes on. The interrupted driver reruns first, from the beginning, after the first question that starts after the boot. |
| a driver waiting in begin | The hold is removed. The question it waited for reruns. The driver reruns first, after that question has started (its begin waits for it to finish). |
| port_gap4 end (the last ~3 min) | The step has no exit line, so it counts as interrupted and the whole gap reruns. This follows Karl's rule literally. |
| replays.sh (step 3's between) | A replay folder without report.md, a half-written merge, and a verify-results.json swapped during the merge check are moved aside or restored, so replays.sh does not refuse. The chain resumes at "3 4" and replays.sh skips the finished labels. |
| replays.sh after a replay had failed | **Not resumed (Karl):** replays.sh would retry the failed label in-line and count failures from 0 again (D8). The retry is held back. |
| a plan switch | Before the unit file is rewritten: the same step again. After it: the bench unit already starts on TO at boot, so the chain resumes at the next step. Phase 5 only: a reboot inside the <1 s bench2.py install window makes switch.sh stop on `.before-p5` (Karl). |
| install-ldr-fixes.sh (step 1, past) | Not resumed (it has its own UNDO.sh). |
| nothing | 8080 comes back. The chain, series, retry and watcher restart and wait as they did before. |

The tests cover all of these, plus: kcheck fails, an error line in the previous boot's kernel log, boot messages from
before kwatch's start ignored, the wrong engine sha, the service started again in the same boot, `resume` by hand (no
duplicates), the recorder during "stopping", a stale record (cleanup and 8080 only), no record yet, the STOP file, a
live driver, and a second reboot while the series waiter was still waiting.

A live read-only `boot-resume.sh plan` (21:38) matched the current state: o03 interrupted, csample waiting in begin,
hold stale, chain at "2 3 4", series csample-first.

## Enable (Claude, after review)

```
cp -p ~/ai/deep-research/staging/post7d/boot-resume.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now boot-resume.service
systemctl --user is-active boot-resume.service; sleep 40; head -2 ~/ai/deep-research/run/boot-resume/units.txt; grep -c '^unit ' ~/ai/deep-research/run/boot-resume/units.txt   # expect 4
```
Use `--now`: with no record yet it only records. Undo: `systemctl --user disable --now boot-resume.service`.

## Needs Karl / suggested script changes (not made)

- **STAGED 11-05 22:0x: `replays.sh.new`** (seed_fails + the guarded verify backup; scratch/weekend/test_replays.sh 36/36,
  test_retry.sh 16/16 on it) and **`boot-resume.sh.new`** (lifts the D8 refusal when the installed replays.sh has
  `seed_fails`; bootresume suite 58/58, and 4b resumes with replays.sh.new). Not installed. Was:
- **replays.sh:** at start, take FAILS / FAILED from `item8/failed-replays.tsv` and skip labels whose last event is
  failed or void-twice. After that, a reboot in step 3 is always resumable. Also: back up verify-results.json only if
  `verify-results.item8-1029.json` does not exist yet.
- **gap-series.sh (optional):** read STEPS from an env var, so a restart needs no copy.
- **A failed kernel check at boot only alerts.** In the mid-question case the enabled research queue still runs. If
  Karl wants the queue held too, boot-resume could write a hold on a failed check.
- Unclean shutdowns are only reported. Should a reboot with no shutdown in the journal (power loss or crash) also stop
  the resume?

## 11-05 22:3x: Karl's decisions staged (boot-resume.sh.new, boot-check.service, boot-resume.service.new) - NOT installed

- **Boot check before the queue (decisions 1 + 2).** `boot-check.service` is `Type=oneshot`, `Before=deep-research-bench`
  and `After=kwatch`. It runs `boot-resume.sh boot-check`, which writes `tmp/bench2.hold` FIRST ("boot check RUNNING
  ... then: <command>"). A crash or the 15-min timeout therefore leaves the queue held (fail closed). A pre-boot gap hold
  is kept aside with its mtime. Then come kcheck, the previous boot's kernel log, and a clean-shutdown test (a
  reboot / power-off / halt target reached in `journalctl -b -1`).
  - **Pass:** the hold goes back to what it was before.
  - **Fail:** the hold says "boot check FAILED (<kind>) - ... Resume with: bash ~/ai/deep-research/staging/post7d/boot-resume.sh resume".
    NOTES.md in both repos gets the reason, what the journal shows (the last entry, whether a shutdown target was
    reached, panic / oops / MCE / Xid lines, the last 15 lines, also in `run/boot-resume/boot-<id>/last-boot.txt`) and
    the one command. boot-resume then restarts nothing, and its critical notice carries the same facts and the command.
  - **Why this and not an ExecStartPre drop-in:** a drop-in would gate every later start of the bench unit. switch.sh
    checks that the unit is active 5 s after its start, so a waiting pre-start would make it fail. The oneshot acts
    once per boot and is independent of the unit file that switch.sh rewrites.
  - **Weekend watcher:** it is not restarted on a failure. Its hold alert quotes the hold's first 120 chars, which now
    read "boot check FAILED (...) - the research queue is held until Karl checks. Resume with ...", so the alert does
    not mislead.
- **`boot-resume.sh resume` (the one command):** waits for kwatch, then runs kcheck again (refuses and keeps the hold
  while it fails). It clears the boot hold, putting back a pre-boot gap hold, and then runs the normal resume from the
  record. Karl's command counts as his OK for an unclean shutdown or for kernel-log lines from the previous boot.
  **Bug fixed:** in the installed version the recorder keeps `run/boot-resume/lock` for good, so a manual `resume` could
  never run. The .new uses `resume.lock` for resumes only.
- **One-shot waiters (Karl: "cover them in the resume").** A recorded `series-restart-after-*` unit is not restarted.
  Its logic is applied instead:
  - the `.ready.held` files its script names (literally, or as `$VAR.ready.held` with `VAR=.../<driver>`; today that is
    only gap-ud31.sh's) are restored by boot-resume-series right before the series starts;
  - its `--description` is used for the series;
  - the steps are computed its way: finished -> dropped; refused under the old series ("... - skipped") -> once more,
    first, with SERIES_RETRIED; interrupted -> rerun first;
  - if the waiter had stopped the series already, the series still resumes.

  The live list today is gap-series, post7d-chain, post7d-retry, weekend-watch and series-restart-after-cs.
  power-key-revert.timer is a persistent enabled timer, not a one-shot.
- **Tests** (scratch/bootresume):
  - test3.sh: 23/23 (boot-check pass with a gap hold, kcheck fail -> resume refuses then resumes, unclean shutdown +
    Xid, a crash/timeout, a late start does nothing, waiter W1-W4, resume beside the running recorder);
  - test2.sh: 58/58 on the .new;
  - `systemd-analyze --user verify` of the two units: rc 0;
  - a live read-only `plan`: csample first, gap-ud31.sh.ready.held listed, the waiter's description.

Install (Claude):
```
P=~/ai/deep-research/staging/post7d
cp -p $P/boot-resume.sh $P/boot-resume.sh.before-bootcheck && mv $P/boot-resume.sh.new $P/boot-resume.sh && bash -n $P/boot-resume.sh
cp -p $P/boot-resume.service.new ~/.config/systemd/user/boot-resume.service && cp -p $P/boot-check.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable boot-check.service && systemctl --user restart boot-resume.service
```
Do not use `--now` for boot-check; it only acts at boot (when started later than 30 min after boot it does nothing).
The restart of boot-resume only records (same boot).
