#!/bin/bash
# fetch_extract.sh [FIRST] [LAST] - r21 item 7: download FP4-Local's expert shards (1-14) one at a time, extract each into
# standard ModelOpt NVFP4 per layer (extract.py: CSF scales decoded, round trip checked per matrix), check the shard's
# size and SHA-256 against Hugging Face's listing (hf/tree-tensors.json), then delete the shard.
# The next shard downloads while the current one is extracted (at most two shards on disk).  Stops when a check fails
# or when the disk would drop under 100 GB free.
set -u
WS=/home/USER/ai-speed-testing/strata-compare
HERE=$WS/work/r21/fp4local
DL=$WS/tmp/fp4local/dl            # downloads only (untrusted data); scripts stay in $HERE
ST=$WS/tmp/fp4local/staging
PY=$WS/tmp/fp4local/venv-conv/bin/python
URL=https://huggingface.co/nvidia/Qwen3.8-Flash-Next-FP4-Local/resolve/main/tensors
FIRST=${1:-1}; LAST=${2:-14}
mkdir -p "$DL" "$ST"
cd "$WS" || exit 1

name() { printf 'model-%05d-of-00021.safetensors' "$1"; }
want() { python3 -c "import json,sys;t={e['path']:e for e in json.load(open('$HERE/hf/tree-tensors.json'))};e=t['tensors/'+sys.argv[1]];print(e['size'],e['lfs']['oid'])" "$1"; }
free_gb() { df -B1G --output=avail "$WS" | tail -1 | tr -d ' '; }
log() { echo "$(date +%H:%M:%S) $*"; }

fetch() {   # $1 = shard number; downloads to $DL, checks the size
  local n f size oid
  n=$(name "$1"); f=$DL/$n
  read -r size oid < <(want "$n")
  if [ $(( $(free_gb) - size / 1000000000 - 1 )) -lt 100 ]; then log "STOP: $n would leave < 100 GB free ($(free_gb) GB now)"; return 3; fi
  for try in 1 2 3; do
    curl -sSL --fail --retry 5 --retry-delay 10 -C - -o "$f" "$URL/$n" && break
    log "$n: curl failed (try $try)"
  done
  if [ "$(stat -c %s "$f" 2>/dev/null)" != "$size" ]; then log "STOP: $n size $(stat -c %s "$f" 2>/dev/null) != $size"; return 2; fi
  return 0
}

extract() { # $1 = shard number; extracts, checks the sha256 extract.py computed, deletes the shard
  local n f size oid got
  n=$(name "$1"); f=$DL/$n
  read -r size oid < <(want "$n")
  log "$n: extract"
  "$PY" -I "$HERE/extract.py" "$f" "$ST" || { log "STOP: extract.py failed on $n"; return 2; }
  got=$(python3 -c "import json;print(json.load(open('$ST/s$(printf %02d "$1").json'))['sha256'])")
  if [ "$got" != "$oid" ]; then log "STOP: $n sha256 $got != $oid"; return 2; fi
  rm -f "$f"
  log "$n: done (sha256 ok), staging $(du -sh "$ST" | cut -f1), free $(free_gb) GB"
}

log "fetch shards $FIRST-$LAST, free $(free_gb) GB"
t0=$(date +%s)
fetch "$FIRST" || exit $?
log "$(name "$FIRST"): downloaded in $(( $(date +%s) - t0 )) s"
for s in $(seq "$FIRST" "$LAST"); do
  pid=
  if [ "$s" -lt "$LAST" ]; then
    ( t1=$(date +%s); fetch $((s + 1)) && log "$(name $((s + 1))): downloaded in $(( $(date +%s) - t1 )) s" ) &
    pid=$!
  fi
  extract "$s" || { [ -n "$pid" ] && kill "$pid"; exit 2; }
  if [ -n "$pid" ]; then wait "$pid" || exit $?; fi
done
log "all shards $FIRST-$LAST extracted in $(( $(date +%s) - t0 )) s; staging $(du -sh "$ST" | cut -f1), free $(free_gb) GB"
