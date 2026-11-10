#!/bin/bash
# p4s4-watch.sh - 10-23, replaces gap11-wait.sh (which would have run gap 11 at ANY stop of the queue, a release pause
# included). Watches phase 4 item 4 stage 2's queue (deep-research-bench.service on queue-plan-p4s4.json) until its log
# says "queue finished", then runs work/r22/gap11.sh (the corrected tool-call check on P021m, for the record).
# The queue instance started 14:15 still runs the old release check (it pauses at any tag newer than v0.2.3.1; a running
# bash script is not edited). If it stops on such a pause, work/r22/tagcheck.sh decides: no engine/server change ->
# the queue is started again (on the new check); an engine/server change -> a desktop alert, and this waits for the
# queue to be started again after the review.
L=/home/USER/ai-speed-testing/strata-compare/logs/r22/gap11-wait.log
Q=/home/USER/ai/deep-research/logs/bench2-queue.log
TC=/home/USER/ai-speed-testing/strata-compare/work/r22/tagcheck.sh
say() { echo "$(date '+%F %T') $*" >> $L; }
active() { systemctl --user is-active -q deep-research-bench.service; }
say "p4s4-watch (replaces gap11-wait.sh): waiting for the p4s4 queue to finish"
until active; do sleep 60; done
while :; do
  while active; do sleep 60; done
  last=$(tail -n 1 $Q)
  case "$last" in
    *"queue finished (queue-plan-p4s4.json)"*) break ;;
    *" released: pausing the measurements"*)
      t=$(sed -E 's/.*Strata (v[^ ]+) released.*/\1/' <<< "$last")
      until r=$($TC --who "p4s4 watch"); [ "${r%% *}" != UNKNOWN ]; do say "the queue paused on $t: $r - retrying in 10 min"; sleep 600; done
      if [ "${r%% *}" = PAUSE ]; then
        say "the queue paused on $t (old release check): $r - alert sent; waiting for the queue to be started again"
        notify-send -a "Deep research" -u critical "Measurements paused: Strata $t" "$t changes the engine or server (${r#PAUSE }). The research queue stopped before its next question. After the review: work/r22/tagcheck.sh --accept $t, then start deep-research-bench.service again." 2> /dev/null || true
        until active; do sleep 60; done
      else
        say "the queue paused on $t (old release check); $r - no engine/server change: starting the queue again"
        for f in /home/USER/ai/deep-research/NOTES.md /home/USER/ai-speed-testing/strata-compare/NOTES.md; do
          printf '\n%s\n' "$(date '+%m-%d %H:%M') The p4s4 queue (old release check) paused on Strata $t; tagcheck.sh: $r - no engine/server change, so work/r22/p4s4-watch.sh started the queue again." >> $f
        done
        systemctl --user start deep-research-bench.service
        sleep 5
      fi ;;
    *)
      say "the queue stopped without finishing (last log line: ${last:0:200}); waiting for it to run again"
      until active; do sleep 60; done ;;
  esac
done
say "p4s4 queue finished; gap 11"
cd /home/USER/ai-speed-testing/strata-compare && exec work/r22/gap11.sh > logs/r22/gap11.out 2>&1
