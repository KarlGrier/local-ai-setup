#!/bin/bash
# verify_git.sh - Round 19 integrity check after the RAM fault: git fsck --full on every repository under ai-speed-testing
# and ai/, then every worktree's tracked files re-hashed against the index. A file whose content differs from the index
# while git's stat check calls it clean (so `git status` would not show it) is reported as SILENT; files git already shows
# as modified are only counted.  Output: results/r19/integrity/git-fsck.txt, git-worktrees.txt
set -u
WS=/home/USER/ai-speed-testing/strata-compare; OUT=$WS/results/r19/integrity; mkdir -p $OUT
LIST=$(mktemp); find /home/USER/ai-speed-testing /home/USER/ai -maxdepth 5 -name .git \( -type d -o -type f \) 2>/dev/null | sed 's|/.git$||' | sort > $LIST
[ "${SKIP_FSCK:-0}" = 1 ] || : > $OUT/git-fsck.txt
fsck_one() {
  local r=$1 o; o=$(nice git -C "$r" fsck --full --no-progress --no-dangling 2>&1); local rc=$?
  printf '%s\trc=%s\t%s\n' "$([ $rc -eq 0 ] && [ -z "$o" ] && echo OK || echo CHECK)" "$rc" "$r"
  [ -n "$o" ] && printf '%s\n' "$o" | sed 's/^/    /' | head -20
}
export -f fsck_one
[ "${SKIP_FSCK:-0}" = 1 ] || while read d; do [ -d "$d/.git" ] && echo "$d"; done < $LIST | xargs -P 6 -I{} bash -c 'fsck_one "$@"' _ {} >> $OUT/git-fsck.txt
: > $OUT/git-worktrees.txt
check_wt() {
  local w=$1
  cd "$w" 2>/dev/null || { echo "GONE	$w"; return; }
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "NOT-A-WT	$w"; return; }
  local idx files hashes shown silent=0 changed=0 n
  idx=$(mktemp); git ls-files -s -z | tr '\0' '\n' | awk '$1 != "160000"' > $idx      # skip submodule entries
  n=$(wc -l < $idx)
  shown=$(git diff --name-only 2>/dev/null | sort)
  cut -f2 $idx | while IFS= read -r p; do [ -f "$p" ] && [ ! -L "$p" ] && echo "$p"; done > $idx.f   # regular files present
  # map path -> index sha, path -> worktree sha
  awk -F'\t' '{split($1,a," "); print $2"\t"a[2]}' $idx | sort > $idx.want
  git hash-object --stdin-paths < $idx.f | paste $idx.f - | sort > $idx.got
  join -t$'\t' $idx.want $idx.got | awk -F'\t' '$2 != $3 {print $1}' > $idx.diff
  while IFS= read -r p; do
    if grep -qxF -- "$p" <<< "$shown"; then changed=$((changed+1)); else silent=$((silent+1)); echo "    SILENT $p"; fi
  done < $idx.diff
  printf '%s\t%s tracked, %s modified (shown by git), %s silent\t%s\n' "$([ $silent -eq 0 ] && echo OK || echo SILENT)" "$n" "$changed" "$silent" "$w"
  rm -f $idx $idx.f $idx.want $idx.got $idx.diff
}
export -f check_wt
xargs -P 8 -I{} bash -c 'check_wt "$@"' _ {} < $LIST >> $OUT/git-worktrees.txt 2>&1
rm -f $LIST
echo "fsck: $(grep -c '^OK' $OUT/git-fsck.txt) OK, $(grep -c '^CHECK' $OUT/git-fsck.txt) to check"
echo "worktrees: $(grep -c '^OK' $OUT/git-worktrees.txt) OK, $(grep -c '^SILENT' $OUT/git-worktrees.txt) with silent differences, $(grep -cE '^(GONE|NOT-A-WT)' $OUT/git-worktrees.txt) gone"
