"""Shared set-up for item 7d's offline tests (11-03; after staging/item7/tests/_offline.py): no network beyond 127.0.0.1,
temp files only (under staging/item7d/scratch/, never /tmp), a local mock Exa / Tavily / Semantic Scholar server.

Import this before any tool module: it blocks every non-local connection and DNS lookup, points HOME and every path
the code writes (counters, run counts, run file, route log, 7d state, S2 log, cache) into a fresh temp folder, and puts
the STAGED 7d files (staging/item7d/tools) in front of the INSTALLED tools folder, so the staged search_route /
paid_search / s2_search run with the live exa_fallback / tavily_fallback / paid_budget / paid_cache. Run with python -I -B
(no bytecode is written into the tools folders). No real key is read: the key files are fakes in the temp HOME.
"""
import contextvars
import http.server
import json
import os
import socket
import sys
import tempfile
import threading
import types
import urllib.parse
from pathlib import Path

STAGE = Path("/home/USER/ai/deep-research/staging/item7d")
TOOLS = str(STAGE / "tools")            # item7_regression.py points this at the live folder (today's paid-route.json)
SCRATCH = STAGE / "scratch"
LIVE_TOOLS = "/home/USER/ai/deep-research/tools"
FAKE_KEY = "fake-not-a-key-7d-0123"
LOCAL = {"127.0.0.1", "::1", "localhost"}
REAL_NEW_PATHS = [Path("/home/USER/.cache/deep-research/paid-search"),
                  Path("/home/USER/.config/deep-research/paid-route-state.json"),
                  Path("/home/USER/ai/deep-research/logs/s2-search.jsonl")]
REAL_BEFORE = {p: p.exists() for p in REAL_NEW_PATHS}
REAL_SIZES = {p: (p.stat().st_size if p.exists() else None) for p in
              [Path("/home/USER/ai/deep-research/logs/paid-route.jsonl"),
               Path("/home/USER/ai/deep-research/logs/exa-fallback.jsonl"),
               Path("/home/USER/ai/deep-research/logs/tavily-fallback.jsonl"),
               Path("/home/USER/.config/deep-research/paid-runs.json"),
               Path("/home/USER/.config/deep-research/exa-usage.json"),
               Path("/home/USER/.config/deep-research/tavily-usage.json")]}

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

SCRATCH.mkdir(parents=True, exist_ok=True)
TMP = Path(tempfile.mkdtemp(prefix="item7dtest-", dir=str(SCRATCH)))
os.environ["HOME"] = str(TMP / "home")
(TMP / "home" / ".config" / "deep-research").mkdir(parents=True)
os.environ["PAID_SEARCH_RUNS_FILE"] = str(TMP / "paid-runs.json")
os.environ["PAID_SEARCH_RUN_NOW"] = str(TMP / "paid-run.json")
os.environ["PAID_ROUTE_LOG"] = str(TMP / "paid-route.jsonl")
os.environ["PAID_ROUTE_STATE"] = str(TMP / "paid-route-state.json")
os.environ["PAID_SEARCH_CACHE_DIR"] = str(TMP / "cache")
os.environ["PAID_ROUTE_CONFIG"] = str(STAGE / "tools" / "paid-route.json")
os.environ["S2_LOG"] = str(TMP / "s2-search.jsonl")
os.environ["S2_MIN_INTERVAL_S"] = "0"
for k in ("PAID_SEARCH_KIND", "PAID_SEARCH_RUN", "PAID_SEARCH_RUN_CAP", "PAID_ROUTE_PROFILE", "PAID_SEARCH_CACHE",
          "EXA_MONTHLY_CAP_USD", "TAVILY_MONTHLY_CAP", "EXA_SEARCH_TYPE"):
    os.environ.pop(k, None)


