#!/bin/bash
# gap16-wait.sh - starts gap16.sh once the GPU queue before it has ended (gpu-chain-bp90: Basalt check + K4 tries;
# gpu-chain-fix1c: the Fix 1c replays) and no port gap is open (a kernel error leaves one open: then nothing starts).
SC=/home/USER/ai-speed-testing/strata-compare
LOG=$SC/results/r22/basalt-pr90/chain.log
say() { echo "$(date '+%m-%d %H:%M:%S') gap16-wait: $*" >> "$LOG"; }
say "waiting for gpu-chain-bp90 and gpu-chain-fix1c"
until ! systemctl --user is-active --quiet gpu-chain-bp90.service && ! systemctl --user is-active --quiet gpu-chain-fix1c.service; do sleep 60; done
[ -s $SC/tmp/port-gap.lockpid ] && { say "a port gap is still open - gap 16 not started"; notify-send -a "GPU queue" "Gap 16 not started" "A port gap is still open" 2> /dev/null; exit 1; }
say "starting gap 16"
bash $SC/work/r22/gap16.sh 8>&- 9>&-
say "gap 16 ended rc $?"
notify-send -a "GPU queue" "Gap 16 done" "results/r22/gap16/summary.txt" 2> /dev/null || true
