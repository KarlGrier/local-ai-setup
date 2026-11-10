#!/bin/bash
# test_post_p5_chain.sh - Claude 11-08: the real work/r23/post-p5-chain.sh (executed as a file) against a sandbox:
# PC_SC / PC_DR point at scratch folders with a fake queue log, plan and run summaries; the steps are fake drivers that
# log their own path and exit with scripted codes; ntfy-note, the guard installer and kcheck are fakes; alerts go to a
# file (PC_TEST_HOOK). Units: test-named transient user units (never the real ones). Nothing real is read except
# overflow.py (imported) and its flags file (read-only); nothing real is written.
set -u
S=/home/USER/ai-speed-testing/strata-compare; CH=$S/work/r23/post-p5-chain.sh
B=$S/work/r23/scratch-post-p5/run-$(date +%m%d-%H%M%S); mkdir -p $B
pass=0; fail=0
ok() { if eval "$2"; then pass=$((pass + 1)); echo "ok   $1"; else fail=$((fail + 1)); echo "FAIL $1"; fi; }
FIN="queue finished (queue-plan-p5-holdout.json)"

mk() {   # mk NAME: a fresh sandbox $T; drivers d1..d4 (rc scripted by $T/rc-dN, one line per call; default 0)
  T=$B/$1; local d
  mkdir -p $T/sc/tmp $T/sc/results/r23 $T/sc/work/r23 $T/dr/logs $T/dr/tmp $T/dr/.venv/bin \
           $T/dr/results/bench2/runs/sandbox-baseline-t/x1 $T/dr/results/bench2/runs/sandbox-baseline-t/x2 $T/dr/staging/phase5
  : > $T/sc/NOTES.md; : > $T/order.log; : > $T/notify.log; : > $T/ntfy.log; : > $T/guard.log
  ln -s /usr/bin/python3 $T/dr/.venv/bin/python
  ln -s /home/USER/ai/deep-research/staging/phase5/overflow.py $T/dr/staging/phase5/overflow.py
  echo '[{"set": "sandbox", "profile": "baseline", "label": "t", "ids": ["x1", "x2", "x3"]}]' > $T/dr/results/bench2/queue-plan-p5-holdout.json
  echo '{"final_status": "completed"}' > $T/dr/results/bench2/runs/sandbox-baseline-t/x1/summary.json
  echo '{"final_status": "completed"}' > $T/dr/results/bench2/runs/sandbox-baseline-t/x2/summary.json
  echo '{}' > $T/dr/results/bench2/runs/sandbox-baseline-t/x1/bench.json; echo '{}' > $T/dr/results/bench2/runs/sandbox-baseline-t/x2/bench.json
  echo "2026-11-09 06:40:00 holdout / deep / p5final / o01: running" > $T/dr/logs/bench2-queue.log
  for d in d1 d2 d3 d4; do
    cat > $T/sc/work/r23/$d.sh <<EOF
#!/bin/bash
echo "$d \$0" >> $T/order.log
rc=0; if [ -s $T/rc-$d ]; then rc=\$(head -1 $T/rc-$d); sed -i 1d $T/rc-$d; fi
[ -s $T/act-$d ] && bash $T/act-$d
exit \$rc
EOF
    echo "reviewed by test; sha256 $(sha256sum $T/sc/work/r23/$d.sh | cut -c1-12)" > $T/sc/work/r23/$d.sh.ready
  done
  cat > $T/note.sh <<EOF
#!/bin/bash
echo "NTFY \$1 | \$2" >> $T/ntfy.log
EOF
  cat > $T/guard.sh <<EOF
#!/bin/bash
echo "GUARD \${1:-install}" >> $T/guard.log; [ -s $T/guard-rc ] && exit \$(cat $T/guard-rc); echo installed; exit 0
EOF
  printf '#!/bin/bash\nexit %s\n' "${KC_RC:-0}" > $T/kcheck.sh
  chmod +x $T/note.sh $T/guard.sh $T/kcheck.sh
  cat > $T/hook.sh <<EOF
notify() { echo "\$(date +%T) ALERT \$1 | \$2" >> $T/notify.log; }
engine_sha() { cat $T/sha 2> /dev/null || echo f4c4f654fb24; }
ds_session() { false; }
EOF
}
runc() {   # runc [VAR=VAL ...]: the real chain on the sandbox; rc in $rc
  env PC_SC=$T/sc PC_DR=$T/dr PC_STEPS="work/r23/d1.sh work/r23/d2.sh work/r23/d3.sh work/r23/d4.sh" PC_NOTE=$T/note.sh \
      PC_GUARD=$T/guard.sh PC_KCHECK=$T/kcheck.sh PC_BENCH_UNIT=pc-test-bench-$$ PC_RETRY_UNIT=pc-test-retry-$$ PC_POLL_S=1 \
      PC_RETRY_S=1 PC_READY_N=3 PC_JAN_S=2 PC_TEST_HOOK=$T/hook.sh "$@" /bin/bash "$CH" < /dev/null > $T/out.txt 2>&1
  rc=$?; }
