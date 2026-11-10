#!/usr/bin/env python3
"""turnlog.py - a recording pass-through in front of Strata for the harness comparison (usability round).

    python3 turnlog.py --listen 8090 --upstream 8080 --out logs/usability/turns

Every request is forwarded unchanged to 127.0.0.1:<upstream> and its response streamed back unchanged; on the side the
request body and the raw response body are written gzip'd to <out>/<label>/NNNN.req.json.gz / NNNN.resp.gz, plus one
index line (<out>/<label>/index.jsonl: time, method, path, status, wall seconds, bytes). The label is read from the
file <out>/LABEL at each request (the test driver writes it before each run), so one proxy serves every run.
Listens on 127.0.0.1 only; nothing leaves the PC.
"""
import argparse
import gzip
import http.client
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOCK = threading.Lock()
COUNTERS = {}


def next_slot(out, label):
    with LOCK:
        d = os.path.join(out, label)
        os.makedirs(d, exist_ok=True)
        n = COUNTERS.get(label)
        if n is None:
            n = len([f for f in os.listdir(d) if f.endswith(".req.json.gz")])
        COUNTERS[label] = n + 1
        return d, n + 1


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _proxy(self):
        out = self.server.out
        try:
            label = open(os.path.join(out, "LABEL")).read().strip() or "unlabelled"
        except OSError:
            label = "unlabelled"
        if "chunked" in (self.headers.get("Transfer-Encoding") or "").lower():
            parts = []
            while True:
                size_line = self.rfile.readline().split(b";")[0].strip()
                k = int(size_line or b"0", 16)
                if k == 0:
                    self.rfile.readline()                    # the empty line after the last chunk (no trailers)
                    break
                parts.append(self.rfile.read(k))
                self.rfile.readline()
            body = b"".join(parts)
        else:
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        n = len(body)
        d, k = next_slot(out, label)
        with gzip.open(os.path.join(d, f"{k:04d}.req.json.gz"), "wb") as f:
            f.write(body)
        t0 = time.time()
        conn = http.client.HTTPConnection("127.0.0.1", self.server.upstream, timeout=3600)
        hdrs = {h: v for h, v in self.headers.items() if h.lower() not in ("host", "connection", "content-length",
                                                                           "accept-encoding", "transfer-encoding")}
        hdrs["Content-Length"] = str(len(body))
        conn.request(self.command, self.path, body=body if n else None, headers=hdrs)
        resp = conn.getresponse()
        self.send_response(resp.status, resp.reason)
        for h, v in resp.getheaders():
            if h.lower() not in ("transfer-encoding", "connection", "content-length", "keep-alive"):
                self.send_header(h, v)
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        size = 0
        with gzip.open(os.path.join(d, f"{k:04d}.resp.gz"), "wb") as f:
            while True:
                chunk = resp.read1(65536)
                if not chunk:
                    break
                size += len(chunk)
                f.write(chunk)
                try:
                    self.wfile.write(chunk)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break                                   # the client left (Stop): the upstream sees the close
        conn.close()
        with LOCK, open(os.path.join(d, "index.jsonl"), "a") as f:
            f.write(json.dumps({"n": k, "t": round(t0, 3), "method": self.command, "path": self.path,
                                "status": resp.status, "wall_s": round(time.time() - t0, 3),
                                "req_bytes": len(body), "resp_bytes": size}) + "\n")

    do_GET = do_POST = do_DELETE = do_PUT = _proxy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen", type=int, default=8090)
    ap.add_argument("--upstream", type=int, default=8080)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", a.listen), Handler)
    srv.out, srv.upstream = a.out, a.upstream
    print(f"turnlog 127.0.0.1:{a.listen} -> 127.0.0.1:{a.upstream}, out {a.out}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
