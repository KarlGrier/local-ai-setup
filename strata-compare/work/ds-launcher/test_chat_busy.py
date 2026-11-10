#!/usr/bin/python3 -I
"""test_chat_busy.py - configs/usability/bin/chat-busy.py against a stub, then against the REAL server.py of both trees
(mock engine, the sandbox copies in work/ds-launcher/model-guard/, spare ports; nothing touches 8080)."""
import http.server
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request

SC = "/home/USER/ai-speed-testing/strata-compare"
CB = f"{SC}/configs/usability/bin/chat-busy.py"
G = f"{SC}/work/ds-launcher/model-guard"
PY = f"{SC}/.venv/bin/python"
fails = 0


def ok(name, cond):
    global fails
    print(("ok   " if cond else "FAIL ") + name)
    fails += 0 if cond else 1


def rc(port, *extra):
    return subprocess.run(["/usr/bin/python3", "-I", CB, "--port", str(port), *extra], capture_output=True, text=True).returncode


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class H(http.server.BaseHTTPRequestHandler):
    body = b"{}"
    delay = 0.0

    def do_GET(self):
        time.sleep(H.delay)
        self.send_response(200); self.end_headers(); self.wfile.write(H.body)

    def log_message(self, *a):
        pass


httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
P = httpd.server_address[1]
now = time.time()


def put(live, reqs=()):
    H.body = json.dumps({"live": live, "requests": list(reqs), "time": now}).encode()


put({"state": "idle", "queued": 0}); ok("idle, no requests: quiet (1)", rc(P) == 1)
put({"state": "generating", "queued": 0}); ok("generating: busy (0)", rc(P) == 0)
put({"state": "reading", "queued": 0}); ok("reading the prompt: busy (0)", rc(P) == 0)
put({"state": "idle", "queued": 2}); ok("queued: busy (0)", rc(P) == 0)
put({"state": None, "queued": None}); ok("state null: quiet (1)", rc(P) == 1)
put({"state": "idle", "queued": 0}, [{"time": now - 70, "duration_s": 30}]); ok("finished 40 s ago, default 120 s: busy (0)", rc(P) == 0)
ok("finished 40 s ago, --quiet-s 30: quiet (1)", rc(P, "--quiet-s", "30") == 1)
put({"state": "idle", "queued": 0}, [{"time": now - 900, "duration_s": 30}]); ok("finished 870 s ago: quiet (1)", rc(P) == 1)
put({"state": "idle", "queued": 0}, [{"time": now - 900, "duration_s": 1}, {"time": now - 20, "duration_s": 5}, {"time": None, "duration_s": None}]); ok("the newest of several, a blank one ignored: busy (0)", rc(P) == 0)
H.body = b"not json"; ok("not JSON: nothing to wait for (2)", rc(P) == 2)
H.body = b'{"other": 1}'; ok("no live state: nothing to wait for (2)", rc(P) == 2)
H.delay = 2.0; put({"state": "idle", "queued": 0}); ok("up but too slow: busy (0)", rc(P, "--timeout", "0.5") == 0); H.delay = 0.0
ok("nothing listening: nothing to wait for (2)", rc(free_port()) == 2)
httpd.shutdown()
env_proxy = dict(os.environ, HTTP_PROXY="http://127.0.0.1:9", http_proxy="http://127.0.0.1:9")
print("-- the real server.py, both trees, mock engine")
cfg = f"{G}/mock-qwen.json"
for tree in ("p028x", "v026"):
    port = free_port()
    p = subprocess.Popen([PY, "-B", "serve/server.py", "--engine", "mock", "--port", str(port), "--config", cfg], cwd=f"{G}/{tree}",
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1).read(); break
            except OSError:
                time.sleep(0.25)
        ok(f"{tree}: just started, no requests: quiet (1)", rc(port) == 1)
        req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", json.dumps(
            {"model": "x", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 4}).encode(), {"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=20).read()
        ok(f"{tree}: a request just finished: busy (0)", rc(port) == 0)
        ok(f"{tree}: the same with --quiet-s 0: quiet (1)", rc(port, "--quiet-s", "0") == 1)
        r = subprocess.run(["/usr/bin/python3", "-I", CB, "--port", str(port)], capture_output=True, text=True, env=env_proxy)
        ok(f"{tree}: proxy variables set: still asks the server directly", r.returncode == 0)
    finally:
        p.terminate(); p.wait(10)
print(f"failed {fails}")
sys.exit(1 if fails else 0)
