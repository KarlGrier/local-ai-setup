#!/bin/bash
# test_stop_model.sh - Claude 11-09: sandbox tests of the "Stop model" launcher (configs/usability/bin/deepseek-session.sh
# stop-model / ensure-gate / stopped-reminder / back-to-qwen from the stopped state / to-deepseek from it) and its hooks in
# strata-ensure.sh, port_gap4.sh and weekend-watch.sh. The REAL scripts are executed as files (or sandbox copies with only
# their paths changed); real flock and real files in a sandbox; the steps that touch 8080, the GPUs or memory are stubbed
# through DSS_TEST_HOOK. Nothing here stops, starts or holds anything outside the sandbox.
# STOP_TEST_SCRIPT / STOP_TEST_ENSURE / STOP_TEST_WW choose the files under test (default: the installed ones).
set -u
SC0=/home/USER/ai-speed-testing/strata-compare; DR0=/home/USER/ai/deep-research
S=${STOP_TEST_SCRIPT:-$SC0/configs/usability/bin/deepseek-session.sh}
EN=${STOP_TEST_ENSURE:-$SC0/configs/usability/bin/strata-ensure.sh}
WW=${STOP_TEST_WW:-$DR0/staging/post7d/weekend-watch.sh}
B=$SC0/work/ds-launcher/stop-model/scratch/sb; rm -rf "$B"; mkdir -p "$B"
BOOT=$(cat /proc/sys/kernel/random/boot_id)
pass=0; fail=0
ok() { if eval "$2"; then pass=$((pass + 1)); echo "ok   $1"; else fail=$((fail + 1)); echo "FAIL $1"; fi; }
cleanup_case() { local p; p=$(cat "$SC/tmp/port-gap.lockpid" 2> /dev/null); [ -n "$p" ] && kill "$p" 2> /dev/null; [ -n "${HP:-}" ] && kill "$HP" 2> /dev/null; HP=""; return 0; }
new() {   # new CASE: a fresh sandbox + the stub hook; Qwen up on 8080, 50 GB available before the stop
  [ -n "${SC:-}" ] && cleanup_case
  SB=$B/$1; rm -rf "$SB"; SC=$SB/SC; DR=$SB/DR; mkdir -p "$SC/tmp" "$SC/logs/run" "$SC/configs/usability/bin" "$DR/tmp" "$DR/run" "$DR/logs" "$SB/bin"
  : > "$DR/run/bench.lock"; : > "$SC/tmp/gpu-test.lock"; : > "$DR/NOTES.md"; : > "$DR/logs/bench2-queue.log"; : > "$SB/calls"
  printf '#!/bin/bash\necho "notify $*" >> %s/calls\n' "$SB" > "$SB/bin/notify-send"
  printf '#!/bin/bash\necho "systemctl $*" >> %s/calls\ncase "$*" in *is-active*) [ -e %s/units-up ] && exit 0; exit 3;; esac; exit 0\n' "$SB" "$SB" > "$SB/bin/systemctl"
  printf '#!/bin/bash\ncase "$*" in */health*) grep -qs . %s/model && { echo "{\\"status\\": \\"ok\\", \\"loaded\\": true}"; exit 0; }; exit 7;; esac; exit 7\n' "$SB" > "$SB/bin/curl"
  printf '#!/bin/bash\necho "ntfy $*" >> %s/calls\n' "$SB" > "$SC/configs/usability/bin/ntfy-note.py"
  chmod +x "$SB/bin/"* "$SC/configs/usability/bin/ntfy-note.py"
  cat > "$SB/hook.sh" <<'EOF'
SBX=__SB__
memav_mib() { cat $SBX/mem 2> /dev/null || echo 90000; }
need_mib() { echo 81305; }
engines_left() { cat $SBX/engines 2> /dev/null; }
old_server_gone() { return 0; }
jan_active() { [ -e $SBX/jan ]; }
jan_eta() { echo "a deep Jan research job started at 20:10, budget 180 min: expected to end around 23:10, about 120 min from now"; }
chat_busy() { [ -e $SBX/chat ]; }
model_8080() { cat $SBX/model 2> /dev/null; }
listening_8080() { grep -qs . $SBX/model; }
server_rss_mib() { grep -qs . $SBX/model && echo 40000 || echo 0; }
gpu_mem() { cat $SBX/gpu 2> /dev/null || printf '0, NVIDIA GeForce RTX 4060 Ti, 3, 8188\n1, NVIDIA GeForce RTX 5080, 2, 16303\n'; }
gpu_apps() { cat $SBX/apps 2> /dev/null; }
take_lock() { echo "take_lock" >> $SBX/calls; [ -e $SBX/lock-fails ] && return 1
  setsid bash -c "exec flock -s '$TESTLOCK' bash -c 'echo \$\$ > \"$LP\"; exec sleep infinity'" < /dev/null > /dev/null 2>&1 7>&- &
  local i; for i in $(seq 50); do [ -s "$LP" ] && break; sleep 0.1; done; touch $SBX/lock-ours; [ -s "$LP" ]; }
lock_is_ours() { [ -s "$LP" ] && [ -e $SBX/lock-ours ]; }
stop_8080() { echo "stop_8080 model=$(model_8080) lp=$(cat "$LP" 2> /dev/null) hold=$([ -e "$HOLD" ] && echo yes || echo no)" >> $SBX/calls; rm -f $SBX/model; echo 90000 > $SBX/mem; }
start_ds() { echo "start_ds" >> $SBX/calls; echo deepseek-v4.1-flash > $SBX/model; }
health_ds() { echo "ok: stub"; }
placement_ds() { echo "placement_ds" >> $SBX/calls; echo "ok: stub"; }
start_guard() { echo "start_guard" >> $SBX/calls; }
start_qwen() { echo "start_qwen lockfree=$(flock -n -x "$TESTLOCK" true && echo yes || echo no) state=$(mark_get state)" >> $SBX/calls; [ -e $SBX/qwen-fails ] && return 1; echo strata-qwen3.8-flash-next-iq3s > $SBX/model; }
check_qwen() { echo "ok: stub"; }
is_qwen_8080() { grep -qs qwen $SBX/model; }
real_check() { return 0; }
promoted_cfg() { echo /nonexistent; }
arm_held_alert() { echo "arm_held_alert" >> $SBX/calls; }
arm_reminder() { echo "arm_reminder" >> $SBX/calls; }
pause_end() { :; }
DSS_MEM_LOOK_S=0.05
EOF
  sed -i "s#__SB__#$SB#" "$SB/hook.sh"
  echo strata-qwen3.8-flash-next-iq3s > "$SB/model"; echo 50000 > "$SB/mem"
}
envv() { echo PATH=$SB/bin:$PATH DSS_SC=$SC DSS_DR=$DR DSS_TEST_HOOK=$SB/hook.sh DSS_POLL_S=0.2 DSS_LOOK_S=0.3 DSS_MEM_WAIT_S=1 DSS_MEM_BACK_S=1 DSS_ENGINE_WAIT_S=1 DSS_CLOSE_S=0; }
run() { env $(envv) bash "$S" "$@" > /dev/null 2>&1 < /dev/null; }
L() { cat "$SC/logs/run/deepseek-session.log" 2> /dev/null; }
mark() { sed -n "s/^$1 //p" "$SC/tmp/ds-session" 2> /dev/null | head -1; }
lockfree() { flock -n -x "$SC/tmp/gpu-test.lock" true; }
order() { grep -nE "$1" "$SB/calls" | head -1 | cut -d: -f1; }

