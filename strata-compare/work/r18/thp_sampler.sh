#!/bin/bash
# thp_sampler.sh OUT - round 18: every 20 s, the engine process's AnonHugePages / Rss (MiB) from /proc/PID/smaps_rollup
# (the expert arena's transparent huge pages: the CPU pool's speed depends on them; the kernel decides per run) -> OUT.
# Stops when killed. The engine = the newest process whose executable is named strata.
OUT=$1; : > $OUT
while true; do
  for p in $(pgrep -n -f 'strata (--serve|--pack)'); do
    [ "$(basename "$(readlink /proc/$p/exe 2>/dev/null)")" = strata ] || continue
    awk -v t="$(date +%T)" -v p=$p '/^Rss:/ {r=$2} /^AnonHugePages:/ {h=$2} END {if (r) printf "%s pid %s rss_mib %d anonhuge_mib %d share %.3f\n", t, p, r/1024, h/1024, h/r}' /proc/$p/smaps_rollup 2>/dev/null >> $OUT
  done
  sleep 20
done
