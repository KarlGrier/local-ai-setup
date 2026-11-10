#!/bin/bash
# test_deepseek_session.sh - sandbox tests of configs/usability/bin/deepseek-session.sh + its hooks in port_gap4.sh and
# weekend-watch.sh. Real flock, real files in a sandbox; the steps that touch 8080, memory or the GPU are stubbed through
# DSS_TEST_HOOK. Nothing here stops, starts or holds anything outside the sandbox.
set -u
SC0=/home/USER/ai-speed-testing/strata-compare; DR0=/home/USER/ai/deep-research
S=$SC0/configs/usability/bin/deepseek-session.sh
B=$SC0/work/ds-launcher/scratch/sb; rm -rf "$B"; mkdir -p "$B"
pass=0; fail=0
ok() { if eval "$2"; then pass=$((pass + 1)); echo "ok   $1"; else fail=$((fail + 1)); echo "FAIL $1"; fi; }
new() {   # new CASE: a fresh sandbox + the stub hook
  SB=$B/$1; SC=$SB/SC; DR=$SB/DR; mkdir -p "$SC/tmp" "$SC/logs/run" "$SC/configs" "$DR/tmp" "$DR/run" "$DR/logs" "$SB/bin"
  : > "$DR/run/bench.lock"; : > "$SC/tmp/gpu-test.lock"; : > "$DR/NOTES.md"; : > "$DR/logs/bench2-queue.log"; : > "$SB/calls"
  printf '#!/bin/bash\necho "notify $*" >> %s/calls\n' "$SB" > "$SB/bin/notify-send"
  printf '#!/bin/bash\ncase "$*" in *is-active*) [ -e %s/units-up ] && exit 0; exit 3;; esac; exit 0\n' "$SB" > "$SB/bin/systemctl"
  chmod +x "$SB/bin/"*
  cat > "$SB/hook.sh" <<EOF
memav_mib() { cat $SB/mem 2> /dev/null || echo 90000; }
need_mib() { echo 81305; }
engines_left() { echo; }
old_server_gone() { return 0; }
jan_active() { [ -e $SB/jan ]; }
chat_busy() { [ -e $SB/chat ]; }
model_8080() { cat $SB/model 2> /dev/null; }
take_lock() { echo "take_lock" >> $SB/calls; setsid bash -c "exec flock -s '\$TESTLOCK' bash -c 'echo \\\$\\\$ > \"\$LP\"; exec sleep infinity'" < /dev/null > /dev/null 2>&1 7>&- & for i in 1 2 3 4 5 6 7 8 9 10; do [ -s "\$LP" ] && return 0; sleep 0.2; done; return 1; }
stop_8080() { echo "stop_8080 model=\$(model_8080) lp=\$(cat "\$LP" 2> /dev/null) hold=\$([ -e "\$HOLD" ] && echo yes || echo no)" >> $SB/calls; rm -f $SB/model; }
start_ds() { echo "start_ds" >> $SB/calls; [ -e $SB/ds-slow ] && sleep 1.5; [ -e $SB/ds-fails ] && return 1; echo deepseek-v4.1-flash > $SB/model; }
health_ds() { [ -e $SB/health-fails ] && { echo "bad health"; return 1; }; echo "ok: stub"; }
placement_ds() { echo "placement_ds" >> $SB/calls; [ -e $SB/placement-fails ] && { echo "bad placement"; return 1; }; echo "ok: stub"; }
start_guard() { echo "start_guard" >> $SB/calls; }
start_qwen() { echo "gap_end lp=\$(cat "\$LP" 2> /dev/null) lockfree=\$(flock -n -x "\$TESTLOCK" true && echo yes || echo no)" >> $SB/calls; [ -e $SB/end-fails ] && return 1; echo strata-qwen3.8-flash-next-iq3s > $SB/model; }
check_qwen() { [ -e $SB/qwen-check-fails ] && { echo "wrong engine"; return 1; }; echo "ok: stub"; }
is_qwen_8080() { grep -qs qwen $SB/model; }
real_check() { [ -e $SB/check-bad ] && echo " not-executable:x"; return 0; }
promoted_cfg() { echo /nonexistent; }
arm_held_alert() { echo "arm_held_alert" >> $SB/calls; }
pause_end() { :; }
DSS_MEM_LOOK_S=0.05
EOF
  echo strata-qwen3.8-flash-next-iq3s > "$SB/model"
}
run() { PATH=$SB/bin:$PATH DSS_SC=$SC DSS_DR=$DR DSS_TEST_HOOK=$SB/hook.sh DSS_POLL_S=0.2 DSS_LOOK_S=0.3 DSS_MEM_WAIT_S=1 DSS_MEM_BACK_S=1 DSS_ENGINE_WAIT_S=1 bash "$S" "$@" > /dev/null 2>&1 < /dev/null; }
order() { grep -nE "$1" "$SB/calls" | head -1 | cut -d: -f1; }