# ---- S1 Qwen up, nothing running: hold -> lock -> stop -> the freed check; stopped, reminder armed, no alert
new s1; run stop-model; rc=$?
ok "S1 rc 0, says stopped" '[ $rc = 0 ] && L | grep -q "The model is stopped. Nothing starts a model by itself"'
ok "S1 the order: lock, then stop" '[ -n "$(order take_lock)" ] && [ $(order take_lock) -lt $(order stop_8080) ]'
ok "S1 at the stop the hold is set and the lock taken" 'grep "^stop_8080" "$SB/calls" | grep -q "hold=yes" && [ -n "$(grep "^stop_8080" "$SB/calls" | sed -E "s/.*lp=([0-9]*).*/\1/")" ]'
ok "S1 the hold: phase 4 gap: Model stopped (boot-resume rule), not a DeepSeek text" '[ "$(head -c 13 "$DR/tmp/bench2.hold")" = "phase 4 gap: " ] && grep -q "Model stopped" "$DR/tmp/bench2.hold" && ! grep -q "DeepSeek session" "$DR/tmp/bench2.hold"'
ok "S1 the marker: this boot, state stopped, stopped_since" '[ "$(mark boot)" = "$BOOT" ] && [ "$(mark state)" = stopped ] && [ -n "$(mark stopped_since)" ]'
ok "S1 the lock stays held after the window" '! lockfree'
ok "S1 VRAM both cards freed, RAM shown with what came back" 'L | grep -q "VRAM GPU 0 (NVIDIA GeForce RTX 4060 Ti): 3 of 8188 MiB in use - freed" && L | grep -q "VRAM GPU 1 (NVIDIA GeForce RTX 5080): 2 of 16303 MiB in use - freed" && L | grep -qE "RAM: 87.9 GiB available of [0-9.]+ GiB \(before the stop 48.8 GiB: 39.1 GiB freed\)" && L | grep -q "both cards. VRAM and the RAM are free"'
ok "S1 the 12-h reminder armed; no held alert; no critical notification" 'grep -q "^arm_reminder" "$SB/calls" && ! grep -q arm_held_alert "$SB/calls" && ! grep -q "critical" "$SB/calls"'
ok "S1 a normal notification and NOTES lines" 'grep -q "notify -a Stop model -u normal The model is stopped" "$SB/calls" && [ "$(grep -c "STOP MODEL" "$DR/NOTES.md")" = 2 ]'
# S1b clicked again: already stopped, no second stop
n=$(grep -c "^stop_8080" "$SB/calls"); run stop-model; ok "S1b again: already stopped, nothing stopped twice" '[ "$(grep -c "^stop_8080" "$SB/calls")" = "$n" ] && L | grep -q "already stopped"'
# S1c a gap during the stop waits and leaves the hold alone (port_gap4.sh begin, sandbox copy)
P=$SB/port_gap4.sh
sed -e "s#^SC=/home/USER/ai-speed-testing/strata-compare#SC=$SC#" -e "s#^DR=/home/USER/ai/deep-research#DR=$DR#" -e 's/sleep 45/sleep 0.2/; s/sleep 30; done/sleep 0.2; done/g; s/sleep 60; done/sleep 0.2; done/g' -e 's#(cd "$SC" \&\& STRATA_PORT=8080 ./run-strata.sh stop) || true#echo gap-stopped-8080 >> '"$SB"'/calls#' "$SC0/work/r22/port_gap4.sh" > "$P"
PATH=$SB/bin:$PATH bash "$P" begin "test gap" > "$SB/gap.txt" 2>&1 & GP=$!; sleep 1
ok "S1c a gap while stopped waits, the stop's hold untouched, no stop" 'kill -0 $GP 2> /dev/null && grep -q "Model stopped" "$DR/tmp/bench2.hold" && ! grep -q gap-stopped-8080 "$SB/calls" && grep -q "DeepSeek session holds" "$SB/gap.txt"'
kill $GP 2> /dev/null; wait $GP 2> /dev/null
# S1d the gate: an app other than Jan / DS Harness is refused, nothing changes; the queue's callers too
G=$(env $(envv) bash "$S" ensure-gate OpenCode 2> /dev/null); grc=$?
ok "S1d ensure-gate OpenCode: rc 1, says stopped and Back to Qwen; nothing changed" '[ $grc = 1 ] && echo "$G" | grep -q "the model is stopped" && echo "$G" | grep -q "Back to Qwen" && [ "$(mark state)" = stopped ] && ! lockfree && [ -e "$DR/tmp/bench2.hold" ]'
env $(envv) bash "$S" ensure-gate "Deep research" > /dev/null 2>&1; grc=$?
ok "S1d ensure-gate Deep research (the runner): rc 1" '[ $grc = 1 ] && ! grep -q "^start_qwen" "$SB/calls"'
# S1e the reminder: not yet 12 h -> nothing; 12 h -> one ntfy note
run stopped-reminder; ok "S1e the reminder before 12 h: nothing" '! grep -q "^ntfy" "$SB/calls"'
sed -i "s/^stopped_since .*/stopped_since $(( $(date +%s) - 43300 ))/" "$SC/tmp/ds-session"
run stopped-reminder; ok "S1e the reminder after 12 h: one gentle ntfy note, no notify-send alert" '[ "$(grep -c "^ntfy The model is still stopped" "$SB/calls")" = 1 ] && ! grep -q critical "$SB/calls"'
# S1f the weekend watcher: a stop held for 5 h gives no 4-h alert and is not a stale hold
sed -i "s/^held_since .*/held_since $(( $(date +%s) - 18000 ))/" "$SC/tmp/ds-session"; echo old > "$DR/logs/bench2-queue.log"; : > "$SB/ww.log"
PATH=$SB/bin:$PATH WW_WS=$DR WW_SC=$SC WW_NOTES=$SB/notes WW_LOG=$SB/ww.log WW_KC=/bin/true WW_POLL_S=0.2 timeout 1.2 bash "$WW" > /dev/null 2>&1
ok "S1f weekend watch: no DeepSeek 4-h alert for a stop, not a stale hold" '! grep -q "DeepSeek has held" "$SB/ww.log" && ! grep -q "the gap series is not running" "$SB/ww.log"'
# S1g Back to Qwen from the stopped state: nothing to stop, P028x started, lock + hold + marker + reminder released
run back-to-qwen; rc=$?
ok "S1g back: rc 0, Qwen serves, nothing stopped first" '[ $rc = 0 ] && grep -q qwen "$SB/model" && [ "$(grep -c "^stop_8080" "$SB/calls")" = "$n" ] && L | grep -q "Nothing is running on 8080 (the model was stopped)"'
ok "S1g back: the start ran with the lock free and the state back (the gate lets it through)" 'grep "^start_qwen" "$SB/calls" | tail -1 | grep -q "lockfree=yes state=back"'
sleep 0.3; ok "S1g back: lock, hold, marker released, the reminder stopped" 'lockfree && [ ! -e "$DR/tmp/bench2.hold" ] && [ ! -e "$SC/tmp/ds-session" ] && grep -q "systemctl --user stop model-stopped-reminder.timer" "$SB/calls"'
ok "S1g back: a NOTES line names the stop's end" 'grep -q "STOP MODEL ended: P028x back on 8080, the test lock and the queue released" "$DR/NOTES.md"'

