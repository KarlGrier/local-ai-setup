#!/bin/bash
# p44nomtp.sh — round 13 Part 4.4: the engine with the MTP assets removed from a config copy (configs/R13NOMTP.json =
# C*13.1 without --mtp). It must either serve correctly or stop with a precise message. If it serves: a correctness
# check (two short questions with known answers), then the chat cache: chat A (a ~9K-token document), chat B, back to A
# (cached tokens reused?). The 0.1.39 server is expected to require --mtp (#708 makes it optional upstream).
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
D=results/r13/p44; mkdir -p $D
if ! PORT=8081 work/r13/srv.sh start nomtp configs/R13NOMTP.json > $D/start.txt 2>&1; then
  echo "DID NOT START:"; tail -12 $D/start.txt
  L=$(ls -t logs/r13/server_nomtp_*.log | head -1); echo "--- server log tail ($L):"; tail -8 $L
  echo "--- engine log tail:"; tail -8 logs/engine-R13NOMTP.log 2>/dev/null
  exit 0
fi
.venv/bin/python - <<'PY'
import json, time, urllib.request
B = "http://127.0.0.1:8081"
def ask(msgs, n=64):
    t0 = time.time()
    d = json.loads(urllib.request.urlopen(urllib.request.Request(B + "/v1/chat/completions", data=json.dumps(
        {"model": "x", "messages": msgs, "max_tokens": n, "temperature": 0, "reasoning_effort": "none"}).encode(),
        headers={"Content-Type": "application/json"}), timeout=600).read())
    return d["choices"][0]["message"]["content"], d.get("usage", {}), round(time.time() - t0, 2)
for q, want in (("What is 17*3? Answer with the number only.", "51"), ("What is the capital of Australia? One word.", "Canberra")):
    a, u, t = ask([{"role": "user", "content": q}])
    print(f"correctness: {q!r} -> {a!r} ({'ok' if want in a else 'WRONG'}), {t} s")
doc = "Here is a field report.\n\n" + " ".join(f"river{i % 13} harbor{i % 7} lantern." for i in range(2600)) + "\n\nWhich word appears first?"
A = [{"role": "user", "content": doc}]
a, u, t = ask(A, 16); print(f"chat A: {u.get('prompt_tokens')} prompt tokens, {t} s")
a2, u2, t2 = ask([{"role": "user", "content": "A different short chat: name a color."}], 16); print(f"chat B: {t2} s")
a3, u3, t3 = ask(A + [{"role": "assistant", "content": a}, {"role": "user", "content": "And the second word?"}], 16)
print(f"back to A: {u3.get('prompt_tokens')} prompt tokens, cached {(u3.get('prompt_tokens_details') or {}).get('cached_tokens')}, {t3} s")
PY
grep -iE "draft|mtp|spec|suffix" $(ls -t logs/r13/server_nomtp_*.log | head -1) | head -6
work/r13/srv.sh stop
