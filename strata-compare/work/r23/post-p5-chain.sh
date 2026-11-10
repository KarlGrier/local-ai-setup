#!/bin/bash
# post-p5-chain.sh - Claude 11-08. Karl 11-08: "After Phase 5's queue finishes, run these in order without waiting for
# me, once you've reviewed them: 1. the port confirmation gap; 2. the Basalt speed gap; 3. D1; 4. D2 (the sampled test
# on D1's winner, plus the 1017 probe). Each waits for an active Jan or DS Harness chat, as usual. Send an ntfy alert on
# any failure. Then install the mismatch guard" ... "send a non-urgent ntfy when Phase 5's queue finishes".
# Run as a user unit (no arguments):
#   systemd-run --user --unit=post-p5-chain --description="..." /bin/bash <this file>
#   1 waits for Phase 5's queue: the line "queue finished (queue-plan-p5-holdout.json)" in the queue log AND
#     deep-research-bench.service inactive. The service inactive at two looks 2 min apart WITHOUT that line = the queue
#     stopped early: critical alert, exit 1 (no gap runs). A kernel check (kcheck p5-finished): a failure = critical
#     alert, exit 3. Then ONE non-urgent ntfy (ntfy-note.py): runs completed / not completed / flagged, of the plan.
#   2 waits for post7d-retry.service (Karl 11-05 D8, one retry of each failed replay after Phase 5) to end, so no replay
#     runs beside a gap; a critical alert if it is still active after 3 h (the wait goes on).
#   3 STEPS in order, each only after Claude's review ("$f.ready" + bash -n; waited for up to 6 h, else skipped with a
#     critical alert). Each runs as a snapshot copy (results/r23/run-copies/) with 8>&- 9>&-. No step starts during a
#     DeepSeek session (waits for Back to Qwen). The gap opening itself (work/r22/port_gap4.sh begin) waits for an active
#     Jan job, a chat being answered on 8080 (Jan, DS Harness or any client), a DeepSeek session and Karl's quiet window
#     (Pause research). Beside each step: the weekend watcher's 2-h rule - a critical alert once if tmp/gap-waiting-jan
#     is older than 2 h (the gap still waits; nothing is cancelled).
#     Exit codes of the drivers: 0 done -> next. 1 = refused before its gap opened (8080 untouched) -> ONE retry 15 min
#     later, then skipped with a critical alert; exit 1 with the gap still OPEN (tmp/port-gap.lockpid) = a crash after
#     begin -> critical alert, the chain STOPS. 3 (kernel check, gap left OPEN) / 4 (P028x not back) -> critical alert,
#     STOP. Any other exit -> critical alert; the chain goes on only if the state is clean (no test-lock holder, no hold
#     file, 8080 answering with the P028x engine), else STOPS.
#   4 the mismatch guard: install-model-guard.sh --check, then install (it refuses by itself unless Phase 5 is done and
#     no gap, hold or DeepSeek session is left; restarts nothing). Not run if the chain stopped. A refusal or failure =
#     critical alert.
# Alerts: notify-send -a "Gap series" -u critical (alert-push.py forwards them to ntfy, path-free) + a NOTES.md line.
# Log: results/r23/post-p5-chain.log. Exit 0 done (steps may have been skipped: see the log), 1 / 3 stopped.
# Test overrides (sandbox test work/r23/test_post_p5_chain.sh only; unset in the real run): PC_SC, PC_DR, PC_STEPS,
# PC_NOTE, PC_GUARD, PC_KCHECK, PC_BENCH_UNIT, PC_RETRY_UNIT, PC_POLL_S, PC_RETRY_S, PC_READY_N, PC_JAN_S, PC_TEST_HOOK
# (sourced last: may redefine notify / engine_sha / ds_session).
set -u
SC=${PC_SC:-/home/USER/ai-speed-testing/strata-compare}; DR=${PC_DR:-/home/USER/ai/deep-research}; Q=$DR/logs/bench2-queue.log
L=$SC/results/r23/post-p5-chain.log; mkdir -p $SC/results/r23/run-copies
PLAN=queue-plan-p5-holdout.json; FIN="queue finished ($PLAN)"
read -r -a STEPS <<< "${PC_STEPS:-work/r23/gap-confirm0211.sh work/r23/gap-basalt-speed.sh work/ds41/gate/gap-d1.sh work/ds41/gate/gap-d2.sh}"
NOTE=${PC_NOTE:-$SC/configs/usability/bin/ntfy-note.py}; GUARD=${PC_GUARD:-$SC/work/ds-launcher/model-guard/install-model-guard.sh}
KCHECK=${PC_KCHECK:-$SC/bringup/lib/kcheck.sh}; BENCH_UNIT=${PC_BENCH_UNIT:-deep-research-bench}; RETRY_UNIT=${PC_RETRY_UNIT:-post7d-retry}
POLL=${PC_POLL_S:-60}; RETRY_S=${PC_RETRY_S:-900}; READY_N=${PC_READY_N:-360}; JAN_S=${PC_JAN_S:-7200}
LOCKPID=$SC/tmp/port-gap.lockpid; HOLDF=$DR/tmp/bench2.hold; JANW=$SC/tmp/gap-waiting-jan
P028X_SHA=f4c4f654fb24
say() { echo "$(date '+%F %T') post-p5-chain: $*" >> $L; }
note() { echo "- $(date '+%m-%d %H:%M') POST-P5 CHAIN: $*" >> $SC/NOTES.md; }
notify() { notify-send -a "Gap series" -u critical "$1" "$2" 2> /dev/null; }
alert() { say "ALERT: $1 - $2"; note "$1: $2"; notify "$1" "$2" || say "notify-send failed"; }
ds_session() { grep -qsF "boot $(cat /proc/sys/kernel/random/boot_id)" $SC/tmp/ds-session; }
bench_active() { systemctl --user is-active -q $BENCH_UNIT.service; }
engine_sha() { local lp pid
  lp=$(ss -ltnpH 'sport = :8080' 2> /dev/null | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2)
  [ -n "$lp" ] && pid=$(pgrep -P "$lp" -x "strata|strata-host" | head -1) && [ -n "$pid" ] && sha256sum /proc/$pid/exe | cut -c1-12; }
