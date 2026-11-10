#!/bin/bash
# stress.sh - round 19: the user's RAM check after the fix (6000 MT/s 1:1), required before the first run above 60 GiB of
# locked RAM: `stressapptest -M 80000 -s 3600 -W` once, with no model server running (8080 stopped: one big memory user at
# a time). The log must end with "Status: PASS". PASS -> C*16.1 back on 8080 (phase end, kept). Anything else -> STOP at
# the head of the queue, tmp/r19/STRESS_FAIL, nothing restarted (the user: "if it does not end with Status: PASS, stop
# and tell me"). The kernel-log watcher (bringup/lib/kwatch.sh) runs beside it.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
LOG=logs/r19/stressapptest.log; Q=bringup/lib/queue.txt
stop_all() { echo "$(date -Is) $1" | tee -a $LOG; echo "$1" > tmp/r19/STRESS_FAIL; cp $Q work/r19/queue-at-stress-fail.txt; { echo STOP; cat $Q; } > $Q.new && mv $Q.new $Q; exit 1; }
bringup/lib/kcheck.sh stress-before || stop_all "kernel check failed before stressapptest"
echo "=== $(date -Is) stress: 8080 stopped (no model server during the RAM test)"
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -2
for i in $(seq 60); do pgrep -x strata > /dev/null || break; sleep 1; done
pgrep -xa strata && stop_all "a strata process is still running"
sync; echo "=== $(date -Is) MemAvailable $(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo) MiB, swap used $(free -m | awk '/Swap/ {print $3}') MiB, tainted $(cat /proc/sys/kernel/tainted)"
echo "=== $(date -Is) stressapptest -M 80000 -s 3600 -W ($(stressapptest -V 2>&1 | head -1))" | tee $LOG.head
stressapptest -M 80000 -s 3600 -W > $LOG 2>&1
rc=$?
# stressapptest prefixes every line with a timestamp, the last one blank: judge the last line that has text after it
last=$(sed -E 's/^[0-9]{4}\/[0-9]{2}\/[0-9]{2}-[0-9:]{8}\([A-Z]+\) ?//' $LOG | grep -v '^[[:space:]]*$' | tail -1)
echo "=== $(date -Is) stressapptest rc $rc; last line: $last"
grep -iE 'error|miscompare|hardware|corrected' $LOG | head -10
case "$last" in
  "Status: PASS"*) echo "=== $(date -Is) stress PASS" ;;
  *) stop_all "stressapptest did not end with Status: PASS (rc $rc): $last" ;;
esac
bringup/lib/kcheck.sh stress-after || stop_all "kernel check failed after stressapptest"
echo "=== $(date -Is) MemAvailable $(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo) MiB, swap used $(free -m | awk '/Swap/ {print $3}') MiB"
if nvidia-smi > /dev/null 2>&1; then bringup/lib/phase_end.sh r19-stress keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
else echo "=== $(date -Is) no NVIDIA driver loaded on this boot (kernel $(uname -r)): C*16.1 not started"; fi
echo "=== $(date -Is) stress done"
