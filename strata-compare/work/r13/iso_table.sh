#!/bin/bash
# iso_table.sh — round 11: per onereq.sh run in the batch log, each request's decode time and the host's wait for the helper
grep -A12 'RUN: work/r13/onereq.sh' /home/USER/ai-speed-testing/strata-compare/logs/r13/batch.log | grep -E 'RUN|generated in|CUDA1' | \
  sed -E 's/.*RUN: work\/r11\/onereq.sh ([A-Za-z0-9-]+).*/== \1/; s/strata serve: prompt ([0-9]+) tokens.*, ([0-9]+) generated in ([0-9]+) ms.*/prompt \1 gen \2 dec \3 ms/; s/.*CUDA1: ([0-9]+) expert entries.* ([0-9]+) ms waiting.*/   helper entries \1 wait \2 ms/'