# T1 nothing running: hold -> lock -> stop -> start -> health -> guard; DeepSeek stays up, hold stays, DS Harness is not involved
new t1; run to-deepseek; rc=$?
ok "T1 rc 0, says it is up" '[ $rc = 0 ] && grep -q "DeepSeek is up on" "$SC/logs/run/deepseek-session.log" && grep -q "start_guard" "$SB/calls"'
ok "T1 the order: lock, stop, start, guard" '[ $(order take_lock) -lt $(order stop_8080) ] && [ $(order stop_8080) -lt $(order start_ds) ] && [ $(order start_ds) -lt $(order start_guard) ]'
ok "T1 at the stop: the hold is set and the lock taken" 'grep -E "^stop_8080" "$SB/calls" | grep -q "hold=yes" && [ -n "$(grep -E "^stop_8080" "$SB/calls" | sed -E "s/.*lp=([0-9]*).*/\1/")" ]'
ok "T1 the hold starts with phase 4 gap: (boot-resume rule) and names DeepSeek" '[ "$(head -c 13 "$DR/tmp/bench2.hold")" = "phase 4 gap: " ] && grep -q "DeepSeek session" "$DR/tmp/bench2.hold"'
ok "T1 the launcher ended: DeepSeek still up, hold + marker stay" '[ "$(cat "$SB/model")" = deepseek-v4.1-flash ] && [ -e "$DR/tmp/bench2.hold" ] && grep -q "state up" "$SC/tmp/ds-session"'
ok "T1 it never starts DS Harness, and the hold names the new icon" '! grep -q "Opening DS Harness" "$SC/logs/run/deepseek-session.log" && ! grep -qw dsh "$SB/calls" && grep -q "Switch to DeepSeek" "$DR/tmp/bench2.hold"'
ok "T1 held_since recorded" 'grep -qE "^held_since [0-9]+" "$SC/tmp/ds-session"'
# T1b the launcher again while up: nothing to do, no second switch
n=$(grep -c start_ds "$SB/calls"); run to-deepseek; ok "T1b clicked again while up: no second switch" '[ "$(grep -c start_ds "$SB/calls")" = "$n" ] && grep -q "already up" "$SC/logs/run/deepseek-session.log"'
# T1c Back to Qwen: everything released, in order
run back-to-qwen; rc=$?
ok "T1c back: rc 0, hold + marker + lock gone, Qwen serves" '[ $rc = 0 ] && [ ! -e "$DR/tmp/bench2.hold" ] && [ ! -e "$SC/tmp/ds-session" ] && [ ! -s "$SC/tmp/port-gap.lockpid" ] && grep -q qwen "$SB/model"'
ok "T1c back: DeepSeek stopped before the daily starter" '[ $(grep -n "^stop_8080" "$SB/calls" | tail -1 | cut -d: -f1) -lt $(grep -n "^gap_end" "$SB/calls" | tail -1 | cut -d: -f1) ]'
sleep 0.3; ok "T1c the test lock is free again" 'flock -n -x "$SC/tmp/gpu-test.lock" true'
run back-to-qwen; ok "T1d back again: nothing to do" 'grep -q "No DeepSeek session" "$SC/logs/run/deepseek-session.log"'

# T2 a question is running: waits with the expected wait, never stops before it ends
new t2; echo "2026-11-06 20:00:00 screen / deep / pc3c / o01: running" >> "$DR/logs/bench2-queue.log"; echo "19:00 o03: rc 0, 169 min wall (0 min held)" >> "$DR/logs/bench2-queue.log"; touch "$SB/units-up"
( flock -x 9; sleep 2.5 ) 9> "$DR/run/bench.lock" & Q=$!; sleep 0.3
run to-deepseek & L=$!; sleep 1.5
ok "T2 while the question runs: hold set, 8080 untouched" '[ -e "$DR/tmp/bench2.hold" ] && ! grep -q stop_8080 "$SB/calls"'
ok "T2 the marker says waiting, for this boot, with no held_since yet" 'grep -q "state waiting" "$SC/tmp/ds-session" && grep -qF "boot $(cat /proc/sys/kernel/random/boot_id)" "$SC/tmp/ds-session" && ! grep -q held_since "$SC/tmp/ds-session"'
ok "T2 it shows the expected wait" 'grep -qE "question o01 started at 20:00, budget 171 min" "$SC/logs/run/deepseek-session.log"'
wait $Q; wait $L
ok "T2 after the question: switched" 'grep -q start_guard "$SB/calls"'

