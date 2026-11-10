#!/usr/bin/env python3
"""ldr-client.py — set up an LDR account for Strata and run measured research tests against the local LDR web UI.

  setup [--user karl]                 create the account if needed (password kept in run/ldr-credentials, mode 600)
                                      and apply the per-account settings LDR 1.10.7 cannot take from the environment
  research TAG "question" [--mode quick|detailed] [--cancel-after S] [--effort-extract low|medium|off]
                          [--max-minutes M] [--watchdog-min W]
                                      run one research, measure it, save everything to results/TAG/ (a deep-profile
                                      run's own files — report.md, verification.json, evidence.jsonl, ... — are
                                      copied to results/TAG/deep/)
  analyze TAG                         recompute results/TAG/summary.json from the saved raw data

Measurements (all passive): the proxy's per-call log (logs/llm-calls.jsonl), Strata's GET /metrics?requests=all,
and Strata's engine log (chat cache: parked / restored / dropped lines, counted between the run's line offsets).
A MemAvailable guard terminates the research if it drops below 12 GB (the floor since 2026-10-19 evening; 16 / 20 before).
The stuck-run watchdog (11-03, Karl; on with --watchdog-min W or $WATCHDOG_MIN, which bench2.py sets, default 30 there):
no model call for W minutes (held time not counted, see Watchdog) -> the research is terminated, results/TAG/faulted.json
is written and the client exits with WATCHDOG_RC (86); bench2-queue.sh then stops LDR and requeues the question once.
Search trips (11-06, Karl: "A run whose end check passes counts as complete; log the trip and flag it in the results"):
the during-run search rule (research_common.search_health) no longer fails the run by itself - it is logged
(search-trip.json, marks.json "search_trip"), LDR is not sent a terminate for it, and the end check (search_health
final) decides: passed -> analysed as normal (summary.json) and flagged; failed -> search-failed.json, FAILED as before.
"""
import argparse
import json
import os
import re
import secrets
import stat
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests

WS = Path("/home/USER/ai/deep-research")
LDR = "http://127.0.0.1:5000"
STRATA = "http://127.0.0.1:8080"
CREDS = WS / "run" / "ldr-credentials"
SESSION = WS / "run" / "ldr-session.json"           # the session cookie (mode 600), reused across runs
CALL_LOG = WS / "logs" / "llm-calls.jsonl"
FETCH_GUARD_LOG = WS / "logs" / "fetch-guard.jsonl"   # 11-03: LDR patch 0006's events (fetch_guard.py)
sys.path.insert(0, str(WS / "tools"))
import research_common as rc  # noqa: E402  (10-21: search_health, the search-failure guard)
MODE_FILE = WS / "run" / "proxy-mode.json"
MIN_AVAIL_GB = 12.0   # the standing floor (2026-10-19 evening; 16 that morning, 20 before)
# the deep profile's efforts for the call types LDR cannot set itself (the proxy adds them; README "Thinking effort")
DEEP_EFFORTS = {"agent_effort": "xhigh", "extract_effort": "xhigh"}
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"

# Per-account settings (not settable through LDR_* in 1.10.7: the keys are not in LDR's defaults).
ACCOUNT_SETTINGS = {
    # streamed calls: Strata stops a request when LDR hangs up (cancel/timeout) and sends keep-alives during long
    # prompt reads; a non-streamed call keeps running on Strata after the client gave up (measured)
    "llm.streaming": (True, "checkbox"),
    # the openai client's timeout is per read (time between bytes). Streamed, the only silent phase is the wait in
    # Strata's queue (one request at a time): 1800 s covers a full 128K-token answer ahead in the queue.
    "llm.request_timeout": (1800, "number"),
    # a retry after a timeout re-sends the whole prompt; one is enough
    "llm.max_retries": (1, "number"),
    # explicit (it is 1.10.7's default too); not env-locked so the UI can still pick another strategy
    "search.search_strategy": ("langgraph-agent", None),
    # 2026-10-19: Semantic Scholar's engine (on as an agent tool only in the user's research, LDR_RESEARCH_S2=1 in
    # run-ldr.sh) without its LLM relevance filter (~10 parallel calls per search flooded Strata in September); the
    # key is not in LDR's defaults, so an LDR_* env value would be ignored - it lives in the account
    "search.engine.web.semantic_scholar.default_params.enable_llm_relevance_filter": (False, "checkbox"),
}
# SearXNG only: engines the langgraph agent would otherwise get as extra tools and that have no registered
# agent_enabled flag (the registered ones are env-locked off in run-ldr.sh)
for _e in ("gutenberg", "openlibrary", "pubchem", "stackexchange", "zenodo"):
    ACCOUNT_SETTINGS[f"search.engine.web.{_e}.agent_enabled"] = (False, "checkbox")


def engine_log_path() -> Path:
    """Strata's engine log for the running config (from the running server's --config)."""
    pid = None
    for line in os.popen("ss -H -ltnp '( sport = :8080 )'"):
        m = re.search(r"pid=(\d+)", line)
        if m:
            pid = m.group(1)
    if pid:
        cmd = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
        cwd = os.readlink(f"/proc/{pid}/cwd")
        if b"--config" in cmd:
            cfg = Path(cwd) / cmd[cmd.index(b"--config") + 1].decode()
            return Path(json.loads(cfg.read_text())["log"])
    raise SystemExit("cannot find Strata's engine log (is Strata on 8080?)")


def avail_gb() -> float:
    for line in open("/proc/meminfo"):
        if line.startswith("MemAvailable"):
            return int(line.split()[1]) / 1048576
    return 0.0


