#!/bin/bash
# q8_honesty.sh - overnight 2026-10-16/17, your request (after the effort test): Q8_0 on the honesty items, to separate
# the weights from the settings.  configs/r21-q8-honesty.json = the yardstick's Q8_0 reference setup (configs/r21-q8ref.json:
# Unsloth Q8_0, 176 GB in six shards, round-15 pack, C*18's engine, 5080 only, 52 GiB of experts page-locked in RAM, the
# rest read from the SSD unbuffered) served with C*18t's server code, chat template and loop stop (256).
#   0  nothing maps the Q8_0 files before the start (every /proc/*/maps); while it runs a sampler records every 30 s
#      MemAvailable, Cached and the engine's resident pages inside its Q8_0 mappings (the engine keeps a read-only view
#      of the shards; its reads go through O_DIRECT, so that view should stay at ~0 resident)
#   1  a short decode screen (warm-up, long reasoning math + code capped at 1,024 tokens, correctness x5, no 32K):
#      decode < 3 tok/s -> stop and report the speed; more than 2 GiB of the shards resident -> stop (not SSD-only)
#   2  h03, h05, h07, h12 at your sampling (sent by the suite: T 1.0 / 0.95 / 20 / min-p 0.05), effort xhigh, 2 samples
#   3  if there is time before 10:00: the same at effort "high" (2 samples; Strata and the template render "high" as
#      xhigh, so these are the identical prompt), cut off at 10:00
#   4  C*18t back on 8080, grade, per-answer table -> results/r21/q8h/
# Memory floor 6 GiB for this run (your rule for it); kernel check after every step, stop at the first error.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE NO32K
export GUARD_MEM_GIB=6
CFG=configs/r21-q8-honesty.json; Q8=$WS/models/r15/Q8_0; O=results/r21/q8h; mkdir -p $O logs/r21
ITEMS=honesty/h03_viirmets,honesty/h05_strondalsvik,honesty/h07_glasbienen,honesty/h12_pan_baltic_1923
DEADLINE=$(date -d '2026-10-17 10:00' +%s)
P=.venv/bin/python
step() { echo "=== $(date -Is) $*"; }
SAMP=""
finish() {   # C*18t back on 8080 (standing guard), sampler off
  [ -n "$SAMP" ] && kill $SAMP 2>/dev/null
  bringup/lib/phase_end.sh r21-q8h keep 9>&- 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
}
kc() { bringup/lib/kcheck.sh "q8h-$1" || { step "KERNEL CHECK FAILED after $1 - stopped"; finish; exit 1; }; }
gline() { grep " $1 " bringup/out/logs/guard/summary.txt | tail -1 | cut -c1-260; }
stopcheck() {
  local l; l=$(gline "$1"); echo "guard: $l"
  if echo "$l" | grep -q GUARD-STOP; then step "GUARD-STOP in $1 - stopped"; finish; kc stop; exit 3; fi
}
SRV='^[^ ]*/llama-server( |$)|^[^ ]*/strata --serve'
srv_gone() { for i in $(seq 60); do pgrep -f "$SRV" > /dev/null || break; sleep 1; done; ! pgrep -fa "$SRV"; }
exec 9> tmp/suite/heavy.lock; flock 9
kc start
STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -1
srv_gone || { step "a model server is still running - stop"; finish; exit 1; }

step "0 does anything map the Q8_0 files?"
M=$(grep -l "$Q8/" /proc/[0-9]*/maps 2>/dev/null | cut -d/ -f3 | tr '\n' ' ')
if [ -n "$M" ]; then
  step "STOP: the Q8_0 files are mapped by PID(s) $M: $(for p in $M; do tr '\0' ' ' < /proc/$p/cmdline | cut -c1-80; echo; done)"
  finish; exit 1