class Mock(http.server.BaseHTTPRequestHandler):
    counts = {"exa": 0, "tavily": 0, "s2": 0}
    queries = {"exa": [], "tavily": [], "s2": []}
    s2_keyed = []
    seen_auth = []          # item 7's suites check that the providers still send their key header

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
        Mock.queries.setdefault(who, []).append(q)
        Mock.seen_auth.append(bool(self.headers.get("x-api-key") or self.headers.get("Authorization")))
        if "fail500" in q:
            return self._send(500, {"error": "mock"})
        n = 0 if "empty" in q else 3
        slug = urllib.parse.quote(q.replace(" ", "-"))[:60]
        res = [{"url": f"https://{who}.example/{slug}/{i}", "title": f"{who} {i}", "content": f"text {i}",
                "highlights": [f"passage {i}"], "score": 0.5} for i in range(n)]
        self._send(200, {"results": res, "costDollars": {"total": 0.004}} if who == "exa" else {"results": res})

    def do_GET(self):
        Mock.counts["s2"] += 1
        Mock.s2_keyed.append(self.headers.get("x-api-key") == FAKE_KEY)
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("query", [""])[0]
        Mock.queries["s2"].append(q)
        if "rate429" in q:
            return self._send(429, {"message": "Too Many Requests"})
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

for p in (LIVE_TOOLS, str(STAGE / "tools")):          # staged first (inserted last)
    if p in sys.path:
        sys.path.remove(p)
    sys.path.insert(0, p)

# a stand-in for LDR deep mode's module (local_deep_research.deep.current_agent), as sys.modules holds it in LDR
_ldr = types.ModuleType("local_deep_research")
_deep = types.ModuleType("local_deep_research.deep")
_deep.current_agent = contextvars.ContextVar("ldr_deep_agent", default="lead")
_ldr.deep = _deep


def ldr_deep_on():
    sys.modules["local_deep_research"] = _ldr
    sys.modules["local_deep_research.deep"] = _deep
    return _deep.current_agent


def ldr_deep_off():
    sys.modules.pop("local_deep_research.deep", None)
    sys.modules.pop("local_deep_research", None)


def wire_providers():
    """Point the live providers' key, counter and log files into the temp folder (the key files hold FAKE_KEY)."""
    import exa_fallback as ex
    import tavily_fallback as tv
    for m, name in ((ex, "exa"), (tv, "tavily")):
        assert str(Path(m.__file__).parent) == LIVE_TOOLS, m.__file__
        m.KEY_FILE = TMP / f"{name}.key"
        m.KEY_FILE.write_text(FAKE_KEY + "\n")
        m.USAGE_FILE = TMP / f"{name}-usage.json"
        m.LOG_FILE = TMP / f"{name}-fallback.jsonl"
    import paid_search
    import search_route
    import s2_search
    for m in (paid_search, search_route, s2_search):
        assert str(Path(m.__file__).parent) == str(STAGE / "tools"), m.__file__
    return ex, tv


def write_run_file(run: str, route: str | None, kind: str = "test", written: float = 1.0) -> dict:
    """run/paid-run.json as bench2.py writes it (pid = this test process, so paid_budget takes it as live)."""
    import paid_budget
    rec = {"kind": kind, "run": run, "writer": "test", "pid": os.getpid(),
           "pid_start": paid_budget._pid_start(os.getpid()), "written": written}
    if route:
        rec["route"] = route
    Path(os.environ["PAID_SEARCH_RUN_NOW"]).write_text(json.dumps(rec) + "\n")
    return rec


def route_rows() -> list[dict]:
    p = Path(os.environ["PAID_ROUTE_LOG"])
    return [json.loads(x) for x in p.read_text().split("\n") if x] if p.exists() else []


def no_key_anywhere():
    for p in TMP.rglob("*"):
        if p.is_file() and not p.name.endswith(".key"):
            assert FAKE_KEY not in p.read_text(errors="replace"), f"the fake key leaked into {p}"


def check_real_paths():
    """Nothing the code would create or append to in the live places has changed."""
    for p, before in REAL_BEFORE.items():
        assert p.exists() == before, f"test touched a live path: {p}"
    for p, size in REAL_SIZES.items():          # (a live Jan job or chat writing at the same time also trips this)
        now = p.stat().st_size if p.exists() else None
        assert now == size, f"a live file changed during the test: {p} ({size} -> {now})"


def finish(msg: str):
    no_key_anywhere()
    check_real_paths()
    SRV.shutdown()
    if not os.environ.get("ITEM7D_KEEP_TMP"):
        import shutil
        shutil.rmtree(TMP, ignore_errors=True)
    print(msg)
