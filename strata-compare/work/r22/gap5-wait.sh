#!/bin/bash
# gap5-wait.sh - 2026-10-21: open the build gap after the last phase 4 baseline (h08), before stage 1. Waits for the
# queue to start h08, sets the hold (no new queue run, stage 1 waits), then waits for h08 to end and opens the gap
# (port_gap4.sh begin: test lock, 8080 stopped). The builds (0.2.2 port, Basalt, strata-vision CUDA) run by hand after.
set -u
SC=/home/USER/ai-speed-testing/strata-compare
QLOG=/home/USER/ai/deep-research/logs/bench2-queue.log
N0=$(wc -l < "$QLOG")
since() { tail -n +$((N0 + 1)) "$QLOG"; }   # only lines written after this script started (the HH:MM lines carry no date)
until since | grep -q '/ h08: running'; do sleep 60; done
echo "phase 4 gap: builds after h08 (set $(date '+%F %T'))" > /home/USER/ai/deep-research/tmp/bench2.hold
echo "$(date '+%F %T') hold set while h08 runs"
until since | grep -q '^[0-9:]* h08: rc'; do sleep 60; done
echo "$(date '+%F %T') h08 ended: $(since | grep '^[0-9:]* h08: rc' | tail -1)"
bash $SC/work/r22/port_gap4.sh begin "builds: 0.2.2 port, Basalt, strata-vision CUDA"