class Client:
    def __init__(self):
        self.s = requests.Session()
        self.csrf = None

    def _csrf(self):
        self.csrf = self.s.get(f"{LDR}/auth/csrf-token", timeout=10).json()["csrf_token"]
        return self.csrf

    def login(self, user, password, register=False):
        tok = self._csrf()
        if register:
            r = self.s.post(f"{LDR}/auth/register", data={"username": user, "password": password,
                            "confirm_password": password, "acknowledge": "true", "csrf_token": tok},
                            timeout=120, allow_redirects=False)
            if r.status_code not in (200, 302):
                raise SystemExit(f"register failed: HTTP {r.status_code} {r.text[:300]}")
            tok = self._csrf()
        waited = 0
        while True:
            r = self.s.post(f"{LDR}/auth/login", data={"username": user, "password": password, "csrf_token": tok},
                            timeout=120, allow_redirects=False)
            # LDR allows 5 logins per 15 min (the runner's and the UI's count too): wait it out instead of failing
            if r.status_code != 429 or waited >= 1200:
                break
            print(f"login: HTTP 429 (LDR's login rate limit) - retrying in 60 s ({waited // 60} min waited)", flush=True)
            time.sleep(60)
            waited += 60
            tok = self._csrf()
        if r.status_code != 302:
            raise SystemExit(f"login failed: HTTP {r.status_code} {r.text[:300]}")
        self._csrf()

    def resume(self) -> bool:
        """Reuse the session saved by an earlier run (valid while the same LDR process runs): no login needed."""
        try:
            self.s.cookies.update(json.loads(SESSION.read_text()))
            self._csrf()
            return self.s.get(f"{LDR}/settings/api", timeout=30, allow_redirects=False).status_code == 200
        except (OSError, ValueError, KeyError, requests.RequestException):
            return False

    def save(self) -> None:
        with os.fdopen(os.open(SESSION, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
            f.write(json.dumps(self.s.cookies.get_dict()))

    def api(self, method, path, **kw):
        h = kw.pop("headers", {})
        h["X-CSRFToken"] = self.csrf
        r = self.s.request(method, f"{LDR}{path}", headers=h, timeout=kw.pop("timeout", 60), **kw)
        return r


def creds():
    if CREDS.exists():
        d = json.loads(CREDS.read_text())
        return d["username"], d["password"], False
    return None


def cmd_setup(a):
    c = Client()
    have = creds()
    if have:
        user, pw, _ = have
        c.login(user, pw)
        print(f"logged in as {user} (credentials in {CREDS})")
    else:
        user, pw = a.user, secrets.token_urlsafe(18)
        CREDS.write_text(json.dumps({"username": user, "password": pw}))
        CREDS.chmod(stat.S_IRUSR | stat.S_IWUSR)
        c.login(user, pw, register=True)
        print(f"created account {user!r}; password in {CREDS} (mode 600) — change it in the UI if you like")
    for key, (value, ui) in ACCOUNT_SETTINGS.items():
        body = {"value": value}
        if ui:
            body["ui_element"] = ui
        r = c.api("PUT", f"/settings/api/{key}", json=body)
        print(f"  {key} = {value!r}: HTTP {r.status_code} {r.text[:120].strip()}")
    r = c.api("GET", "/settings/api")
    allv = r.json()
    allv = allv.get("settings", allv)
    for key in list(ACCOUNT_SETTINGS) + ["llm.provider", "llm.model", "llm.openai_endpoint.url", "llm.temperature",
                                         "llm.max_tokens", "llm.context_window_size", "llm.context_window_unrestricted",
                                         "llm.local_context_window_size", "langgraph_agent.max_subagent_workers",
                                         "search.tool", "search.engine.web.searxng.default_params.instance_url",
                                         "search.engine.web.searxng.default_params.result_format"]:
        v = allv.get(key)
        v = v.get("value") if isinstance(v, dict) else v
        print(f"  effective {key} = {v!r}")


def login_default() -> Client:
    have = creds()
    if not have:
        raise SystemExit("no account yet: run `tools/ldr-client.py setup` first")
    c = Client()
    if c.resume():
        return c
    c = Client()
    c.login(have[0], have[1])
    c.save()
    return c


def strata_requests():
    return requests.get(f"{STRATA}/metrics?requests=all", timeout=10).json()["requests"]


# -- the stuck-run watchdog (11-03, Karl) ------------------------------------------------------------------------------
# 11-03: shop-7e-deep-p7dx/s2 made its last model call at 18:47 (LDR's research thread spun on a fetched page, RSS 13 GB)
# and sat until this client's own limit (budget + 150 min) at 22:35. Karl: "stop a run with no model call for 30 minutes,
# mark it faulted, and requeue it once. If the same run hangs twice, stop and report instead of requeueing." The stop
# and faulted.json are here; the requeue and the second-hang stop are bench2-queue.sh's.
WATCHDOG_RC = 86                  # the exit code of a watchdog stop (bench2.py passes it on; bench2-queue.sh's WD_RC)
WATCHDOG_STOP_WAIT_S = 120        # after LDR's terminate: how long to wait for the research to show a final status
CLOCK_FILE = WS / "run" / "research-clock.json"     # strata-proxy's gate snapshot (every ~1 s): gate, reason, inflight, held
GATE_DOWN = "Strata is not answering"               # strata-proxy's Gate.DOWN reason
CLOCK_FRESH_S = 30.0              # an older snapshot = the proxy is not running: no call can be running or held
FINAL_STATES = ("completed", "failed", "error", "suspended", "cancelled", "terminated")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name) or default)
    except ValueError:
        return default


def _size(p: Path) -> int:
    try:
        return p.stat().st_size
    except OSError:
        return -1