# T3 an open gap: never interrupted; the gap's end removes the hold -> the launcher sets it again
new t3; setsid sleep 3 < /dev/null > /dev/null 2>&1 & G=$!; echo $G > "$SC/tmp/port-gap.lockpid"; echo "phase 4 gap: x" > "$DR/tmp/bench2.hold"
run to-deepseek & L=$!; sleep 1
ok "T3 during the gap: no stop, says so" '! grep -q stop_8080 "$SB/calls" && grep -q "measurement gap is open" "$SC/logs/run/deepseek-session.log"'
ok "T3 the launcher took over the hold text" 'grep -q "DeepSeek session" "$DR/tmp/bench2.hold"'
rm -f "$DR/tmp/bench2.hold"; kill $G 2> /dev/null; rm -f "$SC/tmp/port-gap.lockpid"; wait $L
ok "T3 after the gap: the hold was set again, then switched" 'grep -q "DeepSeek session" "$DR/tmp/bench2.hold" && grep -q start_guard "$SB/calls"'

# T4 cancelled while waiting (window closed): nothing switched, hold + marker gone
new t4; touch "$SB/jan"; PATH=$SB/bin:$PATH DSS_SC=$SC DSS_DR=$DR DSS_TEST_HOOK=$SB/hook.sh DSS_POLL_S=0.2 DSS_LOOK_S=0.3 bash "$S" to-deepseek > /dev/null 2>&1 < /dev/null & L=$!; sleep 1
ok "T4 waits for the Jan job" 'grep -q "Jan research job" "$SC/logs/run/deepseek-session.log" && [ -e "$DR/tmp/bench2.hold" ]'
kill -HUP $L; wait $L
ok "T4 HUP: hold + marker gone, nothing switched" '[ ! -e "$DR/tmp/bench2.hold" ] && [ ! -e "$SC/tmp/ds-session" ] && ! grep -q stop_8080 "$SB/calls" && grep -q Cancelled "$SC/logs/run/deepseek-session.log"'

