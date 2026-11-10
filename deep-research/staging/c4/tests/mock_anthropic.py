"""A stand-in for Anthropic's Messages API on 127.0.0.1 (C4 offline tests). Nothing here talks to the network.

POST /v1/messages[?beta=true]: records the body and the auth / beta headers, then answers from a script (push()) or,
when the script is empty, with a thinking block + "ok". Streamed requests get the API's SSE events (message_start,
content_block_start / _delta / _stop with thinking signature, text and tool-input deltas, message_delta, message_stop);
others get a JSON message.

Usage is simulated unless the script gives it: tokens = bytes // 4 per content position (tools, system blocks,
message blocks); each cache_control marker (and the last position when the body has a top-level cache_control) is a
breakpoint; the longest breakpoint prefix seen before is a cache read, the rest up to the last breakpoint a cache
write, the remainder plain input - enough to show whether consecutive requests share a byte-identical prefix.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _strip_cc(b):
    return {k: v for k, v in b.items() if k != "cache_control"} if isinstance(b, dict) else b


def simulate_usage(body: dict, cache: dict) -> dict:
    pos = []
    for t in body.get("tools") or []:
        pos.append((t, "cache_control" in t))
    sysb = body.get("system")
    if isinstance(sysb, str):
        sysb = [{"type": "text", "text": sysb}]
    for b in sysb or []:
        pos.append((b, "cache_control" in b))
    for m in body.get("messages") or []:
        c = m["content"] if isinstance(m["content"], list) else [{"type": "text", "text": m["content"]}]
        for b in c:
            pos.append(({"role": m["role"], **b}, "cache_control" in b))
    if body.get("cache_control") and pos:
        pos[-1] = (pos[-1][0], True)
    h = hashlib.sha256()
    cum, hashes, tokens = [], [], 0
    for b, _ in pos:
        s = json.dumps(_strip_cc(b), sort_keys=True).encode()
        tokens += max(1, len(s) // 4)
        h.update(s)
        cum.append(tokens)
        hashes.append(h.hexdigest())
    bps = [i for i, (_, m) in enumerate(pos) if m]
    read = 0
    for i in reversed(bps):                 # each breakpoint looks back at most 20 positions for an earlier entry
        hit = next((j for j in range(i, max(-1, i - 20), -1) if hashes[j] in cache), None)
        if hit is not None:
            read = cum[hit]
            break
    write = (cum[bps[-1]] - read) if bps and cum[bps[-1]] > read else 0
    for i in bps:
        cache[hashes[i]] = True
    ttl = "1h" if (body.get("cache_control") or {}).get("ttl") == "1h" else "5m"
    return {"input_tokens": tokens - read - write, "cache_creation_input_tokens": write,
            "cache_read_input_tokens": read,
            "cache_creation": {"ephemeral_5m_input_tokens": write if ttl == "5m" else 0,
                               "ephemeral_1h_input_tokens": write if ttl == "1h" else 0},
            "output_tokens": 7}


class MockAnthropic:
    def __init__(self):
        self.requests: list[dict] = []
        self.script: list[dict] = []
        self.cache: dict = {}
        self.lock = threading.Lock()
        self._n = itertools.count(1)
        mock = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *a):
                pass

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                hdr = {k.lower(): v for k, v in self.headers.items()
                       if k.lower() in ("x-api-key", "authorization", "anthropic-beta", "anthropic-version", "x-test")}
                with mock.lock:
                    mock.requests.append({"path": self.path, "body": body, "headers": hdr, "t": time.time()})
                    spec = mock.script.pop(0) if mock.script else {}
                    num = next(mock._n)
                if spec.get("delay_s"):
                    time.sleep(spec["delay_s"])
                if not self.path.startswith("/v1/messages"):
                    return self._json(404, {"type": "error", "error": {"type": "not_found_error", "message": "?"}})
                st = spec.get("status", 200)
                if st != 200:
                    return self._json(st, {"type": "error", "error": {"type": spec.get("err_type", "api_error"),
                                                                       "message": spec.get("err_msg", "mock error")}},
                                      spec.get("headers"))
                with mock.lock:
                    usage = spec.get("usage") or simulate_usage(body, mock.cache)
                content = spec.get("content") or [
                    {"type": "thinking", "thinking": "", "signature": f"sig-{num}"},
                    {"type": "text", "text": spec.get("text", "ok")}]
                stop = spec.get("stop_reason") or ("tool_use" if any(b["type"] == "tool_use" for b in content)
                                                   else "end_turn")
                msg = {"id": f"msg_mock_{num}", "type": "message", "role": "assistant", "model": body.get("model"),
                       "content": [], "stop_reason": None, "stop_sequence": None, "usage": dict(usage)}
                if spec.get("input_transformations") is not None:
                    msg["input_transformations"] = spec["input_transformations"]
                if not body.get("stream"):
                    msg.update(content=content, stop_reason=stop, stop_details=spec.get("stop_details"))
                    return self._json(200, msg)
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Connection", "close")
                self.end_headers()
                try:
                    self._ev("message_start", {"type": "message_start", "message": {**msg, "usage": {
                        **usage, "output_tokens": 1}}})
                    self._ev("ping", {"type": "ping"})
                    for i, b in enumerate(content):
                        if spec.get("fail_after_start") and i == 1:
                            self._ev("error", {"type": "error", "error": {"type": "overloaded_error",
                                                                          "message": "Overloaded"}})
                            return
                        if b["type"] == "thinking":
                            self._ev("content_block_start", {"type": "content_block_start", "index": i,
                                     "content_block": {"type": "thinking", "thinking": "", "signature": ""}})
                            self._ev("content_block_delta", {"type": "content_block_delta", "index": i,
                                     "delta": {"type": "signature_delta", "signature": b["signature"]}})
                        elif b["type"] == "text":
                            self._ev("content_block_start", {"type": "content_block_start", "index": i,
                                     "content_block": {"type": "text", "text": ""}})
                            t = b["text"]
                            for part in (t[:len(t) // 2], t[len(t) // 2:]):
                                if part:
                                    self._ev("content_block_delta", {"type": "content_block_delta", "index": i,
                                             "delta": {"type": "text_delta", "text": part}})
                        elif b["type"] == "tool_use":
                            self._ev("content_block_start", {"type": "content_block_start", "index": i,
                                     "content_block": {"type": "tool_use", "id": b["id"], "name": b["name"],
                                                       "input": {}}})
                            js = json.dumps(b["input"])
                            for part in (js[:len(js) // 2], js[len(js) // 2:]):
                                if part:
                                    self._ev("content_block_delta", {"type": "content_block_delta", "index": i,
                                             "delta": {"type": "input_json_delta", "partial_json": part}})
                        self._ev("content_block_stop", {"type": "content_block_stop", "index": i})
                    self._ev("message_delta", {"type": "message_delta",
                                               "delta": {"stop_reason": stop, "stop_sequence": None,
                                                         "stop_details": spec.get("stop_details")},
                                               "usage": {"output_tokens": usage.get("output_tokens", 7)}})
                    self._ev("message_stop", {"type": "message_stop"})
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def _ev(self, name, data):
                self.wfile.write(f"event: {name}\ndata: {json.dumps(data)}\n\n".encode())
                self.wfile.flush()

            def _json(self, code, obj, headers=None):
                data = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def push(self, **spec) -> None:
        with self.lock:
            self.script.append(spec)

    def clear(self) -> None:
        with self.lock:
            self.requests.clear()
            self.script.clear()
            self.cache.clear()

    def close(self) -> None:
        self.server.shutdown()
