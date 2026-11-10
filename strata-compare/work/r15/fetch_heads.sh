#!/bin/bash
# fetch_heads.sh REPO PREFIX — the first 16 MB of every .gguf shard under PREFIX in REPO (headers only)
set -u
REPO=$1; PREFIX=$2
WS=/home/USER/ai-speed-testing/strata-compare
OUT=$WS/tmp/r15/heads/$(echo $REPO | tr / _)
mkdir -p "$OUT"
curl -s --max-time 30 "https://huggingface.co/api/models/$REPO/tree/main?recursive=true" | python3 -I -c "
import json,sys
for it in json.load(sys.stdin):
    if it.get('type')=='file' and it['path'].endswith('.gguf') and it['path'].startswith(sys.argv[1]): print(it['path'])
" "$PREFIX" | while read -r p; do
  f="$OUT/$p"; mkdir -p "$(dirname "$f")"
  [ -s "$f" ] && continue
  curl -sL --max-time 120 -r 0-16777215 "https://huggingface.co/$REPO/resolve/main/$p" -o "$f" || echo "FAIL $p"
  echo "$(stat -c %s "$f") $p"
done
