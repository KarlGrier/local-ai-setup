#!/bin/bash
# queue.sh — round 3: runs work/r3/queue.txt line by line (each line = a shell command, run from the workspace),
# appending output to logs/r3/batch.log. Lines can be appended while it runs. "STOP" ends it; empty queue = wait.
# CODEX GUARD: before every job, if any Codex process is alive (or a GPU app that is not ours holds memory), stop our
# test server (scripts/server-C.sh stop; it only stops the server this workspace started) and wait until 15 minutes
# have passed with neither, then continue. Codex's test must never share the machine with a benchmark of ours.
WS=/home/USER/ai-speed-testing/strata-compare; Q=$WS/work/r3/queue.txt; LOG=$WS/logs/r3/batch.log
cd $WS; touch $Q
codex_alive() { ps -eo pid=,comm=,args= | awk -v me=$$ '$1!=me && ($2=="codex" || $3 ~ /\/codex( |$)/ || $3 ~ /codex-/){f=1} END{exit !f}'; }
foreign_gpu() {  # a compute app on the GPU that is not a strata engine / nsys we started
  nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | while read -r p; do
    [ -z "$p" ] && continue
    tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -qE "$WS/(engine-|strata-)" || echo "$p"
  done | grep -q .
}
guard() {   # called when Codex/foreign GPU work is present: stop our server, then wait for 15 quiet minutes
  local quiet_since=""
  while true; do
    if codex_alive || foreign_gpu; then
      if [ -f $WS/logs/server-C.pid ]; then echo "### $(date -Is) GUARD: stopping our server" >> $LOG; scripts/server-C.sh stop >> $LOG 2>&1; fi
      echo "### $(date -Is) GUARD: Codex process or foreign GPU app present; waiting" >> $LOG
      quiet_since=""
    else
      [ -z "$quiet_since" ] && quiet_since=$(date +%s)
      (( $(date +%s) - quiet_since >= 900 )) && { echo "### $(date -Is) GUARD: 15 min quiet, resuming" >> $LOG; return; }
    fi
    sleep 60
  done
}
while true; do
  line=$(head -1 $Q)
  if [ -z "$line" ]; then
    if [ "$(wc -l < $Q)" -gt 0 ]; then sed -i 1d $Q; continue; fi
    sleep 5; continue
  fi
  if codex_alive || foreign_gpu; then guard; fi
  sed -i 1d $Q
  [ "$line" = STOP ] && { echo "=== $(date -Is) queue STOP" >> $LOG; exit 0; }
  echo "### $(date -Is) RUN: $line" >> $LOG
  bash -c "$line" >> $LOG 2>&1
  echo "### $(date -Is) END ($?): $line" >> $LOG
done
