"""Offline test of the staged item 7 counters: a local mock server, temp counter/log/key files (no real key, no network)."""
import http.server, json, os, sys, tempfile, threading
from pathlib import Path

tmp = Path(tempfile.mkdtemp(prefix="paidtest-"))
os.environ["PAID_SEARCH_RUNS_FILE"] = str(tmp / "paid-runs.json")
os.environ["PAID_SEARCH_RUN_NOW"] = str(tmp / "paid-run.json")


class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        body = json.dumps({"results": [{"url": "https://example.org/a", "title": "t", "highlights": ["h"], "content": "c"}],
                           "costDollars": {"total": 0.004}}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)

    def log_message(self, *a):
        pass


srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["EXA_URL"] = os.environ["TAVILY_URL"] = f"http://127.0.0.1:{srv.server_port}/search"
sys.path.insert(0, "/home/USER/ai/deep-research/staging/item7/tools")
import exa_fallback as ex, tavily_fallback as tv, paid_budget as pb  # noqa: E402

for m, name in ((ex, "exa"), (tv, "tavily")):
    m.KEY_FILE = tmp / f"{name}.key"; m.KEY_FILE.write_text("fake-not-a-key\n")
    m.USAGE_FILE = tmp / f"{name}-usage.json"; m.LOG_FILE = tmp / f"{name}.jsonl"


def setenv(kind=None, run=None):
    for k, v in (("PAID_SEARCH_KIND", kind), ("PAID_SEARCH_RUN", run)):
        os.environ.pop(k, None)
        if v is not None:
            os.environ[k] = v


def set_usage(exa_usd=None, tav=None):
    if exa_usd is not None:
        ex.USAGE_FILE.write_text(json.dumps({"month": ex._month(), "usd": exa_usd, "searches": 0, "closed": False}))
    if tav is not None:
        tv.USAGE_FILE.write_text(json.dumps({"month": tv._month(), "count": tav}))


# 1. a test caller without a run id gets nothing
setenv("test"); set_usage(0.0, 0)
assert ex.search("q", client="ldr") is None and tv.search("q", client="ldr") is None
# 2. a test run: 30 across both providers, then nothing
setenv("test", "p4s7/o01")
got = sum(bool(ex.search("q", client="ldr")) for _ in range(20)) + sum(bool(tv.search("q", client="ldr")) for _ in range(15))
assert got == 30 and pb.run_count("p4s7/o01") == 30, (got, pb.run_count("p4s7/o01"))
assert ex.search("q", client="ldr") is None and tv.search("q", client="ldr") is None
# 3. "ldr" without PAID_SEARCH_KIND is research: 100 per run
setenv(None, "job-123")
assert pb.kind("ldr") == "research" and pb.kind("jan") == "chat" and pb.kind("chat") == "chat"
got = sum(bool(tv.search("q", client="ldr")) for _ in range(105))
assert got == 100, got
# 4. month thresholds, Exa: a test stops at $7.50 spent, chat goes on to $9.00; the refused search is given back to the run
setenv("test", "p4s7/o02"); set_usage(7.494, None)
assert ex.search("q", client="ldr")                       # 7.498
assert ex.search("q", client="ldr") is None               # 7.502 > 7.50
assert pb.run_count("p4s7/o02") == 1, pb.run_count("p4s7/o02")
setenv(None); set_usage(8.994, None)
assert ex.search("q", client="jan")                       # chat: 8.998
assert ex.search("q", client="jan") is None               # 9.002 > 9.00
# 5. month thresholds, Tavily: research stops at 750, chat at 900
setenv(None, "job-456"); set_usage(None, 749)
assert tv.search("q", client="ldr") and tv.search("q", client="ldr") is None
setenv(None); set_usage(None, 899)
assert tv.search("q", client="chat") and tv.search("q", client="chat") is None
# 6. the chain still falls through to Tavily when Exa is over its limit
import search_fallback as sf  # noqa: E402
setenv(None); set_usage(9.0, 0)
r = sf.search("q", client="jan")
assert r and r[0]["engine"] == "tavily", r
# 7. logs carry kind and run, never the key
logs = (ex.LOG_FILE.read_text() + tv.LOG_FILE.read_text())
assert "fake-not-a-key" not in logs and '"kind": "test"' in logs and '"run": "p4s7/o01"' in logs
# 8. the run file: LDR's searches follow it, chat never does
setenv(None); set_usage(0.0, 0)
Path(os.environ["PAID_SEARCH_RUN_NOW"]).write_text(json.dumps({"kind": "test", "run": "p4s7/h02"}))
assert ex.search("q", client="ldr") and pb.run_count("p4s7/h02") == 1
assert ex.search("q", client="jan") and pb.run_count("p4s7/h02") == 1 and pb.kind("jan") == "chat"
Path(os.environ["PAID_SEARCH_RUN_NOW"]).unlink()
assert pb.kind("ldr") == "research" and pb.run_id("ldr") == ""
assert ex.search("q", client="ldr") is None              # research without a run id: refused
print("ok: run file for LDR only;", end=" ")
print("ok: run caps 30/100, no-run test refused, Exa $7.50/$9.00 and Tavily 750/900 thresholds, release on refusal, chain fallthrough, no key in logs")
srv.shutdown()
