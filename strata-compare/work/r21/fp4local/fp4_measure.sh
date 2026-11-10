#!/bin/bash
# fp4_measure.sh - r21 item 7: FP4-Local (models/fp4local/pack: nvidia's QAD routed experts, the GPTQ pack's dense
# weights / PLE / embeddings / MTP) against the GPTQ NVFP4 pack, both on C*18's engine with every expert in RAM.
#   1 load + sanity (work/r20/nv_sanity.py), the start-up lines
#   2 quant yardstick (tools/quant_quality.py run, experts on the CPU, 5080 only) vs the Q8_0 reference; C*18's IQ3_S
#     as a third arm for context
#   3 speed, A B B A (A = GPTQ, configs/r20-nv18.json; B = FP4-Local, configs/r21-nv-fp4local.json): decode screen +
#     full screen (TTFT 32K / 64K / 120K) per arm
#   4 the suite's quick run on each (labels c18-nvfp4-quick, c18-fp4local-quick), graded after the servers are gone
# Your 10-16 rule: NVFP4 runs may go down to 6 GiB MemAvailable (GUARD_MEM_GIB=6); a GUARD-STOP stops the item.
# STAGES="1 2 3 4" limits it; ends with the promoted build (C*18t) on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export GUARD_MEM_GIB=6
P=.venv/bin/python; O=results/r21/fp4local; Y=results/r21/yq; mkdir -p $O $Y logs/r21
G=$WS/models/Maximilian228--Qwen3.8-Flash-Next-NVFP4-GPTQ-Strata; F=$WS/models/fp4local
export EVICT_GLOB="$G/*.gguf $G/pack/experts.bin $F/pack/experts.bin"
A=configs/r20-nv18.json; B=configs/r21-nv-fp4local.json
step() { echo "=== $(date -Is) $*"; }
SRV='^[^ ]*/llama-server( |$)|^[^ ]*/strata --serve'
srv_gone() { for i in $(seq 60); do pgrep -f "$SRV" > /dev/null || break; sleep 1; done; ! pgrep -fa "$SRV"; }
kc() { bringup/lib/kcheck.sh "fl-$1" || { step "KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
guardcheck() {   # a GUARD-STOP ends the item (the lowest MemAvailable reported)
  local l; l=$(grep " $1 " bringup/out/logs/guard/summary.txt | tail -1)
  echo "guard: $(echo "$l" | cut -c1-230)"
  if echo "$l" | grep -q GUARD-STOP; then
    step "GUARD-STOP in $1: lowest MemAvailable $(echo "$l" | grep -oE 'min_MemAvailable=[0-9.]+GiB@[0-9]+s') - stopped (floor: 6 GiB on NVFP4 runs, 20 GiB otherwise)"
    bringup/lib/phase_end.sh r21-fl-stop keep 9>&- 2>&1 | grep -E "phase end|8080:"; kc stop; exit 3
  fi
}
exec 9> tmp/suite/heavy.lock; flock 9
kc start
step "configs"
$P - <<'PY'
import json
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); C = WS / "configs"
c = json.loads((C / "r20-nv18.json").read_text()); a = c["args"]
a[a.index("--pack") + 1] = str(WS / "models/fp4local/pack")
c["log"] = str(WS / "logs/engine-r21-nv-fp4local.log"); c["model_name"] = "strata-qwen3.8-flash-next-nvfp4-fp4local"
c["_comment"] = ("2026-10-16 r21 item 7: FP4-Local = nvidia/Qwen3.8-Flash-Next-FP4-Local's routed experts (QAD, CSF scales "
                 "decoded, lossless repack: work/r21/fp4local) with the GPTQ pack's dense weights, PLE, embeddings and MTP; "
                 "otherwise configs/r20-nv18.json (C*18's engine and settings, every expert in RAM, 4060 Ti helper 2400 slots, "
                 "STRATA_ROUTE_TAIL_SKIP=0).")
(C / "r21-nv-fp4local.json").write_text(json.dumps(c, indent=1) + "\n")
(C / "r21-nv-fp4local.shared-settings.json").write_text((C / "r20-nv18.shared-settings.json").read_text())
PY
STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -1
srv_gone || { step "a model server is still running - stop"; exit 1; }
for s in ${STAGES:-1 2 3 4}; do case $s in
1)
  step "1 load + sanity: FP4-Local"
  : > logs/engine-r21-nv-fp4local.log
  bringup/lib/with_server.sh 9>&- fl-sanity $B -- "$P work/r20/nv_sanity.py http://127.0.0.1:8081 $O/sanity.json" 2>&1 | grep -vE '^\[strata\]' | tail -12
  guardcheck srv-fl-sanity
  grep -hiE "expert cache|arena|helper|device1|tail skip|nvfp4|w4a8|pinned|non-finite|error" logs/engine-r21-nv-fp4local.log | grep -vE "^\[strata\] (done|reading)" | sort -u | head -30 | cut -c1-240 | tee $O/startup-lines.txt
  kc sanity ;;
