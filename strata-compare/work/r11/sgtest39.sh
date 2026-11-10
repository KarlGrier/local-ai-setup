#!/bin/bash
# sgtest39.sh — round 11 F: Signal on 0.1.39 + Q6_K embedding vs IQ3_S V39W; sgtest.sh — round 10 (your addition, after the Q4 retest; at most 2 h, no tuning): the same prompts on Signal
# AP-Q4_K_XL (budget work/r11/signal/budget, 32K, the 5080 alone) and on IQ3_S C*11 (configs/R10-C11.json = C*11 as
# promoted), order Signal / C*11 / C*11 / Signal, fresh guarded server and cold page cache each, your settings:
# work/r11/q4run.py plan "signal". Then the table: draft acceptance, tokens per round, output tokens per answer, decode
# tok/s, time per finished answer.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source work/r11/env.sh
[ -f work/r11/signal/STOP ] && { echo "Signal test stopped: $(cat work/r11/signal/STOP)"; exit 0; }
B=$(cat work/r11/signal/budget)
G=/home/USER/.cache/huggingface/hub/models--agentionai--Signal-3.8-Flash-Next-GGUF/snapshots/eba565bea194b899480ebd8a8ab63d537917004b/AP-Q4_K_XL
n=0; for arm in sg c11 c11 sg; do n=$((n+1)); L=SGsrv-$arm-$n
  if [ $arm = sg ]; then CFG=configs/SG39-$B.json; else CFG=configs/V39W.json; fi
  ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
  .venv/bin/python scripts/evict.py $G/*.gguf $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
  (setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern '/strata --serve' --out logs/r11/monitor-$L > /dev/null 2>&1 &)
  echo "=== $(date -Is) $L start ($CFG)"
  if work/r11/srv.sh start $L $CFG; then
    grep -E 'expert cache [0-9]|budget|resident' $ELOG | tail -4
    .venv/bin/python work/r5/warmup.py http://127.0.0.1:8081
    .venv/bin/python work/r11/q4run.py $L $ELOG signal
    work/r11/srv.sh stop
  else echo "$L: start FAILED"; fi
  scripts/stopmon.sh $L
done
.venv/bin/python - <<'PY'
import json, statistics as st
from pathlib import Path
R = Path("/home/USER/ai-speed-testing/strata-compare/results/r11")
print("| arm | runs | draft acceptance | tokens per round | output tokens per answer (all / finished) | decode tok/s (generated / decode time) | time per finished answer (s) | answers finished |")
print("|---|---|---|---|---|---|---|---|")
for arm, name in (("sg", "Signal AP-Q4_K_XL (32K, 5080 alone)"), ("c11", "IQ3_S, the Phase B build (V39W, both GPUs)")):
    files = sorted(R.glob(f"q4io-SGsrv-{arm}-*.json"))
    rows = [o for f in files for o in json.loads(f.read_text())]
    ans = [o for o in rows if o["item"] not in ("8k", "32k-cut")]
    fin = [o for o in ans if o.get("finish") == "stop"]
    acc = sum(o["drafts_accepted"] or 0 for o in ans) / max(1, sum(o["drafts_offered"] or 0 for o in ans))
    gen = sum(o["generated"] or 0 for o in ans); rounds = sum(o["rounds"] for o in ans)
    dec = st.mean([o["decode_tps"] for o in ans if o["decode_tps"]]) if ans else 0
    print(f"| {name} | {len(files)} | {acc:.3f} | {gen / max(1, rounds):.2f} | {st.mean([o['output_tokens'] or 0 for o in ans]):.0f} / "
          f"{st.mean([o['output_tokens'] for o in fin]) if fin else 0:.0f} | {dec:.1f} | {st.mean([o['t_total_s'] for o in fin]) if fin else 0:.1f} | {len(fin)} of {len(ans)} |")
    for o in rows:
        if o["item"] in ("8k", "32k-cut"):
            print(f"   {name} {o['item']}: TTFT {o['ttft_s'] and round(o['ttft_s'], 2)} s")
print("\n| prompt | Signal: output tokens / finish / tok/s / acceptance (per run) | C*11: same |\n|---|---|---|")
per = {}
for arm in ("sg", "c11"):
    for f in sorted(R.glob(f"q4io-SGsrv-{arm}-*.json")):
        for o in json.loads(f.read_text()):
            per.setdefault(o["item"], {}).setdefault(arm, []).append(o)
for item, d in per.items():
    if item in ("8k", "32k-cut"): continue
    cell = lambda arm: "; ".join(f"{o['output_tokens']} / {o['finish']} / {o['decode_tps']} / {o['acceptance'] and round(o['acceptance'], 2)}" for o in d.get(arm, []))
    print(f"| {item} | {cell('sg')} | {cell('c11')} |")
PY
