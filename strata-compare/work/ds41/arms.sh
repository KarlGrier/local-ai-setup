#!/bin/bash
# arms.sh - 10-23 (the user: "Yes to more DeepSeek arms tonight, after the current run, in this order"): after the stock run
# (work/ds41/speedtest.sh, store auto = 48 GB) has finished, one gap (work/r22/port_gap4.sh begin ... end) with:
#   a. the RAM store set explicitly to 60 GB, then 70 GB - the 70 only if the 60 arm ran clean; both with the store's growth
#      floor DS4_STORE_FLOOR_GB=16 (it takes no chunk that would leave under 16 GB available), a soft stop below 15 GB
#      available (the user's limit; speedarm.sh SOFTSTOP) and the 12 GB hard stop;
#   b. at whichever store size gave the best W1-W3 decode (the stock 48 GB run included): DSpark forced on (--dspark on).
#      The code check first (the user): the trunk's verify is the speculative-sampling rule (draft kept with probability
#      min(1, p/q), else a draw from max(0, p - q), p through the request's own top-k / top-p / min-p / temperature chain;
#      strata-v024 src/dsv41/ds4_model.cu verify, vendor/sampler.cu MODE 2) - exact in distribution, so the arm runs.
# Same measurements per arm (work/ds41/speed.py: W1-W3 decode, prompt reading 4K and 20K, SSD GB per request). P021m back
# on 8080 at the end - unless a kernel error stopped the chain (the user's rule: stop at the first kernel error; 8080 is
# then left stopped and a critical alert sent). Summary: results/ds41/arms-summary-MMDD.txt.
set -u
SC=/home/USER/ai-speed-testing/strata-compare
BASE=$SC/configs/DS41-v024-stock.json
L=$SC/logs/ds41/arms.log
R=$SC/results/ds41/arms-summary-$(date +%m%d).txt
say() { echo "=== $(date '+%F %T') $*" | tee -a $R; }
STOCK=$(ls -td $SC/results/ds41/speed-v024-* | head -1)
until grep -q "=== .* done$" $STOCK/summary.txt 2>/dev/null; do sleep 30; done

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
mean() {   # the W1-W3 mean decode tok/s of a run folder ("" unless all six responses are there)
  python3 -c '
import json, sys, statistics as st
r = [json.loads(l) for l in open(sys.argv[1] + "/ds41.jsonl")]
w = [x["decode_tps"] for x in r if x["id"][:2] in ("W1", "W2", "W3") and x.get("decode_tps")]
print(f"{st.mean(w):.3f}" if len(w) == 6 else "")' "$1" 2> /dev/null
}
clean() { [ ! -e "$1/GUARD" ] && [ ! -e "$1/SOFTSTOP" ] && [ -n "$(mean "$1")" ]; }
kernel_stop() { grep -q -i "kernel" "$1/GUARD" 2> /dev/null || grep -q -i -E "KCHECK FAILED|kernel check failed" "$1/summary.txt" 2> /dev/null; }
halt_kernel() {
  say "KERNEL ERROR in arm $1 - chain stopped, 8080 left stopped (the user's rule); stressapptest before anything else"
  notify-send -a "DeepSeek-V4.1" -u critical "Kernel error in the DeepSeek arms" "Arm $1 stopped on a kernel error. 8080 is NOT restarted. See results/ds41/." 2> /dev/null
  exit 1
}
run() {   # run NAME STORE DSPARK -> prints the arm's folder
  mk "$1" "$2" "$3"
  "$SC/work/ds41/speedarm.sh" "$1" "$SC/configs/DS41-v024-$1.json" >> $L 2>&1
  local d; d=$(cat $SC/tmp/ds41-arm-out)
  cat "$d/summary.txt" >> $R
  echo "$d"
}

say "arms: the stock run is done ($STOCK; store auto 48 GB: W1-W3 mean $(mean $STOCK) tok/s)"
$SC/work/r22/port_gap4.sh begin "DS4.1 arms (RAM store 60 / 70 GB, DSpark on)" >> $R 2>&1 || { say "port_gap4 begin failed"; exit 1; }
best=auto; bestv=$(mean $STOCK); bestv=${bestv:-0}; bestn=48

D60=$(run s60 60 auto); kernel_stop "$D60" && halt_kernel s60
if clean "$D60"; then
  v=$(mean "$D60"); awk "BEGIN{exit !($v > $bestv)}" && { best=60; bestv=$v; bestn=60; }
  D70=$(run s70 70 auto); kernel_stop "$D70" && halt_kernel s70
  if clean "$D70"; then v=$(mean "$D70"); awk "BEGIN{exit !($v > $bestv)}" && { best=70; bestv=$v; bestn=70; }
  else say "the 70 GB arm did not run clean ($(cat $D70/GUARD $D70/SOFTSTOP 2> /dev/null | head -1)) - not a candidate"; fi
else
  say "the 60 GB arm did not run clean ($(cat $D60/GUARD $D60/SOFTSTOP 2> /dev/null | head -1)) - the 70 GB arm skipped"
  grep -q "MemAvailable" "$D60/GUARD" 2> /dev/null && { say "hard memory stop in the 60 GB arm - no DSpark arm either"; best=none; }
fi

if [ "$best" != none ]; then
  say "best store size by W1-W3 decode: $bestn GB ($bestv tok/s) - DSpark forced on there"
  DD=$(run dsp$bestn $best on); kernel_stop "$DD" && halt_kernel dsp$bestn
fi

$SC/work/r22/port_gap4.sh end >> $R 2>&1 && say "8080 back on P021m" || say "port_gap4 end FAILED - check 8080"
bash $SC/bringup/lib/kcheck.sh ds41-arms-after && say "kcheck clean" || say "KCHECK FAILED after the arms"
say "done"
notify-send -a "DeepSeek-V4.1" "DeepSeek arms done" "$(grep -E 'W1-W3 decode mean|best store' $R | tail -n 4 | cut -c1-120)" 2> /dev/null || true