# ---- S2 a chat being answered: it waits; closing the window (HUP) cancels: nothing stopped, hold + marker gone
new s2; touch "$SB/chat"
env $(envv) bash "$S" stop-model > /dev/null 2>&1 < /dev/null & SP=$!; sleep 1.2
ok "S2 waits for the chat, says how to cancel; the hold is set meanwhile" 'kill -0 $SP && L | grep -q "Waiting: a chat is being answered" && L | grep -q "Close this window while it waits to cancel" && grep -q "Model stopped" "$DR/tmp/bench2.hold" && [ "$(mark state)" = stop-waiting ]'
kill -HUP $SP; wait $SP 2> /dev/null
ok "S2 closed while waiting: nothing stopped, the hold and the marker released, the lock never taken" '! grep -q "^stop_8080" "$SB/calls" && ! grep -q take_lock "$SB/calls" && [ ! -e "$DR/tmp/bench2.hold" ] && [ ! -e "$SC/tmp/ds-session" ] && grep -q qwen "$SB/model" && L | grep -q "Cancelled while waiting"'

# ---- S3 a Jan job: the expected wait is shown; when it ends the stop goes on
new s3; touch "$SB/jan"
env $(envv) bash "$S" stop-model > /dev/null 2>&1 < /dev/null & SP=$!; sleep 1
ok "S3 waits for the Jan job with its expected end" 'kill -0 $SP && L | grep -q "Waiting: a deep Jan research job started at 20:10, budget 180 min: expected to end around 23:10" && ! grep -q "^stop_8080" "$SB/calls"'
rm -f "$SB/jan"; wait $SP; rc=$?
ok "S3 the job ended: stopped" '[ $rc = 0 ] && [ "$(mark state)" = stopped ] && grep -q "^stop_8080" "$SB/calls"'
# S3b a research question (bench.lock held): its expected end is shown
new s3b; echo "$(date '+%F %T') queue: c / p5 / c01: running" > "$DR/logs/bench2-queue.log"; touch "$SB/units-up"
setsid flock "$DR/run/bench.lock" sleep 30 < /dev/null > /dev/null 2>&1 & HP=$!; sleep 0.3
env $(envv) bash "$S" stop-model > /dev/null 2>&1 < /dev/null & SP=$!; sleep 1
ok "S3b waits for a running research question, shows when it should end" 'kill -0 $SP && L | grep -qE "Waiting: research question c01 started at [0-9:]+, budget 47 min: expected to end around" && ! grep -q take_lock "$SB/calls"'
kill $SP 2> /dev/null; wait $SP 2> /dev/null; pkill -P $HP 2> /dev/null; kill $HP 2> /dev/null; HP=""

