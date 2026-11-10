#!/bin/bash
# gpu1mon.sh — round 11: a PASSIVE log of who uses the RTX 4060 Ti (the helper, which also drives your desktop): nvidia-smi
# pmon every 2 s (per process: type G = graphics / C = compute, SM %), timestamped, to logs/r11/gpu1-pmon.log. Read-only.
WS=/home/USER/ai-speed-testing/strata-compare
echo $$ > $WS/tmp/r11/gpu1mon.pid
nvidia-smi pmon -i 1 -s u -d 2 2>&1 | while IFS= read -r l; do echo "$(date +%s) $l"; done >> $WS/logs/r11/gpu1-pmon.log
