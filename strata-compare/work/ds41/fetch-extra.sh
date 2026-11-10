#!/bin/bash
# fetch-extra.sh - 10-23: the two shared files v0.2.4's stock pack recipe for the IST-DAS sets needs beside the shards
# (setup.py "shared"): Unsloth's UD-Q8_K_XL shard 1 (5.8 MB, only the Engram hash metadata - pack_gguf.py --engram-meta)
# and the DSpark drafter (8.0 GB, --dspark-gguf), from unsloth/DeepSeek-V4.1-Flash-1017-GGUF. 35 MB/s cap; run in a user
# unit with MemoryHigh; checksums (setup.py's pins = the Hub's LFS sha256) read back with O_DIRECT (no page cache).
set -u
D=/home/USER/ai-speed-testing/strata-compare/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF
L=/home/USER/ai-speed-testing/strata-compare/logs/ds41/download.log
B=https://huggingface.co/unsloth/DeepSeek-V4.1-Flash-1017-GGUF/resolve/main
say() { echo "$(date '+%F %T') $*" >> $L; }
ok=1
while read -r path size sha; do
  f=$D/$(basename $path)
  for i in 1 2 3 4 5; do
    curl -s -L --fail --limit-rate 35M -C - -o "$f.part" "$B/$path" && break
    say "$(basename $path): curl failed (try $i), resuming"; sleep 20
  done
  got=$(stat -c %s "$f.part" 2>/dev/null || echo 0)
  h=$(dd if="$f.part" iflag=direct bs=16M status=none 2>/dev/null | sha256sum | cut -d' ' -f1)
  if [ "$got" = "$size" ] && [ "$h" = "$sha" ]; then mv "$f.part" "$f"; say "$(basename $path): $size bytes, sha256 matches"
  else ok=0; say "$(basename $path): MISMATCH ($got of $size bytes, sha256 $h)"; fi
done <<'LIST'
UD-Q8_K_XL/DeepSeek-V4.1-Flash-1017-UD-Q8_K_XL-00001-of-00009.gguf 5780589 cc15d470afcb030558bbc4d8e2ccd840182e2e95de1a95198138efe63a5fd99f
dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf 7976914240 6ba6ac1b331c540691a209e7fc97dec2a24e295acb1e755c84c7d24a4373927a
LIST
[ $ok = 1 ] && say "extra files done ($(df -h --output=avail $D | tail -1 | tr -d ' ') free)" || { notify-send -a "DeepSeek-V4.1 download" -u critical "DeepSeek extra files failed" "see logs/ds41/download.log" 2>/dev/null; exit 1; }