# ---- S4 a measurement gap is open (a lock holder that is not this launcher's): refused, nothing touched
new s4; setsid bash -c "exec flock -s '$SC/tmp/gpu-test.lock' bash -c 'echo \$\$ > \"$SC/tmp/port-gap.lockpid\"; exec sleep infinity'" < /dev/null > /dev/null 2>&1 & sleep 0.5
run stop-model; rc=$?
ok "S4 a gap open: rc 1, says refused while a gap is open; nothing written or stopped" '[ $rc = 1 ] && L | grep -q "Not stopping: a measurement gap is open since" && [ ! -e "$DR/tmp/bench2.hold" ] && [ ! -e "$SC/tmp/ds-session" ] && ! grep -q "^stop_8080" "$SB/calls"'
env $(envv) bash "$S" stop-model --dry-run > "$SB/dry.txt" 2>&1
ok "S4 the dry run says REFUSE" 'grep -q "REFUSE: a measurement gap is open" "$SB/dry.txt"'

# ---- S5 VRAM not freed: stopped (the lock and hold stay), the check says so, rc 1, a normal notification
new s5; printf '0, NVIDIA GeForce RTX 4060 Ti, 3, 8188\n1, NVIDIA GeForce RTX 5080, 3100, 16303\n' > "$SB/gpu"
run stop-model; rc=$?
ok "S5 VRAM left on the 5080: rc 1, NOT freed named, still stopped" '[ $rc = 1 ] && L | grep -q "VRAM GPU 1 (NVIDIA GeForce RTX 5080): 3100 of 16303 MiB in use - NOT freed" && L | grep -q "Check NOT passed" && [ "$(mark state)" = stopped ] && ! lockfree'
ok "S5 the notification is normal, not critical" 'grep -q "notify -a Stop model -u normal The model stopped, but not everything was freed" "$SB/calls" && ! grep -q critical "$SB/calls"'
# S5b an engine left: named
new s5b; echo strata-host > "$SB/engines"; run stop-model; rc=$?
ok "S5b an engine still running: rc 1, named" '[ $rc = 1 ] && L | grep -q "engine processes still running: strata-host"'

