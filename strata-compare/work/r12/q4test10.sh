#!/bin/bash
# q4test10.sh — round 10 D.3 (Q4 fair retest, timeboxed 2 h, no tuning). Budget = work/r12/q4/budget (q4budget10.sh).
#  1. served, your settings, fresh guarded server each, the Q4 pages evicted first: Q4 / IQ3_S-ref / Q4 (the IQ3_S reference
#     under Q4's restrictions: 32K context, no chat cache, the 5080 alone): work/r12/q4run.py (decode math + code, TTFT 8K
#     and ~32K, NVMe bytes and swap per request, the engine's file-tier bytes per round);
#  2. teacher-forced NLL on four human-written texts that no model wrote (corpus, long16k, long24k, long28k: source code
#     and licence texts; their prompts fit 32K): Q4 on the K-quant measurement twin (engine-v36q4m), one GPU; IQ3_S =
#     the base twin's one-GPU results (V35mtf-single, same texts).
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source work/r12/env.sh
B=$(cat work/r12/q4/budget)
G=/home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL
echo "=== $(date -Is) q4test10 budget $B GiB"
n=0; for arm in q4 iq3 q4; do n=$((n+1)); L=Q4srv-$arm-$n
  if [ $arm = q4 ]; then CFG=configs/Q4-$B.json; else CFG=configs/Q4ref-iq3.json; fi
  ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
  .venv/bin/python scripts/evict.py $G/*.gguf $WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf > /dev/null
  (setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern '/strata --serve' --out logs/r12/monitor-$L > /dev/null 2>&1 &)
  echo "=== $(date -Is) $L start ($CFG)"
  if work/r12/srv.sh start $L $CFG; then
    grep -E 'expert cache [0-9]|budget|resident|free with|lookahead' $ELOG | tail -6
    .venv/bin/python work/r5/warmup.py http://127.0.0.1:8081
    .venv/bin/python work/r12/q4run.py $L $ELOG
    echo "vram at end: $(nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ' ')"
    work/r12/srv.sh stop
  else echo "$L: start FAILED"; fi
  scripts/stopmon.sh $L
done
.venv/bin/python - <<PY
import json
c = json.load(open("configs/Q4-$B.json"))
c["exe"] = "$WS/engine-v36q4m/strata"; c["server"] = "$WS/strata-v36m/serve/server.py"; c["log"] = "$WS/logs/engine-Q4tf.log"
c["_comment"] = "round 10 D.3: Q4 TF on the K-quant measurement twin (v36-c11-meas built with -DSTRATA_MMQ_KQUANTS=ON), budget $B GiB"
json.dump(c, open("configs/Q4tf.json", "w"), indent=1)
PY
work/r12/tf.sh Q4tf configs/Q4tf.json engine-v36q4m/strata corpus long16k long24k long28k
.venv/bin/python - <<'PY'
import math
from pathlib import Path
R = Path("/home/USER/ai-speed-testing/strata-compare/results")
print("| text (human-written) | IQ3_S NLL (one GPU) | Q4 NLL (one GPU) | Q4 − IQ3_S (clipped at 5) | ± se |")
print("|---|---|---|---|---|")
for t in ("corpus", "long16k", "long24k", "long28k"):
    a = [float(x) for x in (R / f"tf-V35mtf-single-{t}.nll").read_text().split()]
    b = [float(x) for x in (R / f"tf-Q4tf-{t}.nll").read_text().split()] if (R / f"tf-Q4tf-{t}.nll").exists() else None
    if not b: print(f"| {t} | {sum(a)/len(a):.4f} | – | – | – |"); continue
    d = [min(y, 5) - min(x, 5) for x, y in zip(a, b)]
    m = sum(d) / len(d); se = (sum((x - m) ** 2 for x in d) / (len(d) - 1)) ** 0.5 / math.sqrt(len(d))
    print(f"| {t} | {sum(a)/len(a):.4f} | {sum(b)/len(b):.4f} | {m:+.4f} | {se:.4f} |")
PY
# your addition: draft acceptance for Q4 and IQ3_S on the SAME texts (force mode on the measurement twins, greedy drafts)
work/r12/with_server.sh Q4acc configs/Q4tf.json -- ".venv/bin/python work/r12/tfaccept.py q4"
work/r12/with_server.sh IQ3acc configs/Q4ref-iq3m.json -- ".venv/bin/python work/r12/tfaccept.py iq3"
.venv/bin/python - <<'PY'
import json
from pathlib import Path
R = Path("/home/USER/ai-speed-testing/strata-compare/results/r12")
a, b = json.loads((R / "tfaccept-iq3.json").read_text()), json.loads((R / "tfaccept-q4.json").read_text())
print("| text (forced, same ids) | IQ3_S acceptance | Q4 acceptance | IQ3_S first draft | Q4 first draft | IQ3_S / Q4 NLL |")
print("|---|---|---|---|---|---|")
for t in a:
    x, y = a[t], b.get(t, {})
    f = lambda v: "–" if v is None else f"{v:.3f}"
    print(f"| {t} | {f(x['acceptance'])} ({x['accepted']}/{x['offered']}) | {f(y.get('acceptance'))} ({y.get('accepted')}/{y.get('offered')}) | "
          f"{f(x['first_draft_hit'])} | {f(y.get('first_draft_hit'))} | {f(x['nll'])} / {f(y.get('nll'))} |")
for arm in ("q4", "iq3"):
    for f in sorted(R.glob(f"q4io-Q4srv-{arm}-*.json")):
        for o in json.loads(f.read_text()):
            print(f"served {f.stem} {o['item']}: decode {o['decode_tps']} tok/s, acceptance {o.get('acceptance') and round(o['acceptance'], 3)}, "
                  f"TTFT {o['ttft_s'] and round(o['ttft_s'], 2)} s, NVMe {o['nvme_mb_per_round']:.1f} MB/round, file tier {o['file_mb_per_round']:.1f} MB/round, swap in/out {o['swap_in_pages']}/{o['swap_out_pages']} pages")
PY
echo "=== $(date -Is) q4test10 done"
