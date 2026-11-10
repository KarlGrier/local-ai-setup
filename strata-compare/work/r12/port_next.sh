#!/bin/bash
# port_next.sh SRC_RANGE — cherry-pick the commits of SRC_RANGE (e.g. v0.1.38..v38-c12) not yet on HEAD (by subject),
# in order, stopping at the first conflict and naming its files.
source /home/USER/ai-speed-testing/strata-compare/work/r12/gitenv.sh
for c in $(git rev-list --reverse $1); do
  subj=$(git log -1 --format=%s $c)
  git log --format=%s $2..HEAD | grep -qxF "$subj" && continue
  [ -n "${SKIP:-}" ] && echo "$subj" | grep -qF "$SKIP" && { echo "skip ${subj:0:90}"; continue; }
  if git cherry-pick -x $c > /dev/null 2>&1; then echo "ok   ${subj:0:95}"
  else echo "CONF ${subj:0:75} :: $(git diff --name-only --diff-filter=U | tr '\n' ' ')"; exit 1; fi
done
echo "all applied"
