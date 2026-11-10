#!/usr/bin/env python3
"""A fake Strata for the proxy gate tests: streamed chat completions, /metrics with a request counter and a live
state; POST /_fake/foreign simulates another client's request (counted, runs 2 s)."""
import json, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
PORT = int(sys.argv[1])
state = {"total": 0, "busy": 0}
lock = threading.Lock()

class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path.startswith("/metrics"):
            with lock:
                return self._send(200, {"live": {"state": "generating" if state["busy"] else "idle", "queued": max(0, state["busy"] - 1)},
                                        "totals": {"requests": state["total"]}})
        if self.path.startswith("/health"):
            return self._send(200, {"loaded": True})
        self._send(404, {})
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); body = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/_fake/foreign":
            def run():
                with lock: state["busy"] += 1
                time.sleep(2)
                with lock: state["busy"] -= 1; state["total"] += 1
            threading.Thread(target=run).start()
            return self._send(200, {"ok": True})
        text = body.get("_say", "Hello there.")
        with lock: state["busy"] += 1
        try:
            self.send_response(200); self.send_header("Content-Type", "text/event-stream")
            self.send_header("Transfer-Encoding", "chunked"); self.end_headers()
            for part in [text[:5], text[5:]]:
                d = {"choices": [{"delta": {"content": part}}]}
                c = b"data: " + json.dumps(d).encode() + b"\n\n"
                self.wfile.write(b"%x\r\n%s\r\n" % (len(c), c)); self.wfile.flush(); time.sleep(0.2)
            d = {"choices": [{"delta": {}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 5, "completion_tokens": 3}}
            for c in (b"data: " + json.dumps(d).encode() + b"\n\n", b"data: [DONE]\n\n"):
                self.wfile.write(b"%x\r\n%s\r\n" % (len(c), c))
            self.wfile.write(b"0\r\n\r\n"); self.wfile.flush()
        finally:
            with lock: state["busy"] -= 1; state["total"] += 1

ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
