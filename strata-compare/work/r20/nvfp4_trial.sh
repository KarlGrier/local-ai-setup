#!/bin/bash
# nvfp4_trial.sh - Round 20 item 2: the NVFP4 GPTQ pack (models/Maximilian228--..., setup's layout, SHA-checked 10-13) on
# C*18's engine: every expert in the RAM arena (no budget / mmap flag), the 4060 Ti helper (2,400 slots: NVFP4 blobs are
# 2.76 MB, the IQ3_S average 1.93 MiB x 3,300 -> the same 6.2 GiB), the default w4a8 prompt path (STRATA_PREFILL_NVFP4
# unset), STRATA_ROUTE_TAIL_SKIP=0, C*18's settings otherwise. Tokenizer dir = runbook r20a's IQ3_S pack tokenizer: the
# same vocab / merges (the pack's merges.txt has CRLF endings) / token types, and the newer chat template (the NVFP4
# pack's older one rejects the developer role, effort "high" and a second system message).
#   1 load + sanity (nv_sanity.py), the start-up lines
#   2 teacher-forced NLL (math, corpus) on the NVFP4 twin and on C*18's twin
#   3 decode screen: --pcie-frac 0 (C*18's) vs the NVFP4 default share (flag dropped); the default share goes on only if >= 2 % faster
#   4 speed: C*18 IQ3_S (A) vs NVFP4, A B B A, LDR / decode / full screens (speed18.sh)
# The standing 20 GiB MemAvailable floor (guard default): a GUARD-STOP stops the trial and reports the lowest value.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r20
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB LR_MAX SPEED_FILE
P=.venv/bin/python; O=results/r20/nvfp4; mkdir -p $O
M=$WS/models/Maximilian228--Qwen3.8-Flash-Next-NVFP4-GPTQ-Strata
step() { echo "=== $(date -Is) $*"; }
G0=GPU-UUID-RTX5080
disp() { echo "$(date -Is) $1 display_active=$(nvidia-smi --id=$G0 --query-gpu=display_active --format=csv,noheader) 5080_used_MiB=$(nvidia-smi --id=$G0 --query-gpu=memory.used --format=csv,noheader,nounits) servers=$(pgrep -fc '/strata --serve')" | tee -a logs/r20/display.log; }
kc() { bringup/lib/kcheck.sh "nv-$1" || { step "KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; disp "nv-$1"; }
guardcheck() {   # the last guard line: a GUARD-STOP ends the trial (the lowest MemAvailable reported)
  local l; l=$(grep " $1 \| $1-" bringup/out/logs/guard/summary.txt | tail -1)
  echo "guard: $(echo "$l" | cut -c1-230)"
  if echo "$l" | grep -q GUARD-STOP; then
    step "GUARD-STOP in $1: lowest MemAvailable $(echo "$l" | grep -oE 'min_MemAvailable=[0-9.]+GiB@[0-9]+s') - trial stopped (floor kept at 20 GiB)"
    bringup/lib/phase_end.sh r20-nv-stop keep 9>&- 2>&1 | grep -E "phase end|8080:"; kc stop; exit 3
  fi
}
exec 9> tmp/suite/heavy.lock; flock 9
kc start
STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
step "configs"
$P - <<'PY'
import json
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); C = WS / "configs"
M = WS / "models/Maximilian228--Qwen3.8-Flash-Next-NVFP4-GPTQ-Strata"
base = json.loads((C / "Cstar18.json").read_text())
def mk(name, exe, server, drop_pcie=False, twin=False):
    c = json.loads(json.dumps(base)); a = c["args"]
    def setarg(f, v):
        if f in a: a[a.index(f) + 1] = v
        else: a.extend([f, v])
    setarg("--pack", str(M / "pack")); setarg("--native", str(M / "qwen-nvfp4-gptq-dense.gguf"))
    setarg("--native-dense-gguf", str(M / "qwen-nvfp4-gptq-dense.gguf")); setarg("--ple-gguf", str(M / "ple-fp8.gguf"))
    setarg("--embd-gguf", str(M / "token-embd-bf16.gguf")); setarg("--expert-cache-device1", "2400")
    if drop_pcie:
        i = a.index("--pcie-frac"); del a[i:i + 2]
    for f in ("--resident-budget-gib", "--mmap-experts", "--resident-experts"):
        assert f not in a
    c["env"]["STRATA_ROUTE_TAIL_SKIP"] = "0"; c["env"].pop("STRATA_PREFILL_NVFP4", None)
    c.update(exe=str(exe), server=str(server), log=str(WS / f"logs/engine-{name}.log"), fallback=None,
             tokenizer=str(WS / "bringup/out/r20a/pack/tokenizer"), model_name="strata-qwen3.8-flash-next-nvfp4-gptq")
    if twin:
        c["env"]["STRATA_STATE_HASH"] = "1"; c["args"] += ["--adapt-swaps", "0"]
    c["_comment"] = (f"Round 20 item 2 ({name}): the NVFP4 GPTQ pack on C*18's engine, every expert in the RAM arena, helper 2400 slots, "
                     "w4a8 prompt path (default), STRATA_ROUTE_TAIL_SKIP=0" + (", NVFP4's own PCIe share" if drop_pcie else ", --pcie-frac 0 as C*18")
                     + "; tokenizer = the IQ3_S pack's (same vocab, newer template)")
    (C / f"{name}.json").write_text(json.dumps(c, indent=1) + "\n")
    (C / f"{name}.shared-settings.json").write_text((C / "Cstar18.shared-settings.json").read_text())
    print(name, " ".join(x if not x.startswith("/") else Path(x).name for x in c["args"]))
mk("r20-nv18", WS / "engine-cstar18/strata", WS / "strata-cstar18/serve/server.py")
mk("r20-nv18-pf", WS / "engine-cstar18/strata", WS / "strata-cstar18/serve/server.py", drop_pcie=True)
mk("r20-nv18-twin", WS / "engine-twin18/strata", WS / "tmp/r20/meas441/serve/server.py", twin=True)
PY
export EVICT_GLOB="$M/*.gguf $M/pack/experts.bin"
step "1 load + sanity"
: > logs/engine-r20-nv18.log
bringup/lib/with_server.sh 9>&- nv18-sanity configs/r20-nv18.json -- "$P work/r20/nv_sanity.py http://127.0.0.1:8081 $O/sanity.json" 2>&1 | grep -vE '^\[strata\]' | tail -12
guardcheck srv-nv18-sanity
echo "--- start-up lines:"
grep -hiE "patch guard|expert cache|arena|helper|device1|tail skip|TAIL_SKIP|nvfp4|w4a8|prompt path|PREFILL_NVFP4|pinned|ROUTER_Q8K|non-finite" logs/engine-r20-nv18.log | grep -vE "^\[strata\] (done|reading)" | sort -u | head -30 | cut -c1-240 | tee $O/startup-lines.txt
kc sanity
step "2 teacher-forced NLL (math, corpus): NVFP4 twin, then C*18's twin"
export PROMPT_DIR=$WS/bringup/out/r20a/prompts
bringup/lib/tf.sh nv18 configs/r20-nv18-twin.json engine-twin18/strata math corpus 9>&- > $O/tf-nv18.txt 2>&1; grep -h "teacher-forced\|FAILED" $O/tf-nv18.txt
guardcheck tf-nv18
EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf" bringup/lib/tf.sh c18tw configs/twin18.json engine-twin18/strata math corpus 9>&- > $O/tf-c18.txt 2>&1; grep -h "teacher-forced\|FAILED" $O/tf-c18.txt
kc tf
step "3 decode screen: --pcie-frac 0 vs NVFP4's own share"
SS=$(date -Iseconds | cut -c1-19)
bringup/lib/decscreen.sh r20-nv-D-pf0 configs/r20-nv18.json 9>&- > logs/r20/nv-D-pf0.log 2>&1; guardcheck srv-r20-nv-D-pf0
bringup/lib/decscreen.sh r20-nv-D-pfauto configs/r20-nv18-pf.json 9>&- > logs/r20/nv-D-pfauto.log 2>&1; guardcheck srv-r20-nv-D-pfauto
SINCE=$SS $P bringup/lib/ab_table.py pf0=r20-nv-D-pf0 pfauto=r20-nv-D-pfauto > $O/pcie-choice.md 2>&1; cat $O/pcie-choice.md | head -20
CH=$($P - $O/pcie-choice.md <<'PY'
import re, sys
t = open(sys.argv[1]).read()
m = re.search(r"^\|\s*decode[^|]*\|\s*([\d.]+)[^|]*\|\s*([\d.]+)", t, re.M | re.I)
print("configs/r20-nv18-pf.json" if m and float(m.group(2)) > 1.02 * float(m.group(1)) else "configs/r20-nv18.json")
PY
)
echo "chosen for the speed screens: $CH"; echo "$CH" > $O/chosen-config.txt
kc pcie
step "4 speed: C*18 IQ3_S (A) vs NVFP4, A B B A"
A_CFG=configs/Cstar18.json A_TAG=iq3s work/r20/speed18.sh $CH nv18 9>&- > logs/r20/speed-nv18.log 2>&1; grep -E 'results/|done' logs/r20/speed-nv18.log | cut -c1-300
grep -h "r20-s18-.-nv18" bringup/out/logs/guard/summary.txt | grep -oE "^[^ ]+ [^ ]+|min_MemAvailable=[^ ]+|GUARD-STOP.*" | paste - - | tail -12
kc speed
step "NVFP4 trial done"
