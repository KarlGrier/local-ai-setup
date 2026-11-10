#!/usr/bin/env python3
"""c4_web.py URL OUTDIR --plan PLAN.json [--label L | --server-log F] [--elog-base N] - C4 of the v0.2.13 switch checks
(work/r23/switch-gap/switch_rules.py, the C4 rule): the server's own web search end to end on ONE fresh test server
(bringup/lib/with_server.sh, 127.0.0.1:8081): each request carries "strata_web": true, the web page's path through
server.py's run_with_mcp (serve/websearch.py's web_search / fetch_page, run by the server). The requests are JSON
(Content-Type application/json) and carry no Origin header (server.py's _own_page refuses a foreign one). Written
2026-11-10 at the desk; NOT RUN against a server (only `selftest`, on a fake one). The driver runs it when
switch_rules.py webpath found the path SearXNG-only, or the paid path (the Exa / Tavily fallback) within the paid budget.

Every request sends the standard sampling (temperature 1.0, top_p 0.95, top_k 20, min_p 0.05; presence 0, frequency 0,
repetition 1) and its seed, thinking off, stream with usage; no request starts after the plan's whole budget, and one
request is cut at the plan's timeout_s.
-> OUTDIR/web.jsonl (per request: completed, finish, the tool rounds, web_search calls, fetch_page calls and the pages
they opened (result ok), the URLs the search results listed, the URLs the answer cites, cited_fetched (cited AND opened by
fetch_page), cited_tool (cited AND returned by a tool), errors (an error chunk, a failed / cut request, a web_search tool
error, the lost-answer line or a fatal line in the request's server-log slice), tool_errors (fetch_page failures, info),
the answer's first 400 characters, the log byte ranges), OUTDIR/server.out, OUTDIR/engine.out.
Exit 0 every request completed, 1 one did not, 2 refused. `c4_web.py selftest DIR` (DIR under the gap's scratch/).
(coordinator 11-10, review 11-10) THE PAID CALLS. THE HARD LIMIT is paid_budget.py's run cap in the TEST SERVER: the
driver starts it with PAID_SEARCH_KIND=test, PAID_SEARCH_RUN=<the gap's run id> and PAID_SEARCH_RUN_CAP (B 5, P 10; one
run id for both arms, so B can never use more than 5 and the two arms together never more than 10). THIS CLIENT'S STOP
IS THE SOFT ONE: with --paid-base FILE (switch_rules.py paidcheck's counters, read right before C4) it counts the paid
calls through the providers' own counter code (--paid-tools: exa_fallback.usage()["searches"] +
tavily_fallback.usage()["count"]; no key file is read; Jan chat's own calls in that time are counted too); before each
request: the arm's own calls since its first request reach --paid-arm-stop (5) or the total since the base reaches
--paid-stop (10) -> no further request is sent, it and the rest are recorded {"not_run": true, "why": ...}; after each
request its own delta ("paid_calls") and the running total ("paid_total"). Counters that cannot be read: nothing is sent.
THE ENV GATE (review S1): with --paid-env-run RUN --paid-env-cap N, before anything is sent the test server's own
environment (the 8081 listener = server.py, /proc/PID/environ) must hold PAID_SEARCH_KIND=test, PAID_SEARCH_RUN=RUN and
PAID_SEARCH_RUN_CAP=N; else nothing is sent on this arm, every request is recorded "C4 NOT RUN (env)" and the gate
(--paid-env-gate / --paid-env-gates) says FAIL (exit 2).
"""
import glob
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
WS = "/home/USER/ai-speed-testing/strata-compare"
SERVER_LOGS = f"{WS}/bringup/out/logs"
SCRATCH = os.path.join(HERE, "scratch")
STANDARD = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}
URL_RE = re.compile(r"https?://[^\s<>\"'`)\]}]+", re.I)
LOST = "a request ended without an answer and without a finish reason"
FATAL_RE = re.compile(r"fatal GPU error|no progress for [0-9]+ s during a request|the engine had stopped \(exit code|became non-finite")
TOOLERR_RE = re.compile(r"^\[strata\] tool (\w+): error", re.M)
SETTLE_S = 2.0                                       # the request's last server lines follow its last chunk (the selftest: 0)
PAID_TOOLS = "/home/USER/ai/deep-research/tools"