# T5 memory never reached -> says why, goes back to Qwen by itself
new t5; echo 50000 > "$SB/mem"; run to-deepseek; rc=$?
ok "T5 rc 1, no DeepSeek start, back on Qwen, all released" '[ $rc = 1 ] && ! grep -q start_ds "$SB/calls" && grep -q gap_end "$SB/calls" && [ ! -e "$DR/tmp/bench2.hold" ] && [ ! -e "$SC/tmp/ds-session" ] && grep -q "only 48.8 GiB" "$SC/logs/run/deepseek-session.log"'
# T6 DeepSeek fails to start / fails its health check -> the same
new t6; touch "$SB/ds-fails"; run to-deepseek; rc=$?
ok "T6 start fails: rc 1, back on Qwen, released, alert" '[ $rc = 1 ] && grep -q gap_end "$SB/calls" && [ ! -e "$DR/tmp/bench2.hold" ] && grep -q "did not start" "$SB/calls"'
new t6b; touch "$SB/health-fails"; run to-deepseek; rc=$?
ok "T6b health fails: rc 1, back on Qwen, no guard" '[ $rc = 1 ] && grep -q gap_end "$SB/calls" && ! grep -q start_guard "$SB/calls"'
# T6c (11-09, C2 as daily) the drafter's placement check fails -> the same: back on Qwen, released, no guard
new t6c; touch "$SB/placement-fails"; run to-deepseek; rc=$?
ok "T6c placement fails: rc 1, back on Qwen, released, no guard" '[ $rc = 1 ] && grep -q placement_ds "$SB/calls" && grep -q gap_end "$SB/calls" && [ ! -e "$DR/tmp/bench2.hold" ] && ! grep -q start_guard "$SB/calls" && grep -q "placement check failed" "$SC/logs/run/deepseek-session.log"'
new t6d; run to-deepseek; rc=$?
ok "T6d the placement check runs after the health check and before the guard" '[ $rc = 0 ] && [ $(order start_ds) -lt $(order placement_ds) ] && [ $(order placement_ds) -lt $(order start_guard) ]'
# P (11-09) the real placement_ds on real engine logs: D1's C2 start, the daily log's A starts, the rollback config
PB=$B/placement; mkdir -p "$PB/SC/configs"; ln -s $SC0/.venv "$PB/SC/.venv"
C2LOG=$SC0/results/ds41/gate-1109-0938-d1/C2/engine-start.log; ALOG=$SC0/logs/ds41/engine-daily.log
pl() { ( DSS_SC=$PB/SC DSS_SOURCE_ONLY=1; source "$S"; placement_ds "$@" ) > /dev/null 2>&1; }
if [ -s "$C2LOG" ] && [ -s "$SC0/configs/DS41-daily.json.before-c2" ] && grep -q '"on"' "$SC0/configs/DS41-daily.json"; then
  cp "$SC0/configs/DS41-daily.json" "$PB/SC/configs/DS41-daily.json"
  pl "$C2LOG" 0; ok "P1 the C2 daily config + C2's real start lines: ok" '[ $? = 0 ]'
  head -c "$(grep -b -m1 "CUDA0 layers" "$C2LOG" | cut -d: -f1)" "$C2LOG" > "$PB/cut.log"
  pl "$PB/cut.log" 0; ok "P2 the start lines without the placement lines: refused" '[ $? = 1 ]'
  pl "$ALOG" 0; ok "P3 A's real start lines under the C2 config: refused" '[ $? = 1 ]'
  pl "$PB/none.log" 0; ok "P4 no engine log: refused" '[ $? = 1 ]'
  cat "$ALOG" "$C2LOG" > "$PB/a-c2.log"; pl "$PB/a-c2.log" 0; ok "P5 the newest start counts (A, then C2): ok" '[ $? = 0 ]'
  cat "$C2LOG" "$ALOG" > "$PB/c2-a.log"; pl "$PB/c2-a.log" "$(stat -c %s "$C2LOG")"; ok "P6 the offset skips an older C2 start: refused" '[ $? = 1 ]'
  cp "$SC0/configs/DS41-daily.json.before-c2" "$PB/SC/configs/DS41-daily.json"
  pl "$ALOG" 0; ok "P7 the rollback config (A, no drafter): not checked, ok" '[ $? = 0 ]'
