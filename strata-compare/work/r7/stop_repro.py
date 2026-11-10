#!/usr/bin/env python3
"""stop_repro.py [--base URL] — round 7: a request after a Stop during a long prompt read.

1. a 32K document in a new chat, the stream closed 6 s in (= the page's Stop while the prompt is being read);
2. at once, a NEW chat with a ~3K-token prompt (read by the batched prompt path, i.e. through the per-chunk hook);
3. the same chat as 1 with a follow-up (the 32K document read again, like the page's next message in that chat);
4. a short question.
Checks: every request after the Stop answers (no error), and the engine process is the same throughout (no restart).
v0.1.26's draft-layer hook reads the prompt path's error string, which a Stop leaves at "cancelled" -> on the unfixed
engine request 2 (or 3) fails and the engine exits (code 1) and is restarted by the server."""
import argparse
import json
import subprocess
import time
from pathlib import Path

import requests

WS = Path("/home/USER/ai-speed-testing/strata-compare")


def engine_pid(port):
    out = subprocess.run(["ss", "-H", "-ltnp", f"( sport = :{port} )"], capture_output=True, text=True).stdout
    try:
        srv = out.split("pid=")[1].split(",")[0]
    except IndexError:
        return None
    kids = subprocess.run(["pgrep", "-P", srv, "-f", "strata --serve"], capture_output=True, text=True).stdout.split()
    return kids[0] if kids else None


def ask(base, messages, cancel_after=None, max_tokens=64):
    body = {"model": "x", "messages": messages, "stream": True, "max_tokens": max_tokens, "temperature": 0}
    t0 = time.time()
    text, err = [], None
    try:
        with requests.post(base + "/v1/chat/completions", json=body, stream=True, timeout=600) as r:
            if r.status_code != 200:
                return {"error": f"HTTP {r.status_code}: {r.text[:200]}", "text": "", "s": time.time() - t0}
            for raw in r.iter_lines():
                if cancel_after is not None and time.time() - t0 > cancel_after:
                    break                                   # the page's Stop: the stream is closed
                if not raw.startswith(b"data: ") or raw[6:] == b"[DONE]":
                    continue
                c = json.loads(raw[6:])
                if c.get("error"):
                    err = str(c["error"])[:200]
                for ch in c.get("choices") or []:
                    d = ch.get("delta") or {}
                    text.append(d.get("content") or "")
    except Exception as e:  # noqa: BLE001
        err = repr(e)[:200]
    return {"error": err, "text": "".join(text), "s": time.time() - t0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8081")
    a = ap.parse_args()
    port = a.base.rsplit(":", 1)[1]
    doc = next(p for p in json.load(open(WS / "prompts/speed.json")) if p["size"] == "32k" and p["rep"] == 1)
    doc = doc["messages"][-1]["content"]
    mid = " ".join(["The quarterly report lists revenue, costs and the outlook for each region in detail."] * 180)
    pid0 = engine_pid(port)
    res = []
    r = ask(a.base, [{"role": "user", "content": doc}], cancel_after=6)
    print(f"1 Stop during a 32K read (closed at {r['s']:.1f} s)", flush=True)
    time.sleep(0.5)
    r2 = ask(a.base, [{"role": "user", "content": mid + "\n\nHow many regions does the text name? One short sentence."}])
    res.append(("2 new chat, ~3K-token prompt after the Stop", r2))
    r3 = ask(a.base, [{"role": "user", "content": doc}, {"role": "assistant", "content": ""},
                      {"role": "user", "content": "Say OK."}])
    res.append(("3 the stopped chat continued (32K read again)", r3))
    r4 = ask(a.base, [{"role": "user", "content": "What is 12*12? Answer with the number only."}])
    res.append(("4 short question", r4))
    ok_all = True
    for name, x in res:
        ok = x["error"] is None and x["text"].strip() != ""
        ok_all &= ok
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {x['s']:.1f} s, error={x['error']}, text={x['text'].strip()[:40]!r}")
    same = engine_pid(port) == pid0
    ok_all &= same
    print(f"{'PASS' if same else 'FAIL'}  same engine process throughout: {pid0} -> {engine_pid(port)}")
    print("STOP-REPRO", "PASS" if ok_all else "FAIL")


if __name__ == "__main__":
    main()
