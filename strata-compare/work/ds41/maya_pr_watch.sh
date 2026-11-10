#!/bin/bash
# maya_pr_watch.sh - 10-24 (the user: "watch Maya PR #453 (GSQ-RCO loading): if it lands, Maya itself could be A/B'd on
# our files"). Hourly, read-only: GitHub's public API without any login or key (curl, not gh). Logs the PR's state to
# logs/ds41/maya-pr-453.log; when it is merged (or closed without merging) a desktop alert and the watch ends.
# User service maya-pr-watch.service.
L=/home/USER/ai-speed-testing/strata-compare/logs/ds41/maya-pr-453.log
U=https://api.github.com/repos/mw00/project-maya/pulls/453
while :; do
  J=$(curl -s -m 30 -H "Accept: application/vnd.github+json" "$U")
  S=$(python3 -c 'import json,sys
try:
    d = json.loads(sys.stdin.read())
    print(d.get("state", "?"), "merged" if d.get("merged") else "not-merged", (d.get("merged_at") or d.get("closed_at") or "-"), d.get("head", {}).get("sha", "?")[:12])
except Exception:
    print("? ? - ?")' <<< "$J")
  echo "$(date -Is) PR #453: $S" >> $L
  read -r STATE MERGED WHEN SHA <<< "$S"
  if [ "$MERGED" = merged ]; then
    notify-send -a "DeepSeek-V4.1" -u critical "Maya PR #453 merged" "GSQ-RCO loading landed in Project Maya ($WHEN): Maya itself could now be A/B'd on our IQ2_XXS files." 2> /dev/null
    exit 0
  fi
  if [ "$STATE" = closed ]; then
    notify-send -a "DeepSeek-V4.1" "Maya PR #453 closed without merging" "Closed $WHEN; the watch ends." 2> /dev/null
    exit 0
  fi
  sleep 3600
done