order() { awk '{print $1}' $T/order.log | paste -sd' '; }
LG() { echo $T/sc/results/r23/post-p5-chain.log; }

ok "real chain is a file that passes bash -n" '[ -f "$CH" ] && bash -n "$CH"'

# 1 the normal path: the queue already finished, every driver exits 0
mk happy; echo "2026-11-09 06:41:00 $FIN" >> $T/dr/logs/bench2-queue.log; runc
ok "happy: exit 0" '[ $rc = 0 ]'
ok "happy: d1 d2 d3 d4 in order" '[ "$(order)" = "d1 d2 d3 d4" ]'
ok "happy: drivers ran from snapshot copies" 'grep -c "/results/r23/run-copies/d[1-4]-" $T/order.log | grep -qx 4'
ok "happy: one non-urgent ntfy with the counts" '[ $(wc -l < $T/ntfy.log) = 1 ] && grep -q "NTFY Phase 5 queue finished | .*2 of 3 runs completed, 1 not completed, 0 flagged" $T/ntfy.log'
ok "happy: no alert" '! [ -s $T/notify.log ]'
ok "happy: guard --check then install" '[ "$(paste -sd" " $T/guard.log)" = "GUARD --check GUARD install" ]'
ok "happy: NOTES lines (finished, 4 done, guard, chain done)" '[ $(grep -c "POST-P5 CHAIN" $T/sc/NOTES.md) = 7 ]'

# 2 waits while the queue runs, goes on after the finish line
mk wait; systemd-run --user --quiet --unit=pc-test-bench-$$ sleep 6
( sleep 3; echo "2026-11-09 06:41:00 $FIN" >> $T/dr/logs/bench2-queue.log ) &
t0=$(date +%s); runc; t1=$(date +%s)
ok "wait: waited for the queue unit (>= 5 s)" '[ $((t1 - t0)) -ge 5 ] && [ $rc = 0 ] && [ "$(order)" = "d1 d2 d3 d4" ]'

# 3 the queue stopped without the finish line: alert, no step
mk early; runc
ok "early stop: exit 1, alert, no step, no ntfy" '[ $rc = 1 ] && grep -q "ALERT Phase 5 queue stopped early" $T/notify.log && ! [ -s $T/order.log ] && ! [ -s $T/ntfy.log ]'

# 4 the kernel check after Phase 5 fails
KC_RC=1 mk kfail; echo "2026-11-09 06:41:00 $FIN" >> $T/dr/logs/bench2-queue.log; runc
ok "kcheck fail: exit 3, alert, no step" '[ $rc = 3 ] && grep -q "ALERT Kernel check failed" $T/notify.log && ! [ -s $T/order.log ]'

# 5 one refusal, then done on the retry; 6 two refusals: skipped, the chain goes on
mk retry; echo "2026-11-09 06:41:00 $FIN" >> $T/dr/logs/bench2-queue.log; printf '1\n0\n' > $T/rc-d2; printf '1\n1\n' > $T/rc-d3; runc
ok "retry: d2 twice (ok on retry), d3 twice (skipped), d4 runs" '[ "$(order)" = "d1 d2 d2 d3 d3 d4" ] && [ $rc = 0 ]'
ok "retry: one 'Gap skipped' alert for d3 only" '[ $(grep -c "ALERT Gap skipped" $T/notify.log) = 1 ] && grep -q "d3 refused twice" $T/notify.log'

# 7 exit 1 with the gap still open = a crash: stop, no guard
mk crash; echo "2026-11-09 06:41:00 $FIN" >> $T/dr/logs/bench2-queue.log; echo 1 > $T/rc-d2; echo "echo 12345 > $T/sc/tmp/port-gap.lockpid" > $T/act-d2; runc
ok "crash after begin: exit 1, alert, d3 not run, no guard" '[ $rc = 1 ] && grep -q "ALERT Gap crashed" $T/notify.log && [ "$(order)" = "d1 d2" ] && ! [ -s $T/guard.log ]'