# ---- S6 from a DeepSeek session (up): its lock and hold kept, no question wait, DeepSeek stopped, the 4-h alert stopped
new s6; echo deepseek-v4.1-flash > "$SB/model"
env $(envv) DSS_SOURCE_ONLY=1 bash -c 'source "$1"; source "$DSS_TEST_HOOK"; REQ=$(now); HELD=$(now); take_lock; mark_write up; hold_set' _ "$S" > /dev/null 2>&1
touch "$SB/jan"; : > "$SB/calls"   # (a Jan job could not run during a session; it must not be waited for here)
run stop-model; rc=$?
ok "S6 from a session: rc 0, DeepSeek stopped, no new lock, no question wait" '[ $rc = 0 ] && grep "^stop_8080" "$SB/calls" | grep -q "model=deepseek" && ! grep -q take_lock "$SB/calls" && ! L | grep -q "Waiting: a deep Jan"'
ok "S6 the hold now says Model stopped; state stopped; the 4-h alert timer stopped" 'grep -q "Model stopped" "$DR/tmp/bench2.hold" && [ "$(mark state)" = stopped ] && grep -q "systemctl --user stop ds-hold-alert.timer" "$SB/calls"'

# ---- S7 opening Jan while stopped: the FULL Back to Qwen path (Karl 11-09) - Qwen up, checked, lock + hold released
new s7; run stop-model; rm -f "$SB/jan"
G=$(env $(envv) bash "$S" ensure-gate Jan 2> /dev/null); grc=$?
sleep 0.3
ok "S7 ensure-gate Jan: rc 10, Qwen started" '[ $grc = 10 ] && grep -q qwen "$SB/model" && grep -q "^start_qwen lockfree=yes state=back" "$SB/calls"'
ok "S7 Jan: the test lock and the research hold released, the marker gone (Jan jobs will not wait)" 'lockfree && [ ! -e "$DR/tmp/bench2.hold" ] && [ ! -e "$SC/tmp/ds-session" ]'
ok "S7 Jan: NOTES says the stop ended by opening Jan; a Starting Qwen notification" 'grep -q "STOP MODEL ended (opening Jan)" "$DR/NOTES.md" && grep -q "notify -a Stop model -u normal Starting Qwen" "$SB/calls"'
for app in "DS Harness" "DeepSeek Harness"; do
  new "s7h-${app// /_}"; run stop-model
  env $(envv) bash "$S" ensure-gate "$app" > /dev/null 2>&1; grc=$?; sleep 0.3
  ok "S7 ensure-gate $app: rc 10, the full path (lock + hold + marker released)" '[ $grc = 10 ] && grep -q qwen "$SB/model" && lockfree && [ ! -e "$DR/tmp/bench2.hold" ] && [ ! -e "$SC/tmp/ds-session" ]'
