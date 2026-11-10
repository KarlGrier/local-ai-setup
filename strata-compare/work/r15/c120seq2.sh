#!/bin/bash
# c120seq2.sh ARM... (copy of c120seq.sh with SEQ_SIZES; c120seq.sh was running when this was made) — round 15: the splice's placement C broke at 120K inside its full set, but a fresh server answers the
# 120K needle correctly on every build (c120diag.md). So: the full set's own order on a fresh server — the warm-up, the
# 8K / 32K / 64K speed prompts (768 tokens each, as the full set), then the 120K needle (needle2 run 0) — per arm
# (work/r15/cfg/c120-ARM.json from c120diag.sh: asis = ours as configured, stock = v0.1.40.2). Appends to
# results/r15/c120diag.md.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
P=.venv/bin/python; OUT=results/r15/c120diag.md
export GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
grep -q 'after the full set.s own order' $OUT || cat >> $OUT <<'EOF'

**After the full set's own order** (fresh server: warm-up, 8K / 32K / 64K speed prompts with 768 tokens each, then the
120K needle):

| arm | 8K / 32K / 64K answers (characters per token) | needle 120K | output | decode expert-cache hit rate |
|---|---|---|---|---|
EOF
for n in "$@"; do
  C=work/r15/cfg/c120-$n.json L=r15-c120seq-$n
  E=$($P -c "import json; print(json.load(open('$C'))['log'])"); touch "$E"; e0=$(wc -l < "$E")
  for i in $(seq 180); do ss -H -ltn "( sport = :8081 )" | grep -q . || break; sleep 1; done
  $P scripts/evict.py $WS/models/r15/splice-q5/*.gguf > /dev/null
  if ! bringup/lib/srv.sh start $L "$C" > work/r15/cfg/c120seq-$n-start.txt 2>&1; then
    echo "| $n | did not start ($(tail -1 work/r15/cfg/c120seq-$n-start.txt | cut -c1-100)) | – | – | – |" >> $OUT; continue; fi
  $P work/r5/warmup.py http://127.0.0.1:8081 > /dev/null 2>&1
  B="$P scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $E --session $L-$(date +%m%dT%H%M)"
  for sz in ${SEQ_SIZES:-8k 32k 64k}; do SPEED_FILE=r15/speed-r15 $B speed --sizes $sz --reps 0 > /dev/null 2>&1; done
  NEEDLE_DIR=$WS/work/r5/needle2 $P bringup/lib/needle2.py ask --label $L --sizes 120k --runs 0 > /dev/null 2>&1
  bringup/lib/srv.sh stop > /dev/null 2>&1
  $P - "$L" "$E" "$e0" "$n" >> $OUT <<'PY'
import json, re, sys
L, E, e0, n = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
rows = [json.loads(l) for l in open("results/runs.jsonl") if f'"{L}"' in l and '"speed"' in l]
cpt = " / ".join(f"{(r.get('reasoning_chars') or 0) + (r.get('content_chars') or 0)} / {r.get('completion_tokens')} ({((r.get('reasoning_chars') or 0) + (r.get('content_chars') or 0)) / max(1, r.get('completion_tokens') or 1):.1f})" for r in rows)
rec = [json.loads(l) for l in open("bringup/out/results/needle2.jsonl") if f'"{L}"' in l]
t = "\n".join(open(E, errors="replace").read().splitlines()[e0:])
req = re.findall(r"prompt 1228\d\d tokens .*?(\d+) generated in", t)
hit = re.findall(r"decode expert cache hit rate: ([\d.]+)%", t)
if not rec:
    print(f"| {n} | {cpt} | no answer | – | – |"); sys.exit()
r = rec[-1]
print(f"| {n} | {cpt} | {r['score']}/6 | {r.get('reasoning_chars', 0) + len(r.get('answer') or '')} characters for {req[-1] if req else '?'} tokens | {hit[-1] if hit else '–'} % |")
PY
  echo "=== $(date -Is) c120seq $n: $(tail -1 $OUT | cut -c1-160)"
done
cat $OUT
