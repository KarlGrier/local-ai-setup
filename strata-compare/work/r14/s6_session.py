#!/usr/bin/env python3
"""s6_session.py BASE LABEL TOKENS PHASE [ENGINE_LOG] — round 14 step 6 (report only): v0.1.40's session files
(POST /slots/0?action=save|restore) with my config. One chat of ~TOKENS tokens (Round 10's LDR pool, as Round 11's
bigchat262.py), greedy (temperature 0) so the continuation can be compared:

  PHASE build    turn 1 of the chat (greedy, 48 tokens) -> SAVE to <LABEL>.bin (time, size) -> a different short chat
                 (the big one is now parked: in our RAM chat cache) -> RESTORE (time) -> turn 2 (the follow-up):
                 its TTFT, the engine's prompt line (tokens reused), its answer
  PHASE control  the same chat on a fresh server without any save / restore: turn 1, turn 2 -> the reference answers
  PHASE restart  a fresh server: RESTORE (time, a new process) -> turn 2
  PHASE back     after `build`: the short chat again (must come back from the RAM chat cache, not be lost)
State between phases in tmp/r14/s6/<LABEL>.json (the chat text and answers); results appended to results/r14/s6-session.jsonl."""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
BASE, LABEL, TOKENS, PHASE = sys.argv[1].rstrip("/"), sys.argv[2], int(sys.argv[3]), sys.argv[4]
ELOG = sys.argv[5] if len(sys.argv) > 5 else None
ST = WS / "tmp/r14/s6"; ST.mkdir(parents=True, exist_ok=True)
OUT = WS / "results/r14/s6-session.jsonl"
SEED = 7


def post(path, body, timeout=3600):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def count(messages):
    return post("/v1/messages/count_tokens", {"model": "x", "max_tokens": 1, "messages": messages})[1]["input_tokens"]


def chat_text(k, tokens):
    pool = []
    for f in sorted((WS / "work/r10/ldr/corpus/T").glob("*.json")):
        pool += [p["text"] for p in json.loads(f.read_text()).get("pages", []) if p.get("text")]
    stream = "\n\n".join(pool)
    head = f"[{LABEL} session chat {k}]\n"
    ask = "\n\nWhat are the three main disagreements between these sources? Answer in two sentences."
    start = (k * len(stream)) // 3
    lo, hi, best = 2000, 6 * tokens, None
    for _ in range(30):
        mid = (lo + hi) // 2
        body = (stream[start:] + "\n\n" + stream)[:mid]
        n = count([{"role": "user", "content": head + body + ask}])
        best = (head + body + ask, n)
        if abs(n - tokens) <= 256:
            break
        lo, hi = (mid + 1, hi) if n < tokens else (lo, mid - 1)
    return best


def log_mark():
    return len(Path(ELOG).read_text(errors="replace").splitlines()) if ELOG else 0


def log_since(mark, keys=("strata serve: prompt", "chat cache", "session", "RESTORE", "SAVE")):
    if not ELOG:
        return []
    return [l.split("strata serve: ", 1)[-1][:200] for l in Path(ELOG).read_text(errors="replace").splitlines()[mark:]
            if any(k in l for k in keys)]


def turn(messages, tag, max_tokens=48):
    mark = log_mark()
    t0 = time.time()
    ttft, text = None, []
    body = {"model": "x", "stream": True, "max_tokens": max_tokens, "messages": messages, "temperature": 0,
            "seed": SEED, "reasoning_effort": "none"}
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3600) as r:
        for raw in r:
            line = raw.decode(errors="replace").strip()
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            d = (json.loads(line[6:]).get("choices") or [{}])[0].get("delta", {})
            if d.get("content"):
                text.append(d["content"])
            if (d.get("content") or d.get("reasoning_content")) and ttft is None:
                ttft = time.time() - t0
    time.sleep(0.5)
    rec = {"label": LABEL, "phase": PHASE, "turn": tag, "ttft_s": round(ttft or -1, 3), "total_s": round(time.time() - t0, 2),
           "answer": "".join(text), "engine": log_since(mark)}
    emit(rec)
    return rec["answer"]


def slot(action, name):
    t0 = time.time()
    mark = log_mark()
    code, body = post(f"/slots/0?action={action}", {"filename": name})
    rec = {"label": LABEL, "phase": PHASE, "turn": action, "http": code, "wall_s": round(time.time() - t0, 3), "body": body,
           "engine": log_since(mark)}
    emit(rec)
    return code, body


def emit(rec):
    with OUT.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    show = {k: v for k, v in rec.items() if k not in ("engine",)}
    if "answer" in show:
        show["answer"] = show["answer"][:90]
    print(json.dumps(show)[:400], "|", " | ".join(rec.get("engine", []))[:300], flush=True)


state_f = ST / f"{LABEL}.json"
q2 = "Which of the sources is the most recent? One sentence."
if PHASE in ("build", "control"):
    text, n = chat_text(0, TOKENS)
    msgs = [{"role": "user", "content": text}]
    emit({"label": LABEL, "phase": PHASE, "turn": "size", "tokens": n})
    a1 = turn(msgs, "turn1")
    follow = msgs + [{"role": "assistant", "content": a1}, {"role": "user", "content": q2}]
    st = json.loads(state_f.read_text()) if state_f.exists() else {}
    if PHASE == "build":
        slot("save", f"{LABEL}.bin")
        f = WS / "tmp/r14/sessions" / f"{LABEL}.bin"
        emit({"label": LABEL, "phase": PHASE, "turn": "file", "bytes": f.stat().st_size if f.exists() else None})
        other, n2 = chat_text(2, 2000)
        o_msgs = [{"role": "user", "content": other}]
        oa = turn(o_msgs, "other chat (2K): the big chat is parked")
        slot("restore", f"{LABEL}.bin")
        a2 = turn(follow, "turn2 after restore")
        st.update(text=text, a1=a1, a2_restored=a2, other=other, other_a=oa)
    else:
        a2 = turn(follow, "turn2 (no save/restore)")
        st.update(a1_control=a1, a2_control=a2)
    state_f.write_text(json.dumps(st))
elif PHASE == "restart":
    st = json.loads(state_f.read_text())
    slot("restore", f"{LABEL}.bin")
    follow = [{"role": "user", "content": st["text"]}, {"role": "assistant", "content": st["a1"]}, {"role": "user", "content": q2}]
    a2 = turn(follow, "turn2 after restore in a new process")
    st.update(a2_restart=a2)
    state_f.write_text(json.dumps(st))
elif PHASE == "back":
    st = json.loads(state_f.read_text())
    o = [{"role": "user", "content": st["other"]}, {"role": "assistant", "content": st["other_a"]},
         {"role": "user", "content": "And in one word?"}]
    turn(o, "the short chat again (RAM chat cache)", 16)
elif PHASE == "compare":
    st = json.loads(state_f.read_text())
    res = {"label": LABEL, "phase": "compare",
           "turn1_same_as_control": st.get("a1") == st.get("a1_control"),
           "turn2_restored_same_as_control": st.get("a2_restored") == st.get("a2_control"),
           "turn2_restart_same_as_control": st.get("a2_restart") == st.get("a2_control")}
    emit(res)
