"""Item 7 monthly tracker (10-29): synthetic counters, run counts and logs in a temp folder; JSON + text output."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, "/home/USER/ai/deep-research/staging/item7/tests")
from _offline import TMP, TOOLS, finish  # noqa: E402

import paid_tracker as pt  # noqa: E402

M = time.strftime("%Y-%m", time.gmtime())
y, m = map(int, M.split("-"))
PREV = f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"
D = TMP / "tracker"
D.mkdir()
paths = {k: D / Path(str(v)).name for k, v in pt.DEFAULTS.items()}


def jl(p, recs):
    p.write_text("".join(json.dumps(r) + "\n" for r in recs) + "not json\n")


paths["exa_usage"].write_text(json.dumps({"month": M, "usd": 7.6, "searches": 9, "closed": False}))
paths["tavily_usage"].write_text(json.dumps({"month": M, "count": 120}))
paths["runs"].write_text(json.dumps({"month": M, "runs": {"p4s7/o01": 7, "job-1": 2}}))
t = f"{M}-15T10:00:00"
jl(paths["exa_log"], [
    {"t": t, "client": "jan", "kind": "chat", "run": None, "results": 5, "cost_usd": 0.004},
    {"t": t, "client": "jan", "results": 5, "cost_usd": 0.005},                       # before item 7: no kind -> chat
    {"t": t, "client": "ldr", "kind": "test", "run": "p4s7/o01", "results": 10, "cost_usd": 0.004},
    {"t": t, "client": "ldr", "kind": "test", "run": "p4s7/o01", "results": 10, "cost_usd": None},   # estimate
    {"t": t, "client": "ldr", "kind": "test", "run": "p4s7/o01", "error": "HTTP 500"},                 # estimate kept
    {"t": t, "client": "ldr", "kind": "test", "run": "p4s7/o01", "skipped": "run cap 30 reached (p4s7/o01)"},
    {"t": t, "client": "ldr", "kind": "research", "run": "job-1", "results": 8, "cost_usd": 0.004},
    {"t": t, "client": "ldr", "kind": "research", "run": "job-1", "results": 8, "cost_usd": 0.004},
    {"t": t, "client": "ldr", "results": 3, "cost_usd": 0.004},                       # before item 7: ldr -> research
    {"t": t, "client": "ldr", "kind": "test", "run": None, "skipped": "no PAID_SEARCH_RUN for a test caller"},
    {"t": f"{PREV}-28T10:00:00", "client": "jan", "kind": "chat", "results": 5, "cost_usd": 0.004},
])
jl(paths["tavily_log"], [{"t": t, "client": "ldr", "kind": "test", "run": "p4s7/o01", "results": 5}] * 4
   + [{"t": t, "client": "chat", "kind": "chat", "run": None, "results": 5},
      {"t": f"{PREV}-02T10:00:00", "client": "chat", "kind": "chat", "results": 5}])
hit = {"source": "exa", "outcome": "cache hit", "n": 3, "saved": 0.004}
jl(paths["route_log"], [{"t": t, "month": M, "kind": "test", "run": "p4s7/o01", "actions": [hit]}] * 3
   + [{"t": t, "month": M, "kind": "chat", "run": None,
       "actions": [{"source": "tavily", "outcome": "cache hit", "n": 5, "saved": 1.0}]},
      {"t": t, "month": M, "kind": "test", "run": "p4s7/o01", "actions": [{"source": "exa", "outcome": "sent", "n": 3}]},
      {"t": f"{PREV}-28T10:00:00", "month": PREV, "kind": "chat", "actions": [hit]}])

rep = pt.collect(M, paths)
e, v = rep["providers"]["exa"], rep["providers"]["tavily"]
assert (e["used"], e["used_from"], e["credit"], e["stop_tests_research_at"], e["stop_all_at"]) == (7.6, "counter", 10.0, 7.5, 9.0), e
assert e["status"].startswith("tests/research stopped") and abs(e["to_go_all"] - 1.4) < 1e-9 and e["left_pct"] == 24.0, e
assert (v["used"], v["status"], v["to_go_tests_research"], v["to_go_all"]) == (120, "ok", 630, 780), v
assert (e["cache_hits"], e["saved"], v["cache_hits"], v["saved"]) == (3, 0.012, 1, 1.0)
k = rep["kinds"]["exa"]
assert (k["chat"]["sent"], k["chat"]["used"]) == (2, 0.009), k["chat"]
assert (k["test"]["sent"], k["test"]["errors"], k["test"]["refused"], k["test"]["used"]) == (3, 1, 2, 0.012), k["test"]
assert (k["research"]["sent"], k["research"]["used"]) == (3, 0.012), k["research"]
assert rep["kinds"]["tavily"]["test"]["sent"] == 4 and rep["kinds"]["tavily"]["chat"]["sent"] == 1
assert rep["kinds"]["tavily"]["chat"]["cache_hits"] == 1
runs = {r["run"]: r for r in rep["runs"]}
o1 = runs["p4s7/o01"]
assert (o1["kind"], o1["exa"], o1["tavily"], o1["total"], o1["cap"], o1["left"], o1["runs_file"], o1["refused"],
        o1["cache_hits"]) == ("test", 3, 4, 7, 30, 23, 7, 1, 3), o1
j1 = runs["job-1"]
assert (j1["kind"], j1["total"], j1["cap"], j1["left"], j1["runs_file"]) == ("research", 2, 100, 98, 2), j1
nr = runs["(no run id: research)"]                                                # a pre-item-7 ldr search
assert (nr["kind"], nr["exa"], nr["left"], nr["refused"]) == ("research", 1, None, 0), nr
assert runs["(no run id: test)"]["refused"] == 1 and runs["(no run id: test)"]["total"] == 0
assert "jan" not in runs and all(r["kind"] != "chat" for r in rep["runs"])

# thresholds: 10 % left stops everyone; a closed Exa month too
paths["tavily_usage"].write_text(json.dumps({"month": M, "count": 900}))
paths["exa_usage"].write_text(json.dumps({"month": M, "usd": 0.5, "searches": 9, "closed": True}))
rep2 = pt.collect(M, paths)
assert rep2["providers"]["tavily"]["status"].startswith("all stopped") and rep2["providers"]["tavily"]["left_pct"] == 10.0
assert rep2["providers"]["exa"]["status"] == "all stopped (provider said out of credit)" and rep2["providers"]["exa"]["closed"]
# a past month: the counters hold this month, so "used" comes from the logs
old = pt.collect(PREV, paths)
assert old["providers"]["exa"]["used_from"] == "logs" and old["providers"]["exa"]["used"] == 0.004
assert old["providers"]["tavily"]["used"] == 1 and old["providers"]["exa"]["cache_hits"] == 1 and old["runs"] == []
# missing files are empty, not errors
empty = pt.collect(M, {k: D / "nope" / k for k in paths})
assert empty["providers"]["exa"]["used"] == 0 and empty["runs"] == [] and not any(s["present"] for s in empty["sources"].values())
assert "missing (counted as empty)" in pt.text(empty)

# the script itself (python -I, as installed): text, JSON and --write, with every path given
args = [a for k, p in paths.items() for a in ("--" + k.replace("_", "-"), str(p))]
env = {"PATH": "/usr/bin:/bin", "HOME": os.environ["HOME"]}
py = "/home/USER/ai/deep-research/.venv/bin/python"
out = subprocess.run([py, "-I", "-B", f"{TOOLS}/paid_tracker.py", "--month", M, *args], capture_output=True, text=True,
                     env=env, timeout=60)
assert out.returncode == 0, out.stderr
txt = out.stdout
assert f"Paid search, {M}" in txt and "all stopped" in txt and "p4s7/o01" in txt and "job-1" in txt, txt
assert "exa / test" in txt and "tavily / chat" in txt and "query" not in txt.lower()
out = subprocess.run([py, "-I", "-B", f"{TOOLS}/paid_tracker.py", "--json", "--month", M, "--write", str(D / "out"), *args],
                     capture_output=True, text=True, env=env, timeout=60)
assert out.returncode == 0, out.stderr
j = json.loads(out.stdout)
assert j["month"] == M and {r["run"] for r in j["runs"]} == {"job-1", "p4s7/o01", "(no run id: research)", "(no run id: test)"}
assert (D / "out" / f"paid-{M}.json").is_file() and (D / "out" / f"paid-{M}.txt").is_file()
for name in ("exa_usage", "tavily_usage", "runs", "exa_log"):                   # read-only
    assert paths[name].stat().st_size > 0
print(txt)
finish("ok: tracker - per provider (25 % / 10 % thresholds, closed month, counter vs logs), per kind (sent / refused / "
       "errors / used / cache hits / saved), per run (cap, left, runs file), past month, missing files, script text/JSON/"
       "--write")
