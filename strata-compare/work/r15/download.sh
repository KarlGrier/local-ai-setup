#!/bin/bash
# download.sh — Round 15: unsloth Q8_0 (6 shards) + UD-Q5_K_XL (4 unique shards; shards 2 and 3 are Q8_0's blobs,
# hard-linked after their SHA-256 matches) into models/r15/, each shard checked against its LFS SHA-256.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
LOG=logs/r15/download.log; mkdir -p logs/r15 models/r15/Q8_0 models/r15/UD-Q5_K_XL
B=https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF/resolve/38bb39ee97821de2c9009abb7e93950eec396e66
curl -s --max-time 60 "https://huggingface.co/api/models/unsloth/Qwen3.8-Flash-Next-GGUF/tree/38bb39ee97821de2c9009abb7e93950eec396e66/Q8_0" > tmp/r15/tree-q8.json
curl -s --max-time 60 "https://huggingface.co/api/models/unsloth/Qwen3.8-Flash-Next-GGUF/tree/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q5_K_XL" > tmp/r15/tree-q5.json
sha() { python3 -I -c "import json,sys; print({i['path']:i['lfs']['oid'] for i in json.load(open(sys.argv[1])) if 'lfs' in i}[sys.argv[2]])" $1 $2; }
get() {   # get REL DEST TREE
  local rel=$1 dst=$2 tree=$3 want; want=$(sha $tree $rel)
  echo "$(date -Is) start $rel" >> $LOG
  for try in 1 2 3 4 5; do
    curl -sfL -C - --retry 5 --retry-delay 10 "$B/$rel" -o $dst && break
    echo "$(date -Is) retry $try $rel (exit $?)" >> $LOG; sleep 15
  done
  local got; got=$(sha256sum $dst | cut -d' ' -f1)
  if [ "$got" = "$want" ]; then chmod a-w $dst; echo "$(date -Is) OK $rel $(stat -c %s $dst) bytes sha256 $got" >> $LOG
  else echo "$(date -Is) SHA MISMATCH $rel got $got want $want" >> $LOG; fi
}
for n in 1 2 3 4 5 6; do get Q8_0/Qwen3.8-Flash-Next-Q8_0-0000$n-of-00006.gguf models/r15/Q8_0/Qwen3.8-Flash-Next-Q8_0-0000$n-of-00006.gguf tmp/r15/tree-q8.json & done
for n in 1 4 5 6; do get UD-Q5_K_XL/Qwen3.8-Flash-Next-UD-Q5_K_XL-0000$n-of-00006.gguf models/r15/UD-Q5_K_XL/Qwen3.8-Flash-Next-UD-Q5_K_XL-0000$n-of-00006.gguf tmp/r15/tree-q5.json & done
wait
for n in 2 3; do   # the shared blobs: the same LFS SHA-256 in both folders -> a hard link
  q8=models/r15/Q8_0/Qwen3.8-Flash-Next-Q8_0-0000$n-of-00006.gguf q5=models/r15/UD-Q5_K_XL/Qwen3.8-Flash-Next-UD-Q5_K_XL-0000$n-of-00006.gguf
  if [ "$(sha tmp/r15/tree-q8.json Q8_0/$(basename $q8))" = "$(sha tmp/r15/tree-q5.json UD-Q5_K_XL/$(basename $q5))" ] && grep -q "OK Q8_0/$(basename $q8)" $LOG; then
    ln -f $q8 $q5 && echo "$(date -Is) LINK $q5 = $q8 (same LFS sha256)" >> $LOG
  else echo "$(date -Is) NOT SHARED $n: download separately" >> $LOG; fi
done
echo "$(date -Is) DONE; disk free $(df -BG $WS | tail -1 | awk '{print $4}')" >> $LOG