fi
echo "nothing maps $Q8 (checked $(ls -d /proc/[0-9]* | wc -l) processes)" | tee $O/maps-check.txt
$P scripts/evict.py "$Q8"/*.gguf > /dev/null   # none of the 176 GB in the page cache at the start
( while :; do
    e=$(pgrep -f "$SRV" | head -1)
    r=0; [ -n "$e" ] && r=$(awk -v q="$Q8/" '/^[0-9a-f]+-[0-9a-f]+ /{m=index($0, q) > 0} m && /^Rss:/{s+=$2} END{print s+0}' /proc/$e/smaps 2>/dev/null)
    echo "$(date +%H:%M:%S) engine=${e:-none} q8_mapped_rss_kib=$r $(awk '/^(MemAvailable|Cached):/{printf "%s=%.1fGiB ", $1, $2/1048576}' /proc/meminfo)"
    sleep 30
  done ) > logs/r21/q8h-sampler.log 2>&1 &
SAMP=$!
maxrss() { awk -F'q8_mapped_rss_kib=' 'NF>1{split($2,a," "); if (a[1]>m) m=a[1]} END{printf "%.2f", m/1048576}' logs/r21/q8h-sampler.log; }

step "1 short decode screen (LR_MAX 1024, no 32K)"
EVICT_GLOB="$Q8/*.gguf" LR_MAX=1024 NO32K=1 bringup/lib/decscreen.sh r21-q8h-D $CFG 9>&- > logs/r21/q8h-D.log 2>&1
stopcheck srv-r21-q8h-D; kc screen
SPEED=$($P - <<'PY'
import json
g = d = 0.0
for l in open("results/runs.jsonl"):
    r = json.loads(l)
    if r.get("config") == "r21-q8h-D" and r.get("scenario") == "longreason" and r.get("decode_s"):
        g += r["usage"]["completion_tokens"]; d += r["decode_s"]
print(f"{g / d:.2f}" if d else "0")
PY
)
ELOG=$(python3 -c "import json; print(json.load(open('$CFG'))['log'])")
{ echo "decode (long reasoning math + code, client side): $SPEED tok/s"
  grep -hE "generated in" $ELOG | tail -8 | cut -c1-200
  grep -hE "file tier reads|file tier I/O this request|resident RAM mode|pinned cache" $ELOG | tail -6 | cut -c1-200
  echo "max resident pages inside the engine's Q8_0 mappings: $(maxrss) GiB"
  grep -hoE '\[strata\] (sampling defaults|other apps use).*' $(ls -t bringup/out/logs/server_r21-q8h-D_*.log | head -1)
  gline srv-r21-q8h-D; } | tee $O/screen.txt
if $P -c "import sys; sys.exit(0 if float('$SPEED') < 3 else 1)"; then
  step "STOP: Q8_0 decodes at $SPEED tok/s (< 3) - honesty runs not started"; finish; kc end; exit 0
fi
if $P -c "import sys; sys.exit(0 if float('$(maxrss)') > 2 else 1)"; then
  step "STOP: $(maxrss) GiB of the Q8_0 shards became resident through the engine's mapping - not SSD reads only"; finish; kc end; exit 0
fi

step "2 honesty xhigh: $ITEMS x 2"
T0=$(date +%s)
bringup/lib/with_server.sh 9>&- suite-q8h-xhigh $CFG -- \
  "suite/run.sh --label q8h-xhigh --endpoint http://127.0.0.1:8081 --mode quick --items $ITEMS --runs 2 --no-grade; echo suite exit \$?" \
  2>&1 | grep -vE '^\[strata\]' | tail -5
stopcheck srv-suite-q8h-xhigh; kc xhigh
T2=$(( $(date +%s) - T0 )); LEFT=$(( DEADLINE - $(date +%s) ))
step "xhigh round took $((T2 / 60)) min; $((LEFT / 60)) min left before 10:00"
if [ $LEFT -ge $(( T2 / 4 )) ] && [ $LEFT -gt 1200 ]; then   # time for at least ~2 answers at the xhigh pace
  step "3 honesty high (rendered as xhigh): $ITEMS x 2, cut off at 10:00"
  bringup/lib/with_server.sh 9>&- suite-q8h-high $CFG -- \
    "timeout $LEFT suite/run.sh --label q8h-high --endpoint http://127.0.0.1:8081 --mode quick --items $ITEMS --runs 2 --no-grade --extra-body '{\"reasoning_effort\": \"high\"}'; echo suite exit \$?" \
    2>&1 | grep -vE '^\[strata\]' | tail -5
  stopcheck srv-suite-q8h-high; kc high
else
  step "3 skipped: not enough time before 10:00"
fi
finish
for L in q8h-xhigh q8h-high; do [ -d suite/results/$L ] && suite/run.sh regrade $L 9>&- 2>&1 | tail -2; done
$P - <<'PY' | tee results/r21/q8h/answers.md
import json, glob, os
R = "suite/results"
print("| level | item | sample | answer | reasoning tokens | wall time | cut off |")
print("|---|---|---|---|---|---|---|")
for L in ("q8h-xhigh", "q8h-high"):
    if not os.path.isdir(f"{R}/{L}"):
        continue
    g = json.load(open(f"{R}/{L}/grades.json")) if os.path.exists(f"{R}/{L}/grades.json") else {}
    for f in sorted(glob.glob(f"{R}/{L}/answers/honesty/*.json")):
        d = json.load(open(f))
        k = f"{d['item']}#r{d['run']}"
        det = (g.get(k) or {}).get("detail", "") if isinstance(g.get(k), dict) else str(g.get(k, ""))
        t = d["tokens"]; w = d["timing"]["wall_s"]
        print(f"| {L[4:]} | {d['item']} | {d['run']} | {det or (d['response'].get('content') or '')[-60:]!r} | "
              f"{t['reasoning']:,} | {w / 60:.0f} min | {bool(d.get('cut_off'))} |")
PY
echo "sampler: max resident pages inside the engine's Q8_0 mappings $(maxrss) GiB; lowest MemAvailable $(grep -oE 'MemAvailable:=[0-9.]+' logs/r21/q8h-sampler.log | cut -d= -f2 | sort -n | head -1) GiB" | tee -a $O/answers.md
kc end
step "q8_honesty done"
