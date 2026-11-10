#!/usr/bin/env python3
"""failures.py TEST [--base URL] [--engine-log PATH] — round 5, phase 4: failure modes against a running Strata server.

  stop120k   a ~6.6K chat A; a 120K paste in a new chat, cancelled (stream closed) 20 s in; the next request; back to A
  overflow   (a) a chat longer than the context (~135K tokens) -> a clean error, fast; (b) a ~126K prompt with an
             uncapped reasoning answer -> it must end at the context ceiling (finish "length"); (c) (a) streamed;
             a normal request after each
  concurrent (a) a second request while the first streams; (b) two at once from two clients; both must complete
  vramgrab   with the model loaded, another process takes N MiB of the 5080's VRAM (work/r5/vramhog); then a 120K prompt;
             it must fail cleanly or cope - never hang or die mid-request; then the hog goes and a normal request runs
  idlecpu    the server idle for 60 s: CPU time of the server and the engine, per thread (do pool workers spin?)
Every test appends JSON lines to results/r5/failures.jsonl and prints PASS/FAIL lines."""
import argparse
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

import requests

WS = Path("/home/USER/ai-speed-testing/strata-compare")
RES = WS / "results/r5/failures.jsonl"
PAGE = {"reasoning_effort": "high", "temperature": 1.0, "top_p": 0.95, "top_k": 20}   # your chat settings
UUID = "GPU-UUID-RTX5080"
A = None


def rec(test, **kw):
    kw.update(test=test, time=time.strftime("%Y-%m-%dT%H:%M:%S"))
    RES.parent.mkdir(parents=True, exist_ok=True)
    with open(RES, "a") as f:
        f.write(json.dumps(kw) + "\n")


