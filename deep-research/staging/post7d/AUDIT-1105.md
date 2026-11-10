# Post-7d weekend automation - independent audit (11-05 18:10 CST, read-only)

Scope: deep-research-bench (tools/bench2-queue.sh), post7d-chain (chain.sh -> switch.sh, replays.sh), post7d-retry
(retry-failed-replay.sh), gap-series (work/r23/gap-series.sh -> the 5 driver snapshots -> work/r22/port_gap4.sh), and
what they call (bench2.py, ldr-client.py, fix-replay.py, strata-proxy.py, research-runner.py, strata-ensure.sh,
kwatch.sh / kcheck.sh, nogap-run.sh). Nothing was edited, started, stopped or signalled; one sandbox script
(scratch/audit/sim-started.sh, a verbatim copy of gap-series.sh's `started_after_gap` with systemctl stubbed, run on a
synthetic log) is the only thing executed besides reads, `bash -n` and status queries.

State at audit: o02 (p4s9) running since 16:46:42 (ends ~19:35); gap-basalt-b's `port_gap4.sh begin` (pid 1700937) has
held tmp/bench2.hold since 16:47:08 and polls run/bench.lock; chain step 2's switch.sh (pid 1321028) waits for p4s9;
post7d-retry waits for the chain's end; 176 GB free; all 5 driver snapshots/hashes match their `.ready` reviews.

Ranked by class (stall > two-GPU > data > rule > cosmetic); within a class, most likely to bite first.

---

## STALL