clean_state() { ! [ -s $LOCKPID ] && ! [ -e $HOLDF ] && [ "$(engine_sha)" = $P028X_SHA ]; }
janwatch() {   # janwatch FLAG: while FLAG exists, the 2-h rule on tmp/gap-waiting-jan (one alert per marker)
  local told="" t s
  while [ -e $1 ]; do
    if [ -s $JANW ]; then t=$(head -c 19 $JANW); s=$(date -d "$t" +%s 2> /dev/null || echo 0)
      if [ "$t" != "$told" ] && [ $s -gt 0 ] && [ $(( $(date +%s) - s )) -ge $JAN_S ]; then told=$t
        alert "Gap waiting for a chat" "a measurement gap has waited more than 2 h (since $t) for an active Jan job or a chat on 8080 - it starts by itself when that ends; Karl decides whether to wait"; fi
    fi
    sleep $POLL
  done; }
[ -n "${PC_TEST_HOOK:-}" ] && source "$PC_TEST_HOOK"

say "start (pid $$): steps ${STEPS[*]}; then the mismatch guard"
# ---------------------------------------------------------------- 1 Phase 5's queue
off=0; h=0
while :; do
  if grep -qF "$FIN" $Q && ! bench_active; then break; fi
  if ! bench_active && ! grep -qF "$FIN" $Q; then
    off=$((off + 1)); [ $off -ge 3 ] && { alert "Phase 5 queue stopped early" "the research queue is not running but Phase 5's plan has not finished - no gap started; Karl decides"; exit 1; }
  else off=0; fi
  sleep $POLL; h=$((h + 1)); [ $((h % 60)) = 0 ] && say "still waiting for Phase 5's queue ($((h / 60)) h)"
done
say "Phase 5's queue finished: $(grep -F "$FIN" $Q | tail -1 | cut -c1-19)"
if ! $KCHECK p5-finished > /dev/null 8>&- 9>&-; then
  alert "Kernel check failed" "the kernel check after Phase 5's queue failed - no gap started; Karl decides"; exit 3; fi
counts=$($DR/.venv/bin/python -I - "$DR" "$PLAN" <<'PY' 2>> $L
import importlib.util, json, sys
from pathlib import Path
DR = Path(sys.argv[1]); R = DR / "results/bench2/runs"
plan = json.loads((DR / "results/bench2" / sys.argv[2]).read_text())
spec = importlib.util.spec_from_file_location("ov", DR / "staging/phase5/overflow.py")
ov = importlib.util.module_from_spec(spec); spec.loader.exec_module(ov)
n = done = flagged = 0
for b in plan:
    for i in b["ids"]:
        n += 1; d = R / f"{b['set']}-{b['profile']}-{b['label']}" / i
        try:
            if json.loads((d / "summary.json").read_text()).get("final_status") == "completed":
                done += 1
            if ov.flags(d, json.loads((d / "bench.json").read_text()))[0]:
                flagged += 1
        except Exception:
            pass
print(f"{done} of {n} runs completed, {n - done} not completed, {flagged} flagged")
PY
)
[ -n "$counts" ] || counts="run counts not available"
say "Phase 5: $counts"
if "$NOTE" "Phase 5 queue finished" "Phase 5's queue finished at $(date +%H:%M): $counts. Next: the four measurement gaps (about 4-5 h), then the guard install." >> $L 2>&1; then
  say "non-urgent ntfy sent"; else say "non-urgent ntfy NOT sent (see alert-push.log)"; note "the non-urgent 'Phase 5 finished' ntfy was not sent"; fi