else echo "skip P (no C2 daily config, its backup or D1's C2 log)"; fi
# T7 Qwen does not come back: the hold stays, a critical alert
new t7; run to-deepseek; touch "$SB/end-fails"; run back-to-qwen; rc=$?
ok "T7 back fails: rc 1, hold + marker stay, critical alert" '[ $rc = 1 ] && [ -e "$DR/tmp/bench2.hold" ] && [ -e "$SC/tmp/ds-session" ] && grep -E "notify.*critical.*Qwen did not come back" "$SB/calls" > /dev/null'
# T7b Qwen already back with a session left over (the 11-06 22:34 case): nothing stopped, only the leftovers released
new t7b; run to-deepseek; n=$(grep -c "^stop_8080" "$SB/calls"); echo strata-qwen3.8-flash-next-iq3s > "$SB/model"; run back-to-qwen; rc=$?
ok "T7b Qwen already up: not stopped, lock + hold + marker released" '[ $rc = 0 ] && [ "$(grep -c "^stop_8080" "$SB/calls")" = "$n" ] && [ ! -e "$DR/tmp/bench2.hold" ] && [ ! -e "$SC/tmp/ds-session" ] && [ ! -s "$SC/tmp/port-gap.lockpid" ] && grep -q "already serves" "$SC/logs/run/deepseek-session.log"'
sleep 0.3; ok "T7b the test lock is free" 'flock -n -x "$SC/tmp/gpu-test.lock" true'
# T7c the lock is released BEFORE the daily starter (it refuses while a test holds the lock); a retry after a failure works
new t7c; run to-deepseek; touch "$SB/end-fails"; run back-to-qwen; rm -f "$SB/end-fails"
ok "T7c the starter ran with the lock already free" 'grep -E "^gap_end lp= lockfree=yes" "$SB/calls" > /dev/null'
ok "T7c failed: hold + marker kept" '[ -e "$DR/tmp/bench2.hold" ] && [ -e "$SC/tmp/ds-session" ]'
run back-to-qwen; rc=$?; ok "T7c Back again after a failed start: Qwen is checked, hold + marker released" '[ $rc = 0 ] && [ ! -e "$DR/tmp/bench2.hold" ] && [ ! -e "$SC/tmp/ds-session" ]'
# T7d the check after the start fails: the queue stays held
new t7d; run to-deepseek; rm -f "$SB/model"; touch "$SB/qwen-check-fails"; run back-to-qwen; rc=$?
ok "T7d Qwen fails its check: rc 1, the queue stays held, a critical alert" '[ $rc = 1 ] && [ -e "$DR/tmp/bench2.hold" ] && grep -E "notify.*critical.*Qwen did not come back" "$SB/calls" > /dev/null'
# T7e a real script not usable: both launchers refuse before touching anything
new t7e; touch "$SB/check-bad"; run to-deepseek; rc=$?
ok "T7e to-deepseek refuses early: no hold, no marker, no stop" '[ $rc = 1 ] && [ ! -e "$DR/tmp/bench2.hold" ] && [ ! -e "$SC/tmp/ds-session" ] && ! grep -q stop_8080 "$SB/calls"'
rm -f "$SB/check-bad"; run to-deepseek; touch "$SB/check-bad"; n=$(grep -c "^stop_8080" "$SB/calls"); run back-to-qwen; rc=$?
ok "T7e back-to-qwen refuses early: DeepSeek not stopped" '[ $rc = 1 ] && [ "$(grep -c "^stop_8080" "$SB/calls")" = "$n" ] && [ -e "$SC/tmp/ds-session" ]'
# T7f a chat being answered: the switch waits and names any app; it goes on when the chat ends
new t7f; touch "$SB/chat"; run to-deepseek & L=$!; sleep 1
ok "T7f a chat on 8080: the switch waits, Qwen untouched, it names DS Harness" '! grep -q stop_8080 "$SB/calls" && grep -q "chat is being answered on 8080 by Jan, DS Harness" "$SC/logs/run/deepseek-session.log"'
rm -f "$SB/chat"; wait $L; ok "T7f the chat over: switched" 'grep -q start_guard "$SB/calls"'
# T7g Back to Qwen waits for a chat too, and closing its window there changes nothing
new t7g; run to-deepseek; n=$(grep -c "^stop_8080" "$SB/calls"); touch "$SB/chat"; run back-to-qwen & L=$!; sleep 1
ok "T7g a chat on DeepSeek: Back waits, DeepSeek not stopped" '[ "$(grep -c "^stop_8080" "$SB/calls")" = "$n" ] && [ "$(cat "$SB/model")" = deepseek-v4.1-flash ] && grep -q "Close this window to cancel" "$SC/logs/run/deepseek-session.log"'
rm -f "$SB/chat"; wait $L; rc=$?; ok "T7g the chat over: Back goes on, Qwen back, the queue released" '[ $rc = 0 ] && grep -q qwen "$SB/model" && [ ! -e "$DR/tmp/bench2.hold" ] && [ ! -e "$SC/tmp/ds-session" ]'
new t7h; run to-deepseek; n=$(grep -c "^stop_8080" "$SB/calls"); touch "$SB/chat"; PATH=$SB/bin:$PATH DSS_SC=$SC DSS_DR=$DR DSS_TEST_HOOK=$SB/hook.sh DSS_POLL_S=0.2 bash "$S" back-to-qwen > /dev/null 2>&1 < /dev/null & L=$!; sleep 1
kill -HUP $L; wait $L; rc=$?
ok "T7h Back's window closed during that wait: nothing switched, the session stays" '[ $rc = 0 ] && [ "$(grep -c "^stop_8080" "$SB/calls")" = "$n" ] && [ "$(cat "$SB/model")" = deepseek-v4.1-flash ] && [ -e "$DR/tmp/bench2.hold" ] && grep -q "state up" "$SC/tmp/ds-session" && grep -q "Cancelled while waiting" "$SC/logs/run/deepseek-session.log"'
# T7i the window closed in the middle of a switch: it finishes anyway
new t7i; touch "$SB/ds-slow"; PATH=$SB/bin:$PATH DSS_SC=$SC DSS_DR=$DR DSS_TEST_HOOK=$SB/hook.sh DSS_POLL_S=0.2 DSS_LOOK_S=0.3 DSS_MEM_WAIT_S=1 DSS_ENGINE_WAIT_S=1 bash "$S" to-deepseek > /dev/null 2>&1 < /dev/null & L=$!
for i in $(seq 40); do grep -q "^start_ds" "$SB/calls" && break; sleep 0.1; done; kill -HUP $L; sleep 0.1; kill -TERM $L; wait $L; rc=$?
ok "T7i HUP + TERM during the start: the switch completes" '[ $rc = 0 ] && grep -q "state up" "$SC/tmp/ds-session" && grep -q start_guard "$SB/calls"'
# T7j failed windows stay readable, successful ones close: only the failure paths pause
new t7j; cat >> "$SB/hook.sh" <<EOF
pause_end() { echo "pause_end" >> $SB/calls; }
done_end() { echo "done_end" >> $SB/calls; }
EOF
run to-deepseek; ok "T7j switch ok: closes by itself" 'grep -q done_end "$SB/calls" && ! grep -q pause_end "$SB/calls"'
: > "$SB/calls"; run back-to-qwen; ok "T7j back ok: closes by itself" 'grep -q done_end "$SB/calls" && ! grep -q pause_end "$SB/calls"'
run to-deepseek; : > "$SB/calls"; rm -f "$SB/model"; touch "$SB/end-fails"; run back-to-qwen; ok "T7j back failed: stays open" 'grep -q pause_end "$SB/calls" && ! grep -q done_end "$SB/calls"'
# T7k the guard does not keep the switch lock (11-06 23:07: "in the middle of its switch" long after the switch ended)
new t7k; mkdir -p "$SC/.venv/bin"; printf '#!/bin/bash\nif [ "$1" = -I ]; then echo /bin/true; else exec sleep 3; fi\n' > "$SC/.venv/bin/python"; chmod +x "$SC/.venv/bin/python"; echo '{}' > "$SC/configs/DS41-daily.json"
( export DSS_SC=$SC DSS_DR=$DR DSS_SOURCE_ONLY=1; source "$S"; set +e; exec 7> "$SC/tmp/l"; flock -n 7; start_guard; exec 7>&-; sleep 0.4; flock -n "$SC/tmp/l" true )
ok "T7k the lock is free while the guard runs" '[ $? = 0 ]'
# T8 a marker from another boot counts for nothing
new t8; printf 'boot not-this-boot\npid 1\nstate up\nrequested 1\nheld_since 1\n' > "$SC/tmp/ds-session"; run back-to-qwen
ok "T8 stale marker: nothing to do, removed" 'grep -q "No DeepSeek session" "$SC/logs/run/deepseek-session.log" && [ ! -e "$SC/tmp/ds-session" ]'
# T9 a second launcher while one waits; Back to Qwen cancels a waiting launcher
new t9; touch "$SB/jan"; PATH=$SB/bin:$PATH DSS_SC=$SC DSS_DR=$DR DSS_TEST_HOOK=$SB/hook.sh DSS_POLL_S=0.2 DSS_LOOK_S=0.3 bash "$S" to-deepseek > "$SB/out1.txt" 2>&1 < /dev/null & L=$!; sleep 1
run to-deepseek; rc=$?; ok "T9 a second launcher refuses" '[ $rc = 1 ] && grep -q "in progress" "$SC/logs/run/deepseek-session.log"'
run back-to-qwen; rc=$?; wait $L
ok "T9b Back to Qwen cancels the waiting one: nothing switched, released" '[ $rc = 0 ] && grep -q "still waiting: cancelling" "$SC/logs/run/deepseek-session.log" && [ ! -e "$DR/tmp/bench2.hold" ] && [ ! -e "$SC/tmp/ds-session" ] && ! grep -q stop_8080 "$SB/calls"'
# T10 the 4-h alert (the one-shot's path)
new t10; printf 'boot %s\npid 1\nstate up\nrequested 1\nheld_since %s\n' "$(cat /proc/sys/kernel/random/boot_id)" "$(( $(date +%s) - 14500 ))" > "$SC/tmp/ds-session"; run alert-if-held
ok "T10 over 4 h: a critical alert" 'grep -E "notify.*Weekend watch.*critical.*4 h" "$SB/calls" > /dev/null'
new t10b; printf 'boot %s\npid 1\nstate up\nrequested 1\nheld_since %s\n' "$(cat /proc/sys/kernel/random/boot_id)" "$(( $(date +%s) - 100 ))" > "$SC/tmp/ds-session"; run alert-if-held
ok "T10b under 4 h: no alert" '! grep -q notify "$SB/calls"'

