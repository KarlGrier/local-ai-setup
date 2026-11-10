#!/bin/bash
# wait-c.sh T0 - exits 0 with a reason line when: the v3.1 follow-up's decision.txt is written after T0, or a
# timestamped "work/r23/gap-ud31-dec.sh exit N" line appears after T0, or the Qwen4 watch writes a NOTES line
# ("MM-DD HH:MM QWEN4 HF WATCH: ...") naming open Flash weights after T0. CHECK=1: one check, no wait.
SC=/home/USER/ai-speed-testing/strata-compare; T0=$1; TS=$(date -d "@$T0" '+%F %T'); MD=$(date -d "@$T0" '+%m-%d %H:%M')
check() {
  f=$SC/results/r23/ud31/dec/decision.txt
  [ -f "$f" ] && [ "$(stat -c %Y "$f")" -ge "$T0" ] && { echo "decision written $(date -r "$f" '+%T')"; return 0; }
  l=$(awk -v t="$TS" '/^20[0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9] / && substr($0, 1, 19) >= t && /work\/r23\/gap-ud31-dec\.sh exit [0-9]+$/ {l = $0} END {print l}' $SC/results/r23/gap-series.log)
  [ -n "$l" ] && { echo "series: $l"; return 0; }
  l=$(awk -v t="$MD" '/^[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9] QWEN4 HF WATCH: / && substr($0, 1, 11) >= t && /[Ff]lash/ && !/27B only|not open|gated/ {l = $0} END {print l}' $SC/NOTES.md)
  [ -n "$l" ] && { echo "watch: $l"; return 0; }
  return 1
}
if [ "${CHECK:-0}" = 1 ]; then check && exit 0; echo "nothing yet"; exit 1; fi
until check; do sleep 60; done