note "Phase 5's queue finished ($counts); the four gaps start"
# ---------------------------------------------------------------- 2 the replay retry (post7d-retry)
w=0
while systemctl --user is-active -q $RETRY_UNIT.service; do
  [ $w = 0 ] && say "waiting for $RETRY_UNIT.service to end"
  sleep $POLL; w=$((w + 1))
  [ $w = 180 ] && alert "Replay retry still running" "the replay retry after Phase 5 is still running after 3 h - the measurement gaps wait for it"
done
[ $w -gt 0 ] && say "$RETRY_UNIT.service ended after ~$w min"
# ---------------------------------------------------------------- 3 the steps
stopped=0
for s in "${STEPS[@]}"; do
  f=$SC/$s; name=$(basename $s .sh)
  # reviewed = "$f.ready" names the driver's current sha256 (first 12 hex) and bash -n passes: an edit after the review
  # is not run
  ready_ok() { [ -f "$f.ready" ] && bash -n "$f" 2> /dev/null && grep -qE "sha256 $(sha256sum "$f" | cut -c1-12)([^0-9a-f]|$)" "$f.ready"; }
  for i in $(seq $READY_N); do ready_ok && break; sleep $POLL; done
  if ! ready_ok; then
    alert "Gap skipped" "$name was not reviewed (no .ready file naming its current sha256, or bash -n fails) 6 h after it was due - skipped"; continue; fi
  tries=0
  while :; do
    if ds_session; then say "$name: a DeepSeek session holds the GPUs - waiting for Back to Qwen"
      while ds_session; do sleep 30; done; say "$name: the DeepSeek session is over"; fi
    snap=$SC/results/r23/run-copies/$name-$(date +%m%d-%H%M).sh; cp -p "$f" "$snap"
    say "$name: running the snapshot $snap (reviewed: $(head -c 120 "$f.ready" | tr '\n' ' '))"
    flag=$SC/tmp/post-p5-chain.janwatch; touch $flag; janwatch $flag & jw=$!
    bash "$snap" 8>&- 9>&- >> $L 2>&1 < /dev/null; rc=$?
    rm -f $flag; wait $jw 2> /dev/null
    say "$name exit $rc"; tries=$((tries + 1))
    case $rc in
      0) note "$name done (exit 0)"; break ;;
      1) if [ -s $LOCKPID ] && ! ds_session; then
           alert "Gap crashed" "$name exited 1 with its gap still OPEN (8080 down) - a crash after the gap opened; the chain stopped; Karl decides"; stopped=1; break; fi
         if [ $tries -ge 2 ]; then
           alert "Gap skipped" "$name refused twice before opening its gap (8080 untouched) - skipped; the chain goes on"; break; fi
         say "$name refused before opening its gap (exit 1; 8080 untouched) - one retry in 15 min"; note "$name refused (exit 1), one retry in 15 min"
         sleep $RETRY_S ;;
      3) alert "Gap kernel check failed" "$name: a kernel check failed and its gap is left OPEN (8080 down); the chain stopped; Karl decides"; stopped=1; break ;;
      4) alert "Served model not back" "$name: P028x did not come back on 8080 after the gap; the chain stopped; Karl decides"; stopped=1; break ;;
      *) if clean_state; then
           alert "Gap failed" "$name did not complete (exit $rc); the gap is closed and P028x serves - the chain goes on"; break
         else
           alert "Gap failed" "$name did not complete (exit $rc) and the state is not clean (test lock, hold or 8080) - the chain stopped; Karl decides"; stopped=1; break
         fi ;;
    esac
  done
  [ $stopped = 1 ] && break
done
if [ $stopped = 1 ]; then say "chain stopped - the mismatch guard is NOT installed"; exit 1; fi
# ---------------------------------------------------------------- 4 the mismatch guard
say "the mismatch guard: $(bash $GUARD --check 8>&- 9>&- 2>&1 < /dev/null | tail -1)"
if out=$(bash $GUARD 8>&- 9>&- 2>&1 < /dev/null); then
  echo "$out" >> $L; say "mismatch guard installed"; note "mismatch guard installed (each server picks it up at its next start; nothing restarted)"
else
  echo "$out" >> $L; alert "Guard not installed" "the mismatch guard install refused or failed: $(echo "$out" | tail -1 | cut -c1-120)"
fi
say "chain done"; note "chain done: the four gaps ran (see results/r23/post-p5-chain.log), Claude's desk work follows"
exit 0
