#!/bin/bash
# gyrol_watch.sh - 2026-10-19, the user's addition to the release watch: hourly, check every new upstream Strata tag
# (finals and pre-releases) for Gyro-L support (agentionai's Qwen3.8-Flash-Next-Gyro-L, trellis types 147-149). Read
# only: ls-remote, then a tag-only fetch into the local clone. Signs of support: docs/GYRO.md no longer says Gyro-L "is
# not supported", or the engine source names Gyro-L. Exits with a line when a tag has it, so the session can plan the
# test (after the current research queue; see HANDOFF.md "Gyro-L test").
# Checked tags: logs/r21/gyrol_watch.checked; log: logs/r21/gyrol_watch.log.
SC=/home/USER/ai-speed-testing/strata-compare
REPO=$SC/strata
LOG=$SC/logs/r21/gyrol_watch.log
DONE=$SC/logs/r21/gyrol_watch.checked
touch "$DONE"
while :; do
  tags=$(timeout 60 git -C "$REPO" ls-remote --tags --refs origin 2>/dev/null | awk '{print $2}' | sed 's#refs/tags/##' | sort -V)
  if [ -z "$tags" ]; then echo "$(date -Is) ls-remote failed" >> "$LOG"; sleep 3600; continue; fi
  for t in $tags; do
    grep -qxF "$t" "$DONE" && continue
    # only tags from v0.2.0-beta on can be new here (earlier ones were checked by reading the docs on 10-19)
    [ "$(printf '%s\nv0.2.0-beta\n' "$t" | sort -V | head -1)" = "v0.2.0-beta" ] || { echo "$t" >> "$DONE"; continue; }
    timeout 300 git -C "$REPO" fetch origin tag "$t" --no-tags > /dev/null 2>&1 || { echo "$(date -Is) fetch $t failed" >> "$LOG"; continue; }
    unsupported=$(git -C "$REPO" show "$t:docs/GYRO.md" 2>/dev/null | tr '\n' ' ' | grep -c -i "Gyro-L[^.]*is not supported")
    insrc=$(git -C "$REPO" grep -l -i "gyro-l\|gyro_l" "$t" -- src include 2>/dev/null | head -3 | tr '\n' ' ')
    echo "$(date -Is) $t: GYRO.md 'not supported' line: $unsupported; engine source mentions: ${insrc:-none}" >> "$LOG"
    echo "$t" >> "$DONE"
    if [ "$unsupported" = 0 ] || [ -n "$insrc" ]; then
      echo "GYRO-L SUPPORT in $t at $(date -Is) (GYRO.md 'not supported' line $unsupported; source: ${insrc:-none})"
      exit 0
    fi
  done
  sleep 3600
done
