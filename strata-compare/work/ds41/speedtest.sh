#!/bin/bash
# speedtest.sh - 10-23 (the user, DS4.1 step 4): the first speed test of DeepSeek-V4.1-Flash, in a gap (no research run).
# Strata v0.2.4 STOCK strata-dsv41 (engine-v024-ds41), IST-DAS 2.00 bpw (IQ2_XXS), both cards (--tp 2, setup's plan),
# lossless only (configs/DS41-v024-stock.json: prompt skip 0, disk skip off, no route bias in this engine). Its own
# server (strata-v024/serve/server.py) on 127.0.0.1:8085. work/ds41/speed.py: decode on W1-W3, prompt reading at 4K and
# 20K, disk reads per request. Placement (VRAM / RAM / SSD) from the engine's start lines + nvidia-smi + RSS; peak RAM from
# a 2-second monitor. Guard: MemAvailable < 12 GB, the 5080 under 300 MiB free, or a failed kernel check -> the engine is
# killed by PID and the test ends. 8080: work/r22/port_gap4.sh begin ... end (P021m back, checked, logged). No quality suite.
set -u
SC=/home/USER/ai-speed-testing/strata-compare
CFG=$SC/configs/DS41-v024-stock.json
LOGF=$SC/logs/ds41/engine-DS41-v024.log
OUT=$SC/results/ds41/speed-v024-$(date +%m%d-%H%M); mkdir -p $OUT
PORT=8085; URL=http://127.0.0.1:$PORT
S=$OUT/summary.txt
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
mem() { awk '/MemAvailable/{printf "%.1f", $2/1048576}' /proc/meminfo; }
eng_pids() { pgrep -x strata-dsv41; }          # the process name (no command-line pattern)
vram() { nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ';'; }
rss_mb() { local r=0 p; for p in $(eng_pids); do r=$((r + $(awk '/VmRSS/{print $2}' /proc/$p/status 2>/dev/null || echo 0))); done; echo $((r / 1024)); }

say "DS4.1 speed test: v0.2.4 stock strata-dsv41, IST-DAS 2.00 bpw (IQ2_XXS), both cards (--tp 2), prompt skip 0, disk skip off -> $OUT"
bash $SC/bringup/lib/kcheck.sh ds41-before || { say "kernel check failed before the test - not started"; exit 1; }
$SC/work/r22/port_gap4.sh begin "DS4.1 speed test (v0.2.4 stock, IQ2_XXS)" >> $S 2>&1 || { say "port_gap4 begin failed"; exit 1; }
say "before: MemAvailable $(mem) GB; vram $(vram)"
OFF=$(stat -c %s $LOGF 2>/dev/null || echo 0)
T0=$(date +%s)
setsid nohup env -u HTTP_PROXY -u HTTPS_PROXY $SC/.venv/bin/python $SC/strata-v024/serve/server.py --engine strata \
  --config $CFG --host 127.0.0.1 --port $PORT > $OUT/server.out 2>&1 < /dev/null &
SPID=$!; echo $SPID > $SC/tmp/port-test-server.pid

guard() {
  local n=0 m v f0
  echo "time memavail_gb engine_rss_mb gpu0_used gpu0_free gpu1_used gpu1_free (MiB)" > $OUT/monitor.tsv
  while kill -0 $SPID 2>/dev/null; do
    m=$(mem)
    v=$(nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader,nounits | tr -d ' ' | tr '\n' ' ')
    echo "$(date +%T) $m $(rss_mb) $v" >> $OUT/monitor.tsv
    f0=$(echo $v | cut -d' ' -f1 | cut -d, -f2)
    if awk "BEGIN{exit !($m < 12)}"; then echo "GUARD: MemAvailable $m GB < 12" > $OUT/GUARD; break; fi
    if [ -n "$f0" ] && [ "$f0" -lt 300 ]; then echo "GUARD: RTX 5080 free $f0 MiB < 300" > $OUT/GUARD; break; fi
    n=$((n + 1))
    if [ $((n % 30)) = 0 ] && ! bash $SC/bringup/lib/kcheck.sh ds41-run > /dev/null 2>&1; then echo "GUARD: kernel check failed" > $OUT/GUARD; break; fi
    sleep 2
  done
  if [ -e $OUT/GUARD ]; then
    for p in $(eng_pids); do kill -9 $p; done
    kill -TERM $SPID 2>/dev/null
  fi
}
guard & GPID=$!

