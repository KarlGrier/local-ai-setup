"""Shared set-up for item 7's offline tests (10-29): no network beyond 127.0.0.1, temp files only, a local mock server.

Import this before any staged module: it blocks every non-local connection and DNS lookup, points HOME and every
path the staged code writes (counters, run counts, run file, logs, cache) into a fresh temp folder, and starts a mock
Exa / Tavily / Semantic Scholar server on 127.0.0.1. No real key is read or written; the fake key below is a
placeholder that must never show up in a log or cache file.
"""
import http.server
import json
import os
import socket
import sys
import tempfile
import threading
import urllib.parse
from pathlib import Path

FAKE_KEY = "fake-not-a-key-0123"
LOCAL = {"127.0.0.1", "::1", "localhost"}
REAL_NEW_PATHS = [Path("/home/USER/.cache/deep-research/paid-search"),
                  Path("/home/USER/ai/deep-research/logs/paid-route.jsonl")]
REAL_BEFORE = {p: p.exists() for p in REAL_NEW_PATHS}

_connect = socket.socket.connect
_getaddrinfo = socket.getaddrinfo


def _host(addr):
    return addr[0] if isinstance(addr, tuple) else addr


def _guard_connect(self, addr):
    if self.family in (socket.AF_INET, socket.AF_INET6) and _host(addr) not in LOCAL:
        raise RuntimeError(f"network blocked in tests: {_host(addr)}")
    return _connect(self, addr)


def _guard_getaddrinfo(host, *a, **k):
    if host not in LOCAL and host is not None:
        raise RuntimeError(f"DNS blocked in tests: {host}")
    return _getaddrinfo(host, *a, **k)


socket.socket.connect = _guard_connect
socket.getaddrinfo = _guard_getaddrinfo

TMP = Path(tempfile.mkdtemp(prefix="item7test-"))
os.environ["HOME"] = str(TMP / "home")
(TMP / "home").mkdir()
os.environ["PAID_SEARCH_RUNS_FILE"] = str(TMP / "paid-runs.json")
os.environ["PAID_SEARCH_RUN_NOW"] = str(TMP / "paid-run.json")
os.environ["PAID_ROUTE_LOG"] = str(TMP / "paid-route.jsonl")
os.environ["PAID_SEARCH_CACHE_DIR"] = str(TMP / "cache")
os.environ["S2_MIN_INTERVAL_S"] = "0"
for k in ("PAID_SEARCH_KIND", "PAID_SEARCH_RUN", "PAID_SEARCH_RUN_CAP", "PAID_ROUTE_PROFILE", "PAID_SEARCH_CACHE",
          "PAID_ROUTE_CONFIG", "EXA_MONTHLY_CAP_USD", "TAVILY_MONTHLY_CAP", "EXA_SEARCH_TYPE"):
    os.environ.pop(k, None)


class Mock(http.server.BaseHTTPRequestHandler):
    counts = {"exa": 0, "tavily": 0, "s2": 0}
    seen_auth = []

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        who = self.path.strip("/")
        q = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}").get("query", "")
        Mock.counts[who] = Mock.counts.get(who, 0) + 1
        Mock.seen_auth.append(bool(self.headers.get("x-api-key") or self.headers.get("Authorization")))
        if "fail500" in q:
            return self._send(500, {"error": "mock"})
        n = 0 if "empty" in q else 3
        slug = urllib.parse.quote(q.replace(" ", "-"))[:40]
        res = [{"url": f"https://{who}.example/{slug}/{i}", "title": f"{who} {i}", "content": f"text {i}",
                "highlights": [f"passage {i}"], "score": 0.5} for i in range(n)]
        self._send(200, {"results": res, "costDollars": {"total": 0.004}} if who == "exa" else {"results": res})

    def do_GET(self):
        Mock.counts["s2"] += 1
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("query", [""])[0]
        slug = urllib.parse.quote(q.replace(" ", "-"))[:40]
        self._send(200, {"data": [{"title": f"paper {i}", "abstract": "abstract", "year": 2025,
                                   "externalIds": {"DOI": f"10.1234/{slug}.{i}"}} for i in range(2)]})

    def log_message(self, *a):
        pass


SRV = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Mock)
threading.Thread(target=SRV.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{SRV.server_port}"
os.environ["EXA_URL"] = BASE + "/exa"
os.environ["TAVILY_URL"] = BASE + "/tavily"
os.environ["S2_URL"] = BASE + "/s2"

TOOLS = "/home/USER/ai/deep-research/staging/item7/tools"
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)


def wire_providers():
    """Point the staged providers' key, counter and log files into the temp folder (the key file holds FAKE_KEY)."""
    import exa_fallback as ex
    import tavily_fallback as tv
    for m, name in ((ex, "exa"), (tv, "tavily")):
        m.KEY_FILE = TMP / f"{name}.key"
        m.KEY_FILE.write_text(FAKE_KEY + "\n")
        m.USAGE_FILE = TMP / f"{name}-usage.json"
        m.LOG_FILE = TMP / f"{name}-fallback.jsonl"
    return ex, tv


def check_real_paths():
    """Nothing the staged code would create in the live places exists now unless it did before."""
    for p, before in REAL_BEFORE.items():
        assert p.exists() == before, f"test touched a live path: {p}"


def finish(msg: str):
    check_real_paths()
    SRV.shutdown()
    if not os.environ.get("ITEM7_KEEP_TMP"):
        import shutil
        shutil.rmtree(TMP, ignore_errors=True)
    print(msg)