### 1. A gap that ends any way other than `port_gap4.sh end` leaves the hold (and a stale lockpid) for ever
- **Where:** gap-series.sh:56-68 (only rc 0/1/3 handled; any other rc -> `alert; exit 1`, no cleanup); gap-series.sh:64-67
  (rc 1 = "refused before opening, 8080 untouched" - assumed, never checked against tmp/port-gap.lockpid);
  port_gap4.sh:33-39 (hold set, lock holder started with `setsid` but inside gap-series' cgroup); waiters with no timeout:
  bench2-queue.sh:119, switch.sh:84-88 (`wait_hold`), replays.sh:103-106 (`gap_near` / `gap_open` = `[ -s lockpid ]`),
  nogap-run.sh:13/19.
- **Scenarios:** (a) a driver dies mid-gap (bash arithmetic error -> exit 1, unbound variable -> 127, OOM, signal);
  (b) gap-series.service is stopped/restarted (by a person or a restart waiter like series-restart-after-ba.sh:27, which
  only checks lockpid, not the hold) - **right now** that would kill Basalt b's `begin` while its hold is set;
  (c) exit 3 (by design "gap left OPEN").
- **What is left:** the series exits, systemd kills the cgroup -> the `sleep infinity` lock holder dies (tmp/gpu-test.lock
  is FREE), but tmp/port-gap.lockpid stays non-empty (dead pid) and tmp/bench2.hold stays; 8080 down. For rc 1 (case a)
  the series first walks the remaining drivers, each refuses on the live lockpid (exit 1, logged as a normal "skipped",
  normal-urgency notice), then "series done".
- **Effect:** the bench queue, the chain's switch.sh and replays.sh wait for ever (no alert from them); retry waits for
  ever; nogap jobs frozen for ever. Meanwhile the lock is free, so Jan / the proxy can start P028x on demand - the
  "gap left open for Karl" after exit 3 is not actually held.
- **Minimal fix:** in gap-series.sh after line 57: if `[ -s tmp/port-gap.lockpid ]` and rc != 3 (including rc 1), run
  `port_gap4.sh end` and alert critical; a TERM/EXIT trap in gap-series.sh that removes tmp/bench2.hold when lockpid is
  empty (a driver still in `begin`). In bench2-queue.sh:119 alert (critical, once) when the hold is older than ~6 h and
  lockpid is empty or its pid dead. Do not restart gap-series to deploy any fix while a driver is in `begin`.

### 2. A run that fails the same way each time is retried every 10 min for ever, silently - first exposure: Phase 5's baseline arm
- **Where:** bench2-queue.sh:193 (`not completed (rc N); retry in 10 min`, no count, no alert); bench2.py:123-192
  (each SystemExit check -> rc 1 -> this path).
- **Scenario:** Phase 5 starts with `holdout baseline o04` (pristine LDR 1.10.7, run-ldr.sh LDR_PROFILE=baseline). No
  baseline-profile run has gone through this queue since 10-19 (runs/*-baseline* are 10-18/19); since then: a fresh LDR
  per question, C3b model-profile stamps, the watchdog, Pillow 13, the client's fetch guard. The stamps look right on
  paper (run-ldr.sh:189-225 writes ldr.items "off" and ldr.modelprofile for baseline), but nothing has exercised it.
- **Effect:** any repeatable failure loops Saturday -> Sunday with the GPU idle; switch.sh is already gone (chain ended
  at the p5 switch), so no one notices.
- **Minimal fix:** count consecutive non-completions per run key (as SFAIL / the watchdog do); at 3: NOTES line,
  critical notice, `exit 0`. Optionally (Karl's OK, it starts LDR) one baseline smoke before Saturday.

### 3. One kernel-log hit stops the weekend at the next kcheck (and kwatch never re-arms)
- **Where:** kwatch.sh:13 (PAT includes `page allocation failure`, `WARNING: CPU`), kwatch.sh:47 (exits after the
  first hit); kcheck.sh:8-10 (KERNEL_ERROR or watcher not running = FAIL).
- **Scenario:** a benign page-allocation failure under the DeepSeek csample gate's RAM pressure (your 10-25 rule: "drop
  the run and go on"), or an amdgpu WARN after a power-key suspend (10-31). Then: switch.sh:165 dies at the next switch,
  replays.sh:199 dies after the current replay, every remaining driver refuses at preflight (e.g. gap-basalt-b.sh:142,
  exit 1 -> silently skipped), an open gap ends with exit 3 (left "open", see 1).
- **Effect:** stall until Karl; by design for real errors, but the 10-25 exception is not encoded. Gate loosening needs
  Karl's OK - flagged, not proposed.

### 4. Reboot, power loss, logout, power key
- **Where:** `loginctl` Linger=no; post7d-chain / post7d-retry / gap-series are transient (`systemd-run`); GDM
  AutomaticLogin=karl; deep-research-bench is enabled (`[Install] WantedBy=default.target`); power-button-action =
  `suspend`.
- **Scenario / effect:** after a reboot (auto-login) the queue restarts on its current plan, re-runs the interrupted
  question (bench2.py moves the old files to failed-attempt-*), finishes that plan and stops: no switch, no gaps, no
  retry - GPU idle for the rest of the weekend. A gap that was waiting or open at the cut leaves tmp/bench2.hold and a
  stale lockpid (disk files) -> the queue waits for ever (finding 1). A replay cut mid-way leaves a non-empty label
  folder -> a rerun of replays.sh dies at replays.sh:163 until it is moved. A logout or a GNOME session crash with
  Linger=no stops every user unit (same result, nothing comes back until the next login). A power-key press suspends;
  on resume the 10-31 amdgpu W taint fails kcheck (finding 3).
- **Minimal fix:** `loginctl enable-linger karl` (Karl's OK); power button -> "nothing" for the weekend; a small boot-time
  user unit that alerts when tmp/bench2.hold exists with no live lockpid, and (optionally) re-creates the chain from the
  first unfinished step.

### 5. The retry can conclude "chain stopped early" during a queue auto-restart
- **Where:** retry-failed-replay.sh:31 (`is-active`), :68-72, :81-84; deep-research-bench Restart=on-failure,
  RestartSec=60.
- **Scenario:** bench2-queue.sh exits non-zero during Phase 5; for 60 s the unit is "activating (auto-restart)" ->
  `is-active` false; a 300-s poll landing there sees chain + bench "ended", no "queue finished (p5)" line -> every failed
  label goes to RETRY-NEEDS-DECISION and the one-shot exits. Low probability.
- **Fix:** treat ActiveState activating/reloading as active (`systemctl show -p ActiveState`).

## TWO-GPU (a gap over a starting question / two engines resident)

### 6. gap-series' "a question started after the gap" test is always true once a release is logged
- **Where:** gap-series.sh:29 `awk -v t="$rel" 'substr($0, 1, 19) >= t && /: running/'`. Lines without a timestamp
  compare greater than any date ("L" > "2"), and run-ldr.sh's status lines contain ": running" ("LDR (deep profile,
  ...): running (pid ...)", "strata-proxy: running"). The FIRST such line in the whole log (bench2-queue.log line 21,
  10-18) always matches. Verified: scratch/audit/sim-started.sh returns 0 for a log ending "hold released / all planned
  questions done / queue finished" with the chain active (designed answer: 1, keep waiting).
- **Effects this weekend:**
  - **Basalt b -> csample (~30 %):** the series fires 0-10 s after the queue logs "hold released"; the queue takes
    ~3 s (bench2-queue.sh:119 -> 162-175 -> bench2.py:194-195) to hold run/bench.lock; csample's preflight is ~0.1 s.
    If it lands in that window, port_gap4.sh:35 sees bench.lock free and stops 8080 while o03 starts. o03's calls are then
    held at the proxy gate (strata-proxy.py:39) - the GPU is not shared, but an in-flight first call is cut, o03's
    wall-clock client stop keeps running (finding 9), and at the gap's end its held call starts P028x early (finding 7).
  - **csample -> ud31 (near-certain):** p4s9 ends after csample's gap; the series launches ud31 at once (no question
    between; the 11-05 `nothing_left` guard at :21-23 is never reached). switch.sh:162 then waits on ud31's hold:
    item 8 starts ~2 h later. Then no further "hold released" is logged (item 8's queue starts with no hold), so
    ud31-dec waits for the 4-h fallback (finding 12).
  - A race hitting a long gap (ud31 120 min, port0211 130 min) over an item-8 start (client stop 182 min) loses that run.
- **Minimal fix:** anchor both awks to timestamped lines (`substr($0, 1, 2) == "20" && ...`); and in port_gap4.sh begin,
  after bench.lock is first seen free, wait ~45 s (> the queue's 30-s hold poll + its start) and re-test bench.lock
  before taking the test lock.

### 7. `port_gap4.sh end` releases the test lock before the gap's engines and memory are gone
- **Where:** port_gap4.sh:50-52 (lock holder killed, lockpid removed) come before :56-60 (engines, up to 120 s) and
  :61-67 (MemAvailable >= 70 steady, up to 180 s); strata-ensure.sh:35 / research-runner.py:452 / strata-proxy.py:43 all
  key on the lock.
- **Scenario:** a research call held at the gate (finding 6), or a Jan job queued during the gap: as soon as the lock
  goes, the proxy (on-demand start) or the runner (TICK 3 s) runs strata-ensure -> P028x loads while the last test
  engine is still exiting / memory not back - the 11-04 swap push-out the memory wait was added for. strata-ensure's
  busy() (strata-ensure.sh:41, `strata --serve`) does not see a `strata-dsv41` engine. port_gap4's own swap check
  (:68-72) then measures after the fact and reports "no swap-out". nogap-run.sh resumes frozen jobs at the same moment.
- **Minimal fix:** move lines 50-52 to just before line 70 (release the lock right before the strata-ensure call).

### 8. Gaps do not wait for Jan jobs
- **Where:** port_gap4.sh:35 waits only for run/bench.lock; a Jan job never holds it (research-runner.py start()).
  research_wait (with_server.sh:13) only runs later, after 8080 is already stopped (port_gap4.sh:40).
- **Scenario:** a Jan job queued while a question runs starts within 3 s of the question's end (runner tick; the lock is
  still free); begin's 20-s poll then stops 8080 under it - its in-flight call is cut, the rest is held for the whole
  gap. An already active Jan job does not delay a gap at all. Same window between replays: a Jan job queued during
  fix-replay's pre-lock seconds (imports, run_store, code-tool clones before fix-replay.py:228) runs beside the replay.
- **Minimal fix:** in begin, after bench.lock is free, wait while a Jan job is queued/active (research_common's test,
  as bench2-queue.sh:37-41), and call bringup/lib/research_wait.sh after taking the lock and before line 40.

## DATA

### 9. Wall-clock limits count gate-held time
- **Where:** ldr-client.py:545 (`now - t0 > max_minutes`: 291 min open, 182 min item 8); replays.sh:172-176
  (`timeout 180m`), replays.sh:201 (a timeout = "failed on its own").
- **Scenario:** a question held at the gate by a gap (finding 6), by yield to Karl's chat (yield_minutes 5 after each chat
  request) or by a relief restart (`wait-idle` up to 15 min); a replay held the same way.
- **Effect:** the question is terminated on wall time; ldr-client then still writes summary.json (:793), so the cut run
  appears to be recorded as finished (bench.json). A replay hold counts toward D8's "second failure" -> chain stop.
- **Fix:** subtract run/research-clock.json's paused_total delta from both clocks.

### 10. `engine_sha` can pick the wrong engine -> "NOT resuming the queue"
- **Where:** port_gap4.sh:25-26. The 8080 engine's cmdline has no "--port 8080" (only its server.py wrapper does; ps:
  `engine-r22p028x/strata --serve --pack ...`), so the filter never matches and `pgrep -x | head -1` takes the
  lowest-PID strata/strata-host; :60 starts anyway with engines left.
- **Effect:** a test engine still exiting -> wrong sha -> exit 1 (:75-77) -> driver exit 4 -> series stops, hold stays
  (finding 1).
- **Fix:** take the engine as the child of the 8080 listener (`ss -ltnp` pid -> `pgrep -P`).

### 11. Disk floor: thin margin, checked only at preflights
- **Where:** gap-ud31.sh:303-305 (free + old - 54.8 GB - 8 GB >= 100); nothing in the queue, chain or retry checks
  df. 176 GB now -> ~113 GB after ud31's splice/packs -> ~105 GB by Sunday (Phase 5 ~66 runs x ~90 MB, logs). Inside the
  floor, no guard if anything unplanned writes. **Fix:** a df >= 100 GB check before each question (bench2-queue.sh)
  and in replays.sh `ready()`.

### 12. 4-h fallback launches a driver unconditionally
- **Where:** gap-series.sh:50 (1440 x 10 s, no re-test after the loop), :51 logs "a question started" anyway.
- **Effect:** after finding 6's back-to-back ud31 this becomes the normal pacing (ud31-dec ~4 h after ud31). If the
  series slips past item 8, it fires during the replays; a hold set during fix-replay's pre-lock seconds = VOID
  (replays.sh:186-196), twice on one label = chain stop (no C3c, no Phase 5).
- **Fix:** after the loop, re-test; if still false, alert and keep waiting (or skip) instead of launching.

## RULE

### 13. Kernel errors do not stop the research path; Phase 5's "kcheck when the queue finishes" exists nowhere
- **Where:** no KERNEL_ERROR / kcheck in bench2-queue.sh, bench2.py, strata-proxy.py, strata-ensure.sh, phase_end.sh,
  research-runner.py; kwatch.sh:17,30 kill only `strata|strata-host` (not `strata-vision`, not `strata-dsv41`, the
  csample engine); retry-failed-replay.sh:77 exits before its kcheck (:85) when no replay failed.
- **Effect:** after kwatch's one-shot kill, the proxy / queue restart P028x on demand and the plan goes on - all of
  Phase 5 (~36 h, no chain step after it) can run after a kernel error, against RULES-p5.md section 4 Q6 and the "stop
  at the first error" rule; the DeepSeek engine survives the "stop everything".
- **Fix:** kwatch.sh: add strata-vision and strata-dsv41 to both pgrep lists; bench2-queue.sh: before each question
  `bash $SC/bringup/lib/kcheck.sh bench-<id> || { say; NOTES; notify; exit 0; }`, and once at "all planned questions
  done".

### 14. "Every gap between two questions" - see finding 6 (ud31 straight after csample; nothing_left bypassed).

### 15. A transient refusal skips a driver for good
- **Where:** gap-series.sh:64-67 (exit 1 -> skip, never retried). Transient causes: `nvidia-smi did not answer`, a
  listener on 8081, kwatch down, gpu-test.lock momentarily held, the r23-port0211 worktree dirty / moved
  (gap-port0211.sh:253-255 - any other session touching it), ud31's disk sum (finding 11). ud31-dec then refuses too
  (needs ud31's decision). **Fix:** one retry at the next question boundary, or a separate exit code for "not now".

### 16. The retry runs after Phase 5, i.e. most likely after Sunday night; its report is dated days after its pair
- **Where:** retry-failed-replay.sh:81 (needs "queue finished (queue-plan-p5-holdout.json)"); Phase 5 = 66 runs,
  ~36-38.5 GPU h from ~Sat morning (WEEKEND-READY.md section 1). RULES-item8.md section 3 grades claims "on the report's
  own date"; a retried replay and its pair then carry different dates. Note only.

## COSMETIC
- switch.sh:226 and gap-series.sh:51 grep ": running" -> they report run-ldr's "LDR (...): running" line as the
  question (switch log 11-05 11:14:18 "first run: LDR (deep profile ..."), and NOTES.md's switch line inherits it.
- port_gap4.sh:68-72 swap measurement misses a push-out caused by an earlier on-demand start (finding 7).
- Running bash scripts are read incrementally (chain.sh pid 181246, switch.sh 1321028, bench2-queue.sh 1320700,
  gap-series.sh 1700787, retry-failed-replay.sh 1577386): edit them only by new file + mv, and remember a restart of the
  series is finding 1's hazard.

---

## Traces asked for

**(a) Exactly one replay fails on its own.** replays.sh:200-202 -> replay_failed (:145-153): folder -> item8/failed/,
"failed" row in item8/failed-replays.tsv (fix-replay / deep / evidence sha), normal notice, return 0; the other replays
run; :259-263 NOTES line + critical notice, exit 0 -> switch.sh:156-158 -> C3c switch (profile installed) -> step 4 waits
for C3c + GO-p5 (sha matches now: 3e1d0589...) -> Phase 5 switch -> chain.sh exits. post7d-retry (waiting since 14:58,
300-s poll) proceeds when chain + bench are inactive AND the log has "queue finished (queue-plan-p5-holdout.json)" ->
kcheck -> same sha checks -> waits for run/bench.lock -> replay() once (ready(), timeout, VOID rule, kcheck) -> NOTES +
alert. Risks on this path: finding 9 (a gate hold can be the "failure", and a second one stops the chain), finding 5,
finding 16 (timing), and a VOID-twice on another label still stops the chain (not "on its own").

**(b) A gap driver crashes mid-gap.** Finding 1: the series alerts (desktop + strata-compare NOTES) and exits (rc 1 is
misread as "refused" first); its cgroup kill frees tmp/gpu-test.lock and stops any test server; tmp/bench2.hold and a
stale non-empty tmp/port-gap.lockpid remain; 8080 down until something starts it on demand. The queue, switch.sh,
replays.sh, the retry and nogap-run wait for ever. Nothing recovers.

**(c) Reboot / power loss.** Finding 4: enabled units return after auto-login, transient chain / series / retry do not;
the queue finishes its current plan and stops; a hold left on disk blocks it for ever.

**(d) Date / time zone.** No problem in range: CST all weekend (DST ended 11-01); paid_budget's month is UTC
`%Y-%m` (paid_budget.py:89) - November throughout; run/night-ok present (bench2.py:74-79 lifts the night cut);
research.conf night_pause = off; replays.sh's relief window ('%FT%T') matches research-runner.log's format; '%F %T'
string compares are safe across midnight. The one broken time comparison is finding 6 (untimestamped lines sort after
every date).

## Checked, no finding
- **Paid search:** none of the four plans has a paid_route; the queue starts LDR with `env -u LDR_SEARCH_FALLBACK`
  (bench2-queue.sh:167/169), bench2.py refuses an LDR with the fallback on (bench2.py:182-184), the hook is gated on
  LDR_SEARCH_FALLBACK=1 in LDR's SearXNG engine, fix-replay only writes reports, GO-p5's plan is route none. Only Jan
  jobs (Karl's own, paid_budget caps) can spend this weekend.
- **Plans vs rules:** item8 (62 min, p8a/b/c, o01+o03), c3c (pc3c, flash-next-c3c, 171/47), p5-holdout (baseline p5 /
  deep p5final, fix:steps, o01 pair last, all FROZEN files present) match RULES-item8/c3c/p5; replays' fn / c3c env
  (replays.sh:71-72) match RULES-c3c table A; p5.json include_o01=false with o01 in the plan is intended (own round).
- Driver snapshots = reviewed hashes; tagcheck now prints FLAG (the queue's PAUSE branch is dead, no stop on a release);
  gap DeepSeek arms run on 8085 and are killed by tunearm.sh; test servers live in gap-series' cgroup (no GPU leak after
  a series kill).