done
# S7b Qwen does not come back: refused (rc 1), the stop stays (nothing restarts by itself)
new s7b; run stop-model; touch "$SB/qwen-fails"
env $(envv) bash "$S" ensure-gate Jan > /dev/null 2>&1; grc=$?
ok "S7b Qwen fails to start for Jan: rc 1, the state back to stopped, the hold kept" '[ $grc = 1 ] && [ "$(mark state)" = stopped ] && [ -e "$DR/tmp/bench2.hold" ]'
# S7c strata-ensure.sh itself (a sandbox copy: only WS changed; its gate = the script under test)
new s7c; run stop-model; E=$SB/strata-ensure.sh; sed -e "s#^WS=/home/USER/ai-speed-testing/strata-compare\$#WS=$SC#" "$EN" > "$E"
grep -q "^WS=$SC\$" "$E" || echo "SANDBOX SED FAILED (strata-ensure)"
env $(envv) STRATA_ENSURE_DSS="$S" bash "$E" OpenCode > /dev/null 2>&1; erc=$?
ok "S7c strata-ensure for OpenCode while stopped: exit 1, a 'model is stopped' note, nothing started" '[ $erc = 1 ] && grep -q "notify .*The model is stopped" "$SB/calls" && ! grep -q "^start_qwen" "$SB/calls" && [ "$(mark state)" = stopped ]'
env $(envv) STRATA_ENSURE_DSS="$S" bash "$E" Jan > /dev/null 2>&1; erc=$?; sleep 0.3
ok "S7c strata-ensure for Jan while stopped: exit 0 (Qwen ready), lock + hold released" '[ $erc = 0 ] && grep -q qwen "$SB/model" && lockfree && [ ! -e "$DR/tmp/bench2.hold" ] && [ ! -e "$SC/tmp/ds-session" ] && grep -q "brought Qwen back" "$SC/logs/run/strata-ensure.log"'
env $(envv) bash "$S" ensure-gate OpenCode > /dev/null 2>&1; grc=$?
ok "S7c after that the gate lets everyone through again (rc 0)" '[ $grc = 0 ]'
# S7d a failing or missing gate never blocks a start: only rc 1 refuses, rc 10 is checked, no catch-all branch
new s7d; sed -n "/ensure-gate/,/^fi/p" "$EN" > "$SB/gate.txt"
ok "S7d strata-ensure's gate: 10) and 1) branches only, no *) catch-all" 'grep -q "^    10) " "$SB/gate.txt" && grep -q "^    1) " "$SB/gate.txt" && ! grep -qE "^    [*][)] " "$SB/gate.txt"'