ready=""
for i in $(seq 1800); do
  [ -e $OUT/GUARD ] && break
  kill -0 $SPID 2>/dev/null || break
  [ "$(curl -s -m 3 -o /dev/null -w '%{http_code}' $URL/health)" = 200 ] && { ready=1; break; }
  sleep 2
done
tail -c +$((OFF + 1)) $LOGF > $OUT/engine-start.log 2>/dev/null
if [ -n "$ready" ]; then
  say "ready after $(( $(date +%s) - T0 )) s: MemAvailable $(mem) GB, engine RSS $(rss_mb) MB; vram $(vram)"
  grep -i -E "expert|store|vram|ram |dspark|--tp|tp=|layers|ssd|engram|mmap|reserve|threads|context" $OUT/engine-start.log | head -60 > $OUT/placement.txt
  timeout 10800 $SC/.venv/bin/python $SC/work/ds41/speed.py $URL $OUT 2 > $OUT/client.out 2>&1
  say "requests done (rc $?): $(grep -c 'tok/s' $OUT/client.out) responses"
else
  say "NOT READY: $(cat $OUT/GUARD 2>/dev/null || echo 'the server stopped or did not answer in 3600 s'); last lines:"
  tail -n 15 $OUT/server.out | tee -a $S
fi
tail -c +$((OFF + 1)) $LOGF > $OUT/engine-run.log 2>/dev/null
kill -INT $SPID 2>/dev/null
for i in $(seq 90); do [ -z "$(eng_pids)" ] && ! kill -0 $SPID 2>/dev/null && break; sleep 2; done
for p in $(eng_pids); do kill -TERM $p; done
sleep 3; for p in $(eng_pids); do kill -9 $p; done
kill $GPID 2>/dev/null
[ -e $OUT/GUARD ] && say "$(cat $OUT/GUARD)"
awk 'NR > 1 { if (min == "" || $2 < min) min = $2; if ($3 > rss) rss = $3; split($4, a, ","); split($5, b, ","); if (a[1] > g0) g0 = a[1]; if (b[1] > g1) g1 = b[1] }
     END { printf "monitor: lowest MemAvailable %s GB, peak engine RSS %d MB, peak VRAM used 5080 %d MiB / 4060 Ti %d MiB\n", min, rss, g0, g1 }' $OUT/monitor.tsv | tee -a $S
$SC/work/r22/port_gap4.sh end >> $S 2>&1 && say "8080 back on P021m" || say "port_gap4 end FAILED - check 8080"
bash $SC/bringup/lib/kcheck.sh ds41-after && say "kcheck clean" || say "KCHECK FAILED after the test"
[ -s $OUT/ds41.jsonl ] && $SC/.venv/bin/python - $OUT >> $S <<'EOF'
import json, sys, statistics as st
o = sys.argv[1]
recs = [json.loads(l) for l in open(f"{o}/ds41.jsonl")]
disk = {(d["id"], d["rep"]): d for d in map(json.loads, open(f"{o}/disk.jsonl"))}
for key in ("P4K", "P20K", "W1-think", "W2-code", "W3-research"):
    rs = [r for r in recs if r["id"] == key]
    if not rs:
        continue
    if key.startswith("P"):
        print(f"{key}: prompt {[r['prompt_tokens'] for r in rs]} tokens, {[r.get('prompt_tps') for r in rs]} tok/s (TTFT {[r['ttft_s'] for r in rs]} s), "
              f"disk {[disk.get((r['id'], r['rep']), {}).get('disk_read_gb') for r in rs]} GB")
    else:
        print(f"{key}: decode {[r.get('decode_tps') for r in rs]} tok/s (mean {st.mean([r['decode_tps'] for r in rs if r.get('decode_tps')]):.2f}), "
              f"{[r['completion_tokens'] for r in rs]} tokens, prompt {[r['prompt_tokens'] for r in rs]} at {[r.get('prompt_tps') for r in rs]} tok/s, "
              f"finish {[r['finish'] for r in rs]}, disk {[disk.get((r['id'], r['rep']), {}).get('disk_gb_per_token') for r in rs]} GB/token")
w = [r["decode_tps"] for r in recs if r["id"][:2] in ("W1", "W2", "W3") and r.get("decode_tps")]
if w:
    print(f"W1-W3 decode mean {st.mean(w):.2f} tok/s over {len(w)} responses")
EOF
say "done"
notify-send -a "DeepSeek-V4.1" "DS4.1 speed test done" "$(tail -n 3 $S | cut -c1-200)" 2> /dev/null || true
