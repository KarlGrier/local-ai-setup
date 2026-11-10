#!/bin/bash
# test_research_pause.sh - Claude 11-07: the real configs/usability/bin/research-pause.sh (executed as a file, its own
# permissions) against a sandbox: RPS_SC / RPS_DR point at scratch copies of the queue's files, so nothing of the real
# queue, windows or NOTES is touched. The waiter runs as a real user unit with a test name. Notifications go to a file.
set -u
S=/home/USER/ai-speed-testing/strata-compare; RP=$S/configs/usability/bin/research-pause.sh
T=$S/work/ds-launcher/research-pause/scratch/run-$(date +%m%d-%H%M%S); mkdir -p "$T"
export RPS_SC=$T/sc RPS_DR=$T/dr RPS_LOOK_S=1 RPS_POLL_S=1 RPS_CLOSE_S=0 RPS_WAIT_UNIT=rps-test-wait-$$
mkdir -p $RPS_SC/tmp $RPS_SC/logs/run $RPS_SC/work/r22 $RPS_DR/run $RPS_DR/tmp $RPS_DR/logs $RPS_DR/tools
ln -s $S/work/r22/port_gap4.sh $RPS_SC/work/r22/port_gap4.sh               # read only (real_check greps them)
ln -s /home/USER/ai/deep-research/tools/bench2.py $RPS_DR/tools/bench2.py
: > $RPS_DR/NOTES.md; QL=$RPS_DR/logs/bench2-queue.log; : > $QL
cat > $T/hook.sh <<EOF
notify() { echo "\$(date +%T) NOTIFY \$1 | \$2" >> $T/notify.log; }
EOF
export RPS_TEST_HOOK=$T/hook.sh
pass=0; fail=0
ok() { if eval "$2"; then pass=$((pass + 1)); echo "ok   $1"; else fail=$((fail + 1)); echo "FAIL $1"; fi; }
PW=$RPS_DR/run/pause-window; QW=$RPS_SC/tmp/quiet-window; MK=$RPS_SC/tmp/research-pause; LG=$RPS_SC/logs/run/research-pause.log
run() { "$RP" "$@" > "$T/out-$1.txt" 2>&1 < /dev/null; }

ok "real script is executable" '[ -x "$RP" ]'
run pause --dry-run; ok "dry-run pause changes nothing" '! [ -e "$PW" ] && ! [ -e "$QW" ] && ! [ -e "$MK" ]'
run pause; r=$?; ok "pause, nothing running: rc 0" '[ $r = 0 ]'
ok "pause wrote both windows, equal" '[ -s "$PW" ] && [ "$(cat "$PW")" = "$(cat "$QW")" ]'
ok "window ends 2099-12-31 23:59" 'grep -q " 2099-12-31 23:59$" "$PW"'
ok "held at once (two looks)" 'grep -q "^held_since " "$MK"'
ok "held notification" 'grep -q "NOTIFY Research is held" $T/notify.log'
ok "NOTES lines: pause + held" '[ "$(grep -c "RESEARCH PAUSE" $RPS_DR/NOTES.md)" = 2 ]'
/home/USER/ai/deep-research/.venv/bin/python -I - "$PW" <<'PY'
import importlib.util, sys
from datetime import datetime, timedelta
from pathlib import Path
spec = importlib.util.spec_from_file_location("b2", "/home/USER/ai/deep-research/tools/bench2.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.PAUSE_WINDOW = Path(sys.argv[1]); n = datetime.now()
sys.exit(0 if n + timedelta(minutes=1) > m.night_cut(n) else 1)
PY
r=$?; ok "bench2.py sees no room inside the window" '[ $r = 0 ]'
run pause; ok "pause again: already paused, held since" 'grep -q "already paused" "$LG" && grep -q "held since" "$LG"'
run resume --dry-run; ok "dry-run resume changes nothing" '[ -e "$PW" ] && [ -e "$QW" ] && [ -e "$MK" ]'
run resume; ok "resume removed windows + marker" '! [ -e "$PW" ] && ! [ -e "$QW" ] && ! [ -e "$MK" ]'
ok "resumed notification" 'grep -q "NOTIFY Research resumed" $T/notify.log'
run resume; ok "resume when not paused" 'grep -q "Research is not paused" "$LG"'

# a window someone else set: pause refuses and changes nothing; resume leaves a future one alone
echo "2030-01-01 10:00 2030-01-01 12:00" > "$PW"
run pause; ok "pause refuses beside a foreign window" '[ "$(cat "$PW")" = "2030-01-01 10:00 2030-01-01 12:00" ] && ! [ -e "$MK" ] && ! [ -e "$QW" ] && grep -q "Not pausing" "$LG"'
run resume; ok "resume leaves a foreign future window" '[ -e "$PW" ] && grep -q "Left as they are" "$LG"'
rm -f "$PW"

# a running question: the waiter unit holds on until the lock frees
echo "$(date '+%F %T') holdout / deep / p5final / o04: running" >> "$QL"
flock "$RPS_DR/run/bench.lock" sleep 6 & HOLDER=$!; sleep 0.5
"$RP" pause > "$T/out-pause-wait.txt" 2>&1 < /dev/null & PP=$!
sleep 3
ok "waiter unit running while the question runs" 'systemctl --user is-active -q "$RPS_WAIT_UNIT.service"'
ok "not held while the question runs" '! grep -q "^held_since " "$MK"'
ok "the wait names the question and its end" 'grep -q "Waiting: research question holdout / deep / p5final / o04" "$LG" && grep -q "expected to end around" "$LG"'
wait $HOLDER; wait $PP; rc=$?
ok "held after the question ended; pause rc 0" '[ $rc = 0 ] && grep -q "^held_since " "$MK"'
ok "waiter unit gone" '! systemctl --user is-active -q "$RPS_WAIT_UNIT.service"'
run resume

# resume while it waits: the waiter stops, the pause is released
flock "$RPS_DR/run/bench.lock" sleep 30 & HOLDER=$!; sleep 0.5
"$RP" pause > "$T/out-pause-wait2.txt" 2>&1 < /dev/null & PP=$!
sleep 3; run resume; sleep 2
ok "resume while waiting: released, waiter stopped" '! [ -e "$MK" ] && ! [ -e "$PW" ] && ! systemctl --user is-active -q "$RPS_WAIT_UNIT.service"'
kill $HOLDER 2> /dev/null; wait $PP 2> /dev/null
ok "no held notification after a resume while waiting" '[ "$(grep -c "NOTIFY Research is held" $T/notify.log)" = 2 ]'
systemctl --user stop "$RPS_WAIT_UNIT.service" 2> /dev/null
echo "== $pass passed, $fail failed (sandbox $T)"
[ $fail = 0 ]
