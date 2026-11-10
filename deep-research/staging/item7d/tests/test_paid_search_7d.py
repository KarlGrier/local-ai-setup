"""7d end to end: the staged paid_search + search_route with the LIVE providers / paid_budget against a local mock.
python -I -B test_paid_search_7d.py"""
import contextvars
import json
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _offline as T  # noqa: E402

ex, tv = T.wire_providers()
import paid_budget  # noqa: E402
import paid_search as PS  # noqa: E402
import search_route as R  # noqa: E402

n_ok = 0


def ok(cond, what):
    global n_ok
    assert cond, what
    n_ok += 1


SX = [{"url": f"https://searx.example/{i}", "title": "t", "content": "c"} for i in range(10)]   # SearXNG's 10
cv = T.ldr_deep_on()
fast = json.loads(Path(T.STAGE, "tools", "paid-route.json").read_text())
for p in ("7d", "7dx"):
    fast["profiles"][p]["_select"]["follow_after_s"] = 0          # no 15-min wait inside a test
FAST = T.TMP / "paid-route-fast.json"
FAST.write_text(json.dumps(fast))


def counts():
    return dict(T.Mock.counts)


def delta(before):
    now = counts()
    return {k: now.get(k, 0) - before.get(k, 0) for k in now}


def go(q, agent):
    cv.set(agent)
    return PS.search(q, SX, client="ldr", max_results=10)


# --- 7d: a run of 1 lead + 20 sub1 + 10 sub2 (opening), lead follow-up x12, then 8 subagents x 4 ------------------------
R.CONFIG_FILE = FAST                                              # (the module reads the env at import)
T.write_run_file("screen-deep-p7d/o01", "7d", written=111.0)
b = counts()
stream = [("lead", "opening broad query")] * 2 + [("sub1", "sub1 query")] * 20 + [("sub2", "sub2 query")] * 10
stream += [("lead", "lead follow-up check")] * 12
stream += [(f"sub{3 + j}", f"wave2 sub{3 + j} query") for j in range(8) for _ in range(4)]
added = [len(go(f"{q} {i}", a)) for i, (a, q) in enumerate(stream)]
d = delta(b)
rows = [r for r in T.route_rows() if r.get("run") == "screen-deep-p7d/o01"]
ok(len(rows) == len(stream), f"one route line per search ({len(rows)})")
ok(all("select" in r for r in rows), "every 7d line has its select record")
picked = [r["select"]["n"] for r in rows if r["select"]["picked"]]
ok(picked[:10] == list(range(33, 43)), f"the lead's first 10 follow-ups are picked first: {picked[:10]}")
sent = [r["select"]["n"] for r in rows if any(a.get("outcome") == "sent" for a in r["actions"])]
refused = [r for r in rows if any(str(a.get("outcome", "")).startswith("refused: run cap 30") for a in r["actions"])]
ok(d["tavily"] == 30 and len(sent) == 30, f"30 Tavily searches sent (the run cap): {d}")
ok(d["exa"] == 0, "7d never asks Exa")
ok(len(refused) == len(picked) - 30, f"picked beyond 30 are refused by paid_budget ({len(picked)} picked)")
ok(all(not r["actions"] for r in rows if not r["select"]["picked"]), "unpicked searches ask no paid source")
ok(sum(added[:32]) == 0 and sum(added) == 30 * 3, "only picked + sent searches add results (3 each from the mock)")
per = {}
for r in rows:
    if r["select"]["picked"]:
        per[r["select"]["agent"]] = per.get(r["select"]["agent"], 0) + 1
ok(per.get("lead") == 10 and all(v == 3 for k, v in per.items() if k != "lead"), f"caps: lead 10, 3 per sub {per}")
ok(rows[32]["select"]["follow_at"] == 33 and "follow-up from search 33" in rows[40]["select"]["why"],
   "the log says where the follow-up phase began")
ok(paid_budget.run_count("screen-deep-p7d/o01") == 30, "paid-runs.json counts 30")

# --- a rerun under the same run id (new run-file stamp) starts its own state ---------------------------------------
T.write_run_file("screen-deep-p7d/o01", "7d", written=222.0)
go("rerun first search", "lead")
r = T.route_rows()[-1]
ok(r["select"]["n"] == 1 and not r["select"]["picked"], "a new run-file stamp = a fresh state (search 1)")
st = json.loads(Path(os.environ["PAID_ROUTE_STATE"]).read_text())["runs"]
ok({"screen-deep-p7d/o01@111.0", "screen-deep-p7d/o01@222.0"} <= set(st), f"state keys {sorted(st)}")

# --- 7dx: product-tagged follow-ups -> Exa, the rest -> Tavily --------------------------------------------------------
T.write_run_file("shop-7e-deep-p7dx/s3", "7dx", written=333.0)
b = counts()
for a, q in [("lead", "opening"), ("sub1", "sub1 q"), ("lead", "RTX 5060 Ti 16GB price Best Buy November 2026 in stock"),
             ("lead", "RTX 5060 Ti PCIe interface x8 electrical TechPowerUp specifications"),
             ("sub2", "used RTX 3090 eBay sold price November 2026"), ("sub2", "Tesla P40 desktop cooling mod")]:
    go(a and q, a)