class Watchdog:
    """Minutes since the run's last model call, held time not counted; fired() once they reach the limit.

    A model call is seen as: the proxy's record of a finished call (this run's capture file <capture_dir>/calls.jsonl
    grows; without a capture dir the proxy's call log), or a call running upstream or waiting at the gate right now (the
    gate snapshot's "inflight" / "held" > 0). Held time is not counted: the gate closed for a pause (the runner's memory
    relief restart, a Jan job's or your pause, the night pause), a test lock, or yielding to another client. The gate
    closed only because Strata is not answering, with no call waiting, IS counted: Strata's on-demand launcher stops it
    after 45 idle minutes, so a stuck run would look held forever (s2 11-03: strata=None in its samples from ~19:30)."""

    def __init__(self, limit_min: float, calls_file: Path, clock_file: Path | None = None, mono=None, wall=None):
        self.limit_s = float(limit_min) * 60
        self.calls_file = Path(calls_file)
        self.clock_file = Path(clock_file or CLOCK_FILE)
        self.mono = mono or time.monotonic       # the idle clock: CLOCK_MONOTONIC does not run while the PC is suspended
        self.wall = wall or time.time
        self.size = _size(self.calls_file)
        self.idle_s = 0.0                        # counted since the last call
        self.held_s = 0.0                        # not counted since the last call
        self.last_seen = self.wall()             # a call seen (finished, running or held); first the run's start
        self.last_call_end = None                # mtime of the calls file when it last grew (None = no call yet)
        self.state = "start"
        self._t = self.mono()

    def gate(self) -> dict | None:
        try:
            d = json.loads(self.clock_file.read_text())
            if isinstance(d, dict) and self.wall() - float(d.get("updated") or 0) <= CLOCK_FRESH_S:
                return d
        except (OSError, ValueError, TypeError):
            pass
        return None

    def _seen(self, state: str) -> None:
        self.idle_s, self.held_s, self.last_seen, self.state = 0.0, 0.0, self.wall(), state

    def observe(self) -> None:
        now = self.mono()
        dt = min(max(0.0, now - self._t), 120.0)        # one poll never counts more than 2 min (a stalled poll)
        self._t = now
        s = _size(self.calls_file)
        if s != self.size:
            self.size = s
            try:
                self.last_call_end = self.calls_file.stat().st_mtime
            except OSError:
                self.last_call_end = self.wall()
            return self._seen("call recorded")
        g = self.gate()
        if g and (int(g.get("inflight") or 0) > 0 or int(g.get("held") or 0) > 0):
            return self._seen("call running" if int(g.get("inflight") or 0) else f"call held ({g.get('reason')})")
        reason = str((g or {}).get("reason") or "")
        if g and g.get("gate") == "closed" and not reason.startswith(GATE_DOWN):
            self.held_s += dt
            self.state = f"held ({reason})"
            return
        self.idle_s += dt
        self.state = "idle" if g else "idle (no fresh gate snapshot: proxy down?)"

    def fired(self) -> bool:
        return self.limit_s > 0 and self.idle_s >= self.limit_s


def last_record(p: Path) -> dict | None:
    """id and t0 of the last line of a proxy call file, read from the end (a captured call's line can be MBs)."""
    try:
        with open(p, "rb") as f:
            f.seek(0, 2)
            end = pos = f.tell()
            buf = b""
            while pos > 0 and end - pos < (64 << 20):
                step = min(1 << 20, pos)
                pos -= step
                f.seek(pos)
                buf = f.read(step) + buf
                i = buf.rstrip(b"\n").rfind(b"\n")
                if i >= 0:
                    buf = buf[i + 1:]
                    break
        m = re.match(rb'\{"id": (\d+), "t0": ([\d.]+)', buf)
        return {"id": int(m.group(1)), "t0": float(m.group(2))} if m else None
    except OSError:
        return None


def proc_snapshot(pid: int, sample_s: float = 1.0) -> dict:
    """A process as faulted.json records it (from /proc): name, RSS, threads, the three busiest threads (CPU % over
    sample_s, total CPU seconds, state, wchan)."""
    base = Path(f"/proc/{pid}")
    out = {"pid": pid}
    try:
        out["comm"] = (base / "comm").read_text().strip()
        st = dict(l.split(":", 1) for l in (base / "status").read_text().splitlines() if ":" in l)
        out["rss_mb"] = int(st["VmRSS"].split()[0]) // 1024 if "VmRSS" in st else None
        out["threads"] = int(st.get("Threads", "0").strip() or 0)
    except (OSError, ValueError):
        out["error"] = "process not readable (gone?)"
        return out

    def ticks() -> dict:
        r = {}
        try:
            tasks = list((base / "task").iterdir())
        except OSError:
            return r
        for t in tasks:
            try:
                raw = (t / "stat").read_text()
                f = raw[raw.rindex(")") + 2:].split()
                r[t.name] = (raw[raw.index("(") + 1:raw.rindex(")")], f[0], int(f[11]) + int(f[12]))   # utime + stime
            except (OSError, ValueError, IndexError):
                pass
        return r

    hz = os.sysconf("SC_CLK_TCK")
    a, m0 = ticks(), time.monotonic()
    time.sleep(sample_s)
    b, el = ticks(), max(1e-3, time.monotonic() - m0)
    rows = [{"tid": int(tid), "name": name, "state": state, "cpu_s": round(tk / hz, 1),
             "cpu_pct": round(100 * (tk - a.get(tid, ("", "", tk))[2]) / hz / el)}
            for tid, (name, state, tk) in b.items()]
    rows.sort(key=lambda r: (r["cpu_pct"], r["cpu_s"]), reverse=True)
    for r in rows[:3]:
        try:
            r["wchan"] = (base / "task" / str(r["tid"]) / "wchan").read_text().strip() or "0"
        except OSError:
            pass
    out["top_threads"] = rows[:3]
    return out


def _iso(t: float | None) -> str | None:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t)) if t else None


