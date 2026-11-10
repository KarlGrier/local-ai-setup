#!/usr/bin/env python3
"""p13_crash.py BASE LABEL — round 13 Part 1.3: kill the engine of a TEST server mid-request and see what the next request
gets and what is lost.  Synthetic prompts only.  Sequence (no thinking, greedy, one request at a time unless noted):
  0. two chats A (~9K-token document) and B (~5K) answered, so both are in the engine's chat cache; A's follow-up timed
     (the cached-turn baseline: reused tokens, TTFT)
  1. kill9-decode:  a long streamed answer; after 100 content deltas the engine gets SIGKILL.  Recorded: what the client
     got (stream end, error event, HTTP status), then the next request (status, wall time, new engine pid), then A's
     follow-up again (reused tokens = what survived)
  2. segv-prefill:  a fresh ~30K-token prompt, streamed; 1.0 s into the prompt read the engine gets SIGSEGV (a crash
     signature); next request as above
  3. kill9-idle:    SIGKILL with no request running; the next request
Each step writes a JSON line to results/r13/p13/crash-LABEL.jsonl.  The server's own restart handling is what is
measured; nothing is restarted by this script."""
import http.client
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BASE, LABEL = sys.argv[1].rstrip("/"), sys.argv[2]
HOST, PORT = BASE.split("//")[1].split(":")[0], int(BASE.rsplit(":", 1)[1])
OUT = Path(f"/home/USER/ai-speed-testing/strata-compare/results/r13/p13/crash-{LABEL}.jsonl")
OUT.parent.mkdir(parents=True, exist_ok=True)
f = OUT.open("w")


def log(rec):
    rec["t"] = time.strftime("%H:%M:%S")
    f.write(json.dumps(rec) + "\n")
    f.flush()
    print(json.dumps(rec)[:400], flush=True)


def pids():
    out = subprocess.run(["ss", "-H", "-ltnp", f"( sport = :{PORT} )"], capture_output=True, text=True).stdout
    srv = int(out.split("pid=")[1].split(",")[0]) if "pid=" in out else None
    eng = None
    if srv:
        r = subprocess.run(["pgrep", "-P", str(srv), "-f", "strata --serve"], capture_output=True, text=True).stdout.split()
        eng = int(r[0]) if r else None
    return srv, eng


def get(path):
    try:
        return json.loads(urllib.request.urlopen(BASE + path, timeout=20).read())
    except Exception as e:  # noqa: BLE001
        return {"_error": repr(e)[:200]}


def last_record():
    m = get("/metrics?requests=all")
    r = m.get("requests") or []
    return r[-1] if r else {}


def para(seed, n):
    words = ["river", "harbor", "lantern", "granite", "meadow", "copper", "signal", "orchard", "glacier", "canyon",
             "ember", "willow", "quartz", "timber", "falcon", "prairie", "summit", "cobalt", "tundra", "beacon"]
    out, x = [], seed
    for i in range(n):
        x = (x * 1103515245 + 12345) % 2**31
        out.append(words[x % 20])
        if i % 14 == 13:
            out.append(".\n" if i % 70 == 69 else ".")
    return " ".join(out)


