#!/bin/bash
# pubrebase.sh — round 14 step 9: the local pub/* branches (one change of ours each, on v0.1.39) rebuilt on v0.1.40.1
# as pub14/* from the ported series (r14-port's commits = the conflicts already resolved), + each branch's own
# measurements commit (bench/results/2026-10-05-<name>/README.md) from pub/<name>. Author strata-compare
# <noreply@localhost>; Co-Authored-By / session / cherry-pick lines dropped from the messages. Local only.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS/strata-pub
export GIT_AUTHOR_NAME=strata-compare GIT_AUTHOR_EMAIL=noreply@localhost GIT_COMMITTER_NAME=strata-compare GIT_COMMITTER_EMAIL=noreply@localhost
mapfile -t N < <(git rev-list --reverse v0.1.40.1..r14-port)   # r14-port rows 1..40 (results/r14 ledger map)
clean_msg() { git log -1 --format=%B "$1" | grep -vE '^(Co-Authored-By|Co-authored-by|Claude-Session|\(cherry picked from)' | sed -e :a -e '/^\n*$/{$d;N;ba' -e '}'; }
pick() {   # pick COMMIT : cherry-pick with a cleaned message and the noreply author
  git cherry-pick --allow-empty -n "$1" > /dev/null 2>&1 || return 1
  clean_msg "$1" > /tmp/claude-1000/pubmsg.txt
  git commit -q --allow-empty -F /tmp/claude-1000/pubmsg.txt --author="strata-compare <noreply@localhost>"
}
# name | base | new rows (r14-port positions)
SPECS=(
  "side-mixer|v0.1.40.1|15"
  "b3-mmvq-il|pub14/side-mixer~1|22 23 24 25 26"
  "a2-router-q8k|v0.1.40.1|17 18 19 20"
  "ple-prefetch|v0.1.40.1|9"
  "adapt-land|v0.1.40.1|12"
  "adapt-helper|v0.1.40.1|14"
  "spec-exact|v0.1.40.1|11"
  "b1-gr-fork|v0.1.40.1|27 28"
  "b2-split-attn|v0.1.40.1|21"
)
for s in "${SPECS[@]}"; do
  IFS='|' read -r name base rows <<< "$s"
  git checkout -q --detach "$base" && git branch -f pub14/$name HEAD > /dev/null && git checkout -q pub14/$name
  ok=1
  for r in $rows; do
    if ! pick "${N[$((r - 1))]}"; then
      echo "pub14/$name: row $r ($(git log -1 --format=%s ${N[$((r - 1))]} | cut -c1-60)) does not apply alone: $(git diff --name-only --diff-filter=U | tr '\n' ' ')"
      git cherry-pick --abort > /dev/null 2>&1; git reset -q --hard; ok=0; break
    fi
  done
  [ $ok = 1 ] || continue
  # the measurements commit (bench/results/...) from the round 13 branch (its last commit)
  m=$(git rev-parse pub/$name)
  pick "$m" || { echo "pub14/$name: measurements commit conflicts"; git cherry-pick --abort > /dev/null 2>&1; git reset -q --hard; }
  echo "pub14/$name: $(git log --oneline v0.1.40.1..HEAD | wc -l) commits on $(git describe --tags --abbrev=0 HEAD 2>/dev/null)"
done
git checkout -q --detach v0.1.40.1