d = delta(b)
rows = [r for r in T.route_rows() if r.get("run") == "shop-7e-deep-p7dx/s3"]
ok(d["exa"] == 2 and d["tavily"] == 2, f"7dx: 2 product -> Exa, 2 other -> Tavily {d}")
ok([r["tag"] for r in rows if r["select"]["picked"]] == ["product", "general", "product", "general"],
   [r["tag"] for r in rows])
ok(paid_budget.run_count("shop-7e-deep-p7dx/s3") == 4, "both providers count against the one run cap")

# --- the agent label comes from the calling context (LangGraph tool threads copy contextvars) ------------------------
T.write_run_file("screen-deep-p7d/o02", "7d", written=444.0)
go("o02 opening", "lead")
seen = []


def in_thread():
    PS.search("o02 sub7 query in a tool thread", SX, client="ldr")
    seen.append(T.route_rows()[-1]["select"]["agent"])


ctx = contextvars.copy_context()
cv.set("sub7")
ctx2 = contextvars.copy_context()
th = threading.Thread(target=ctx2.run, args=(in_thread,))
th.start()
th.join()
ok(seen == ["sub7"], f"the label read in a thread with a copied context: {seen}")

# --- outside deep mode (no ContextVar in sys.modules): skip 30, then first come, first served -----------------------
T.ldr_deep_off()
T.write_run_file("screen-deep-p7d/nodeep", "7d", written=555.0)
b = counts()
for i in range(35):
    PS.search(f"plain query {i}", SX, client="ldr")
rows = [r for r in T.route_rows() if r.get("run") == "screen-deep-p7d/nodeep"]
ok(delta(b)["tavily"] == 5 and all(r["select"]["agent"] == "?" for r in rows), "no labels: searches 31-35 paid")
cv = T.ldr_deep_on()

# --- profiles without _select are unchanged: 7b (Tavily on every search), routing off (today's fallback) -------------
T.write_run_file("screen-deep-p7b-check/o01", "7b", written=666.0)
b = counts()
for i in range(3):
    go(f"7b query {i}", "lead")
rows = [r for r in T.route_rows() if r.get("run") == "screen-deep-p7b-check/o01"]
ok(delta(b)["tavily"] == 3 and all("select" not in r for r in rows), "7b: every search, no select record")
T.write_run_file("research-job-1", None, kind="research", written=777.0)
b = counts()
go("research query with full searxng", "lead")
ok(sum(delta(b).values()) == 0, "routing off + SearXNG >= 5: nothing asked (today)")
PS.search("research query few results", SX[:2], client="ldr")
ok(delta(b)["exa"] == 1, "routing off + SearXNG < 5: Exa fallback as today")
ok("select" not in T.route_rows()[-1], "routing off: no select record")

# --- no run id: nothing is spent, never raises ------------------------------------------------------------------------
Path(os.environ["PAID_SEARCH_RUN_NOW"]).unlink()
os.environ["PAID_ROUTE_PROFILE"] = "7d"
b = counts()
go("profile from env but no run id", "lead")
ok(sum(delta(b).values()) == 0 and T.route_rows()[-1]["select"]["why"] == "no run id", "no run id: no paid search")
os.environ.pop("PAID_ROUTE_PROFILE")

# --- a broken state file is read as empty; an unwritable one means no paid search, no exception ---------------------
T.write_run_file("screen-deep-p7d/o03", "7d", written=888.0)
Path(os.environ["PAID_ROUTE_STATE"]).write_text("{not json")
go("after a broken state file", "lead")
ok(T.route_rows()[-1]["select"]["n"] == 1, "broken state file -> a fresh state")
good = PS.STATE_FILE
PS.STATE_FILE = T.TMP / "no-such-dir" / "x" / "state.json"
(T.TMP / "no-such-dir").write_text("a file where a folder should be")
b = counts()
res = go("state file cannot be written", "lead")
ok(res == [] and sum(delta(b).values()) == 0, "unwritable state: [] and nothing sent")
ok(T.route_rows()[-1]["select"]["why"].startswith("state file:"), T.route_rows()[-1]["select"])
PS.STATE_FILE = good

# --- old entries are dropped after 7 days ------------------------------------------------------------------------------
st = json.loads(PS.STATE_FILE.read_text())
st["runs"]["old-run@1"] = {**R.new_state(0.0), "t": 0.0}
PS.STATE_FILE.write_text(json.dumps(st))
go("prune check", "lead")
ok("old-run@1" not in json.loads(PS.STATE_FILE.read_text())["runs"], "entries idle > 7 days are dropped")

# --- the hook's call shape still works (patch 0005: search(query, results, client="ldr", max_results=10)) -----------
ok(isinstance(PS.search("hook shape", SX, client="ldr", max_results=10), list), "hook call signature")
ok(PS.search("", SX) == [] and PS.search(None, None) == [], "empty query -> []")

T.finish(f"test_paid_search_7d: {n_ok} checks passed")
