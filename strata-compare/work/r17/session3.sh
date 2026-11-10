#!/bin/bash
# session3.sh - r17b (2026-10-10): the community benchmark on the RTX 5080 alone, added to the r17 report. Same harness,
# prompts and method as session.sh step 1 (cb_bench.py, prompts/r17/cb-prompts.json, needle_bench 32k / 128k x 3 depths);
# configs = cb-stock / cb-c16 with CUDA_VISIBLE_DEVICES = the 5080 only and no --expert-cache-device1 (everything else the
# same). Standing rules: one model server at a time, 127.0.0.1, the guard's 20 GiB / 300 MiB floors, cold model page cache
# per server, stock clocks; ends with C*16 on 8080 and a fresh 48-hour passive monitor.
# (Started after a reboot: nothing on 8080, no monitor, no SearXNG.)
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
export RB_CACHE=$WS/tmp/r17; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
P=.venv/bin/python; C=work/r17/cfg; R=results/r17
step() { echo "=== $(date -Is) $*"; }
startlines() {   # startlines LOG FROMLINE OUT: the engine's start lines that matter for the reports (as in session.sh)
  tail -n +$(( $2 + 1 )) "$1" | grep -E 'expert cache|slots|resident|budget|page-lock|file tier|unbuffered|lend|WARNING|CPU share|VRAM free|max context|arena|refus' | cut -c1-400 | head -60 > "$3"
}
nlines() { wc -l < "$1" 2>/dev/null || echo 0; }

step "start: $(nvidia-smi --query-gpu=index,memory.used,memory.free,power.limit,clocks.max.sm --format=csv,noheader | tr '\n' ' '); MemAvailable $(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo) MiB; swap used $(free -m | awk '/Swap/ {print $3}') MiB"
for E in bringup/out/r16/engine-stock/strata engine-cstar16/strata; do echo "engine $E sha $(sha256sum $E | cut -c1-12)"; done
pgrep -af '/strata --serve' && { echo "a model server is running: refusing"; exit 1; }

for L in cb-stock-5080 cb-c16-5080; do
  CFG=$C/$L.json; ELOG=$($P -c "import json; print(json.load(open('$CFG'))['log'])"); N0=$(nlines $ELOG)
  step "$L"
  bringup/lib/with_server.sh r17-$L $CFG -- "$P work/r17/cb_bench.py --label $L --out $R/$L.json; \
    $P bringup/out/r16/strata-stock/tools/needle_bench.py --url http://127.0.0.1:8081 --lengths 32k,128k --depths 10,50,90 --out $R/$L-needles.json" \
    || echo "STEP $L FAILED"
  startlines $ELOG $N0 $R/$L-start.txt
  tail -1 bringup/out/logs/guard/summary.txt
done

step "phase end"
bringup/lib/phase_end.sh r17b keep
(setsid nohup $P work/r13/uptime_monitor.py --out logs/r17/uptime-c16b > /dev/null 2>&1 < /dev/null &)
sleep 5; echo "monitor: $(cat logs/r17/uptime-c16b/monitor.pid 2>/dev/null)"
echo "SearXNG 8888: $(ss -H -ltn '( sport = :8888 )' | wc -l) listener(s)"
step "session3 done"
