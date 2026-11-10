#!/bin/bash
# weekend-watch.sh (11-05 19:0x, Claude; from the fresh audit staging/post7d/AUDIT-1105.md) - a read-only watcher until
# Phase 5's queue has finished. It changes nothing in the queue, the chain, the gaps or the retry: it only ALERTS (desktop
# notice + one NOTES.md line, once per condition) and, as RULES-p5.md 4 Q6 says ("+ kcheck when the queue finishes"),
# runs the kernel check once when Phase 5's queue finishes.
#   #1 a stale hold: tmp/bench2.hold present while the gap series is not running (only gap drivers write it), or
#      tmp/port-gap.lockpid set with its holder dead - the queue, switch.sh, replays.sh and the retry would wait for ever
#   #2 one run "not completed" 3 times (the queue retries every 10 min without a count)
#   #11 free disk under 105 GB (notice) / under the 100 GB floor (critical)
#   #13 the kernel-log watcher fired (tmp/r19/KERNEL_ERROR) - kwatch stops the engines but nothing stops the research path
#   DS  DeepSeek holding the queue more than 4 h (Karl 11-06; configs/usability/bin/deepseek-session.sh)
#   Jan a gap waiting more than 2 h on an active Jan job (port_gap4.sh begin's marker tmp/gap-waiting-jan; Karl 11-05)
#   Q6 "queue finished (queue-plan-p5-holdout.json)" -> bringup/lib/kcheck.sh p5-queue-finished, the result in NOTES.md,
#      then the watcher exits. It also exits at 2026-11-10 00:00.
# Start: systemd-run --user --unit=weekend-watch --description="post-7d weekend watcher (alerts only)" /bin/bash <this file>
set -u
WS=${WW_WS:-/home/USER/ai/deep-research}; SC=${WW_SC:-/home/USER/ai-speed-testing/strata-compare}
Q=$WS/logs/bench2-queue.log; HOLD=$WS/tmp/bench2.hold; LP=$SC/tmp/port-gap.lockpid; NOTES=${WW_NOTES:-$WS/NOTES.md}
LOG=${WW_LOG:-$WS/logs/weekend-watch.log}; KC=${WW_KC:-$SC/bringup/lib/kcheck.sh}; KERR=$SC/tmp/r19/KERNEL_ERROR; JANW=$SC/tmp/gap-waiting-jan; DSM=$SC/tmp/ds-session
POLL=${WW_POLL_S:-300}; UNTIL=${WW_UNTIL:-2026-11-10 00:00:00}
series_up() { systemctl --user is-active -q gap-series.service; }
say() { echo "$(date '+%F %T') weekend-watch: $*" >> "$LOG"; }
told=" "
tell() {   # tell KEY URGENCY TEXT - once per KEY
  case "$told" in *" $1 "*) return 0 ;; esac; told="$told$1 "
  say "ALERT ($2) $3"
  echo "* $(date '+%F %H:%M') WEEKEND WATCH (staging/post7d/weekend-watch.sh, alerts only): $3" >> "$NOTES"
  notify-send -a "Weekend watch" -u "$2" "Weekend watch" "$3" 2> /dev/null || true
}
start_line=$(wc -l < "$Q" 2> /dev/null || echo 0)
say "start (pid $$): watching from queue-log line $start_line, every $POLL s, until Phase 5's queue finishes or $UNTIL"
stale_n=0; dead_n=0
while :; do
  [ "$(date '+%F %T')" \> "$UNTIL" ] && { say "time limit $UNTIL reached - exit"; exit 0; }
  new=$(tail -n +"$((start_line + 1))" "$Q" 2> /dev/null)
  # Q6: Phase 5's queue finished -> one kernel check, then done
  if grep -qF 'queue finished (queue-plan-p5-holdout.json)' <<< "$new"; then
    if bash "$KC" p5-queue-finished > /dev/null 2>&1; then
      say "Phase 5's queue finished; kcheck p5-queue-finished OK"
      echo "* $(date '+%F %H:%M') PHASE 5 queue finished: kcheck p5-queue-finished OK (RULES-p5 4 Q6; weekend-watch)." >> "$NOTES"
    else
      tell q6 critical "Phase 5's queue finished but kcheck p5-queue-finished FAILED (RULES-p5 4 Q6) - see strata-compare logs/r19/kwatch.log; Karl decides"
    fi
    exit 0
  fi
  # #13 the kernel-log watcher fired
  [ -f "$KERR" ] && tell kerr critical "the kernel-log watcher fired: $(head -c 200 "$KERR") - kwatch stopped the engines, but the research queue is not stopped by it. To clear it after your check: rm ~/ai-speed-testing/strata-compare/tmp/r19/KERNEL_ERROR; systemctl --user restart kwatch; then strata-compare bringup/lib/kcheck.sh must exit 0 (a taint bit clears only with a reboot)"
  # Karl 11-05: a gap that has waited more than 2 h on an active Jan job -> alert (the gap is not started)
  if [ -f "$JANW" ] && [ $(( $(date +%s) - $(stat -c %Y "$JANW" 2> /dev/null || date +%s) )) -gt 7200 ]; then
    tell "jan:$(head -c 19 "$JANW")" critical "a measurement gap has waited more than 2 h for an active Jan job or a chat on 8080 (since $(head -c 19 "$JANW"): $(cut -c21-140 "$JANW")) - it starts by itself when that ends; Karl decides whether to wait"
  fi
  # #1 a stale hold / a stale gap
  # Karl 11-06: DeepSeek holding the queue for more than 4 h (the launcher's tmp/ds-session of this boot) -> alert once a
  # session; its hold is not a stale one
  ds_live=0
  if grep -qsF "boot $(cat /proc/sys/kernel/random/boot_id)" "$DSM"; then ds_live=1
    h=$(sed -n 's/^held_since //p' "$DSM" | head -1)
    # (Karl 11-09, Stop model: no alert for its hold) a stop is a session with no model: no 4-h alert
    if [ -n "$h" ] && ! grep -qsxE 'state (stop-waiting|stopping|stopped)' "$DSM" && [ $(( $(date +%s) - h )) -gt 14400 ]; then
      tell "ds:$h" critical "DeepSeek has held the research queue for more than 4 h (since $(date -d "@$h" '+%H:%M')). Click Back to Qwen when you are done."
    fi
  fi
  if [ -e "$HOLD" ] && [ $ds_live = 0 ] && ! series_up; then stale_n=$((stale_n + 1)); else stale_n=0; fi
  [ $stale_n -ge 2 ] && tell hold critical "tmp/bench2.hold is present ($(head -c 120 "$HOLD")) but the gap series is not running - the queue, the chain's switch, the replays and the retry wait on it; Karl decides"
  if [ -s "$LP" ] && ! kill -0 "$(cat "$LP" 2> /dev/null)" 2> /dev/null; then dead_n=$((dead_n + 1)); else dead_n=0; fi
  [ $dead_n -ge 2 ] && tell lockpid critical "tmp/port-gap.lockpid names a dead lock holder ($(cat "$LP")): a gap ended without port_gap4.sh end (8080 may be down, the hold may stay); Karl decides"
  # #2 the same run not completed 3 times
  rep=$(grep -E '^20[0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9:]+ .*: not completed \(rc' <<< "$new" | sed -E 's/^[0-9-]+ [0-9:]+ //; s/: not completed \(rc.*//' | sort | uniq -c | awk '$1 >= 3 {$1 = ""; sub(/^ /, ""); print}' | head -1)
  [ -n "$rep" ] && tell "rep:$rep" critical "the queue has failed '$rep' 3 times (it retries every 10 min with no limit) - see logs/bench2-queue.log; Karl decides"
  # #11 the disk floor
  free=$(df --output=avail -B1G "$WS" 2> /dev/null | tail -1 | tr -d ' ')
  if [ -n "$free" ]; then
    [ "$free" -lt 100 ] && tell disk100 critical "free disk ${free} GB - under the 100 GB floor"
    [ "$free" -lt 105 ] && tell disk105 normal "free disk ${free} GB - within 5 GB of the 100 GB floor"
  fi
  sleep "$POLL"
done