# ---- port_gap4.sh begin against a session (sandbox copy; no lock holder, no 8080)
new g1; P=$SB/port_gap4.sh
sed -e "s#^SC=/home/USER/ai-speed-testing/strata-compare#SC=$SC#" -e "s#^DR=/home/USER/ai/deep-research#DR=$DR#" -e 's/sleep 45/sleep 0.2/; s/sleep 30; done/sleep 0.2; done/g; s/sleep 60; done/sleep 0.2; done/g' -e 's#(cd "$SC" \&\& STRATA_PORT=8080 ./run-strata.sh stop) || true#echo stopped-8080 >> '"$SB"'/calls#' "$SC0/work/r22/port_gap4.sh" > "$P"
grep -q 'stopped-8080' "$P" || echo "SANDBOX SED FAILED"
sed -i "s#jan_active() { /usr/bin/python3.*#jan_active() { return 1; }#" "$P"
sed -i 's#^  setsid bash -c "exec flock -s.*#  echo $$ > "$LOCKPID"#' "$P"
printf 'boot %s\npid 1\nstate up\nrequested 1\n' "$(cat /proc/sys/kernel/random/boot_id)" > "$SC/tmp/ds-session"; echo "phase 4 gap: DeepSeek session test" > "$DR/tmp/bench2.hold"
PATH=$SB/bin:$PATH bash "$P" begin "test gap" > "$SB/gap.txt" 2>&1 & GP=$!; sleep 1
ok "G1 a gap during a session: waits, the session's hold untouched, no lock, no stop" 'kill -0 $GP 2> /dev/null && grep -q "DeepSeek session test" "$DR/tmp/bench2.hold" && [ ! -s "$SC/tmp/port-gap.lockpid" ] && ! grep -q stopped-8080 "$SB/calls" && grep -q "DeepSeek session holds" "$SB/gap.txt"'
rm -f "$SC/tmp/ds-session" "$DR/tmp/bench2.hold"; sleep 1.5
ok "G1 session over: the gap sets its own hold and opens" 'grep -q "test gap" "$DR/tmp/bench2.hold" && grep -q stopped-8080 "$SB/calls"'
wait $GP; ok "G1 begin finished rc 0" '[ $? = 0 ]'
# G2 a session asks while the gap waits for its question
new g2; P=$SB/port_gap4.sh; sed -e "s#^SC=/home/USER/ai-speed-testing/strata-compare#SC=$SC#" -e "s#^DR=/home/USER/ai/deep-research#DR=$DR#" -e 's/sleep 45/sleep 0.2/; s/sleep 20; done/sleep 0.2; done/; s/sleep 30; done/sleep 0.2; done/g; s/sleep 60; done/sleep 0.2; done/g' -e 's#(cd "$SC" \&\& STRATA_PORT=8080 ./run-strata.sh stop) || true#echo stopped-8080 >> '"$SB"'/calls#' "$SC0/work/r22/port_gap4.sh" > "$P"
sed -i "s#jan_active() { /usr/bin/python3.*#jan_active() { return 1; }#; s#^  setsid bash -c \"exec flock -s.*#  echo \$\$ > \"\$LOCKPID\"#" "$P"
( flock -x 9; sleep 1.5 ) 9> "$DR/run/bench.lock" & Q=$!; sleep 0.2
PATH=$SB/bin:$PATH bash "$P" begin "test gap" > "$SB/gap.txt" 2>&1 & GP=$!; sleep 0.5
printf 'boot %s\npid 1\nstate waiting\nrequested 1\n' "$(cat /proc/sys/kernel/random/boot_id)" > "$SC/tmp/ds-session"; echo "phase 4 gap: DeepSeek session test" > "$DR/tmp/bench2.hold"
wait $Q; sleep 1
ok "G2 the gap yields to the session at the boundary: hold kept, not opened" 'kill -0 $GP 2> /dev/null && grep -q "DeepSeek session test" "$DR/tmp/bench2.hold" && ! grep -q stopped-8080 "$SB/calls"'
kill $GP 2> /dev/null; wait $GP 2> /dev/null
# G3 a marker from another boot does not stop a gap
new g3; P=$SB/port_gap4.sh; sed -e "s#^SC=/home/USER/ai-speed-testing/strata-compare#SC=$SC#" -e "s#^DR=/home/USER/ai/deep-research#DR=$DR#" -e 's/sleep 45/sleep 0.2/' -e 's#(cd "$SC" \&\& STRATA_PORT=8080 ./run-strata.sh stop) || true#echo stopped-8080 >> '"$SB"'/calls#' "$SC0/work/r22/port_gap4.sh" > "$P"
sed -i "s#jan_active() { /usr/bin/python3.*#jan_active() { return 1; }#; s#^  setsid bash -c \"exec flock -s.*#  echo \$\$ > \"\$LOCKPID\"#" "$P"
printf 'boot other\npid 1\nstate up\nrequested 1\n' > "$SC/tmp/ds-session"
PATH=$SB/bin:$PATH timeout 5 bash "$P" begin "test gap" > "$SB/gap.txt" 2>&1; ok "G3 stale marker: the gap opens" '[ $? = 0 ] && grep -q stopped-8080 "$SB/calls"'

