#!/bin/bash
# pick.sh N... — round 14 port: cherry-pick ledger rows N (r13-fix's commit order, 1-based) onto the current branch in
# order; stops at the first conflict (prints the conflict list). A row number prefixed with "-" is skipped (dropped).
source /home/USER/ai-speed-testing/strata-compare/work/r13/gitenv.sh
mapfile -t C < <(git rev-list --reverse v0.1.39..r13-fix)
for n in "$@"; do
  case $n in -*) echo "row ${n#-}: DROPPED ($(git log -1 --format=%s ${C[$(( ${n#-} - 1 ))]} | cut -c1-70))"; continue;; esac
  c=${C[$(( n - 1 ))]}
  if git cherry-pick $c > /tmp/claude-1000/pick.out 2>&1; then echo "row $n: applied ($(git log -1 --format='%h %s' | cut -c1-80))"
  elif grep -q "empty" /tmp/claude-1000/pick.out; then echo "row $n: EMPTY (upstream has it)"; git cherry-pick --skip; 
  else echo "row $n: CONFLICT in $(git diff --name-only --diff-filter=U | tr '\n' ' ')"; exit 1; fi
done
