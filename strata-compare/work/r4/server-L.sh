#!/bin/bash
# Round 4 reference server: llama.cpp llama-server AS-IS (default: signal-3.8-opus build 6fcaa16, read-only; LLAMA_BIN overrides) + ISTA IQ3_S,
# Placement/batch/threads reused from signal-3.8-opus (all routed experts in pinned host RAM, ubatch 4096,
# default threads); n-gram table lazy (read on demand from disk/page cache) as ISTA recommends; YOUR sampling 0.6/0.95/20/0.05, xhigh (same as Strata).
#   server-B.sh start|stop|status   (127.0.0.1:8081)   EXTRA="..." adds flags
WS=/home/USER/ai-speed-testing/strata-compare
BIN=${LLAMA_BIN:-/home/USER/ai-speed-testing/signal-3.8-opus/build/llama.cpp-6fcaa16/build/bin/llama-server}
MODEL=$WS/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf
PORT=${PORT:-8081}
PIDF=$WS/logs/server-L.pid
case ${1:-} in
start)
  LOG=$WS/logs/r4/server-L_$(date +%Y%m%dT%H%M%S).log
  ARGS=(--model "$MODEL" --alias ista-iq3s --host 127.0.0.1 --port $PORT
    --ctx-size 131072 --parallel 1 --kv-unified --cache-type-k q8_0 --cache-type-v q8_0 --flash-attn on
    --no-context-shift --cache-reuse 0 --jinja --reasoning on --reasoning-effort xhigh --reasoning-format deepseek
    --reasoning-budget -1 --n-predict -1 --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0.05 --no-mmproj
    --fit off --gpu-layers all --override-tensor 'blk\.[0-9]+\.ffn_(up|gate|down)_exps\.weight=CPU'
    --ubatch-size ${UB:-4096} --batch-size ${UB:-4096} --load-mode ${LM:-mmap} --lazy-mode on --cache-ram 4096
    --log-verbosity 4 --log-timestamps --log-colors off $EXTRA)
  echo "# $(date -Is) ${ARGS[*]}" > "$LOG"
  t0=$(date +%s.%N)
  setsid nohup env -u LLAMA_ARG_HOST "$BIN" "${ARGS[@]}" >> "$LOG" 2>&1 < /dev/null &
  echo $! > "$PIDF"
  (setsid nohup $WS/work/r4/memguard.sh $(cat "$PIDF") 20480 1024 >> "$LOG" 2>&1 &)
  for i in $(seq 1 900); do
    kill -0 $(cat "$PIDF") 2>/dev/null || { tail -30 "$LOG"; echo "B exited"; exit 1; }
    curl -sf -m 2 http://127.0.0.1:$PORT/health >/dev/null 2>&1 && break; sleep 1
  done
  echo "B ready pid $(cat $PIDF) load_time_s $(echo "$(date +%s.%N) - $t0" | bc) log $LOG";;
stop)
  [ -f "$PIDF" ] && kill -TERM $(cat "$PIDF") 2>/dev/null; for i in $(seq 1 120); do kill -0 $(cat "$PIDF") 2>/dev/null || break; sleep 0.5; done; rm -f "$PIDF"; echo stopped;;
status) [ -f "$PIDF" ] && ps -o pid,etime,rss,args -p $(cat "$PIDF") | cut -c1-200;;
*) echo "usage: $0 start|stop|status";;
esac