# G4 a chat being answered (any app, chat-busy.py): the gap waits, sets the 2-h marker, then opens
new g4; P=$SB/port_gap4.sh; sed -e "s#^SC=/home/USER/ai-speed-testing/strata-compare#SC=$SC#" -e "s#^DR=/home/USER/ai/deep-research#DR=$DR#" -e 's/sleep 45/sleep 0.2/; s/sleep 30; done/sleep 0.2; done/g' -e 's#(cd "$SC" \&\& STRATA_PORT=8080 ./run-strata.sh stop) || true#echo stopped-8080 >> '"$SB"'/calls#' "$SC0/work/r22/port_gap4.sh" > "$P"
sed -i "s#jan_active() { /usr/bin/python3.*#jan_active() { return 1; }#; s#^  setsid bash -c \"exec flock -s.*#  echo \$\$ > \"\$LOCKPID\"#" "$P"
mkdir -p "$SC/configs/usability/bin"; printf 'import os, sys\nsys.exit(0 if os.path.exists("%s/chat") else 1)\n' "$SB" > "$SC/configs/usability/bin/chat-busy.py"
touch "$SB/chat"; PATH=$SB/bin:$PATH bash "$P" begin "test gap" > "$SB/gap.txt" 2>&1 & GP=$!; sleep 1.2
ok "G4 a chat on 8080: the gap waits, hold set, no lock, 8080 not stopped, the 2-h marker written" 'kill -0 $GP 2> /dev/null && grep -q "test gap" "$DR/tmp/bench2.hold" && [ ! -s "$SC/tmp/port-gap.lockpid" ] && ! grep -q stopped-8080 "$SB/calls" && grep -q "test gap" "$SC/tmp/gap-waiting-jan" && grep -q "chat is being answered" "$SB/gap.txt"'
rm -f "$SB/chat"; wait $GP; rc=$?
ok "G4 the chat over: the marker gone, the gap opens" '[ $rc = 0 ] && [ ! -e "$SC/tmp/gap-waiting-jan" ] && grep -q stopped-8080 "$SB/calls"'