def paid_counter(tools):
    """a function returning the providers' paid calls this month (their own usage() code; the key files are not touched)"""
    import importlib.util
    if tools not in sys.path:
        sys.path.insert(0, tools)
    mods = []
    for name in ("exa_fallback", "tavily_fallback"):
        spec = importlib.util.spec_from_file_location(f"{name}_c4", os.path.join(tools, f"{name}.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        mods.append(m)
    return lambda: int(mods[0].usage().get("searches", 0)) + int(mods[1].usage().get("count", 0))


def size(p):
    try:
        return os.path.getsize(p) if p else None
    except OSError:
        return None


def server_log(label, path=None):
    if path:
        return path
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", label or ""):
        return None
    c = sorted(glob.glob(f"{SERVER_LOGS}/server_{label}_*.log"), key=os.path.getmtime)
    return c[-1] if c else None


def norm_url(u):
    u = u.strip().rstrip(".,;:")
    m = re.match(r"^(?:https?://)?([^/?#]+)([^?#]*)(\?[^#]*)?", u, re.I)
    if not m:
        return u.lower()
    host = m.group(1).lower()
    host = host[4:] if host.startswith("www.") else host
    return host + (m.group(2).rstrip("/") or "") + (m.group(3) or "")


def body_of(r, fields):
    return {"model": "x", "messages": r["messages"], "max_tokens": r["max_tokens"], "stream": True,
            "stream_options": {"include_usage": True}, **fields, "seed": r["seed"],
            "chat_template_kwargs": {"enable_thinking": bool(r.get("thinking"))}, "strata_web": True}


def post_web(url, body, timeout_s):
    req = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    content, calls, results, finish, errs, done, limit = [], {}, {}, None, [], False, False
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=min(120, timeout_s)) as resp:
        for raw in resp:
            if time.monotonic() - t0 > timeout_s:
                errs.append(f"cut at {timeout_s} s")
                break
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                done = True
                break
            try:
                ev = json.loads(data)
            except ValueError:
                continue
            if ev.get("error"):
                errs.append("error chunk: " + str(ev["error"])[:200])
            m = ev.get("strata_mcp")
            if isinstance(m, dict):
                if m.get("event") == "call":
                    calls[m.get("id")] = m
                elif m.get("event") == "result":
                    results[m.get("id")] = m
                elif m.get("event") == "limit":
                    limit = True
            for ch in ev.get("choices") or []:
                d = ch.get("delta") or {}
                if d.get("content"):
                    content.append(d["content"])
                if ch.get("finish_reason"):
                    finish = ch["finish_reason"]
    return "".join(content), calls, results, finish, errs, done, limit, round(time.monotonic() - t0, 1)


def record(r, answer, calls, results, finish, errs, done, limit, wall):
    rounds = sorted({c.get("round") for c in calls.values() if c.get("round") is not None})
    search = [c for c in calls.values() if c.get("name") == "web_search"]
    fetch = [c for c in calls.values() if c.get("name") == "fetch_page"]
    surls, fok, tool_err = set(), set(), []
    for cid, c in calls.items():
        res = results.get(cid) or {}
        txt = str(res.get("text") or "")
        if c.get("name") == "web_search":
            surls |= {norm_url(u) for u in URL_RE.findall(txt)}
            if res and not res.get("ok"):
                errs = errs + [f"web_search error: {txt[:120]}"]
        elif c.get("name") == "fetch_page":
            if res.get("ok"):
                u = str((c.get("arguments") or {}).get("url") or "")
                fok.add(norm_url(u))
                hm = re.match(r"^URL: (\S+)", txt)
                if hm:
                    fok.add(norm_url(hm.group(1)))
            else:
                tool_err.append(f"fetch_page {(c.get('arguments') or {}).get('url')}: {txt[:80]}")
    cited = {norm_url(u) for u in URL_RE.findall(answer)}
    completed = bool(done and finish in ("stop", "length") and not errs and answer.strip())
    return {"name": r["name"], "seed": r["seed"], "completed": completed, "finish": finish, "done": done, "rounds": len(rounds),
            "search_calls": len(search), "fetch_calls": len(fetch), "fetch_ok": sorted(fok), "search_urls": len(surls),
            "cited": sorted(cited), "cited_fetched": sorted(cited & fok), "cited_tool": sorted(cited & (fok | surls)),
            "errors": errs, "tool_errors": tool_err, "limit": limit, "answer_chars": len(answer), "answer": answer[:400],
            "wall_s": wall}


def listener_environ(port):
    """(pid, env) of the process listening on 127.0.0.1:PORT (the test server's server.py)"""
    import subprocess
    r = subprocess.run(["ss", "-H", "-ltnp", f"( sport = :{int(port)} )"], capture_output=True, text=True, timeout=10)
    m = re.search(r"pid=(\d+)", r.stdout)
    if not m:
        raise RuntimeError(f"nothing listens on port {port}")
    pid = m.group(1)
    return pid, read_environ(f"/proc/{pid}/environ")


def read_environ(path):
    raw = open(path, "rb").read().decode("utf-8", "replace")
    return dict(x.split("=", 1) for x in raw.split("\0") if "=" in x)


def paid_env_problems(env, run, cap):
    want = {"PAID_SEARCH_KIND": "test", "PAID_SEARCH_RUN": run, "PAID_SEARCH_RUN_CAP": str(cap)}
    return [f"{k}={env.get(k, 'unset')} (want {v})" for k, v in want.items() if env.get(k) != v]


def not_run(out, reqs, why):
    with open(f"{out}/web.jsonl", "a") as f:
        for r in reqs:
            f.write(json.dumps({"name": r["name"], "seed": r["seed"], "not_run": True, "completed": False, "why": why,
                                "paid_calls": 0}) + "\n")
    print(f"not run ({why}): {', '.join(r['name'] for r in reqs)}", flush=True)


def run(url, out, plan, slog, elog, ebase, paid_base=None, paid_tools=PAID_TOOLS, paid_stop=10, arm_stop=5, penv=None):
    os.makedirs(out, exist_ok=True)
    fields = plan.get("fields") or {}
    bad = [f"{k}={fields.get(k)!r} (the standard sampling is {v})" for k, v in STANDARD.items() if fields.get(k) != v]
    if bad or not plan.get("requests"):
        print("refused: " + ("; ".join(bad) or "no requests in the plan"), flush=True)
        return 2
    tmo = float(plan.get("timeout_s") or 300)
    if penv:   # (review S1) the hard cap must be in the test server's own environment before anything is sent
        try:
            if penv.get("environ"):
                pid, env = "file", read_environ(penv["environ"])
            else:
                pid, env = listener_environ(penv.get("port", 8081))
            probs = paid_env_problems(env, penv["run"], penv["cap"])
        except Exception as e:  # noqa: BLE001
            pid, probs = "?", [f"the server's environment could not be read ({type(e).__name__}: {str(e)[:100]})"]
        line = (f"PAID ENV OK: server pid {pid} has PAID_SEARCH_KIND=test, PAID_SEARCH_RUN={penv['run']}, PAID_SEARCH_RUN_CAP="
                f"{penv['cap']}" if not probs else f"C4 NOT RUN (env): server pid {pid}: {'; '.join(probs)}")
        print(line, flush=True)
        if penv.get("gate") and penv.get("gates"):
            with open(penv["gates"], "a") as f:
                f.write(f"{penv['gate']} {'PASS' if not probs else 'FAIL'} {line[:300]}\n")
        if probs:
            not_run(out, plan["requests"], line[:200])
            return 2
    count, base = None, 0
    if paid_base:
        try:
            base = sum(int(x["calls"]) for x in json.load(open(paid_base)).values())
            count = paid_counter(paid_tools)
            count()
        except Exception as e:  # noqa: BLE001 - unbounded paid use is not allowed: nothing is sent
            not_run(out, plan["requests"], f"the paid counters could not be read ({type(e).__name__}: {str(e)[:100]})")
            return 2
    rc = 0
    reqs = list(plan["requests"])
    arm0 = count() if count else None
    for i, r in enumerate(reqs):
        before = count() if count else None
        if count and (before - base >= paid_stop or before - arm0 >= arm_stop):
            not_run(out, reqs[i:], f"the paid-call stop (soft): {before - arm0} of the arm's {arm_stop}, {before - base} of "
                                   f"{paid_stop} in all")
            rc = rc or 1
            break
        s0, e0 = size(slog), size(elog)
        try:
            rec = record(r, *post_web(url, body_of(r, fields), tmo))
        except Exception as e:  # noqa: BLE001
            rec = record(r, "", {}, {}, None, [f"request failed: {type(e).__name__}: {e}"[:200]], False, False, None)
        if count:
            after = count()
            rec["paid_calls"], rec["paid_total"] = after - before, after - base
        time.sleep(SETTLE_S)
        s1, e1 = size(slog), size(elog)
        sl = ""
        if slog and s0 is not None and s1 is not None:
            with open(slog, "rb") as f:
                f.seek(s0)
                sl = f.read(s1 - s0).decode("utf-8", "replace")
        el = ""
        if elog and e0 is not None and e1 is not None:
            with open(elog, "rb") as f:
                f.seek(e0)
                el = f.read(e1 - e0).decode("utf-8", "replace")
        if LOST in sl:
            rec["errors"].append("the lost-answer line")
        nf = len(FATAL_RE.findall(sl + el))
        if nf:
            rec["errors"].append(f"{nf} fatal / stall / restart / non-finite line(s)")
        rec["server_tool_errors"] = TOOLERR_RE.findall(sl)
        if rec["errors"]:
            rec["completed"] = False
        rec["srv_off"] = [s0, s1] if s0 is not None and s1 is not None else None
        rec["eng_off"] = [e0 - ebase, e1 - ebase] if e0 is not None and e1 is not None else None
        if not rec["completed"]:
            rc = 1
        with open(f"{out}/web.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"{rec['name']}: completed {rec['completed']} ({rec['finish']}), {rec['search_calls']} search / "
              f"{rec['fetch_calls']} fetch call(s), cited {len(rec['cited'])} (fetched {len(rec['cited_fetched'])})"
              + (f", paid {rec['paid_calls']} (total {rec['paid_total']})" if "paid_calls" in rec else "")
              + (f", ERRORS {rec['errors']}" if rec["errors"] else ""), flush=True)
    for src, dst, off in ((slog, "server.out", 0), (elog, "engine.out", ebase)):
        if src and os.path.exists(src):
            with open(src, "rb") as f, open(f"{out}/{dst}", "wb") as g:
                f.seek(off)
                g.write(f.read())
    return rc


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["selftest"]:
        return selftest(argv[1] if len(argv) > 1 else f"{SCRATCH}/c4-web-selftest")
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("url")
    ap.add_argument("out")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--label")
    ap.add_argument("--server-log")
    ap.add_argument("--elog-base", type=int, default=0)
    ap.add_argument("--paid-base", help="switch_rules.py paidcheck's counters before C4 (the stop counts from them)")
    ap.add_argument("--paid-tools", default=PAID_TOOLS)
    ap.add_argument("--paid-stop", type=int, default=10)
    ap.add_argument("--paid-arm-stop", type=int, default=5)
    ap.add_argument("--paid-env-run", help="(review S1) the run id the test server's environment must carry")
    ap.add_argument("--paid-env-cap", help="... and its PAID_SEARCH_RUN_CAP")
    ap.add_argument("--paid-env-port", type=int, default=8081)
    ap.add_argument("--paid-env-gate")
    ap.add_argument("--paid-env-gates")
    a = ap.parse_args(argv)
    try:
        plan = json.load(open(a.plan))
    except (OSError, ValueError) as e:
        print(f"refused: the plan {a.plan}: {e}")
        return 2
    penv = ({"run": a.paid_env_run, "cap": a.paid_env_cap, "port": a.paid_env_port, "gate": a.paid_env_gate,
             "gates": a.paid_env_gates} if a.paid_env_run else None)
    return run(a.url, a.out, plan, server_log(a.label, a.server_log), os.environ.get("ELOG"), a.elog_base, a.paid_base,
               a.paid_tools, a.paid_stop, a.paid_arm_stop, penv)


# ================================================================ the stub selftest (no server, no network)
class Fake:
    """a fake strata_web stream: MODE good (a search, a fetch, the answer citing the page), snippet (a search, the answer
    cites a search result only), nosearch (an answer without a tool), error (an error chunk), lost (the server's lost line)"""
    def __init__(self, slog, modes, counter=None, paid_per=0, run_cap=None):
        self.slog, self.modes, self.reqs, self.counter, self.paid_per = slog, list(modes), [], counter, paid_per
        self.run_cap = run_cap          # paid_budget.py's run cap in this server (None: no cap emulated)

    def __call__(self, req, timeout=None):
        import io
        b = json.loads(req.data.decode())
        self.reqs.append((req, b))
        mode = self.modes[len(self.reqs) - 1]
        if self.counter:                                 # (paid fallback calls: the counters move, the run cap holds)
            u = json.loads(open(self.counter).read())
            n = self.paid_per if self.run_cap is None else max(0, min(self.paid_per, int(self.run_cap) - u.get("run", 0)))
            u["exa"] += n
            u["run"] = u.get("run", 0) + n
            open(self.counter, "w").write(json.dumps(u))
        page = "https://www.python.org/downloads/"
        ev = []
        if mode != "nosearch":
            ev += [{"strata_mcp": {"event": "call", "id": "c1", "name": "web_search", "arguments": {"query": "python"}, "round": 1}},
                   {"strata_mcp": {"event": "result", "id": "c1", "ok": True,
                                   "text": f"Search results for: python\n\n1. Download\n   {page}\n   snippet\n\n2. Docs\n   https://docs.python.org/3/"}}]
        if mode in ("good", "lost"):
            ev += [{"strata_mcp": {"event": "call", "id": "c2", "name": "fetch_page", "arguments": {"url": page}, "round": 2}},
                   {"strata_mcp": {"event": "result", "id": "c2", "ok": True, "text": f"URL: {page}\nTitle: Download\nPython 3.14.1"}}]
        cite = {"good": f"Python 3.14.1 ([python.org]({page})).", "snippet": "See https://docs.python.org/3/ .",
                "nosearch": "Python 3 is current.", "error": "x", "lost": f"See {page}"}[mode]
        ev += [{"choices": [{"delta": {"content": cite}}]}]
        if mode == "error":
            ev += [{"error": {"type": "server_error", "message": "the engine ended the request without an answer"}}]
        else:
            ev += [{"choices": [{"delta": {}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 900, "completion_tokens": 40}}]
        with open(self.slog, "a") as f:
            f.write("[strata] done: 40 tokens in 1 s (40.0 tok/s) (stop, cancel=False)\n")
            if mode == "lost":
                f.write(f"[strata] {LOST}; it is answered as an error\n")

        class Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        return Resp(("".join(f"data: {json.dumps(e)}\n\n" for e in ev) + "data: [DONE]\n").encode())


def selftest(base):
    import shutil
    global SETTLE_S
    SETTLE_S = 0.0
    root = os.path.realpath(SCRATCH)
    if not os.path.realpath(base).startswith(root + os.sep):
        print(f"selftest writes only under {root}")
        return 2
    shutil.rmtree(base, ignore_errors=True)
    os.makedirs(base)
    ok = True

    def chk(what, cond):
        nonlocal ok
        print(f"{'ok  ' if cond else 'FAIL'} {what}", flush=True)
        ok = ok and bool(cond)
    fields = dict(STANDARD, presence_penalty=0.0, frequency_penalty=0.0, repetition_penalty=1.0)
    modes = ("good", "snippet", "nosearch", "error", "lost")
    plan = {"fields": fields, "timeout_s": 60, "requests": [
        {"name": m, "messages": [{"role": "user", "content": f"search {m}"}], "seed": 7200001 + i, "max_tokens": 1024,
         "thinking": False} for i, m in enumerate(modes)]}
    slog, elog = f"{base}/server.log", f"{base}/engine.log"
    open(slog, "w").write("[strata] sampling defaults\n")
    open(elog, "w").write("strata generate: memory guard: mock\n")
    real = urllib.request.urlopen
    fake = Fake(slog, modes)
    try:
        urllib.request.urlopen = fake
        rc = run("http://127.0.0.1:1", f"{base}/out", plan, slog, elog, 0)
    finally:
        urllib.request.urlopen = real
    R = {r["name"]: r for r in (json.loads(x) for x in open(f"{base}/out/web.jsonl"))}
    chk(f"exit {rc} (some did not complete), 5 records", rc == 1 and len(R) == 5)
    chk("good: completed, 1 search + 1 fetch, the cited page is a fetched source (www / slash normalized)",
        R["good"]["completed"] and R["good"]["search_calls"] == 1 and R["good"]["fetch_calls"] == 1
        and R["good"]["cited_fetched"] == ["python.org/downloads"] and R["good"]["rounds"] == 2)
    chk("snippet: completed, cites a search result only: cited_tool yes, cited_fetched none",
        R["snippet"]["completed"] and R["snippet"]["cited_tool"] == ["docs.python.org/3"] and not R["snippet"]["cited_fetched"])
    chk("nosearch: completed without a search round", R["nosearch"]["completed"] and R["nosearch"]["search_calls"] == 0)
    chk("error chunk: not completed, the error recorded", not R["error"]["completed"] and "error chunk" in R["error"]["errors"][0])
    chk("lost line in the request's server-log slice: not completed, named", not R["lost"]["completed"]
        and "the lost-answer line" in R["lost"]["errors"])
    chk("every body: strata_web true, JSON, no Origin header, the standard sampling, thinking off, its seed",
        all(b["strata_web"] is True and all(b[k] == v for k, v in fields.items()) and b["chat_template_kwargs"] == {"enable_thinking": False}
            and rq.get_header("Origin") is None and rq.get_header("Content-type") == "application/json" for rq, b in fake.reqs)
        and [b["seed"] for _, b in fake.reqs] == [7200001 + i for i in range(5)])
    # the paid-call stop (fake counter modules; no key file anywhere)
    td = f"{base}/tools"
    os.makedirs(td)
    open(f"{td}/u.json", "w").write(json.dumps({"exa": 292, "tav": 365}))
    for m, k, f in (("exa_fallback", "exa", "searches"), ("tavily_fallback", "tav", "count")):
        open(f"{td}/{m}.py", "w").write(f"import json, os\ndef usage():\n    return {{'{f}': json.load(open(os.path.join("
                                        f"os.path.dirname(__file__), 'u.json')))['{k}']}}\n")
    open(f"{base}/paid-start.json", "w").write(json.dumps({"exa": {"calls": 292}, "tavily": {"calls": 365}}))
    p4 = dict(plan, requests=[dict(r, name=f"g{i}") for i, r in enumerate(plan["requests"][:1] * 4)])
    tot = {}
    for arm, cap in (("B", 5), ("P", 10)):     # one run id for both arms: B's server caps at 5, P's at 10 (the hard limit)
        fake = Fake(slog, ["good"] * 4, counter=f"{td}/u.json", paid_per=4, run_cap=cap)
        try:
            urllib.request.urlopen = fake
            rc = run("http://127.0.0.1:1", f"{base}/out-stop-{arm}", p4, slog, elog, 0, f"{base}/paid-start.json", td, 10, 5)
        finally:
            urllib.request.urlopen = real
        tot[arm] = (rc, len(fake.reqs), [json.loads(x) for x in open(f"{base}/out-stop-{arm}/web.jsonl")])
    (rb, nb, SB), (rp, np_, SP) = tot["B"], tot["P"]
    u = json.load(open(f"{td}/u.json"))
    chk(f"4 paid per request: B sends 2 (paid 4 + 1: its hard cap 5), its 3rd and 4th not run (the arm's soft share 5); P "
        f"sends 2 (4 + 1: the hard total 10), the rest not run; the hard cap holds the total at {u['run']} <= 10",
        nb == 2 and [x.get("paid_calls") for x in SB[:2]] == [4, 1] and all(x.get("not_run") for x in SB[2:])
        and "5 of the arm's 5" in SB[2]["why"] and np_ == 2 and [x.get("paid_calls") for x in SP[:2]] == [4, 1]
        and all(x.get("not_run") for x in SP[2:]) and "10 of 10 in all" in SP[2]["why"] and u["run"] <= 10
        and u["exa"] - 292 <= 10 and rb == 1 and rp == 1)
    open(f"{td}/u.json", "w").write(json.dumps({"exa": 292, "tav": 365}))
    fake = Fake(slog, ["good"] * 4, counter=f"{td}/u.json", paid_per=40, run_cap=10)
    try:
        urllib.request.urlopen = fake
        run("http://127.0.0.1:1", f"{base}/out-hard", p4, slog, elog, 0, f"{base}/paid-start.json", td, 10, 10)
    finally:
        urllib.request.urlopen = real
    chk(f"a request that would make 40 paid calls: the hard cap holds the run at {json.load(open(td + '/u.json'))['run']} <= 10",
        json.load(open(f"{td}/u.json"))["run"] == 10 and len(fake.reqs) == 1)
    # (review S1) the env gate: the hard cap must be in the server's own environment before anything is sent
    good_env = "PAID_SEARCH_KIND=test\0PAID_SEARCH_RUN=switch0213/x\0PAID_SEARCH_RUN_CAP=10\0PATH=/usr/bin\0"
    for name, env_text, want_sent in (("all three", good_env, True), ("no cap", good_env.replace("PAID_SEARCH_RUN_CAP=10\0", ""), False),
                                      ("chat kind", good_env.replace("=test", "=chat"), False),
                                      ("another run", good_env.replace("switch0213/x", "switch0213/y"), False)):
        open(f"{base}/environ", "w").write(env_text)
        fake = Fake(slog, ["good"] * 5)
        gf = f"{base}/penv-gates.txt"
        try:
            urllib.request.urlopen = fake
            rc = run("http://127.0.0.1:1", f"{base}/out-penv-{name.replace(' ', '_')}", plan, slog, elog, 0,
                     penv={"run": "switch0213/x", "cap": 10, "environ": f"{base}/environ", "gate": "penv_webP", "gates": gf})
        finally:
            urllib.request.urlopen = real
        R2 = [json.loads(x) for x in open(f"{base}/out-penv-{name.replace(' ', '_')}/web.jsonl")]
        g = open(gf).read().splitlines()[-1].split()[1]
        chk(f"env gate, {name}: {'sent, gate PASS' if want_sent else 'nothing sent, every request C4 NOT RUN (env), gate FAIL'}",
            (bool(fake.reqs) == want_sent) and (g == ("PASS" if want_sent else "FAIL"))
            and (want_sent or (rc == 2 and all(x["not_run"] and x["why"].startswith("C4 NOT RUN (env)") for x in R2))))
    fake = Fake(slog, ["good"] * 4)
    try:
        urllib.request.urlopen = fake
        rc = run("http://127.0.0.1:1", f"{base}/out-nocount", p4, slog, elog, 0, f"{base}/paid-start.json", f"{base}/no-tools", 10)
    finally:
        urllib.request.urlopen = real
    S = [json.loads(x) for x in open(f"{base}/out-nocount/web.jsonl")]
    chk(f"counters that cannot be read: nothing sent, all 4 not run (exit {rc})", rc == 2 and not fake.reqs and len(S) == 4
        and all(x["not_run"] for x in S))
    print("C4 WEB SELFTEST " + ("OK" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
