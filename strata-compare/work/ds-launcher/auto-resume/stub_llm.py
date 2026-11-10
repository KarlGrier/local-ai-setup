#!/usr/bin/python3 -I
"""A slow OpenAI-style stream on 127.0.0.1:18099 for the cancel test: real DS Harness code, no real model, nothing on 8080."""
import http.server, json, socketserver, sys, time
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        b = json.dumps({"object": "list", "data": []}).encode(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); self.rfile.read(n)
        print("request", time.strftime("%T"), flush=True)
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        try:
            for i in range(600):
                d = {"id": "x", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"content": "word "}, "finish_reason": None}]}
                self.wfile.write(f"data: {json.dumps(d)}\n\n".encode()); self.wfile.flush(); time.sleep(1)
        except OSError:
            print("client went away", time.strftime("%T"), flush=True)
class S(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True
S(("127.0.0.1", 18099), H).serve_forever()
