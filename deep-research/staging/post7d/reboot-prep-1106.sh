#!/bin/bash
# reboot-prep-1106.sh (Claude, 11-06): Karl reboots into Windows at ~18:00. The queue starts no question that would not
# end by 17:30 (run/pause-window 17:30-23:00); no gap opens 14:50-23:00 (strata-compare tmp/quiet-window). This one
# shot: at 17:00, if the replays are not done, sets the hold so no NEW replay starts (a running one is not touched; a
# hold does not void it); at 17:40 one critical alert (desktop + phone): ready to reboot, or what still runs.
# After the reboot boot-resume clears a pre-boot hold and resumes the chain at the next clean boundary.
set -u
WS=/home/USER/ai/deep-research; SC=/home/USER/ai-speed-testing/strata-compare; HOLD=$WS/tmp/bench2.hold
RL=$WS/logs/post7d-replays.log; RLOG=$WS/results/bench2/fixes/replays.log
note() { echo "* $(date '+%F %H:%M') REBOOT PREP (staging/post7d/reboot-prep-1106.sh): $*" >> $WS/NOTES.md; }
replays_done() { grep -qE '^2026-11-06 .* replays: done' $RL; }
replay_running() { local s e; s=$(grep -E '^2026-11-06 .* replays: r-[a-z0-9-]+: start' $RL | tail -1 | grep -oE 'r-[a-z0-9-]+'); [ -n "$s" ] || return 1
  e=$(grep -E "^11-06 .* end $s rc" $RLOG | tail -1); [ -z "$e" ] && echo "$s"; [ -z "$e" ]; }
until [ "$(date +%H%M)" -ge 1700 ]; do sleep 30; done
if ! replays_done && [ ! -e $HOLD ]; then
  echo "Karl's reboot into Windows (11-06 ~18:00): no NEW replay or question starts until he is back (set at $(date '+%H:%M') by staging/post7d/reboot-prep-1106.sh; boot-resume clears it after the reboot; by hand: rm ~/ai/deep-research/tmp/bench2.hold)" > $HOLD
  note "17:00: the replays were not done - hold set (no new replay starts; a running one finishes)"
fi
until [ "$(date +%H%M)" -ge 1740 ]; do sleep 30; done
why=""
[ -s $SC/tmp/port-gap.lockpid ] && why="$why a measurement gap is open;"
flock -n $WS/run/bench.lock true 2> /dev/null || why="$why a research question is running;"
r=$(replay_running) && why="$why replay $r is still running;"
if [ -z "$why" ]; then
  msg="Ready to reboot: no question, replay or gap is running (the queue waits until 23:00; the chain resumes after the reboot)."
else
  msg="NOT ready to reboot yet:$why see NOTES.md - wait for it to finish, or reboot and lose that run."
fi
note "17:40: $msg"
notify-send -a "Deep research" -u critical "Reboot check" "$msg" 2> /dev/null || true
