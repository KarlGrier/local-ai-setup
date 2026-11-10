#!/bin/bash
# nv_vs_c18t.sh NV_CONFIG - 2026-10-16, your addition for the final report: NVFP4 against C*18t's IQ3_S under today's
# conditions (desktop on the iGPU, both arms at your Chat settings T 1.0 / 0.95 / 20 + the config's min-p 0.05).
# A B B A, A = C*18t (configs/Cstar18t.json, as served on 8080), B = the better NVFP4 pack (NV_CONFIG, every expert in
# RAM, 4060 Ti helper); per arm the decode screen (long reasoning math + code, correctness x5, 32K) and the full screen
# (TTFT 32K / 64K / 120K, each + 768 decoded tokens, long reasoning, chat switch), fresh guarded server, cold page cache.
# Memory floor: 20 GiB for C*18t, 6 GiB for the NVFP4 arms (your 10-16 rule). Runs before the sampling changes and the
# harness rerun; ends with C*18t on 8080. Tables -> results/r21/nv-vs-c18t-{dec,full}.md.
set -u
NV=${1:?NV_CONFIG}
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
P=.venv/bin/python; O=results/r21; A=configs/Cstar18t.json
G=$WS/models/Maximilian228--Qwen3.8-Flash-Next-NVFP4-GPTQ-Strata
export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf $G/*.gguf $G/pack/experts.bin $WS/models/fp4local/pack/experts.bin"
step() { echo "=== $(date -Is) $*"; }
kc() { bringup/lib/kcheck.sh "nv18t-$1" || { step "KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
gline() { grep " $1 " bringup/out/logs/guard/summary.txt | tail -1 | cut -c1-260; }
stopcheck() {
  local l; l=$(gline "$1"); echo "guard: $l"
  if echo "$l" | grep -q GUARD-STOP; then
    step "GUARD-STOP in $1 - stopped"; bringup/lib/phase_end.sh nv18t-stop keep 9>&- 2>&1 | grep -E "phase end|8080:"; kc stop; exit 3
  fi
}
SRV='^[^ ]*/llama-server( |$)|^[^ ]*/strata --serve'
srv_gone() { for i in $(seq 60); do pgrep -f "$SRV" > /dev/null || break; sleep 1; done; ! pgrep -fa "$SRV"; }
[ -f "${NV%.json}.shared-settings.json" ] || { step "$NV has no Chat settings file - stop"; exit 1; }
exec 9> tmp/suite/heavy.lock; flock 9
kc start
STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -1
srv_gone || { step "a model server is still running - stop"; exit 1; }
step "A B B A: A = C*18t, B = $NV"
SS=$(date -Iseconds | cut -c1-19); : > $O/nv-vs-c18t-arms.txt
for arm in "c-a $A 20" "n-a $NV 6" "n-b $NV 6" "c-b $A 20"; do
  set -- $arm
  GUARD_MEM_GIB=$3 bringup/lib/decscreen.sh r21-nvc-D-$1 $2 9>&- > logs/r21/nvc-D-$1.log 2>&1; stopcheck srv-r21-nvc-D-$1
  GUARD_MEM_GIB=$3 bringup/lib/fullscreen.sh r21-nvc-F-$1 $2 9>&- > logs/r21/nvc-F-$1.log 2>&1; stopcheck srv-r21-nvc-F-$1
  for k in D F; do
    f=$(ls -t bringup/out/logs/server_r21-nvc-$k-$1_*.log | head -1)
    echo "$1 $k ($2): $(grep -E '^\[strata\] (sampling defaults|other apps use)' $f | sed 's/\[strata\] //' | tr '\n' '|')" \
         "$(gline srv-r21-nvc-$k-$1 | grep -oE 'min_MemAvailable=[0-9.]+GiB|min_5080_free=[0-9]+MiB' | tr '\n' ' ')" >> $O/nv-vs-c18t-arms.txt
  done
  step "arm $1 done"; kc speed-$1
done
SINCE=$SS $P bringup/lib/ab_table.py C18T=r21-nvc-D-c-a,r21-nvc-D-c-b NVFP4=r21-nvc-D-n-a,r21-nvc-D-n-b > $O/nv-vs-c18t-dec.md 2>&1
SINCE=$SS $P bringup/lib/ab_table.py C18T=r21-nvc-F-c-a,r21-nvc-F-c-b NVFP4=r21-nvc-F-n-a,r21-nvc-F-n-b > $O/nv-vs-c18t-full.md 2>&1
for f in $O/nv-vs-c18t-dec.md $O/nv-vs-c18t-full.md; do echo "--- $f"; head -16 $f; done; cat $O/nv-vs-c18t-arms.txt
bringup/lib/phase_end.sh r21-nvc keep 9>&- 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
kc end
step "nv_vs_c18t done"
