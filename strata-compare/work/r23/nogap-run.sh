#!/bin/bash
# nogap-run.sh LOG CMD... (11-05, Karl: "Builds and other heavy CPU work run under nice -n 19 and only while no gap is
# open; check the gap's hold before starting, and pause if one opens.") Runs CMD under nice -n 19 in its own process
# group. A gap counts as OPEN while tmp/port-gap.lockpid is non-empty (the driver took the test lock and stopped 8080 -
# measurements run); a hold file alone (a driver waiting for a research question) is not an open gap. Before starting
# it waits while a gap is open; while CMD runs it checks every 5 s and freezes the whole process group (SIGSTOP) as soon
# as a gap opens, resuming it (SIGCONT) when the gap closes. Exit = CMD's exit status. Children get 8>&- 9>&-.
set -u
SC=/home/USER/ai-speed-testing/strata-compare; LP=$SC/tmp/port-gap.lockpid
LOG=${1:?usage: nogap-run.sh LOG CMD...}; shift
log() { echo "$(date '+%F %T') nogap-run: $*" >> "$LOG"; }
gap_open() { [ -s "$LP" ]; }
while gap_open; do log "a gap is open ($(cat "$LP" 2> /dev/null)) - waiting to start"; sleep 30; done
log "start: $*"
setsid nice -n 19 "$@" 8>&- 9>&- >> "$LOG" 2>&1 < /dev/null &
pid=$!; sleep 1; pg=$(ps -o pgid= -p $pid 2> /dev/null | tr -d ' '); pg=${pg:-$pid}
stopped=0
while kill -0 $pid 2> /dev/null; do
  if gap_open && [ $stopped = 0 ]; then kill -STOP -- -$pg 2> /dev/null && { stopped=1; log "gap opened - process group $pg frozen"; }
  elif ! gap_open && [ $stopped = 1 ]; then kill -CONT -- -$pg 2> /dev/null && { stopped=0; log "gap closed - process group $pg resumed"; }
  fi
  sleep 5
done
wait $pid; rc=$?
log "end: rc $rc"
exit $rc
