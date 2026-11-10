#!/bin/bash
# Round 3 quiet-watcher: one line per minute, read-only (ps + nvidia-smi + ss).
# Logs whether any Codex process is alive, which processes hold GPU compute memory,
# and which model-server ports listen. Used to prove "15 min with no Codex process
# and no model server on the GPU" before any benchmark starts.
LOG=/home/USER/ai-speed-testing/strata-compare/logs/r3/watch.log
while true; do
  ts=$(date '+%F %T')
  cdx=$(ps -eo pid=,comm=,args= | awk -v me=$$ '$1!=me && ($2=="codex" || $3 ~ /\/codex( |$)/ || $3 ~ /codex-/){printf "%s:%s ", $1, $2}')
  gpu=$(nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>/dev/null | tr '\n' ';')
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null)
  ports=$(ss -ltnH 2>/dev/null | awk '{print $4}' | grep -E '127\.0\.0\.1:|0\.0\.0\.0:|\*:' | grep -vE ':(22|53|631|3000|5432|6379)$' | tr '\n' ' ')
  srv=$(ps -eo pid=,args= | grep -E 'llama-server|strata serve|serve/server\.py|engine/strata|unsloth' | grep -v grep | awk '{print $1}' | tr '\n' ' ')
  echo "$ts codex=[${cdx}] gpu_apps=[${gpu}] gpu_used=${used} servers=[${srv}] ports=[${ports}]" >> "$LOG"
  sleep 60
done
