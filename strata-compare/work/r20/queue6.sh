#!/bin/bash
# queue6.sh - 2026-10-14: after the D chain (pid given), the b8 arm again with --vram-reserve-mib 1213 (the first was
# guard-stopped on the 5080's 300 MiB floor), then the tables of all four arms.
cd /home/USER/ai-speed-testing/strata-compare
while kill -0 "$1" 2>/dev/null; do sleep 10; done
ARMS="b8" CHECKS=0 work/r20/d_conc.sh > logs/r20/d_conc_b8.console 2>&1
for k in decode agent; do suite/.venv/bin/python work/r20/conc.py table --kind $k --arms base,b8,b8-nohelp,b8-mtp; done > results/r20/conc/tables.md 2>&1
