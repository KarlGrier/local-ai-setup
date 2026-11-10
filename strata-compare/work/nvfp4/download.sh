#!/bin/bash
# download.sh - 2026-10-13, prep for the port after Wednesday's release (not the port itself; setup is not run):
# the NVFP4 GPTQ pack Strata v0.1.44's setup.py pins for `--family nvfp4 --model NVFP4` (sergqwer's pack,
# Maximilian228/Qwen3.8-Flash-Next-NVFP4-GPTQ-Strata @ 640a1db9), its 12 files from setup.py's NVFP4_REPOS
# (tmp/nvfp4/pinned-gptq.json, extracted from `git show v0.1.44:setup.py`), from the URL setup builds
# (https://huggingface.co/<repo>/resolve/<revision>/<path>), into setup's layout: models/<owner>--<repo>/<path>.
# The repository's mtp/ folder is not downloaded (setup does not either). Each file is checked against setup's size
# and SHA-256; a match gets setup's finish mark (<name>.done = "sha256 <hex>") and is made read-only. New files only:
# nothing existing under models/ is touched (the shared ple-fp8 / token-embd files differ from models/r11's by size).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
REPO=Maximilian228/Qwen3.8-Flash-Next-NVFP4-GPTQ-Strata; REV=640a1db97446ddd5e89d2b70ecd0297987192c93
DST=models/Maximilian228--Qwen3.8-Flash-Next-NVFP4-GPTQ-Strata
LOG=logs/nvfp4/download.log; PIN=tmp/nvfp4/pinned-gptq.json
[ -e $DST ] && { echo "$(date -Is) $DST exists - stop (nothing overwritten)" >> $LOG; exit 1; }
mkdir -p $DST
echo "$(date -Is) START $REPO@$REV -> $DST; disk free $(df -B1 $WS | tail -1 | awk '{print $4}') bytes" >> $LOG
get() {   # get PATH
  local rel=$1 dst=$DST/$1 size sha got
  size=$(jq -r --arg p "$rel" '.[$p][1]' $PIN); sha=$(jq -r --arg p "$rel" '.[$p][2]' $PIN)
  mkdir -p "$(dirname $dst)"
  echo "$(date -Is) start $rel ($size bytes)" >> $LOG
  for try in 1 2 3 4 5 6; do
    curl -sfL -C - --retry 5 --retry-delay 10 "https://huggingface.co/$REPO/resolve/$REV/$rel" -o $dst && break
    echo "$(date -Is) retry $try $rel (exit $?, have $(stat -c %s $dst 2>/dev/null) bytes)" >> $LOG; sleep 20
  done
  if [ "$(stat -c %s $dst 2>/dev/null)" != "$size" ]; then
    echo "$(date -Is) SIZE MISMATCH $rel: $(stat -c %s $dst 2>/dev/null) bytes, want $size" >> $LOG; return
  fi
  got=$(sha256sum $dst | cut -d' ' -f1)
  if [ "$got" = "$sha" ]; then
    printf 'sha256 %s' "$sha" > $dst.done; chmod a-w $dst $dst.done
    echo "$(date -Is) OK $rel $size bytes sha256 $got" >> $LOG
  else echo "$(date -Is) SHA MISMATCH $rel got $got want $sha" >> $LOG; fi
}
for p in $(jq -r 'keys[]' $PIN); do get $p & done
wait
n=$(grep -c " OK " $LOG)
echo "$(date -Is) DONE: $n / 12 OK; pack $(du -sb $DST | cut -f1) bytes on disk; disk free $(df -B1 $WS | tail -1 | awk '{print $4}') bytes" >> $LOG