def search_trip(trip: dict, final: dict, t0: float) -> dict:
    """11-06: the record of a during-run search trip whose run passed the end check - when, the rule's counts, the
    outage (the empty searches in a row up to the trip, until the first search with results after it)."""
    ev = rc.search_events(t0)
    before = [e for e in ev if e.get("t", 0) <= trip["t_abs"]]
    run = []
    for e in reversed(before):
        if e.get("n"):
            break
        run.append(e)
    run.reverse()
    back = next((e["t"] for e in ev if e.get("t", 0) > trip["t_abs"] and e.get("n")), None)
    errs = [e.get("err") or "no results" for e in run]
    return {"at": _iso(trip["t_abs"]), "t_s": round(trip["t_abs"] - t0, 1), "rule": trip["reason"],
            "tried": trip["tried"], "failed": trip["failed"], "empty_in_a_row": len(run),
            "outage_from": _iso(run[0]["t"]) if run else None, "searches_back_at": _iso(back),
            "outage_s": round(back - run[0]["t"], 1) if run and back else None,
            "errors": {x: errs.count(x) for x in sorted(set(errs))},
            "end_check": {k: final.get(k) for k in ("tried", "failed", "error", "bad", "reason")},
            "terminate_sent": False, "flag": "search trip, end check passed"}


def watchdog_stop(a, c, rid, wd: Watchdog, st: dict, t0: float, marks: dict) -> dict:
    """The watchdog fired: LDR's process as it is now (before the terminate), then the research terminated through
    LDR's API. bench2-queue.sh stops this LDR right after (run-ldr.sh stop), so a thread that ignores the terminate goes
    too. Returns faulted.json's record."""
    now = time.time()
    print(f"[{a.tag}] WATCHDOG: no model call for {wd.idle_s / 60:.0f} min (held time not counted; limit "
          f"{a.watchdog_min:g} min) - terminating", flush=True)
    try:
        ldr = proc_snapshot(int((WS / "run" / "ldr.pid").read_text().strip()))
    except (OSError, ValueError):
        ldr = {"pid": None, "error": "run/ldr.pid unreadable"}
    last = last_record(wd.calls_file)
    rec = {"reason": f"watchdog: no model call for {wd.idle_s / 60:.1f} min (held time not counted)",
           "watchdog_min": a.watchdog_min, "tag": a.tag, "research_id": rid, "rc": WATCHDOG_RC,
           "fired_at": _iso(now), "run_start": _iso(t0), "wall_min": round((now - t0) / 60, 1),
           "last_call_end": _iso(wd.last_call_end), "last_call": last and {**last, "t0_iso": _iso(last["t0"])},
           "idle_min": round(wd.idle_s / 60, 1), "held_min_not_counted": round(wd.held_s / 60, 1),
           "wall_min_since_last_call": round((now - wd.last_seen) / 60, 1), "calls_file": str(wd.calls_file),
           "proxy_calls_since_start": line_count(CALL_LOG) - marks["call_log_line0"],
           "gate": wd.gate(), "ldr_status": {"status": st.get("status"), "progress": st.get("progress")}, "ldr": ldr}
    try:
        rr = c.api("POST", f"/api/terminate/{rid}")
        rec["terminate"] = {"http": rr.status_code, "text": rr.text[:200]}
    except requests.RequestException as e:
        rec["terminate"] = {"error": f"{type(e).__name__}: {e}"[:200]}
    status, t1 = None, time.time()
    while time.time() - t1 < WATCHDOG_STOP_WAIT_S:
        time.sleep(3)
        try:
            status = c.api("GET", f"/api/research/{rid}/status").json().get("status")
        except (requests.RequestException, ValueError, AttributeError):
            status = None
        if status in FINAL_STATES:
            break
    rec.update(ldr_status_after=status, stopped_by_api=status in FINAL_STATES, waited_s=round(time.time() - t1, 1))
    print(f"[{a.tag}] terminate: {rec['terminate']}; LDR status after {rec['waited_s']:.0f} s: {status}", flush=True)
    return rec


def watchdog_finish(a, out: Path, c, rid, marks: dict, samples: list, fault: dict, t_end: float, min_avail: float) -> None:
    """faulted.json first, then what a post-mortem needs (marks, the poll samples, LDR's research record and logs). No
    analysis: no summary.json, so bench2.py writes bench-fail.json for this run."""
    MODE_FILE.unlink(missing_ok=True)            # the capture stops: nothing more lands in this run's folder
    (out / "faulted.json").write_text(json.dumps(fault, indent=1, ensure_ascii=False))
    marks.update(t_end=t_end, final_status=fault.get("ldr_status_after"), faulted=True, min_avail_gb=round(min_avail, 1),
                 call_log_line1=line_count(CALL_LOG))
    (out / "marks.json").write_text(json.dumps(marks, indent=1))
    (out / "samples.json").write_text(json.dumps(samples))
    for name, path in (("research.json", f"/api/research/{rid}"), ("research-logs.json", f"/api/research/{rid}/logs")):
        try:
            (out / name).write_text(c.api("GET", path, timeout=30).text)
        except requests.RequestException as e:
            fault.setdefault("save_errors", []).append(f"{name}: {type(e).__name__}")
    if fault.get("save_errors"):
        (out / "faulted.json").write_text(json.dumps(fault, indent=1, ensure_ascii=False))
    print(f"[{a.tag}] FAULTED ({fault['reason']}): {out / 'faulted.json'}; exit {WATCHDOG_RC}", flush=True)