2)
  for arm in gptq fp4local iq3s; do      # iq3s: C*18's daily IQ3_S for context - not NVFP4, so the 20 GiB floor
    GM=6; [ $arm = iq3s ] && GM=20
    step "2 yardstick: $arm (guard floor $GM GiB)"
    GUARD_MEM_GIB=$GM $P bringup/lib/guard.py yq-$arm -- $P strata-cstar18/tools/quant_quality.py run --config configs/r21-yq-$arm.json \
      --out $Y/$arm.tsv --min-free-gb 30 9>&- 2>&1 | grep -vE '^\[strata\]' | tail -8
    guardcheck yq-$arm; kc yq-$arm
  done
  $P strata-cstar18/tools/quant_quality.py compare $Y/q8ref.tsv $Y/gptq.tsv $Y/fp4local.tsv $Y/iq3s.tsv --segments --json $Y/compare.json > $Y/compare.md 2>&1
  cat $Y/compare.md ;;
3)
  step "3 speed A B B A (A = GPTQ, B = FP4-Local)"
  SS=$(date -Iseconds | cut -c1-19)
  for arm in "gptq-a $A" "fl-a $B" "fl-b $B" "gptq-b $A"; do
    set -- $arm
    bringup/lib/decscreen.sh r21-fl-D-$1 $2 9>&- > logs/r21/fl-D-$1.log 2>&1; guardcheck srv-r21-fl-D-$1
    bringup/lib/fullscreen.sh r21-fl-F-$1 $2 9>&- > logs/r21/fl-F-$1.log 2>&1; guardcheck srv-r21-fl-F-$1
    step "arm $1 done"; kc speed-$1
  done
  SINCE=$SS $P bringup/lib/ab_table.py GPTQ=r21-fl-D-gptq-a,r21-fl-D-gptq-b FP4LOCAL=r21-fl-D-fl-a,r21-fl-D-fl-b > $O/speed-dec.md 2>&1
  SINCE=$SS $P bringup/lib/ab_table.py GPTQ=r21-fl-F-gptq-a,r21-fl-F-gptq-b FP4LOCAL=r21-fl-F-fl-a,r21-fl-F-fl-b > $O/speed-full.md 2>&1
  for f in $O/speed-dec.md $O/speed-full.md; do echo "--- $f"; head -30 $f; done ;;
4)
  for which in gptq fp4local; do
    case $which in gptq) L=c18-nvfp4-quick; CFG=$A ;; fp4local) L=c18-fp4local-quick; CFG=$B ;; esac
    step "4 suite quick: $L on $CFG (8081, guarded)"
    srv_gone || { step "a model server is still running - stop"; exit 1; }
    bringup/lib/with_server.sh 9>&- suite-$L $CFG -- \
      "suite/run.sh --label $L --endpoint http://127.0.0.1:8081 --mode quick --no-grade; echo suite exit \$?" 2>&1 | grep -vE '^\[strata\]' | tail -8
    guardcheck srv-suite-$L; kc suite-$which
  done ;;
esac; done
bringup/lib/phase_end.sh r21-fl keep 9>&- 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
if echo " ${STAGES:-1 2 3 4} " | grep -q " 4 "; then
  step "grade (CPU only; the promoted build serves 8080)"
  for L in c18-nvfp4-quick c18-fp4local-quick; do suite/run.sh regrade $L 9>&- 2>&1 | tail -30; done
  suite/run.sh compare c18-nvfp4-quick c18-fp4local-quick 9>&- 2>&1 | tail -40
fi
kc end
step "fp4_measure done"
