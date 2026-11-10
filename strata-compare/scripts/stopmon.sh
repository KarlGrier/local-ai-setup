#!/bin/bash
# stop the resource monitor(s) whose output prefix contains $1 (never matches this script's own command line)
for p in $(pgrep -f 'scripts/monitor[.]py'); do tr '\0' ' ' < /proc/$p/cmdline | grep -q -- "monitor-$1" && kill $p; done; true
