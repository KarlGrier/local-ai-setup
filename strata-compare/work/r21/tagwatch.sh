#!/bin/bash
# tagwatch.sh - 2026-10-17, your standing request: check hourly for a new final Strata release tag (read-only). Since
# 10-23 (the user: "make the queue and tag watch decide by what changed") the decision is work/r22/tagcheck.sh's: a
# release that changes nothing on the engine/server path raises the baseline itself (NOTES.md line) and the watch
# carries on; one that changes the engine or server (10-24: our served Qwen build's path only, work/r22/qwenpath.py) is
# flagged by tagcheck.sh (desktop alert + NOTES.md line, once) and the watch carries on too ("FLAGGED ..." in
# tagwatch.out) - 10-31 (Karl): a new release doesn't pause work on the served build; only installing or switching
# engines waits for his decision, after which: work/r22/tagcheck.sh --accept <tag>. (10-23 to 10-31 the watch ended.)
# The baseline: ~/ai/deep-research/run/strata-baseline-tag (shared with the research queue). Log: logs/r21/tagwatch.log.
# 10-27 (Karl: "if Strata adds Qwen4 support before then, tell Karl"): every new tag's lines that name Qwen4 - not our
# Flash-Next's preview arch qwen4exp / qwen4_exp - are compared with the last scanned tag's; new ones -> a desktop alert
# and logs/r21/qwen4-watch.log. Reads the tags tagcheck.sh fetched into the strata checkout (read-only).
REPO=/home/USER/ai-speed-testing/strata-compare/strata
Q4LOG=${Q4LOG:-/home/USER/ai-speed-testing/strata-compare/logs/r21/qwen4-watch.log}
Q4TAG=${Q4TAG:-/home/USER/ai-speed-testing/strata-compare/logs/r21/qwen4-scan-tag}
Q4PAT=${Q4PAT:-'qwen[-_ ]?4(?![0-9]|\.[0-9]|[-_ ]?exp)'}
q4lines() { git -C "$REPO" grep -h -i -P "$Q4PAT" "$1" -- . ':!bench' ':!data' 2>/dev/null | sort -u; }
q4scan() {   # $1 = the newest tag
  local last new
  last=$(cat "$Q4TAG" 2>/dev/null); [ -n "$last" ] || { echo "$1" > "$Q4TAG"; return; }
  [ "$1" = "$last" ] && return
  new=$(comm -13 <(q4lines "$last") <(q4lines "$1"))
  if [ -n "$new" ]; then
    { echo "$(date -Is) Strata $1 names Qwen4 in $(echo "$new" | wc -l) new line(s) since $last:"; echo "$new" | cut -c1-200 | head -20; } >> "$Q4LOG"
    notify-send -a "Strata tag watch" -u critical "Strata $1 mentions Qwen4" "$(echo "$new" | wc -l) new line(s) name Qwen4 since $last - possibly Qwen4 support. Details: logs/r21/qwen4-watch.log" 2> /dev/null || true
  else
    echo "$(date -Is) Strata $1: no new Qwen4 lines since $last" >> "$Q4LOG"
  fi
  echo "$1" > "$Q4TAG"
}
[ -n "${Q4_TEST:-}" ] && return 0 2> /dev/null   # (sourced by a test: the functions only)
while :; do
  R=$(/home/USER/ai-speed-testing/strata-compare/work/r22/tagcheck.sh --who "tag watch")
  T=""
  case "$R" in SAME*) read -r _ T <<< "$R" ;; RAISED*) read -r _ _ T <<< "$R" ;; FLAG*) read -r _ T _ <<< "$R" ;; esac
  [ -n "$T" ] && q4scan "$T"
  case "$R" in
    FLAG*)
      read -r _ T B N WHY <<< "$R"
      [ "$T" = "${FLAGGED:-}" ] || echo "FLAGGED $T at $(date -Is): $N files on our Qwen build's path changed since $B (${WHY#*: }) - for Karl's decision; the watch and the queue carry on"
      FLAGGED=$T ;;
    RAISED*) echo "$(date -Is) $R (nothing on our Qwen build's path changed; baseline raised)" ;;
  esac
  sleep 3600
done
