#!/bin/bash
# c120diag.sh — round 15: the splice's placement C (layer split) answered both 120K requests of its full set with
# degenerate output (256 tokens of 255 characters, every draft accepted, the decode's expert lookups 100 % VRAM hits:
# the router picks the same experts every token) and scored 0/6 on the 120K needle; 8K-64K decoded normally. Which
# build does it: each arm a fresh guarded server with C's placement (both GPUs, --layer-split auto, 72 GiB, unbuffered),
# the 120K needle (needle2, run 0), its score and the engine's decode hit-rate line. Stops at the first answer:
#   1 stock v0.1.40.2 (its own binary and profile, the upstream switches only)  -> fails: upstream; done
#   2 ours without STRATA_QSA_SPLIT_ATTN (the long-context attention switch)    -> passes: that switch
#   3 ours patched-off (our binary, the stock switches)                          -> fails: the port; passes: a switch
# Results: results/r15/c120diag.md
set -u
ok() { [[ "$1" =~ ^[0-9]+$ ]] && [ "$1" -ge 5 ]; }
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
P=.venv/bin/python; D=work/r15/cfg; OUT=results/r15/c120diag.md
export GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
mk() {   # mk NAME EXE PROFILE DROP_ENV... -> work/r15/cfg/c120-NAME.json from configs/r15-q5s-Cx72.json
  local n=$1 exe=$2 prof=$3; shift 3
  $P - "$n" "$exe" "$prof" "$@" <<'PY'
import json, sys
from pathlib import Path
n, exe, prof, drop = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
src = Path("configs/r15-q5s-Cx72.json"); c = json.loads(src.read_text()); a = c["args"]
if exe != "-":
    c["exe"] = exe
    for f in ("--chat-cache", "--chat-cache-mib"):   # our patch's flags: the stock binary refuses them
        if f in a: i = a.index(f); del a[i:i + 2]
if prof != "-": a[a.index("--expert-profile") + 1] = prof
for k in drop + ["STRATA_PREFILL_TIMING", "STRATA_SPLIT_TIMING", "STRATA_DECODE_TIMING"]:
    c["env"].pop(k, None)
c["log"] = c["log"].replace(".log", f"-c120-{n}.log")
c["_comment"] = f"c120diag arm {n}: C's placement, 120K needle; dropped {drop}"
Path(f"work/r15/cfg/c120-{n}.json").write_text(json.dumps(c, indent=1) + "\n")
sh = Path("configs/r15-q5s-Cx72.shared-settings.json")
if sh.exists(): Path(f"work/r15/cfg/c120-{n}.shared-settings.json").write_text(sh.read_text())
PY
}
arm() {   # arm NAME -> prints "score chars hit" and appends a row
  local n=$1 C=$D/c120-$1.json E L=r15-c120-$1
  E=$($P -c "import json; print(json.load(open('$C'))['log'])"); touch "$E"; local e0; e0=$(wc -l < "$E")
  for i in $(seq 180); do ss -H -ltn "( sport = :8081 )" | grep -q . || break; sleep 1; done   # the last server gone
  $P scripts/evict.py $WS/models/r15/splice-q5/*.gguf > /dev/null
  if ! bringup/lib/srv.sh start $L "$C" > work/r15/cfg/c120-$n-start.txt 2>&1; then
    echo "| $n | did not start ($(tail -1 work/r15/cfg/c120-$n-start.txt | cut -c1-120)) | – | – |" >> $OUT; echo "nostart"; return; fi
  NEEDLE_DIR=$WS/work/r5/needle2 $P bringup/lib/needle2.py ask --label $L --sizes 120k --runs 0 > /dev/null 2>&1
  bringup/lib/srv.sh stop > /dev/null 2>&1
  local r; r=$($P - "$L" "$E" "$e0" <<'PY'
import json, re, sys
L, E, e0 = sys.argv[1], sys.argv[2], int(sys.argv[3])
rec = [json.loads(l) for l in open("bringup/out/results/needle2.jsonl") if f'"{L}"' in l]
t = "\n".join(open(E, errors="replace").read().splitlines()[e0:])
req = re.findall(r"prompt 1228\d\d tokens .*?(\d+) generated in [\d.]+ ms \(([\d.]+) tok/s\), drafts accepted (\d+) of (\d+)", t)
hit = re.findall(r"decode expert cache hit rate: ([\d.]+)%", t)
if not rec: print("no-answer - - -"); sys.exit()
r = rec[-1]
print(r["score"], r.get("reasoning_chars", 0) + len(r.get("answer") or ""), (req[-1][0] if req else "-"), (hit[-1] if hit else "-"))
PY
)
  set -- $r
  echo "| $n | $1/6 | $2 characters for $3 tokens | $4 % |" >> $OUT
  echo "$1"
}
if [ "${1:-}" = asis ]; then   # the positive control: ours exactly as the full set ran it, on a fresh server
  mk asis - -
  s4=$(arm asis)
  echo "=== $(date -Is) c120diag asis: $s4"
  if ok "$s4"; then echo -e "\n→ ours as configured PASSES on a fresh server: the full set's failure needs the earlier requests too (not the switch alone)." >> $OUT
  else echo -e "\n→ ours as configured fails on a fresh server too ($s4/6): confirmed - STRATA_QSA_SPLIT_ATTN on a layer split breaks long prompts." >> $OUT; fi
  cat $OUT; exit 0
fi
cat > $OUT <<EOF
# Round 15 — the splice's placement C at 120K: which build gives the degenerate answer ($(date -Is))

the full set (r15-q5s-Cx72-full): both 120K requests 256 tokens / 255 characters, drafts 170/170, decode hit rate 100 %,
needle 0/6; 8K-64K normal. Each arm: a fresh server with C's placement, the 120K needle (run 0).

| arm | needle 120K | output | decode expert-cache hit rate |
|---|---|---|---|
EOF
mk stock $WS/bringup/out/r15q5s/engine-stock/strata $WS/bringup/out/r15q5s/strata-stock/data/expert-profile.bin \
   STRATA_SPEC_EXACT STRATA_SIDE_MIXER STRATA_ROUTER_Q8K STRATA_GR_FORK STRATA_QSA_SPLIT_ATTN STRATA_COST_GATE
s=$(arm stock)
echo "=== $(date -Is) c120diag stock: $s"
if ! [[ "$s" =~ ^[0-9]+$ ]]; then
  echo -e "\n→ the stock arm gave no score ($s): no conclusion." >> $OUT
elif ! ok "$s"; then
  echo -e "\n→ stock v0.1.40.2 fails too: an upstream bug in the layer split at long context, not the port." >> $OUT
else
  mk nosplitattn - - STRATA_QSA_SPLIT_ATTN
  s2=$(arm nosplitattn)
  echo "=== $(date -Is) c120diag nosplitattn: $s2"
  if ok "$s2"; then
    echo -e "\n→ stock passes and ours passes without STRATA_QSA_SPLIT_ATTN: that switch breaks C at 120K." >> $OUT
  else
    mk patchedoff - - STRATA_SPEC_EXACT STRATA_SIDE_MIXER STRATA_ROUTER_Q8K STRATA_GR_FORK STRATA_QSA_SPLIT_ATTN STRATA_COST_GATE
    s3=$(arm patchedoff)
    echo "=== $(date -Is) c120diag patchedoff: $s3"
    echo -e "\n→ stock passes; ours without QSA_SPLIT_ATTN: $s2; ours patched-off: $s3 (fails = the port's binary; passes = one of our other switches)." >> $OUT
  fi
fi
cat $OUT
