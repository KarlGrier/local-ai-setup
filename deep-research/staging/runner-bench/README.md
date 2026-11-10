# Runner + bench queue: model-profile restart and item 7's run file (staged 10-29, NOT installed)

Two changes for the Jan research runner, the bench queue and run-ldr.sh:

1. **Model-profile restart.** LDR is restarted when its model profile changes. This is C3's open point 6.
2. **run/paid-run.json.** This file tells item 7's paid-search budget whether LDR's searches are Karl's research or a
   test. It is item 7's install prerequisite 1.

Nothing changes when nothing differs. The tests below show this on 6,480 runner and 11,664 queue stamp states, and on
today's live stamps.

## Install order

**C3 first** (`staging/c3/install.sh`), **then this**, then item 7.

- This builds on C3's copies of run-ldr.sh and research-runner.py (kept here as `*.c3`).
- The runner's model-profile check needs C3's `run/ldr.modelprofile` stamp.
- Item 7 then installs `item7/tools/paid_budget.py` from **here**, not `staging/item7/tools/paid_budget.py`.

## Files

Each staged file is diffed against the copy kept next to it.

| file | lines | what |
|---|---|---|
| tools/ldr_runfiles.py | new, 254 | One helper (stdlib) for the stamp check and the run file. CLI: `mp-check`, `paid-show`, `paid-clear --stale-only`. |
| tools/research-runner.py (vs `.c3`) | +81 -17 | See below. |
| tools/bench2-queue.sh (vs `.orig` = live) | +41 -11 | See below. |
| tools/bench2.py (vs `.orig` = live) | +76 -7 | See below. |
| run-ldr.sh (vs `.c3`) | +13 -1 | `stop` / `restart` remove a **stale** run file. `status` shows the run file. The C3 stamp is unchanged. |
| item7/tools/paid_budget.py (vs `.item7`) | +22 -1 | `_run_now()` ignores a stale file (see "Stale files"). |

**research-runner.py**

- The inline stamp checks are now `ldr_restart_reasons()`, with the same logic. It also checks the model profile:
  `LDR_MODEL_PROFILE`, default flash-next. The restart log line gives the reason.
- `paid_run()`:
  - `start()` writes `{"kind": "research", "run": <job id>}` just before `/api/start_research`.
  - It removes the file if the start fails.
  - `tick()` keeps the file while the job is running or paused, and removes it after the job ends.

**bench2-queue.sh**

- The restart condition is now `ldr_restart_why <run dir> ...`: the same checks in the same order, plus the model
  profile and the fallback an item 7 step needs.
- It reads `bench2.py next --wide`, which adds three columns: ROUTE, CACHE, MODEL_PROFILE.
- For an item 7 step it starts LDR with `LDR_SEARCH_FALLBACK=1` and `LDR_MODEL_PROFILE`.
- It passes `--model-profile` and `--paid-route` / `--paid-cache` to bench2.py.

**bench2.py**

- `next --wide`: plan-step keys `"paid_route"` (types / 7a / 7b / 7c), `"paid_cache"` (bool) and `"model_profile"`.
  Without `--wide` the output is unchanged.
- `run` refuses an LDR on another model profile.
- `run --paid-route R` needs `ldr.fallback` on and R in tools/paid-route.json.
- Around each question it writes `{"kind": "test", "run": "<runs folder>/<qid>", "route": R, "cache": bool}` and
  removes it in `finally`. bench.json records `paid_run`.
- Ordinary runs write nothing.

### Design points and deviations

- **No stamp counts as flash-next.** An LDR started before C3 runs the built-in values, which equal flash-next.env (C3
  equivalence test). So today's LDR causes no restart. The stamp's hash covers the file's content, so any edit to the
  profile restarts LDR at the next job or question start.
- **The test-run file is written by bench2.py, not the queue shell.** Both units use `KillMode=process`: stopping the
  queue leaves bench2.py and its research running. So the owner must be the process that runs the question. A trap in
  the shell would either delete the file under a live run, or delay the queue's stop.
- **The run id is `<runs folder>/<qid>`**, for example `screen-deep-p7b/s01`, not `<label>/<qid>`. It is unique, and a
  run without a label would otherwise be `/s01`.