# ---- S8 the gate while the stop is mid-way (stopping): refused, says open it again
new s8; printf 'boot %s\npid 1\nstate stopping\nrequested 1\n' "$BOOT" > "$SC/tmp/ds-session"
G=$(env $(envv) bash "$S" ensure-gate Jan 2> /dev/null); grc=$?
ok "S8 Jan while the stop is mid-way: rc 1, 'being stopped right now'" '[ $grc = 1 ] && echo "$G" | grep -q "being stopped right now"'
# S8b a marker from an earlier boot counts for nothing (boot-resume's rule): the gate lets the start through
printf 'boot 00000000-old-boot\npid 1\nstate stopped\nrequested 1\nstopped_since 1\n' > "$SC/tmp/ds-session"
env $(envv) bash "$S" ensure-gate "boot resume" > /dev/null 2>&1; grc=$?
ok "S8b a pre-boot stopped marker: the gate says go on (boot-resume brings P028x back)" '[ $grc = 0 ]'

# ---- S9 Switch to DeepSeek from the stopped state: straight to the start, nothing waited for or stopped
new s9; run stop-model; : > "$SB/calls"; touch "$SB/jan"
run to-deepseek; rc=$?
ok "S9 to-deepseek from stopped: rc 0, DeepSeek started, no stop, no wait, no new lock" '[ $rc = 0 ] && grep -q "^start_ds" "$SB/calls" && ! grep -q "^stop_8080" "$SB/calls" && ! grep -q take_lock "$SB/calls" && ! L | grep -q "Waiting: a deep Jan"'
ok "S9 the session is up with a DeepSeek hold; the reminder stopped, the 4-h alert armed" '[ "$(mark state)" = up ] && grep -q "DeepSeek session" "$DR/tmp/bench2.hold" && grep -q "systemctl --user stop model-stopped-reminder.timer" "$SB/calls" && grep -q arm_held_alert "$SB/calls"'
rm -f "$SB/jan"; run back-to-qwen; sleep 0.3
ok "S9b then Back to Qwen: DeepSeek stopped, Qwen up, all released" 'grep -q "^stop_8080 model=deepseek" "$SB/calls" && grep -q qwen "$SB/model" && lockfree && [ ! -e "$DR/tmp/bench2.hold" ] && [ ! -e "$SC/tmp/ds-session" ]'

# ---- S10 Back to Qwen while Stop model is still waiting: cancels it (nothing stopped)
new s10; touch "$SB/chat"
env $(envv) bash "$S" stop-model > /dev/null 2>&1 < /dev/null & SP=$!; sleep 1
run back-to-qwen; wait $SP 2> /dev/null
ok "S10 Back to Qwen cancels a waiting stop: nothing stopped, hold + marker gone, Qwen still up" '! grep -q "^stop_8080" "$SB/calls" && [ ! -e "$DR/tmp/bench2.hold" ] && [ ! -e "$SC/tmp/ds-session" ] && grep -q qwen "$SB/model"'

# ---- S11 the test lock cannot be taken: nothing stopped, the hold released
new s11; touch "$SB/lock-fails"; run stop-model; rc=$?
ok "S11 no lock: rc 1, nothing stopped, the hold and the marker released" '[ $rc = 1 ] && ! grep -q "^stop_8080" "$SB/calls" && [ ! -e "$DR/tmp/bench2.hold" ] && [ ! -e "$SC/tmp/ds-session" ]'

# ---- S12 the dry run writes nothing
new s12; env $(envv) bash "$S" stop-model --dry-run > "$SB/dry.txt" 2>&1; rc=$?
ok "S12 dry run: rc 0, nothing written, says what it would do" '[ $rc = 0 ] && grep -q "DRY RUN of Stop model" "$SB/dry.txt" && grep -q "4 stop: strata-qwen3.8" "$SB/dry.txt" && [ ! -e "$DR/tmp/bench2.hold" ] && [ ! -e "$SC/tmp/ds-session" ] && ! grep -qE "^(take_lock|stop_8080)" "$SB/calls"'

# ---- S13 the existing DeepSeek flow is unchanged at its key points (a session still gets its own hold text and the 4-h alert)
new s13; run to-deepseek; rc=$?
ok "S13 to-deepseek from Qwen: rc 0, the DeepSeek hold text, held alert armed, no reminder" '[ $rc = 0 ] && grep -q "DeepSeek session" "$DR/tmp/bench2.hold" && grep -q arm_held_alert "$SB/calls" && ! grep -q arm_reminder "$SB/calls" && [ "$(mark state)" = up ]'

cleanup_case
echo "passed $pass, failed $fail"; [ $fail = 0 ]