# 8 exit 3 (kernel check, gap open): stop
mk k3; echo "2026-11-09 06:41:00 $FIN" >> $T/dr/logs/bench2-queue.log; echo 3 > $T/rc-d1; runc
ok "exit 3: stop at d1, alert, no guard" '[ $rc = 1 ] && grep -q "ALERT Gap kernel check failed" $T/notify.log && [ "$(order)" = "d1" ] && ! [ -s $T/guard.log ]'

# 9 another exit with a clean state goes on; with a hold file left it stops
mk other; echo "2026-11-09 06:41:00 $FIN" >> $T/dr/logs/bench2-queue.log; echo 2 > $T/rc-d3; runc
ok "exit 2, clean state: alert, d4 still runs, guard installed" '[ $rc = 0 ] && grep -q "ALERT Gap failed | d3 did not complete (exit 2); the gap is closed" $T/notify.log && [ "$(order)" = "d1 d2 d3 d4" ] && grep -q "GUARD install" $T/guard.log'
mk dirty; echo "2026-11-09 06:41:00 $FIN" >> $T/dr/logs/bench2-queue.log; echo 2 > $T/rc-d3; echo "touch $T/dr/tmp/bench2.hold" > $T/act-d3; runc
ok "exit 2, hold left: stop, no guard" '[ $rc = 1 ] && grep -q "state is not clean" $T/notify.log && [ "$(order)" = "d1 d2 d3" ] && ! [ -s $T/guard.log ]'
mk dirtysha; echo "2026-11-09 06:41:00 $FIN" >> $T/dr/logs/bench2-queue.log; echo 2 > $T/rc-d1; echo deadbeef0000 > $T/sha; runc
ok "exit 2, 8080 not P028x: stop" '[ $rc = 1 ] && grep -q "state is not clean" $T/notify.log && [ "$(order)" = "d1" ]'

# 10 a driver never reviewed: waited for, then skipped with an alert; the rest go on
mk noready; echo "2026-11-09 06:41:00 $FIN" >> $T/dr/logs/bench2-queue.log; rm $T/sc/work/r23/d2.sh.ready; runc
ok "no .ready: d2 skipped with an alert, d1 d3 d4 run" '[ "$(order)" = "d1 d3 d4" ] && grep -q "ALERT Gap skipped | d2 was not reviewed" $T/notify.log && [ $rc = 0 ]'

# 10b a driver edited after its review: not run, skipped with an alert
mk edited; echo "2026-11-09 06:41:00 $FIN" >> $T/dr/logs/bench2-queue.log; echo "# edited after review" >> $T/sc/work/r23/d3.sh; runc
ok "edited after review: d3 skipped with an alert, d1 d2 d4 run" '[ "$(order)" = "d1 d2 d4" ] && grep -q "ALERT Gap skipped | d3 was not reviewed" $T/notify.log && [ $rc = 0 ]'

# 11 the 2-h rule on a gap waiting for a chat (2 s in the test): one alert per marker
mk jan; echo "2026-11-09 06:41:00 $FIN" >> $T/dr/logs/bench2-queue.log
echo "echo '$(date -d '3 hours ago' '+%F %T') a test gap' > $T/sc/tmp/gap-waiting-jan; sleep 4; rm -f $T/sc/tmp/gap-waiting-jan" > $T/act-d1; runc
ok "jan wait: exactly one 'waiting for a chat' alert" '[ $(grep -c "ALERT Gap waiting for a chat" $T/notify.log) = 1 ] && [ $rc = 0 ]'

# 12 the replay retry unit still active: the steps wait for it
mk retryunit; echo "2026-11-09 06:41:00 $FIN" >> $T/dr/logs/bench2-queue.log; systemd-run --user --quiet --unit=pc-test-retry-$$ sleep 4
t0=$(date +%s); runc; t1=$(date +%s)
ok "replay retry: steps waited for its unit" '[ $((t1 - t0)) -ge 3 ] && grep -q "waiting for pc-test-retry-$$.service to end" $(LG) && [ "$(order)" = "d1 d2 d3 d4" ]'

# 13 the guard refuses: alert, exit 0
mk guardno; echo "2026-11-09 06:41:00 $FIN" >> $T/dr/logs/bench2-queue.log; echo 1 > $T/guard-rc; runc
ok "guard refusal: alert, exit 0" '[ $rc = 0 ] && grep -q "ALERT Guard not installed" $T/notify.log'

systemctl --user stop pc-test-bench-$$.service pc-test-retry-$$.service 2> /dev/null
echo "== $pass passed, $fail failed (sandbox $B)"
[ $fail = 0 ]
