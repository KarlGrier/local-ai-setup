"""Item 7 entry point (10-29): route -> cache -> budget -> provider, against a local mock server and temp files.

Budget interplay: cache hits spend nothing and do not count against the run cap, misses do, caps refuse, refusals and
failures are never cached; routing off = today's fallback; every decision logged without keys."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/home/USER/ai/deep-research/staging/item7/tests")
from _offline import FAKE_KEY, TMP, TOOLS, Mock, finish, wire_providers  # noqa: E402

ex, tv = wire_providers()
import paid_budget as pb  # noqa: E402
import paid_search as ps  # noqa: E402
import paid_tracker  # noqa: E402

ROUTE_LOG = Path(os.environ["PAID_ROUTE_LOG"])
RUN_NOW = Path(os.environ["PAID_SEARCH_RUN_NOW"])
CACHE = Path(os.environ["PAID_SEARCH_CACHE_DIR"])
base_cfg = json.loads((Path(TOOLS) / "paid-route.json").read_text())


def config(enabled=False, cache=False):
    p = TMP / "route.json"
    p.write_text(json.dumps({**base_cfg, "enabled": enabled, "cache": {**base_cfg["cache"], "enabled": cache}}))
    os.environ["PAID_ROUTE_CONFIG"] = str(p)
    import search_route
    search_route.CONFIG_FILE = p


def caller(kind="test", run="t1", cap=None):
    for k, v in (("PAID_SEARCH_KIND", kind), ("PAID_SEARCH_RUN", run), ("PAID_SEARCH_RUN_CAP", cap)):
        os.environ.pop(k, None)
        if v is not None:
            os.environ[k] = str(v)


def sx(n, q="x"):
    return [{"title": f"s{i}", "url": f"https://searx.example/{q}/{i}", "content": "c"} for i in range(n)]


def last_log():
    return json.loads(ROUTE_LOG.read_text().splitlines()[-1])


def counts():
    return dict(Mock.counts)


def usage():
    return ex.usage()["usd"], tv.usage()["count"]


config()
caller()
# 1. routing off (the staged default): SearXNG has 5+ -> nothing asked, nothing logged
c0 = counts()
assert ps.search("history of rome", sx(6)) == [] and counts() == c0 and not ROUTE_LOG.exists()
# ... < 5 -> today's fallback, Exa first; results new to SearXNG's list only; the decision logged
exa_urls = [f"https://exa.example/history-of-rome-2/{i}" for i in range(3)]
got = ps.search("history of rome 2", sx(2) + [{"url": exa_urls[0] + "/"}])        # one Exa URL already there
assert [x["url"] for x in got] == exa_urls[1:] and all(x["engine"] == "exa" for x in got), got
r = last_log()
assert (r["profile"], r["profile_from"], r["tag"], r["searxng"], r["added"]) == ("fallback", "routing off", "general", 3, 2), r
assert r["actions"][0]["outcome"] == "sent" and r["actions"][0]["step"] == "fallback" and r["cache"] is False
assert '"reason": "searxng returned 3"' in ex.LOG_FILE.read_text()
# ... Exa finds nothing -> Tavily (as today's chain)
got = ps.search("empty one", sx(1))
assert got == [] and [a["source"] for a in last_log()["actions"]] == ["exa", "tavily"]   # mock: "empty" -> no results
got = ps.search("nothing on exa", sx(1))
assert got and got[0]["engine"] == "exa"

# 2. routing on (a test run's run file names the profile): academic -> Semantic Scholar, product -> Exa,
#    news -> Tavily, even with 10 SearXNG results; general -> nothing
caller(None, None)
RUN_NOW.write_text(json.dumps({"kind": "test", "run": "t2", "route": "types"}))
c0 = counts()
got = ps.search("meta-analysis of creatine and memory", sx(10), client="ldr")
assert got and {x["engine"] for x in got} == {"s2"} and got[0]["url"].startswith("https://doi.org/10.1234/"), got
assert counts()["s2"] == c0["s2"] + 1 and counts()["exa"] == c0["exa"] and counts()["tavily"] == c0["tavily"]
assert last_log()["profile_from"] == "run file" and last_log()["kind"] == "test" and last_log()["run"] == "t2"
got = ps.search("cheapest 4TB NVMe SSD", sx(10), client="ldr")
assert got and got[0]["engine"] == "exa" and last_log()["tag"] == "product", last_log()
got = ps.search("breaking news chip tariffs", sx(10), client="ldr")
assert got and got[0]["engine"] == "tavily" and last_log()["tag"] == "news"
c1 = counts()
assert ps.search("history of carthage", sx(10), client="ldr") == [] and counts() == c1
r = last_log()
assert (r["tag"], r["actions"], r["profile"]) == ("general", [], "types"), r          # logged: routing is on
assert pb.run_count("t2") == 2                                                            # Exa + Tavily, S2 is free
# chat is never routed by the run file (that is LDR's)
n_lines, c1 = len(ROUTE_LOG.read_text().splitlines()), counts()
assert ps.search("cheapest 4TB NVMe SSD", sx(10), client="jan") == [] and counts() == c1
assert len(ROUTE_LOG.read_text().splitlines()) == n_lines          # chat: routing off -> fallback, nothing to do
RUN_NOW.unlink()

# 3. cache on: a repeat is a hit - no request, no credit, no run count; logged with what it saved
config(enabled=True, cache=True)
caller("test", "t3")
c0, u0 = counts(), usage()
first = ps.search("RTX 5090 price in Germany", sx(10))
assert first and counts()["exa"] == c0["exa"] + 1 and pb.run_count("t3") == 1
u1 = usage()
again = ps.search("  rtx 5090 PRICE in germany? ", sx(10))
assert again == first and counts()["exa"] == c0["exa"] + 1, "a cache hit must not send"
assert usage() == u1 and pb.run_count("t3") == 1, "a cache hit must not spend credit or count against the run"
a = last_log()["actions"][0]
assert (a["outcome"], a["saved"], a["n"]) == ("cache hit", ex.PRICE_USD["lite"], 3), a
assert u1[0] > u0[0]

# 4. run cap: misses count, the cap refuses, a hit is still served at the cap, a refusal is not cached
caller("test", "t4", cap=2)
assert ps.search("best laptop under $900", sx(10)) and ps.search("used RTX 3090 for sale", sx(10))
assert pb.run_count("t4") == 2
c0 = counts()
assert ps.search("where to buy a 4090", sx(10)) == [] and counts()["exa"] == c0["exa"]
a = last_log()["actions"][0]
assert a["outcome"].startswith("refused: run cap 2 reached"), a
assert ps.search("best laptop under $900", sx(10)) and last_log()["actions"][0]["outcome"] == "cache hit"
assert pb.run_count("t4") == 2
# the refused query was not cached: with room again it is sent
caller("test", "t4", cap=3)
assert ps.search("where to buy a 4090", sx(10)) and last_log()["actions"][0]["outcome"] == "sent"
assert pb.run_count("t4") == 3

# 5. month threshold: a test stops at $7.50 of Exa's $10; product falls back to Tavily when SearXNG is thin;
#    a cached answer is still served
caller("test", "t5")
ex.USAGE_FILE.write_text(json.dumps({"month": ex._month(), "usd": 7.499, "searches": 0, "closed": False}))
got = ps.search("cheap 2TB SSD price", sx(1))
acts = last_log()["actions"]
assert acts[0]["source"] == "exa" and acts[0]["outcome"].startswith("refused: test month limit $7.50"), acts
assert acts[1]["source"] == "tavily" and acts[1]["outcome"] == "sent" and got and got[0]["engine"] == "tavily", acts
assert pb.run_count("t5") == 1                          # the refused Exa reservation was given back
assert ps.search("RTX 5090 price in Germany", sx(10)) and last_log()["actions"][0]["outcome"] == "cache hit"
ex.USAGE_FILE.write_text(json.dumps({"month": ex._month(), "usd": 0.0, "searches": 0, "closed": False}))

# 6. a failed request is not cached; the next try is sent again
caller("test", "t6")
assert ps.search("fail500 price check", sx(10)) == [] and last_log()["actions"][0]["outcome"] == "error: HTTP 500"
c0 = counts()
ps.search("fail500 price check", sx(10))
assert counts()["exa"] == c0["exa"] + 1 and last_log()["actions"][0]["cache"] == "miss"

# 7. a profile for one item 7 part: 7c = Exa Lite on every search (PAID_ROUTE_PROFILE wins over the config)
os.environ["PAID_ROUTE_PROFILE"] = "7c"
got = ps.search("history of byzantium", sx(10))
assert got and got[0]["engine"] == "exa" and last_log()["profile"] == "7c"
del os.environ["PAID_ROUTE_PROFILE"]

# 8. a test caller without a run id gets no paid search, cached or not counted
caller("test", None)
assert ps.search("cheapest 8TB HDD", sx(10)) == [] and last_log()["actions"][0]["outcome"].startswith("refused: no PAID_SEARCH_RUN")

# 9. never raises; no key or request header in the cache or the logs
real = ps.FREE["s2"].search
ps.FREE["s2"].search = lambda *a, **k: 1 / 0
assert ps.search("meta-analysis of sleep", sx(10)) == [] and last_log()["error"] == "ZeroDivisionError"
ps.FREE["s2"].search = real
blob = ROUTE_LOG.read_text() + ex.LOG_FILE.read_text() + tv.LOG_FILE.read_text()
blob += "".join(p.read_text() for p in CACHE.glob("*.json"))
assert FAKE_KEY not in blob and "x-api-key" not in blob and "Bearer" not in blob
assert all(Mock.seen_auth), "the providers still send their key header to the (mock) API"
assert list(CACHE.glob("*.json")), "the cache folder is the temp one"

# 10. the tracker reads these temp files: cache hits and runs line up with the counts above
rep = paid_tracker.collect(ex._month(), {"exa_usage": ex.USAGE_FILE, "tavily_usage": tv.USAGE_FILE,
                                         "runs": Path(os.environ["PAID_SEARCH_RUNS_FILE"]), "exa_log": ex.LOG_FILE,
                                         "tavily_log": tv.LOG_FILE, "route_log": ROUTE_LOG})
hits = sum(1 for line in ROUTE_LOG.read_text().splitlines()
           for a in json.loads(line).get("actions", []) if a.get("outcome") == "cache hit")
assert rep["providers"]["exa"]["cache_hits"] == hits == 3, (rep["providers"]["exa"], hits)
t4 = next(r for r in rep["runs"] if r["run"] == "t4")
assert (t4["exa"], t4["runs_file"], t4["cache_hits"], t4["refused"], t4["cap"]) == (3, 3, 1, 1, 30), t4

# 11. the staged LDR hook compiles and calls this entry point
src = Path("/home/USER/ai/deep-research/staging/item7/ldr/search_engine_searxng.py").read_text()
compile(src, "search_engine_searxng.py", "exec")
assert "_ps.search(query, results, client=\"ldr\", max_results=10)" in src and "_dr_paid_reason" not in src

finish("ok: routing off = today's fallback (Exa then Tavily, < 5, dedupe), routing on per tag (S2 / Exa / Tavily / "
       "none), cache hits free and uncounted, run cap + month threshold refuse, refusals and failures not cached, "
       "7c profile, no-run test refused, never raises, no keys, tracker agrees, LDR hook compiles")
