#!/bin/bash
# get-lucebox-dspark.sh (11-03, Karl: "Download Lucebox's DSpark-draft-Q2K-Q4K (~4.9 GB) and build its pack. Keep the
# Q8_0 drafter."): Lucebox/DeepSeek-V4.1-Flash-DSpark-GGUF at revision 11403d34 (MIT), the Q2K-Q4K file, resumable,
# 25 MB/s, low I/O priority, into models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/lucebox-dspark/ (its own folder), the
# sha256 from the repo's LFS id / model card checked. Starts once the splice rerun (user unit sweep-splice58) has ended:
# that rerun reads the SSD hard. Stops if the disk would go under 105 GB free. Log: logs/ds41/get-lucebox-dspark.log.
set -u
D=/home/USER/ai-speed-testing/strata-compare/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/lucebox-dspark
F=$D/DeepSeek-V4.1-Flash-DSpark-draft-Q2K-Q4K.gguf; LOG=/home/USER/ai-speed-testing/strata-compare/logs/ds41/get-lucebox-dspark.log
U="https://huggingface.co/Lucebox/DeepSeek-V4.1-Flash-DSpark-GGUF/resolve/11403d34ca19eb1ac2b532b5a05e61a4b0c61485/DeepSeek-V4.1-Flash-DSpark-draft-Q2K-Q4K.gguf"
SIZE=4923041440; SHA=5efffdb5ab4769bac7192fd2ce7c08cfa37945cad37be0825526c83139ef200a
say() { echo "$(date '+%F %T') $*" >> $LOG; }
for i in $(seq 1080); do systemctl --user is-active -q sweep-splice58.service || break; sleep 10; done
free_gb=$(( $(df -B1 --output=avail $D | tail -1) / 1000000000 ))
[ $free_gb -ge $(( 105 + SIZE / 1000000000 + 1 )) ] || { say "only $free_gb GB free: not downloading"; exit 1; }
say "start ($free_gb GB free)"
ionice -c3 nice -n 10 curl -s -L --fail --retry 5 --retry-delay 20 -C - --limit-rate 25M -o $F.part "$U"; rc=$?
got=$(stat -c %s $F.part 2>/dev/null || echo 0); say "curl rc $rc, $got of $SIZE bytes"
[ "$got" = $SIZE ] || { say "size wrong - kept as .part"; exit 1; }
[ "$(sha256sum $F.part | cut -d' ' -f1)" = $SHA ] || { say "SHA256 MISMATCH - kept as .part"; exit 1; }
mv $F.part $F && chmod a-w $F && say "sha256 OK -> $F"
