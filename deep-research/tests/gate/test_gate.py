#!/usr/bin/env python3
"""Offline tests of strata-proxy's research gate against fake_strata.py (no real Strata, no GPU)."""
import json, os, subprocess, sys, tempfile, threading, time, http.client
WS = "/home/USER/ai/deep-research"
FAKE, PROXY = 8098, 8097
tmp = tempfile.mkdtemp(prefix="gate-", dir=WS + "/tmp")
ctl, clk, log = f"{tmp}/control.json", f"{tmp}/clock.json", f"{tmp}/calls.jsonl"
fake = subprocess.Popen([sys.executable, f"{WS}/tests/gate/fake_strata.py", str(FAKE)])
env = dict(os.environ, PROXY_PORT=str(PROXY), UPSTREAM=f"http://127.0.0.1:{FAKE}", PROXY_LOG=log,
           PROXY_CONTROL_FILE=ctl, PROXY_CLOCK_FILE=clk, PROXY_MODE_FILE=f"{tmp}/mode.json", PROXY_ENSURE="/bin/false",
           PROXY_TEST_LOCKS=f"{tmp}/gpu-test.lock:ex", PROXY_GRACE_S="0")
proxy = subprocess.Popen([sys.executable, f"{WS}/tools/strata-proxy.py"], env=env)
time.sleep(1.5)
ok = True
def check(name, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + name + (f"  ({extra})" if extra else ""), flush=True)
    ok &= bool(cond)
def setctl(**kw): json.dump(kw, open(ctl, "w"))
def call(say="Hello there.", tools=None):
    c = http.client.HTTPConnection("127.0.0.1", PROXY, timeout=120)
    body = {"model": "m", "stream": True, "messages": [{"role": "user", "content": "hi"}], "_say": say}
    if tools: body["tools"] = tools
    t0 = time.time(); c.request("POST", "/v1/chat/completions", body=json.dumps(body), headers={"Content-Type": "application/json"})
    r = c.getresponse(); t_head = time.time() - t0; data = r.read().decode(); c.close()
    return r.status, t_head, time.time() - t0, data
def status():
    c = http.client.HTTPConnection("127.0.0.1", PROXY, timeout=10); c.request("GET", "/_research/status")
    d = json.loads(c.getresponse().read()); c.close(); return d
try:
    setctl(yield_minutes=0)
    time.sleep(1.5)
    st, th, tt, data = call()
    check("open gate passes through", st == 200 and "Hello" in data and tt < 3, f"{tt:.1f} s")
    # pause: held with keep-alives, then released; clock grows by the paused time
    p0 = status()["paused_total_s"]
    setctl(pause=True, reason="test pause"); time.sleep(1.5)
    res = {}
    th_ = threading.Thread(target=lambda: res.update(r=call())); th_.start()
    time.sleep(12)
    s = status()
    check("held while paused", s["held"] == 1 and s["gate"] == "closed", s["reason"])
    setctl(pause=False); th_.join(30)
    st, t_head, tt, data = res["r"]
    check("released after resume, answer complete", st == 200 and "Hello there." in data.replace('"', '') or "there." in data, f"{tt:.1f} s")
    check("keep-alive comments sent while held", ": held - paused: test pause" in data)
    check("headers sent at once while held", t_head < 2, f"{t_head:.1f} s")
    p1 = status()["paused_total_s"]
    check("research clock paused ~13 s", 11 <= p1 - p0 <= 16, f"{p1 - p0:.1f} s")
    # abort: held call fails at once with an SSE error
    setctl(pause=True, reason="x"); time.sleep(1.5)
    th_ = threading.Thread(target=lambda: res.update(r=call())); th_.start(); time.sleep(3)
    setctl(abort=True); th_.join(15)
    st, _, tt, data = res["r"]
    check("abort releases held call with an error", "research_cancelled" in data, f"{tt:.1f} s")
    # yield: a foreign request seen in /metrics closes the gate for yield_minutes
    setctl(yield_minutes=0.25); time.sleep(1.5)
    c = http.client.HTTPConnection("127.0.0.1", FAKE); c.request("POST", "/_fake/foreign", body="{}"); c.getresponse().read(); c.close()
    time.sleep(12)
    s = status()
    check("foreign use detected -> yielding", s["gate"] == "closed" and "yielding" in (s["reason"] or ""), s["reason"])
    t0 = time.time(); st, _, tt, _ = call()
    check("call waits out the yield (<= 15 s left)", st == 200 and 1 <= tt <= 20, f"{tt:.1f} s")
    # own calls are not foreign
    setctl(yield_minutes=0.25); time.sleep(1.5)       # the foreign request above is > 15 s old by now
    for _ in range(3): call()
    time.sleep(8)
    s = status()
    check("own calls do not trigger the yield", s["gate"] == "open", s["reason"])
    # a test holding the lock closes the gate; released when the lock goes
    import fcntl
    setctl(yield_minutes=0)
    lf = open(f"{tmp}/gpu-test.lock", "w"); fcntl.flock(lf, fcntl.LOCK_SH); time.sleep(2)
    s = status()
    check("test lock closes the gate", s["gate"] == "closed" and "test holds" in (s["reason"] or ""), s["reason"])
    th_ = threading.Thread(target=lambda: res.update(r=call())); th_.start(); time.sleep(3)
    c = http.client.HTTPConnection("127.0.0.1", PROXY, timeout=30); c.request("GET", "/_research/wait-idle?timeout=10")
    w = json.loads(c.getresponse().read()); c.close()
    check("wait-idle returns while held", w.get("idle") is True, f"waited {w.get('waited_s')} s")
    fcntl.flock(lf, fcntl.LOCK_UN); lf.close(); th_.join(20)
    check("released when the lock is dropped", res["r"][0] == 200 and "there." in res["r"][3])
    # tool tag in prose
    call(say="I will now call <tool_call>web_search</tool_call> to look.")
    time.sleep(0.5)
    recs = [json.loads(l) for l in open(log)]
    check("tool tag in prose is logged", any((r.get("tooltag") or {}).get("kind") == "tag_in_content" for r in recs))
    json.dump({"capture_dir": f"{tmp}/cap"}, open(f"{tmp}/mode.json", "w"))
    call(say="Captured answer.")
    time.sleep(0.5)
    caps = [json.loads(l) for l in open(f"{tmp}/cap/calls.jsonl")]
    check("capture mode writes messages and answer", caps and caps[-1]["content"] == "Captured answer." and caps[-1]["messages"])
    check("clock file written", json.load(open(clk)).get("gate") in ("open", "closed"))
finally:
    proxy.terminate(); fake.terminate()
print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
