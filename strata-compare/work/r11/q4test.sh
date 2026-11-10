#!/bin/bash
# q4test.sh — round 9 Phase 0.4 (Unsloth UD-Q4_K_XL short test, timeboxed, no tuning). Budget = work/r11/q4/budget
# (q4budget.sh). Same flags on the stock v0.1.31 binary (Q4s-B) and on C*10 (Q4c-B); the RTX 5080 alone unless noted.
#  1. exact greedy pair (CLI, fixed computation: --adapt-swaps 0 --suffix-draft 0 --expert-cache 1500), math 256 tokens,
#     stock / C*10 / C*10 / stock (output hashes, ms per round, the engine's SSD figures);
#  2. served, your settings, fresh guarded server each, Q4 pages evicted first, order stock / C*10 / C*10 / stock:
#     warm-up, long reasoning math + code (2,048-token cap), one 8K and one 32K prompt (+64 tokens); monitor = SSD reads;
#  3. teacher-forced NLL on the short texts (math, corpus): stock twin (engine-v0131m) and C*10's twin (engine-r9m);
#  4. C*10 with the 4060 Ti helper (--expert-cache-device1 2000) if it starts cleanly: one served round;
#  5. llama.cpp (Round 4's work/r4/llama_tf-6fcaa16, read-only libraries) on the same Q4 file: TF math + corpus.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source work/r11/env.sh
B=$(cat work/r11/q4/budget)
G=/home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 1500"
echo "=== $(date -Is) q4test budget $B GiB"
# 1
n=0; for arm in s c c s; do n=$((n+1))
  COLD=0 work/r11/run.sh q4x-$arm-$n configs/Q4$arm-$B.json math 256 $X | grep -E 'exit|decode |speculation' | tr '\n' ' '; echo
  grep -iE 'ssd|mapped|budget|resident|lookahead' logs/r11/prof/q4x-$arm-$n.out | head -6
done
.venv/bin/python work/r11/p0_table.py q4x-s-1 q4x-c-2 q4x-c-3 q4x-s-4
# 2
n=0; for arm in s c c s; do n=$((n+1)); L=Q4$arm-srv-$n; CFG=configs/Q4$arm-$B.json
  ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
  .venv/bin/python scripts/evict.py $G/*.gguf > /dev/null
  (setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern '/strata --serve' --out logs/r11/monitor-$L > /dev/null 2>&1 &)
  echo "=== $(date -Is) $L start"
  if work/r11/srv.sh start $L $CFG; then
    grep -E 'expert cache|budget|resident|free with|lookahead|pinned|page-lock' $ELOG | tail -8
    .venv/bin/python work/r5/warmup.py http://127.0.0.1:8081
    .venv/bin/python scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $L longreason --items math,code --max-tokens 2048
    .venv/bin/python work/r11/q4prompts.py $L $ELOG
    echo "vram at end: $(nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader | tr '\n' ' ')"
    work/r11/srv.sh stop
  fi
  scripts/stopmon.sh $L
done
# 3
for arm in s c; do
  E=$([ $arm = s ] && echo engine-v0131m/strata || echo engine-r9m/strata)
  work/r11/tf.sh TFq4-$arm configs/Q4$arm-$B.json $E math corpus
done
# 4
.venv/bin/python - <<PY
import json
c = json.load(open("configs/Q4c-$B.json"))
c["args"] += ["--expert-cache-device1", "2000"]
c["env"]["CUDA_VISIBLE_DEVICES"] = "GPU-UUID-RTX5080,GPU-UUID-RTX4060TI"
c["log"] = c["log"].replace("Q4c-", "Q4ch-")
c["_comment"] += " + the 4060 Ti helper cache (--expert-cache-device1 2000)."
json.dump(c, open("configs/Q4ch-$B.json", "w"), indent=1)
json.dump(json.load(open("configs/Q4c-$B.shared-settings.json")), open("configs/Q4ch-$B.shared-settings.json", "w"), indent=1)
PY
L=Q4ch-srv-1; CFG=configs/Q4ch-$B.json; ELOG=$(.venv/bin/python -c "import json; print(json.load(open('$CFG'))['log'])")
.venv/bin/python scripts/evict.py $G/*.gguf > /dev/null
(setsid nohup .venv/bin/python scripts/monitor.py --pid-pattern '/strata --serve' --out logs/r11/monitor-$L > /dev/null 2>&1 &)
if work/r11/srv.sh start $L $CFG; then
  grep -E 'expert cache|CUDA1|budget|free with' $ELOG | tail -6
  .venv/bin/python work/r5/warmup.py http://127.0.0.1:8081
  .venv/bin/python scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $L longreason --items math,code --max-tokens 2048
  .venv/bin/python work/r11/q4prompts.py $L $ELOG
  work/r11/srv.sh stop
else echo "helper start FAILED (recorded, not fixed)"; tail -20 $ELOG; fi
scripts/stopmon.sh $L
# 5
J=(); for T in math corpus; do rm -f results/tf-LQ4-$T.nll; J+=(--tf $WS/work/prof/tf-$T.prompt $WS/work/prof/tf-$T.text $WS/results/tf-LQ4-$T.nll); done
echo "=== $(date -Is) llama.cpp TF on the Q4 file"
env -u LLAMA_ARG_HOST CUDA_VISIBLE_DEVICES=0 .venv/bin/python work/r11/guard.py LQ4-tf -- $WS/work/r4/llama_tf-6fcaa16 "${J[@]}" --model $G/Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf \
  --ctx-size 8192 --cache-type-k q8_0 --cache-type-v q8_0 --flash-attn on --fit off --gpu-layers all \
  --override-tensor 'blk\.[0-9]+\.ffn_(up|gate|down)_exps\.weight=CPU' --ubatch-size 4096 --batch-size 4096 \
  --load-mode mmap --parallel 1 > logs/r11/LQ4-tf.out 2> logs/r11/LQ4-tf.err
echo "llama.cpp exit $?"; cat logs/r11/LQ4-tf.out; grep -E 'llama_tf:|error|ERROR|failed' logs/r11/LQ4-tf.err | head -8
tail -1 logs/r11/guard/summary.txt
echo "=== $(date -Is) q4test done"
