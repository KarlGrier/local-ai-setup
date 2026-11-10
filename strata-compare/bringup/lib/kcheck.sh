#!/bin/bash
# kcheck.sh [LABEL] - round 19: the kernel-log check between runs (after the RAM fault). Exit 1 and print why when the
# watcher has seen an error (tmp/r19/KERNEL_ERROR), the watcher is not running, or the kernel is tainted by an oops (D 128),
# a machine check (M 16), a bad page (B 32), a soft lockup (L 16384) or a warning (W 512); else exit 0 and log one line.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
t=$(cat /proc/sys/kernel/tainted); bad=$(( t & (128 | 16 | 32 | 16384 | 512) ))
why=""
[ -f tmp/r19/KERNEL_ERROR ] && why="kernel error seen: $(cat tmp/r19/KERNEL_ERROR)"
[ $bad -ne 0 ] && why="$why tainted $t (bits $bad)"
{ [ -f tmp/r19/kwatch.pid ] && kill -0 "$(cat tmp/r19/kwatch.pid)" 2>/dev/null; } || why="$why kernel-log watcher not running"
if [ -n "$why" ]; then echo "$(date -Is) KCHECK FAIL ${1:-}: $why" | tee -a logs/r19/kwatch.log; exit 1; fi
echo "$(date -Is) kcheck ok ${1:-} (tainted $t)" >> logs/r19/kwatch.log