def check(test, name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {test}: {name}{'  — ' + str(detail) if detail != '' else ''}", flush=True)
    rec(test, check=name, ok=bool(ok), detail=str(detail)[:600])
    return ok


def stream(messages, max_tokens=None, cancel_after=None, extra=None, timeout=3600):
    """a chat-page request (stream); returns dict(ttft, total, text, reasoning, finish, error, status, cancelled)"""
    body = {"model": "x", "messages": messages, "stream": True, **PAGE, **(extra or {})}
    if max_tokens:
        body["max_tokens"] = max_tokens
    t0 = time.time()
    out = {"ttft": None, "text": "", "reasoning": "", "finish": None, "error": None, "status": None, "cancelled": False}
    try:
        with requests.post(f"{A.base}/v1/chat/completions", json=body, stream=True, timeout=timeout) as r:
            out["status"] = r.status_code
            timer = None
            if cancel_after is not None:   # the page's Stop: close the connection at that moment, from a timer
                def close_now():
                    out["cancelled"] = True
                    out["closed_at"] = time.time() - t0
                    try:
                        r.raw._fp.fp.raw._sock.shutdown(2)   # like the browser aborting its fetch
                    except Exception:  # noqa: BLE001
                        r.close()
                timer = threading.Timer(cancel_after, close_now)
                timer.start()
            if r.status_code != 200:
                out["error"] = r.text[:400]
            else:
                for line in r.iter_lines():
                    if cancel_after is not None and time.time() - t0 > cancel_after:
                        out["cancelled"] = True
                        break                                  # closing the stream = the page's Stop
                    if not line.startswith(b"data: ") or line == b"data: [DONE]":
                        continue
                    ev = json.loads(line[6:])
                    if "error" in ev:
                        out["error"] = str(ev["error"])[:400]
                        break
                    for ch in ev.get("choices", []):
                        d = ch.get("delta", {})
                        piece = (d.get("content") or "") + (d.get("reasoning_content") or "")
                        if piece and out["ttft"] is None:
                            out["ttft"] = time.time() - t0
                        out["text"] += d.get("content") or ""
                        out["reasoning"] += d.get("reasoning_content") or ""
                        out["finish"] = ch.get("finish_reason") or out["finish"]
    except Exception as e:  # noqa: BLE001
        if not out["cancelled"]:
            out["error"] = repr(e)[:400]
    out["total"] = time.time() - t0
    return out


def status():
    try:
        return requests.get(f"{A.base}/status", timeout=5).json()
    except Exception as e:  # noqa: BLE001
        return {"error": repr(e)}


def wait_idle(timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        s = status()
        if not s.get("busy") and not s.get("queued"):
            return True
        time.sleep(0.5)
    return False


def engine_lines(since, pat="strata serve: "):
    try:
        with open(A.engine_log, "rb") as f:
            f.seek(since)
            return [ln for ln in f.read().decode("utf-8", "replace").splitlines() if pat in ln]
    except OSError:
        return []


def log_size():
    try:
        return os.path.getsize(A.engine_log)
    except OSError:
        return 0


def engine_pid():
    """the engine process itself (its name is 'strata'; the resource monitor's command line also contains the pattern)"""
    for p in subprocess.run(["pgrep", "-f", "strata --serve"], capture_output=True, text=True).stdout.split():
        try:
            if open(f"/proc/{p}/comm").read().strip() == "strata":
                return int(p)
        except OSError:
            pass
    return None


def doc(size):
    sp = json.load(open(WS / "prompts/speed.json"))
    return next(p for p in sp if p["size"] == size and p["rep"] == 0)["messages"]


def chat_a():
    mt = json.load(open(WS / "prompts/multiturn.json"))["turns"]
    u1 = "[Chat fail-A] " + mt[0]["user"].replace("[Chat mt-7f3a] ", "")
    return [{"role": "user", "content": u1}, {"role": "assistant", "content": mt[0]["assistant"]},
            {"role": "user", "content": "Which file headers did you find? One line."}]


# ------------------------------------------------------------------------------------------------ tests
def t_stop120k():
    T = "stop120k"
    pid0 = engine_pid()
    a = chat_a()
    r = stream(a[:1], max_tokens=16)
    check(T, "chat A turn 1", r["error"] is None and r["status"] == 200, f"{r['total']:.1f} s")
    off = log_size()
    r = stream(doc("120k"), cancel_after=20)
    check(T, "120K paste: the connection closed at 20 s (Stop)", r["cancelled"] and r.get("closed_at", 99) < 21,
          f"closed at {r.get('closed_at', 0):.1f} s, request returned at {r['total']:.1f} s")
    t0 = time.time()
    idle = wait_idle(60)
    check(T, "server idle again after the cancel", idle, f"{time.time() - t0:.1f} s after the close")
    lines = engine_lines(off)
    check(T, "engine: the prompt read stopped (cancelled), no ERR", any("cancel" in ln for ln in lines) and
          not any(" ERR " in ln or "error" in ln.lower() and "no error" not in ln for ln in lines), lines[-3:])
    r = stream([{"role": "user", "content": "What is 12 * 12? Answer with the number only."}], max_tokens=512)
    check(T, "next request answers normally", r["error"] is None and "144" in r["text"],
          f"ttft {r['ttft'] and round(r['ttft'], 2)} s, text {r['text'][:40]!r}")
    off = log_size()
    r = stream(a, max_tokens=64)
    lines = engine_lines(off, "strata serve: prompt ")
    m = re.search(r"prompt (\d+) tokens = (\d+) reused", lines[-1]) if lines else None
    check(T, "back to chat A: resumed from the chat cache", r["error"] is None and m and int(m.group(2)) > 5000,
          f"ttft {r['ttft'] and round(r['ttft'], 2)} s; {lines[-1] if lines else ''}")
    check(T, "same engine process throughout", engine_pid() == pid0, f"{pid0} -> {engine_pid()}")


def t_overflow():
    T = "overflow"
    pid0 = engine_pid()
    big = doc("120k")[0]["content"]
    extra = json.load(open(WS / "prompts/multiturn.json"))["turns"][0]["user"]      # ~5.6K tokens
    too_long = [{"role": "user", "content": big}, {"role": "assistant", "content": "Noted."},
                {"role": "user", "content": extra + "\n\n" + extra + "\n\nSummarize everything above."}]
    t0 = time.time()
    try:
        resp = requests.post(f"{A.base}/v1/chat/completions", json={"model": "x", "messages": too_long, **PAGE},
                             timeout=600)
        code, body = resp.status_code, resp.text[:300]
    except requests.exceptions.RequestException as e:
        code, body = None, repr(e)
    dt = time.time() - t0
    check(T, "(a) chat longer than the context: clean error, fast", code is not None and 400 <= code < 500 and dt < 30,
          f"HTTP {code} in {dt:.1f} s: {body}")
    r = stream(too_long)
    check(T, "(c) the same, streamed (the chat page): an error, no hang", r["error"] is not None and r["total"] < 60,
          f"{r['total']:.1f} s: status {r['status']} {r['error']}")
    r = stream([{"role": "user", "content": "Say OK."}], max_tokens=256)
    check(T, "a normal request after the overflow", r["error"] is None and r["text"].strip(), r["text"][:40])
    # (b) near the ceiling: ~126K prompt, no max_tokens, a reasoning-heavy task
    near = [{"role": "user", "content": big + "\n\nNow, thinking step by step and very thoroughly, list every "
             "license named in the collection, explain each one's key obligations in detail, and compare them pairwise."
             + "\n\nAlso restate the following notes before you begin:\n" + extra[:14000]}]
    off = log_size()
    r = stream(near, timeout=3600)
    lines = engine_lines(off, "strata serve: prompt ")
    check(T, "(b) uncapped answer at ~126K: ends at the context ceiling (finish length), no hang",
          r["error"] is None and r["finish"] == "length",
          f"{r['total']:.0f} s, finish {r['finish']}, {len(r['reasoning']) + len(r['text'])} chars; {lines[-1] if lines else ''}")
    r = stream([{"role": "user", "content": "Say OK."}], max_tokens=256)
    check(T, "a normal request after the ceiling", r["error"] is None and r["text"].strip(), r["text"][:40])
    check(T, "same engine process throughout", engine_pid() == pid0, f"{pid0} -> {engine_pid()}")


def t_concurrent():
    T = "concurrent"
    res = {}

    def run(k, msgs, mt, delay=0.0):
        time.sleep(delay)
        res[k] = stream(msgs, max_tokens=mt)
    q1 = [{"role": "user", "content": "Write a 600-word story about a lighthouse keeper."}]
    q2 = [{"role": "user", "content": "What is the capital of Australia? One word."}]
    th = [threading.Thread(target=run, args=("first", q1, 2048)), threading.Thread(target=run, args=("second", q2, 512, 3.0))]
    t0 = time.time()
    for x in th:
        x.start()
    time.sleep(4.0)
    st = status()
    for x in th:
        x.join()
    check(T, "(a) second request while the first streams: both complete", all(res[k]["error"] is None for k in res) and
          "Canberra" in res["second"]["text"],
          f"first {res['first']['total']:.1f} s ({res['first']['finish']}), second waited, total {res['second']['total']:.1f} s, "
          f"answer {res['second']['text'][:30]!r}; status during: busy={st.get('busy')} queued={st.get('queued')}")
    res.clear()
    th = [threading.Thread(target=run, args=("x", q2, 512)), threading.Thread(target=run, args=("y", q2, 512))]
    for x in th:
        x.start()
    for x in th:
        x.join()
    check(T, "(b) two requests at the same moment: both complete",
          all(res[k]["error"] is None and "Canberra" in res[k]["text"] for k in res),
          {k: (round(v["total"], 1), v["text"][:20]) for k, v in res.items()})
    check(T, "server idle afterwards", wait_idle(30))


def t_vramgrab():
    T = "vramgrab"
    pid0 = engine_pid()
    stream([{"role": "user", "content": "Say OK."}], max_tokens=64)
    free0 = subprocess.run(["nvidia-smi", "-i", UUID, "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True).stdout.strip()
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=UUID)
    hog = subprocess.Popen([str(WS / "work/r5/vramhog/vramhog"), str(A.mib)], env=env, stdout=subprocess.PIPE, text=True)
    line = hog.stdout.readline().strip()
    free1 = subprocess.run(["nvidia-smi", "-i", UUID, "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True).stdout.strip()
    check(T, f"another process holds {A.mib} MiB", "holding" in line, f"{line}; nvidia-smi free {free0} -> {free1} MiB")
    off = log_size()
    r = stream(doc("120k"), max_tokens=256, timeout=1800)
    lines = engine_lines(off)
    alive = engine_pid()
    ok = (r["error"] is None and r["finish"] in ("length", "stop")) or (r["error"] is not None and r["total"] < 600)
    check(T, "120K prompt with the VRAM taken: completes or fails cleanly (no hang)", ok,
          f"{r['total']:.0f} s, finish {r['finish']}, error {r['error']}; engine pid {pid0} -> {alive}; "
          f"log: {[ln[-160:] for ln in lines if 'ERR' in ln or 'rror' in ln or 'memory' in ln][:4]}")
    hog.terminate()
    hog.wait(10)
    time.sleep(2)
    r2 = stream([{"role": "user", "content": "What is 7 * 8? The number only."}], max_tokens=256, timeout=900)
    check(T, "after the hog is gone: a normal request answers", r2["error"] is None and "56" in r2["text"],
          f"{r2['total']:.1f} s, {r2['text'][:30]!r}; engine pid {engine_pid()}")


def cpu_ticks(pid):
    with open(f"/proc/{pid}/stat") as f:
        v = f.read().rsplit(")", 1)[1].split()
    return int(v[11]) + int(v[12])


def thread_ticks(pid):
    out = {}
    for t in os.listdir(f"/proc/{pid}/task"):
        try:
            with open(f"/proc/{pid}/task/{t}/stat") as f:
                v = f.read().rsplit(")", 1)[1].split()
            with open(f"/proc/{pid}/task/{t}/comm") as f:
                name = f.read().strip()
            out[t] = (name, int(v[11]) + int(v[12]))
        except OSError:
            pass
    return out


def t_idlecpu():
    T = "idlecpu"
    wait_idle(60)
    time.sleep(5)
    e = engine_pid()
    s = next(int(p) for p in subprocess.run(["pgrep", "-f", "serve/server.py --engine strata"], capture_output=True,
                                            text=True).stdout.split() if open(f"/proc/{p}/comm").read().startswith("python"))
    hz = os.sysconf("SC_CLK_TCK")
    e0, s0, th0 = cpu_ticks(e), cpu_ticks(s), thread_ticks(e)
    time.sleep(60)
    e1, s1, th1 = cpu_ticks(e), cpu_ticks(s), thread_ticks(e)
    busy = sorted(((th1[t][1] - th0[t][1], th1[t][0], t) for t in th1 if t in th0), reverse=True)[:5]
    ecpu, scpu = 100.0 * (e1 - e0) / hz / 60, 100.0 * (s1 - s0) / hz / 60
    check(T, "engine idle CPU < 2 % of one core (no spinning pool workers)", ecpu < 2.0,
          f"engine {ecpu:.2f} % of one core over 60 s ({len(th1)} threads; busiest: "
          f"{[(n, round(100.0 * d / hz / 60, 2)) for d, n, _ in busy]}); server {scpu:.2f} %")


def main():
    global A
    ap = argparse.ArgumentParser()
    ap.add_argument("tests", nargs="+")
    ap.add_argument("--base", default="http://127.0.0.1:8081")
    ap.add_argument("--engine-log", default=os.environ.get("ELOG", ""))
    ap.add_argument("--mib", type=int, default=400)
    A = ap.parse_args()
    for t in A.tests:
        print(f"== {time.strftime('%H:%M:%S')} {t}", flush=True)
        globals()[f"t_{t}"]()


if __name__ == "__main__":
    main()