- **Stale files.** Each file records its writer's pid and the start time from `/proc`, so a reused pid or a zombie
  counts as dead. Readers ignore a file whose writer is gone; LDR's searches then get no paid search, and nothing is
  counted against the wrong run. A file without a pid (written by hand) counts for 12 h. A file with a pid has no age
  limit, because a Jan job can be held overnight.
- **Writes are atomic** (temp file + rename, under `run/paid-run.lock`).
- **Who removes the file:**
  - its owner, at the end;
  - the runner, every tick, if the file is its own or stale;
  - run-ldr.sh stop / restart, if stale.
  A live file from another writer is kept.
- **If the runner stops mid-job,** LDR keeps researching, but that research gets no paid search until the runner is
  back. Its first tick rewrites the file.

## Installing: when and how

**When:** no LDR run, no Jan job (queued or active), no bench queue or bench2 run, and no replay. Do it after C3 is
installed and the ldr-fixes-chain has ended. The bench service must be stopped.

1. **Lineage check.** Each of these must print nothing. If one differs, re-stage that file.

   ```
   W=/home/USER/ai/deep-research; S=$W/staging/runner-bench
   cmp $S/run-ldr.sh.c3 $W/run-ldr.sh; cmp $S/tools/research-runner.py.c3 $W/tools/research-runner.py
   cmp $S/tools/bench2-queue.sh.orig $W/tools/bench2-queue.sh; cmp $S/tools/bench2.py.orig $W/tools/bench2.py
   ```

2. **Run the tests:** `TMPDIR=<scratch> $S/tests/run_all.sh` (about 1.5 min, nice 19).

3. **Copy the files.**
   - Back up each live file as `*.before-runnerbench`.
   - Copy to a new name, then `mv -f` over the live file, so a running shell keeps the old file.
   - Order: `ldr_runfiles.py` first, then bench2.py, bench2-queue.sh, run-ldr.sh and research-runner.py.
   - The new queue needs the new bench2.py. The old queue works with the new bench2.py.

4. **Restart the runner service.** It reads its code at start.

   Nothing else needs a restart: LDR takes no new code from this change. The queue picks it up at its next start.

**Rollback:** copy the `*.before-runnerbench` files back, then delete tools/ldr_runfiles.py.

## Tests (offline, 10-29): all pass

`tests/run_all.sh`. Temp folders only. The only live access is read-only: today's `run/ldr.*` stamps are copied, and
the final dry check reads the live run folder.

| test | checks | what it covers |
|---|---|---|
| test_runfiles.py | 62 | The stamp equals the one run-ldr.sh's own line writes. Mismatch cases: other profile, edited file, missing file, path form. The CLI. Run file: write, atomic, mode, unchanged-skip. Stale cases: dead / zombie / reused pid, pid-less file, garbage. Clear rules. The staged paid_budget reader agrees with the writer (kind, run, route, a stale file refused), and both use the same default path. |
| test_runner.py | 44 | The C3 runner and the staged runner both run `start()` with every external call stubbed. On 6,480 stamp states they make identical `run_ldr` calls and job updates. Today's stamps give the same decisions with no model-profile reason. Model-profile restarts. The run file when the start succeeds, gets HTTP 500, or raises. `tick()` for every job state, another writer's file, a runner restart, and a write error (logged once). |
| test_queue.py | 47 | `bash -n`. The staged `ldr_restart_why` against the live queue's inline condition (cut from `.orig`): same decision on 11,664 states and on today's stamps. Model profile and item 7 fallback cases. A missing helper means no restart. The column parsing. bench2.py `next` (7 columns unchanged, `--wide`). `run`'s refusals compared with `.orig`. The run file during each question, removed after, also when the client call fails. |
| run_item7_tests.sh | 5 suites | Item 7's own tests pass with this paid_budget.py, run on a temp copy. |
| dry check | 2 lines | Live run/, read-only. `mp-check flash-next` exits 0 (today's LDR fits, no restart). `paid-run.json: none`. |

There is no shellcheck on this PC, so the shell scripts got `bash -n` only.
