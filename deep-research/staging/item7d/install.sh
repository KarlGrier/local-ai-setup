#!/bin/bash
# Item 7d install (staged 11-03; NOT run by Claude - for the reviewer, see INSTALL.md). Copies the four staged tools
# files over the live ones (backups *.before-7d, new file + mv, so a running reader keeps the old file), puts the queue
# plan in place, and verifies. It does NOT switch or start the bench queue, restart LDR or send any search.
# Refuses (changes nothing) unless check.sh pre passes: no bench queue / bench lock / paid run / Jan job / replay or
# grading live, the live files unchanged since staging, the staged tests green.
set -eu
W=/home/USER/ai/deep-research
S=$W/staging/item7d
bash $S/check.sh pre || { echo "install refused: pre-checks failed (nothing changed)"; exit 1; }
put() {   # src dst: back dst up as dst.before-7d (kept if it exists), copy src beside dst and mv -f over it
  local src=$1 dst=$2
  [ -e "$dst" ] && [ ! -e "$dst.before-7d" ] && cp -p "$dst" "$dst.before-7d"
  cp -p "$src" "$dst.new-7d"
  mv -f "$dst.new-7d" "$dst"
  echo "installed $dst (backup $dst.before-7d)"
}
for f in search_route.py paid_search.py paid-route.json s2_search.py; do
  put $S/tools/$f $W/tools/$f
done
if [ ! -e $W/results/bench2/queue-plan-7d.json ]; then
  cp -p $W/results/bench2/queue-plan-7d.json.draft $W/results/bench2/queue-plan-7d.json
  echo "queue plan: results/bench2/queue-plan-7d.json (from the .draft)"
fi
bash $S/check.sh post || { echo "POST-CHECK FAILED: roll back with the *.before-7d files (INSTALL.md step R)"; exit 1; }
echo "$(date '+%F %T') item 7d tools installed; bench queue not switched or started (INSTALL.md steps 3-5)"
