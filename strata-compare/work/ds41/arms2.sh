#!/bin/bash
# arms2.sh - 10-23 23:40: the rerun of the first chain's two invalid arms (work/ds41/arms.sh: the s70 and DSpark arms were
# answered by the s60 arm's server, still alive on 127.0.0.1:8085 - their folders are marked -INVALID). Same plan as the
# user's: the RAM store at 70 GB (growth floor 16 GB, soft stop below 15 GB available, hard stop 12 GB), then DSpark forced
# on at whichever of 60 / 70 GB gave the better W1-W3 decode (the valid s60 arm: results/ds41/arm-s60-1023-2221). One gap;
# speedarm.sh now stops its server with SIGTERM (+ SIGKILL), refuses a busy port and checks the server it measures is
# its own. Kernel error -> the chain stops, 8080 left stopped, alert. P021m back on 8080 at the end.
set -u
SC=/home/USER/ai-speed-testing/strata-compare
BASE=$SC/configs/DS41-v024-stock.json
L=$SC/logs/ds41/arms2.log
R=$SC/results/ds41/arms2-summary-$(date +%m%d).txt
D60=$SC/results/ds41/arm-s60-1023-2221
say() { echo "=== $(date '+%F %T') $*" | tee -a $R; }
mk() {   # mk NAME STORE(GB|auto) DSPARK(auto|on): configs/DS41-v024-NAME.json from the stock config
  python3 - "$BASE" "$SC/configs/DS41-v024-$1.json" "$2" "$3" <<'EOF'
import json, sys
c = json.load(open(sys.argv[1]))
out, store, dsp = sys.argv[2], sys.argv[3], sys.argv[4]
if store != "auto":
    c["args"] += ["--ssd-cache", store]
    c["env"]["DS4_STORE_FLOOR_GB"] = "16"
if dsp == "on":
    c["args"][c["args"].index("--dspark") + 1] = "on"
c["_comment"] = (f"10-23 arm (the user): RAM store {store} GB (explicit; floor 16 GB for its growth), DSpark {dsp}. "
                 "Otherwise the stock test's config: ") + c["_comment"]
json.dump(c, open(out, "w"), indent=1)
EOF
}
mean() {
  python3 -c '
import json, sys, statistics as st
r = [json.loads(l) for l in open(sys.argv[1] + "/ds41.jsonl")]
w = [x["decode_tps"] for x in r if x["id"][:2] in ("W1", "W2", "W3") and x.get("decode_tps")]
print(f"{st.mean(w):.3f}" if len(w) == 6 else "")' "$1" 2> /dev/null
}
clean() { [ ! -e "$1/GUARD" ] && [ ! -e "$1/SOFTSTOP" ] && [ -n "$(mean "$1")" ] && ! grep -q "not started" "$1/summary.txt"; }
kernel_stop() { grep -q -i "kernel" "$1/GUARD" 2> /dev/null || grep -q -i -E "KCHECK FAILED|kernel check failed" "$1/summary.txt" 2> /dev/null; }
halt_kernel() {
  say "KERNEL ERROR in arm $1 - chain stopped, 8080 left stopped (the user's rule); stressapptest before anything else"
  notify-send -a "DeepSeek-V4.1" -u critical "Kernel error in the DeepSeek arms" "Arm $1 stopped on a kernel error. 8080 is NOT restarted. See results/ds41/." 2> /dev/null
  exit 1
}
run() {
  mk "$1" "$2" "$3"
  "$SC/work/ds41/speedarm.sh" "$1" "$SC/configs/DS41-v024-$1.json" >> $L 2>&1
  local d; d=$(cat $SC/tmp/ds41-arm-out)
  cat "$d/summary.txt" >> $R
  echo "$d"
}

say "arms2: rerun of the s70 and DSpark arms (s60 valid: W1-W3 mean $(mean $D60) tok/s)"
$SC/work/r22/port_gap4.sh begin "DS4.1 arms rerun (RAM store 70 GB, DSpark on)" >> $R 2>&1 || { say "port_gap4 begin failed"; exit 1; }
best=60; bestv=$(mean $D60)
D70=$(run s70 70 auto); kernel_stop "$D70" && halt_kernel s70
if clean "$D70"; then
  v=$(mean "$D70"); awk "BEGIN{exit !($v > $bestv)}" && { best=70; bestv=$v; }
else
  say "the 70 GB arm did not run clean ($(cat $D70/GUARD $D70/SOFTSTOP 2> /dev/null | head -1)) - not a candidate"
fi
grep -q "MemAvailable" "$D70/GUARD" 2> /dev/null && { say "hard memory stop in the 70 GB arm - DSpark arm at 60 GB still runs"; best=60; bestv=$(mean $D60); }
say "faster store size by W1-W3 decode: $best GB ($bestv tok/s) - DSpark forced on there"
DD=$(run dsp$best $best on); kernel_stop "$DD" && halt_kernel dsp$best
clean "$DD" || say "the DSpark arm did not run clean ($(cat $DD/GUARD $DD/SOFTSTOP 2> /dev/null | head -1))"
$SC/work/r22/port_gap4.sh end >> $R 2>&1 && say "8080 back on P021m" || say "port_gap4 end FAILED - check 8080"
curl -s -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/health | grep -q 200 && say "8080 answers" || say "8080 does NOT answer"
bash $SC/bringup/lib/kcheck.sh ds41-arms2-after && say "kcheck clean" || say "KCHECK FAILED after the arms"
say "chain finished"
notify-send -a "DeepSeek-V4.1" "DeepSeek arms rerun done" "$(grep -E 'W1-W3 decode mean|faster store|8080' $R | tail -n 5 | cut -c1-120)" 2> /dev/null || true