def chat(messages, max_tokens=64, stream=False, kill_after=None, kill_sig=signal.SIGKILL, kill_at_s=None):
    """One request.  kill_after: send kill_sig to the engine after that many streamed content deltas; kill_at_s: after
    that many seconds (during the prompt read)."""
    body = {"model": "x", "stream": stream, "reasoning_effort": "none", "temperature": 0, "max_tokens": max_tokens,
            "messages": messages}
    c = http.client.HTTPConnection(HOST, PORT, timeout=900)
    t0 = time.time()
    c.request("POST", "/v1/chat/completions", json.dumps(body), {"Content-Type": "application/json"})
    killed = None
    if kill_at_s is not None:
        time.sleep(kill_at_s)
        _, eng = pids()
        os.kill(eng, kill_sig)
        killed = {"pid": eng, "sig": int(kill_sig), "at_s": round(time.time() - t0, 2)}
    r = c.getresponse()
    res = {"status": r.status, "ttfb_s": round(time.time() - t0, 2)}
    if not stream:
        raw = r.read()
        try:
            d = json.loads(raw)
            res["content"] = (d.get("choices") or [{}])[0].get("message", {}).get("content", "")[:120] if "choices" in d else None
            res["finish"] = (d.get("choices") or [{}])[0].get("finish_reason") if "choices" in d else None
            res["error"] = d.get("error")
            res["usage"] = d.get("usage")
        except ValueError:
            res["raw"] = raw[:300].decode(errors="replace")
    else:
        n, first, events, errors = 0, None, 0, []
        for line in r:
            line = line.strip()
            if not line.startswith(b"data:"):
                continue
            events += 1
            payload = line[5:].strip()
            if payload == b"[DONE]":
                res["done_marker"] = True
                break
            try:
                d = json.loads(payload)
            except ValueError:
                continue
            if "error" in d:
                errors.append(str(d["error"])[:300])
                continue
            ch = (d.get("choices") or [{}])[0]
            if ch.get("delta", {}).get("content"):
                n += 1
                if first is None:
                    first = round(time.time() - t0, 2)
                if kill_after is not None and n == kill_after and killed is None:
                    _, eng = pids()
                    os.kill(eng, kill_sig)
                    killed = {"pid": eng, "sig": int(kill_sig), "after_deltas": n, "at_s": round(time.time() - t0, 2)}
            if ch.get("finish_reason"):
                res["finish"] = ch["finish_reason"]
        res.update({"deltas": n, "first_delta_s": first, "events": events, "errors": errors})
    res["wall_s"] = round(time.time() - t0, 2)
    res["killed"] = killed
    c.close()
    return res


doc_a = "Here is a field report.\n\n" + para(7, 6500) + "\n\nList three words that appear in it."
doc_b = "Here is a second report.\n\n" + para(11, 3600) + "\n\nWhich word appears first?"
A = [{"role": "user", "content": doc_a}]
B = [{"role": "user", "content": doc_b}]
srv0, eng0 = pids()
log({"step": "start", "server": srv0, "engine": eng0, "status": get("/status").get("loaded")})
ra = chat(A)
A2 = A + [{"role": "assistant", "content": ra.get("content") or ""}, {"role": "user", "content": "And one more word?"}]
log({"step": "0 chat A", **ra, "rec": last_record()})
log({"step": "0 chat B", **chat(B), "rec": last_record()})
r = chat(A2)
log({"step": "0 A follow-up (cached baseline)", **r, "rec": last_record()})

ESSAY = [{"role": "user", "content": "Write a long, detailed essay (at least 2,500 words) on the history of lighthouses."}]
for step, kw, msgs in (("1 kill9-decode", dict(stream=True, max_tokens=3000, kill_after=100, kill_sig=signal.SIGKILL), ESSAY),
                       ("2 segv-prefill", dict(stream=True, max_tokens=64, kill_at_s=1.0, kill_sig=signal.SIGSEGV),
                        [{"role": "user", "content": "A long log follows.\n\n" + para(23, 22000) + "\n\nSummarize it."}]),
                       ("3 kill9-idle", None, None)):
    before = pids()
    if kw is None:
        os.kill(before[1], signal.SIGKILL)
        time.sleep(2)
        log({"step": step + " (killed)", "engine_before": before[1], "health": get("/health"), "status": get("/status").get("loaded")})
    else:
        res = chat(msgs, **kw)
        log({"step": step + " (the killed request)", **res, "engine_before": before[1]})
        time.sleep(1)
        log({"step": step + " (right after)", "health": get("/health"), "status_loaded": get("/status").get("loaded"),
             "pids": pids()})
    nxt = chat([{"role": "user", "content": "Say OK."}], max_tokens=16)
    log({"step": step + " next request", **nxt, "pids_after": pids(), "rec": last_record()})
    fol = chat(A2)
    log({"step": step + " A follow-up (what survived)", **fol, "rec": last_record()})
f.close()
print("crash test done:", OUT)