def line_count(p: Path) -> int:
    try:
        with open(p, "rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def cmd_research(a):
    out = WS / "results" / a.tag
    out.mkdir(parents=True, exist_ok=True)
    elog = engine_log_path()
    profile = (WS / "run" / "ldr.profile").read_text().strip() if (WS / "run" / "ldr.profile").exists() else "?"
    sx = 8889                                   # both profiles search the main instance since 2026-10-17 (run-ldr.sh)
    try:                                        # ... unless LDR runs with another instance URL
        env = Path(f"/proc/{(WS / 'run' / 'ldr.pid').read_text().strip()}/environ").read_bytes().split(b"\0")
        url = next((e.split(b"=", 1)[1].decode() for e in env
                    if e.startswith(b"LDR_SEARCH_ENGINE_WEB_SEARXNG_DEFAULT_PARAMS_INSTANCE_URL=")), "")
        sx = int(url.rsplit(":", 1)[1]) if url else sx
    except (OSError, ValueError, IndexError):
        pass
    try:
        requests.get(f"http://127.0.0.1:{sx}/healthz", timeout=20).raise_for_status()
    except requests.RequestException as e:
        raise SystemExit(f"LDR's SearXNG (127.0.0.1:{sx}) does not answer: {e}")
    if not a.max_minutes:
        # deep runs: the research budget plus room for the report and citation check; baseline as before
        budget = (a.budget_s or int(os.environ.get("LDR_DEEP_TIME_BUDGET_S", "10800"))) / 60
        a.max_minutes = budget + 150 if profile == "deep" else 90
    if profile == "deep" and (a.budget_s or a.files):
        # this research's own settings for the deep patch (as the research runner passes them; deep/control.py)
        (WS / "run" / "next-research.json").write_text(json.dumps(
            {"job_id": a.tag, "question": a.question, "budget_s": a.budget_s or None,
             "files": [f for f in (a.files or "").split(",") if f], "seed_dirs": [], "written": time.time()}))
    live = requests.get(f"{STRATA}/metrics", timeout=10).json()["live"]
    if live["state"] != "idle" or live["queued"]:
        print(f"warning: Strata is busy ({live}) — someone else is using it; results will be mixed", flush=True)
    # proxy mode for this run. 2026-10-17: Strata's own default became medium, so the deep settings (agent and
    # extraction at xhigh, which they got from the server default until then) are sent explicitly now.
    mode = dict(DEEP_EFFORTS) if profile == "deep" else {}
    if a.effort_extract:
        mode["extract_effort"] = a.effort_extract
    if a.effort_agent:
        mode["agent_effort"] = a.effort_agent
    for k, v in (("report_effort", a.effort_report), ("verify_effort", a.effort_verify)):
        if v:
            mode[k] = v
    if a.capture_dir:
        mode["capture_dir"] = a.capture_dir          # every call's input and output (strata-proxy capture mode)
    if mode:
        MODE_FILE.write_text(json.dumps(mode))
    else:
        MODE_FILE.unlink(missing_ok=True)
    c = login_default()
    marks = {"engine_log": str(elog), "engine_log_line0": line_count(elog), "call_log_line0": line_count(CALL_LOG),
             "effort_extract": a.effort_extract, "proxy_mode": mode, "question": a.question, "mode": a.mode, "profile": profile,
             "workers": os.environ.get("LDR_WORKERS")}
    body = {"query": a.question, "mode": a.mode}
    wd = None
    if a.watchdog_min > 0:      # 11-03: started before the research, so its first call is this run's
        wd = Watchdog(a.watchdog_min, Path(a.capture_dir) / "calls.jsonl" if a.capture_dir else CALL_LOG)
        marks["watchdog"] = {"min": a.watchdog_min, "calls_file": str(wd.calls_file)}
    fault = None
    t0 = time.time()
    r = c.api("POST", "/api/start_research", json=body, timeout=120)
    if r.status_code != 200:
        raise SystemExit(f"start failed: HTTP {r.status_code} {r.text[:500]}")
    rid = r.json().get("research_id")
    marks.update(research_id=rid, t_start=t0)
    print(f"[{a.tag}] research {rid} started", flush=True)
    samples, status, cancel_at, mem_abort, poll_fail, search_abort = [], None, None, False, 0, None
    min_avail = avail_gb()
    last_print = 0
    while True:
        time.sleep(3)
        now = time.time()
        av = avail_gb()
        min_avail = min(min_avail, av)
        try:
            st = c.api("GET", f"/api/research/{rid}/status").json()
            poll_fail = 0
        except (requests.RequestException, ValueError) as e:
            st = {"status": f"poll-error {e}"}
            poll_fail += 1
            if poll_fail >= 100:                       # ~5 min: LDR is gone (2026-10-18: ldr-web crashed mid-run)
                raise SystemExit(f"[{a.tag}] LDR unreachable for {poll_fail * 3} s: giving up (the queue retries)")
        try:
            lv = requests.get(f"{STRATA}/metrics", timeout=5).json()["live"]
        except (requests.RequestException, ValueError):
            lv = {}
        samples.append({"t": round(now - t0, 1), "status": st.get("status"), "progress": st.get("progress"),
                        "strata": lv.get("state"), "queued": lv.get("queued"), "avail_gb": round(av, 1)})
        if av < MIN_AVAIL_GB and not mem_abort:
            print(f"[{a.tag}] MemAvailable {av:.1f} GB < {MIN_AVAIL_GB} — terminating", flush=True)
            c.api("POST", f"/api/terminate/{rid}")
            mem_abort = True
        # 10-21 (the user): searches mostly failing -> stop; the run is FAILED, not analysed (no report from the
        # model's own knowledge counts as a measurement)
        if search_abort is None:
            h = rc.search_health(t0)
            if h["bad"]:
                # 11-06 (Karl): a trip, not a failure yet - the end check decides. No terminate: LDR's terminate never
                # stopped a deep run (p4s9 o03 11-05 ran on to "completed" after it), and if it did, it would cut short a
                # run the end check may pass
                search_abort = {**h, "t_abs": time.time()}    # (after the check: the searches it counted are before it)
                print(f"[{a.tag}] SEARCH TRIP: {h['reason']} - not terminated; the end check decides (11-06)", flush=True)
        if a.cancel_after and cancel_at is None and now - t0 >= a.cancel_after:
            cancel_at = now
            rr = c.api("POST", f"/api/terminate/{rid}")
            print(f"[{a.tag}] terminate sent at {now - t0:.0f} s: HTTP {rr.status_code} {rr.text[:150]}", flush=True)
        if now - last_print > 60:
            last_print = now
            print(f"[{a.tag}] {now - t0:6.0f} s  {st.get('status')}  {st.get('progress')}%  strata={lv.get('state')}"
                  f"  mem={av:.1f} GB  calls={line_count(CALL_LOG) - marks['call_log_line0']}"
                  + (f"  idle={wd.idle_s / 60:.0f}/{a.watchdog_min:g} min" if wd else ""), flush=True)
        status = st.get("status")
        if status in ("completed", "failed", "error", "suspended", "cancelled", "terminated"):
            break
        if wd is not None:      # 11-03: no model call for --watchdog-min minutes (held time not counted) -> faulted
            wd.observe()
            if wd.fired():
                fault = watchdog_stop(a, c, rid, wd, st, t0, marks)
                break
        if a.max_minutes and now - t0 > a.max_minutes * 60:
            print(f"[{a.tag}] over {a.max_minutes} min — terminating", flush=True)
            c.api("POST", f"/api/terminate/{rid}")
            a.max_minutes = 0
    t_end = time.time()
    if fault is not None:       # 11-03: faulted.json + the post-mortem files, then the watchdog's own exit code
        watchdog_finish(a, out, c, rid, marks, samples, fault, t_end, min_avail)
        sys.exit(WATCHDOG_RC)
    # after a cancel: how long until Strata is idle
    idle_after = None
    if cancel_at:
        for _ in range(600):
            lv = requests.get(f"{STRATA}/metrics", timeout=5).json()["live"]
            if lv["state"] == "idle" and not lv["queued"]:
                idle_after = round(time.time() - cancel_at, 1)
                break
            time.sleep(0.5)
    time.sleep(2)   # let the last proxy line land
    marks.update(t_end=t_end, final_status=status, cancel_at=cancel_at, strata_idle_after_cancel_s=idle_after,
                 min_avail_gb=round(min_avail, 1), mem_abort=mem_abort,
                 engine_log_line1=line_count(elog), call_log_line1=line_count(CALL_LOG))
    rep = c.api("GET", f"/api/report/{rid}")
    report = rep.json() if rep.status_code == 200 else {"http": rep.status_code, "text": rep.text[:2000]}
    (out / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    if isinstance(report, dict) and report.get("content"):
        (out / "report.md").write_text(report["content"])
    det = c.api("GET", f"/api/research/{rid}")
    (out / "research.json").write_text(det.text)
    logs = c.api("GET", f"/api/research/{rid}/logs")
    (out / "research-logs.json").write_text(logs.text)
    (out / "samples.json").write_text(json.dumps(samples))
    # raw slices
    with open(CALL_LOG, encoding="utf-8") as f:
        calls = [json.loads(l) for i, l in enumerate(f) if marks["call_log_line0"] <= i < marks["call_log_line1"]]
    (out / "calls.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in calls))
    with open(elog, encoding="utf-8", errors="replace") as f:
        elines = [l for i, l in enumerate(f) if marks["engine_log_line0"] <= i < marks["engine_log_line1"]]
    (out / "engine-log.txt").write_text("".join(elines))
    reqs = [x for x in strata_requests() if t0 - 5 <= x["time"] <= t_end + 5]
    (out / "strata-requests.json").write_text(json.dumps(sorted(reqs, key=lambda x: x["time"])))
    (out / "marks.json").write_text(json.dumps(marks, indent=1))
    MODE_FILE.unlink(missing_ok=True)
    deep_dir = WS / "results" / "deep-runs" / f"research-{rid}"
    if deep_dir.is_dir():
        import shutil
        shutil.copytree(deep_dir, out / "deep", dirs_exist_ok=True)
    h = rc.search_health(t0, final=True)
    marks["search_health"] = h
    if search_abort and not h["bad"]:       # 11-06 (Karl): tripped, end check passed -> complete, logged + flagged
        marks["search_trip"] = search_trip(search_abort, h, t0)
        (out / "search-trip.json").write_text(json.dumps(marks["search_trip"], indent=1))
        print(f"[{a.tag}] search trip at {marks['search_trip']['at']} ({search_abort['reason']}); end check passed "
              f"({h['reason']}): analysed as complete, flagged", flush=True)
    (out / "marks.json").write_text(json.dumps(marks, indent=1))
    if h["bad"]:                            # the end check failed: FAILED as before (with the trip, if any)
        why = f"FAILED: {(search_abort or h)['reason']}"
        (out / "search-failed.json").write_text(json.dumps({"why": why, "during_run": search_abort, "final": h}, indent=1))
        raise SystemExit(f"[{a.tag}] {why} - not analysed (no summary.json; the queue retries after its service check)")
    s = analyze(out, check_urls=not a.no_url_check)
    print(json.dumps(s, indent=1))


def check_citations(report_md: str):
    """[N] markers in the text vs. the sources list, and whether each source URL loads."""
    body, _, sources = report_md.partition("## Sources")
    if not sources:
        m = re.search(r"\n#+\s*(Sources|References)\b", report_md)
        body, sources = (report_md[:m.start()], report_md[m.start():]) if m else (report_md, "")
    cited = sorted({int(n) for n in re.findall(r"\[(\d{1,3})\]", body)})
    listed, last = {}, None
    for line in sources.splitlines():
        m = re.match(r"\s*\[(\d{1,3})\]", line)
        urls = re.findall(r"https?://[^\s)\]>\"']+", line)
        if m and urls:
            listed[int(m.group(1))] = urls[0].rstrip(".,;")
        elif m:
            last = int(m.group(1))                   # LDR: "[n] title" with "   URL: ..." on the next line
        elif urls and last is not None and last not in listed:
            listed[last] = urls[0].rstrip(".,;")
        elif urls:
            listed.setdefault(len(listed) + 1000, urls[0].rstrip(".,;"))
    # also linked citations inside the text, e.g. [[1]](url)
    inline_urls = set(re.findall(r"\]\((https?://[^\s)]+)\)", body))
    return cited, listed, inline_urls


def linked_numbers(report_md: str):
    """citation numbers that carry their own link in the text, e.g. [[6]](https://...)"""
    return {int(n) for n in re.findall(r"\[\[(\d{1,3})\]\]\(https?://", report_md)}


def url_ok(u: str):
    try:
        r = requests.get(u, headers={"User-Agent": UA}, timeout=20, allow_redirects=True, stream=True)
        code = r.status_code
        r.close()
        return code
    except requests.RequestException as e:
        return type(e).__name__


def fetch_guard_stats(t0: float, t1: float, max_events: int = 50) -> dict:
    """11-03 (LDR patch 0006): the fetch guard's events between t0 and t1 - pages skipped (over the size/tag cap),
    pages whose extraction passed the watchdog time, and the largest / slowest page parsed."""
    out = {"skipped": 0, "slow": 0, "pages": 0, "largest_mb": None, "max_tags": None, "slowest_s": None,
           "events": []}
    try:
        f = open(FETCH_GUARD_LOG, encoding="utf-8")
    except OSError:
        out["log"] = "missing (patch 0006 not installed?)"
        return out
    with f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if not (t0 <= (r.get("t") or 0) <= t1):
                continue
            kind = r.get("kind")
            if kind in ("page", "slow_done"):
                out["pages"] += 1
                if r.get("bytes") is not None:
                    out["largest_mb"] = max(out["largest_mb"] or 0, round(r["bytes"] / 1048576, 2))
                if r.get("tags") is not None:
                    out["max_tags"] = max(out["max_tags"] or 0, r["tags"])
                if r.get("s") is not None:
                    out["slowest_s"] = max(out["slowest_s"] or 0, r["s"])
            if kind in ("skipped", "slow"):
                out[kind] += 1
            if kind in ("skipped", "slow", "slow_done") and len(out["events"]) < max_events:
                out["events"].append({k: r.get(k) for k in ("kind", "url", "reason", "bytes", "tags", "s")})
    return out


def analyze(out: Path, check_urls=True):
    marks = json.loads((out / "marks.json").read_text())
    calls = [json.loads(l) for l in (out / "calls.jsonl").read_text().splitlines() if l.strip()]
    calls = [x for x in calls if x.get("path", "").endswith("/chat/completions")]
    elog = (out / "engine-log.txt").read_text()
    sreq = json.loads((out / "strata-requests.json").read_text())
    by_cls = {}
    for x in calls:
        u = x.get("usage") or {}
        d = by_cls.setdefault(x.get("cls"), {"calls": 0, "prompt_tokens": 0, "cached_tokens": 0, "completion_tokens": 0,
                                             "seconds": 0.0, "reasoning_chars": 0, "content_chars": 0})
        d["calls"] += 1
        d["prompt_tokens"] += u.get("prompt_tokens") or 0
        d["cached_tokens"] += (u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        d["completion_tokens"] += u.get("completion_tokens") or 0
        d["seconds"] += x.get("duration_s") or 0
        d["reasoning_chars"] += x.get("reasoning_chars") or 0
        d["content_chars"] += x.get("content_chars") or 0
    for d in by_cls.values():
        d["seconds"] = round(d["seconds"], 1)
    pt = sum(d["prompt_tokens"] for d in by_cls.values())
    ct = sum(d["cached_tokens"] for d in by_cls.values())
    # re-reads: a call of an agent conversation that did not reuse its own previous prompt
    convs, rereads = {}, []
    for x in calls:
        u = x.get("usage") or {}
        p, cached = u.get("prompt_tokens") or 0, (u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        prev = convs.get(x.get("conv"))
        if prev is not None and x.get("cls") == "agent" and p > prev and cached < prev * 0.9:
            rereads.append({"id": x["id"], "conv": x["conv"], "prompt": p, "cached": cached, "prev_prompt": prev})
        convs[x.get("conv")] = p + (u.get("completion_tokens") or 0)
    conv_calls = {}
    for x in calls:
        if x.get("cls") == "agent":
            conv_calls[x["conv"]] = conv_calls.get(x["conv"], 0) + 1
    lead = next((x["conv"] for x in calls if x.get("cls") == "agent"), None)   # the lead makes the first agent call
    lead_calls = [x for x in calls if x.get("conv") == lead]
    lead_rereads = [r for r in rereads if r["conv"] == lead]
    errors = [{"id": x["id"], "status": x.get("status"), "err": x.get("error") or x.get("stream_error"),
               "finish": x.get("finish")} for x in calls
              if (x.get("status") not in (200, None)) or x.get("error") or x.get("stream_error")
              or x.get("finish") in ("length", None)]
    report_md = (out / "report.md").read_text() if (out / "report.md").exists() else ""
    s = {
        "tag": out.name, "question": marks["question"], "research_id": marks.get("research_id"),
        "final_status": marks.get("final_status"), "effort_extract": marks.get("effort_extract"),
        "wall_s": round(marks["t_end"] - marks["t_start"], 1),
        "llm_calls": len(calls), "llm_calls_by_class": by_cls,
        "prompt_tokens": pt, "cached_prompt_tokens": ct, "reread_prompt_tokens": pt - ct,
        "generated_tokens": sum(d["completion_tokens"] for d in by_cls.values()),
        "largest_prompt": max(((x.get("usage") or {}).get("prompt_tokens") or 0 for x in calls), default=0),
        "largest_context": max((((x.get("usage") or {}).get("prompt_tokens") or 0) +
                                ((x.get("usage") or {}).get("completion_tokens") or 0) for x in calls), default=0),
        "llm_seconds": round(sum(x.get("duration_s") or 0 for x in calls), 1),
        "agent_conversations": len(conv_calls), "lead_conv": lead, "lead_calls": len(lead_calls),
        "lead_rereads": len(lead_rereads), "lead_reread_tokens": sum(r["prompt"] - r["cached"] for r in lead_rereads),
        "agent_rereads": len(rereads), "agent_reread_tokens": sum(r["prompt"] - r["cached"] for r in rereads),
        "chat_cache": {"parked": len(re.findall(r"chat cache: parked", elog)),
                       "restored": len(re.findall(r"chat cache: restored", elog)),
                       "dropped": len(re.findall(r"chat cache: dropped", elog))},
        "strata_requests": len(sreq),
        "strata_prompt_s": round(sum((x.get("prompt_ms") or 0) for x in sreq) / 1000, 1),
        "strata_decode_s": round(sum((x.get("decode_ms") or 0) for x in sreq) / 1000, 1),
        "strata_finish": {f: sum(1 for x in sreq if x.get("finish") == f) for f in {x.get("finish") for x in sreq}},
        "errors": errors, "min_avail_gb": marks.get("min_avail_gb"),
        "cancel": {"at_s": round(marks["cancel_at"] - marks["t_start"], 1) if marks.get("cancel_at") else None,
                   "strata_idle_after_s": marks.get("strata_idle_after_cancel_s"),
                   "ldr_status_after": marks.get("final_status")} if marks.get("cancel_at") else None,
        "report_chars": len(report_md),
        "profile": marks.get("profile"),
        "workers": marks.get("workers"),
    }
    # how busy Strata was (union of this run's call intervals) and the throughput: what extra workers could change
    iv = sorted((max(x["t0"], marks["t_start"]), min(x.get("t_end") or x["t0"], marks["t_end"])) for x in calls
                if x.get("t_end"))
    busy, cur = 0.0, None
    for a_, b_ in iv:
        if cur is None or a_ > cur[1]:
            if cur:
                busy += cur[1] - cur[0]
            cur = [a_, b_]
        else:
            cur[1] = max(cur[1], b_)
    if cur:
        busy += cur[1] - cur[0]
    wall = marks["t_end"] - marks["t_start"]
    s["strata_busy_share"] = round(busy / wall, 3) if wall else None
    s["generated_tokens_per_wall_s"] = round(s["generated_tokens"] / wall, 1) if wall else None
    # 11-03 (Karl): pages the fetch guard skipped or flagged slow are counted in every run's summary
    s["fetch_guard"] = fetch_guard_stats(marks["t_start"], marks["t_end"])
    deep_stats = out / "deep" / "stats.json"
    if deep_stats.exists():
        d = json.loads(deep_stats.read_text())
        d.pop("calls", None)
        s["deep"] = d
        # 10-27 (Karl): a quiet effort drop by deep.llm's retry ladder is visible in every measurement's summary
        s["effort_drops"] = (d.get("effort_drops") or {}).get("count", 0)
    if report_md:
        cited, listed, inline = check_citations(report_md)
        urls = sorted(set(listed.values()) | inline)
        s["citations"] = {"cited_numbers": len(cited), "sources_listed": len(listed),
                          "cited_but_not_listed": [n for n in cited if n not in listed
                                                   and n not in linked_numbers(report_md)],
                          "listed_urls": len(urls)}
        if check_urls and urls:
            res = {}
            threads = []
            def chk(u):
                res[u] = url_ok(u)
            for u in urls:
                t = threading.Thread(target=chk, args=(u,))
                t.start()
                threads.append(t)
            for t in threads:
                t.join()
            ok = [u for u, c in res.items() if isinstance(c, int) and c < 400]
            s["citations"]["urls_resolving"] = len(ok)
            s["citations"]["urls_failing"] = {u: c for u, c in res.items() if u not in ok}
    (out / "summary.json").write_text(json.dumps(s, indent=1, ensure_ascii=False))
    return s


def main():
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)
    q = sp.add_parser("setup")
    q.add_argument("--user", default="karl")
    q = sp.add_parser("research")
    q.add_argument("tag")
    q.add_argument("question")
    q.add_argument("--mode", default="quick")
    q.add_argument("--cancel-after", type=float, default=0)
    q.add_argument("--effort-extract", choices=["low", "medium", "xhigh", "off"], default=None)
    q.add_argument("--effort-agent", choices=["low", "medium", "xhigh"], default=None)
    q.add_argument("--effort-report", choices=["low", "medium", "xhigh"], default=None,
                   help="note: the deep patch sets report/verify effort itself; the proxy only fills it where none is sent")
    q.add_argument("--effort-verify", choices=["low", "medium", "xhigh"], default=None)
    q.add_argument("--budget-s", type=int, default=0, help="deep: this research's time budget (next-research.json)")
    q.add_argument("--files", default="", help="deep: comma-separated files for read_file")
    q.add_argument("--capture-dir", default="", help="strata-proxy capture mode: every call's input/output")
    q.add_argument("--max-minutes", type=float, default=0, help="0 = by profile (baseline 90, deep budget + 150)")
    q.add_argument("--watchdog-min", type=float, default=_env_float("WATCHDOG_MIN", 0.0),
                   help="11-03: no model call for this many minutes (held time not counted) -> terminate, faulted.json, "
                        f"exit {WATCHDOG_RC}; 0 = off (default $WATCHDOG_MIN, else off; bench2.py passes 30)")
    q.add_argument("--no-url-check", action="store_true")
    q = sp.add_parser("analyze")
    q.add_argument("tag")
    q.add_argument("--no-url-check", action="store_true")
    a = p.parse_args()
    if a.cmd == "setup":
        cmd_setup(a)
    elif a.cmd == "research":
        cmd_research(a)
    else:
        print(json.dumps(analyze(WS / "results" / a.tag, check_urls=not a.no_url_check), indent=1))


if __name__ == "__main__":
    main()
