#!/bin/bash
# Stuck-run watchdog install (staged 11-03; NOT run by the stager - see INSTALL.md). Copies the three staged tools files
# over the live ones (backups *.before-watchdog; new file + mv, so the running bench2-queue.sh keeps reading its old
# copy until the unit restarts) and verifies. Refuses (changes nothing) unless check.sh pre passes.
#   install.sh                  install only; restart the bench unit yourself in the same gap (INSTALL.md step 3)
#   install.sh --restart-unit   install, then restart deep-research-bench.service - only if it is waiting on its hold
#                               file (check.sh live again); the new loop then waits on the same hold file
set -eu
W=/home/USER/ai/deep-research
S=$W/staging/watchdog
UNIT=deep-research-bench.service
bash $S/check.sh pre || { echo "install refused: pre-checks failed (nothing changed)"; exit 1; }
put() {   # src dst: back dst up as dst.before-watchdog (kept if it exists), copy src beside dst and mv -f over it
  local src=$1 dst=$2
  [ -e "$dst" ] && [ ! -e "$dst.before-watchdog" ] && cp -p "$dst" "$dst.before-watchdog"
  cp -p "$src" "$dst.new-watchdog"
  mv -f "$dst.new-watchdog" "$dst"
  echo "installed $dst (backup $dst.before-watchdog)"
}
for f in ldr-client.py bench2.py bench2-queue.sh; do
  put $S/tools/$f $W/tools/$f
done
bash $S/check.sh post || { echo "POST-CHECK FAILED: roll back with the *.before-watchdog files (INSTALL.md step R)"; exit 1; }
echo "$(date '+%F %T') stuck-run watchdog installed (ldr-client.py, bench2.py: from the next question; bench2-queue.sh: from the unit's next start)"
if [ "${1:-}" = --restart-unit ]; then
  if systemctl --user is-active --quiet $UNIT; then
    bash $S/check.sh live || { echo "unit NOT restarted: the queue is not waiting on its hold file now (INSTALL.md step 3)"; exit 1; }
    systemctl --user restart $UNIT
    echo "$UNIT restarted (pid $(systemctl --user show -p MainPID --value $UNIT)) - check INSTALL.md step 4"
  else
    echo "$UNIT is not running: the new loop starts with it (systemctl --user start $UNIT, when Karl wants the queue back)"
  fi
fi
