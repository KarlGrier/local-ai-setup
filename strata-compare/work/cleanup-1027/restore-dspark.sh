#!/bin/bash
# restore-dspark.sh - 10-27 13:05: the start check showed both DeepSeek configs need the DSpark drafter file. The pack's
# tensors.txt lists it as file 5 and the engine opens every listed file at load, even with --dspark auto (which then does
# not load the drafter on this PC). The deletion list's "never loads in the daily config" was wrong about the file being
# needed. Restore exactly the deleted file: same source and pins as work/ds41/fetch-extra.sh (size + the Hub's LFS
# sha256, read back with O_DIRECT); it is moved into place only if both match. 35 MB/s cap, idle IO.
set -u
D=/home/USER/ai-speed-testing/strata-compare/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF
L=/home/USER/ai-speed-testing/strata-compare/logs/ds41/download.log
B=https://huggingface.co/unsloth/DeepSeek-V4.1-Flash-1017-GGUF/resolve/main
F=dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf SIZE=7976914240 SHA=6ba6ac1b331c540691a209e7fc97dec2a24e295acb1e755c84c7d24a4373927a
say() { echo "$(date '+%F %T') $*" >> $L; }
[ -e "$D/$F" ] && { say "$F: already present - restore not needed"; exit 0; }
say "$F: restore after the 10-27 deletion (the pack needs the file at load)"
for i in 1 2 3 4 5; do
  ionice -c3 curl -s -L --fail --limit-rate 35M -C - -o "$D/$F.part" "$B/$F" && break
  say "$F: curl failed (try $i), resuming"; sleep 20
done
got=$(stat -c %s "$D/$F.part" 2>/dev/null || echo 0)
h=$(ionice -c3 dd if="$D/$F.part" iflag=direct bs=16M status=none 2>/dev/null | sha256sum | cut -d' ' -f1)
if [ "$got" = "$SIZE" ] && [ "$h" = "$SHA" ]; then mv "$D/$F.part" "$D/$F"; say "$F: $SIZE bytes, sha256 matches (restored)"; exit 0
else say "$F: MISMATCH ($got of $SIZE bytes, sha256 $h) - not put in place"; exit 1; fi