# ---- the weekend watcher
new w1; W=$DR0/staging/post7d/weekend-watch.sh; printf 'boot %s\npid 1\nstate up\nrequested 1\nheld_since %s\n' "$(cat /proc/sys/kernel/random/boot_id)" "$(( $(date +%s) - 14500 ))" > "$SC/tmp/ds-session"; echo "phase 4 gap: DeepSeek session" > "$DR/tmp/bench2.hold"; echo old > "$DR/logs/bench2-queue.log"; : > "$SB/ww.log"
PATH=$SB/bin:$PATH WW_WS=$DR WW_SC=$SC WW_NOTES=$SB/notes WW_LOG=$SB/ww.log WW_KC=/bin/true WW_POLL_S=0.2 timeout 1.2 bash "$W" > /dev/null 2>&1
ok "W1 over 4 h: one critical alert" '[ "$(grep -c "ALERT (critical) DeepSeek has held" "$SB/ww.log")" = 1 ]'
ok "W1 a session hold with the series down is not called stale" '! grep -q "the gap series is not running" "$SB/ww.log"'
new w2; printf 'boot %s\npid 1\nstate up\nrequested 1\nheld_since %s\n' "$(cat /proc/sys/kernel/random/boot_id)" "$(( $(date +%s) - 3600 ))" > "$SC/tmp/ds-session"; echo old > "$DR/logs/bench2-queue.log"; : > "$SB/ww.log"
PATH=$SB/bin:$PATH WW_WS=$DR WW_SC=$SC WW_NOTES=$SB/notes WW_LOG=$SB/ww.log WW_KC=/bin/true WW_POLL_S=0.2 timeout 0.8 bash "$W" > /dev/null 2>&1
ok "W2 under 4 h: no alert" '! grep -q "DeepSeek has held" "$SB/ww.log"'

echo "passed $pass, failed $fail"; [ $fail = 0 ]
