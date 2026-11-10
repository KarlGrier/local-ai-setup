"""Integration: the staged ldr-client.py `research` command end to end on a fake clock - a fake LDR API, a fake proxy
(capture file, call log and gate snapshot in scratch, written the way strata-proxy writes them), fake Strata /metrics.
No network, no LDR, nothing under the live run/ or results/ is touched (WS points into scratch)."""
import contextlib
import io
import json
import os
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _load import FakeLDR, FakeRequests, FakeTime, drop, load, run_tests, scratch  # noqa: E402

TEST_REASON = "a test holds the GPUs (gpu-test.lock)"


class Env:
    """A fresh copy of the staged client wired to scratch + fakes. schedule(minute) -> the proxy's state that minute:
    {"calls": bool, "gate": "open"/"closed", "reason", "inflight", "held", "strata_up", "complete": bool}."""

    def __init__(self, schedule, obeys=True):
        self.d = scratch("wd-loop-")
        ws = self.ws = self.d / "ws"
        for sub in ("run", "logs", "results"):
            (ws / sub).mkdir(parents=True)
        (ws / "run" / "ldr.profile").write_text("deep\n")
        (ws / "run" / "ldr.pid").write_text(str(os.getpid()))      # proc_snapshot reads this test's own process
        (ws / "logs" / "engine.log").write_text("engine start\n")
        m = self.m = load(f"ldr_client_loop_{id(self)}", "ldr-client.py")
        self.ft, self.fr, self.ldr = FakeTime(), FakeRequests(), FakeLDR(obeys=obeys)
        m.time, m.requests = self.ft, self.fr
        m.WS = ws
        m.CALL_LOG = ws / "logs" / "llm-calls.jsonl"
        m.MODE_FILE = ws / "run" / "proxy-mode.json"
        m.CLOCK_FILE = ws / "run" / "research-clock.json"
        m.CREDS, m.SESSION = ws / "run" / "ldr-credentials", ws / "run" / "ldr-session.json"
        m.engine_log_path = lambda: ws / "logs" / "engine.log"
        m.login_default = lambda: self.ldr
        m.avail_gb = lambda: 50.0
        m.rc = types.SimpleNamespace(search_health=lambda since, pid=None, final=False:
                                     {"tried": 12, "failed": 0, "error": None, "bad": False, "reason": "0 of 12 failed"})
        self.cap = ws / "results" / "run-capture"
        self.schedule, self.t_start, self.n, self.last_call_min = schedule, self.ft.t, 0, -9
        self.fired_min = None
        self.ft.hooks.append(self.proxy)

    def minute(self):
        return (self.ft.t - self.t_start) / 60

    def proxy(self, ft):
        mnt = self.minute()
        st = self.schedule(mnt)
        if st.get("calls") and mnt - self.last_call_min >= 1:
            self.last_call_min = mnt
            self.n += 1
            rec = {"id": self.n, "t0": round(ft.t - 4, 3), "method": "POST", "path": "/v1/chat/completions",
                   "cls": "agent", "conv": "c1", "status": 200, "finish": "stop", "t_end": round(ft.t, 3),
                   "duration_s": 4.0, "usage": {"prompt_tokens": 1000, "completion_tokens": 100,
                                                "prompt_tokens_details": {"cached_tokens": 900}}}
            with open(self.m.CALL_LOG, "a") as f:
                f.write(json.dumps(rec) + "\n")
            try:                                     # the capture, as strata-proxy: only while the mode file asks
                cap = json.loads(self.m.MODE_FILE.read_text()).get("capture_dir")
            except (OSError, ValueError):
                cap = None
            if cap:
                os.makedirs(cap, exist_ok=True)
                with open(os.path.join(cap, "calls.jsonl"), "a") as f:
                    f.write(json.dumps({"id": self.n, "t0": rec["t0"], "cls": "agent", "messages": [], "content": "x"}) + "\n")
        g = {"paused_total_s": 0, "gate": st.get("gate", "open"), "reason": st.get("reason"),
             "inflight": st.get("inflight", 0), "held": st.get("held", 0), "updated": round(ft.t, 3),
             "strata_up": st.get("strata_up", True)}
        self.m.CLOCK_FILE.write_text(json.dumps(g))
        self.fr.strata_up = st.get("strata_up", True)
        if st.get("complete") and self.ldr.status == "in_progress":
            self.ldr.status = "completed"
        if self.ldr.terminated and self.fired_min is None:
            self.fired_min = mnt

    def run(self, tag, *extra):
        out = io.StringIO()
        argv = ["ldr-client.py", "research", tag, "A test question?", "--capture-dir", str(self.cap),
                "--budget-s", "3600", "--no-url-check", *extra]
        old = sys.argv
        sys.argv = argv
        code = None
        try:
            with contextlib.redirect_stdout(out):
                self.m.main()
        except SystemExit as e:
            code = e.code
        finally:
            sys.argv = old
        self.out = self.ws / "results" / tag
        return code, out.getvalue()

    def close(self):
        drop(self.d)


def test_normal_run_unaffected():
    # calls every minute, a 20-min quiet stretch in the middle (under the limit), finished at minute 50
    e = Env(lambda m: {"calls": m < 15 or 35 <= m < 50, "complete": m >= 50})
    code, text = e.run("t-normal", "--watchdog-min", "30")
    assert code is None, (code, text[-800:])
    assert (e.out / "summary.json").exists() and not (e.out / "faulted.json").exists()
    assert e.ldr.terminated == 0
    s = json.loads((e.out / "summary.json").read_text())
    assert s["final_status"] == "completed" and s["llm_calls"] == e.n, (s["final_status"], s["llm_calls"], e.n)
    marks = json.loads((e.out / "marks.json").read_text())
    assert marks["watchdog"]["min"] == 30 and marks["watchdog"]["calls_file"].endswith("run-capture/calls.jsonl")
    assert "faulted" not in marks
    assert "idle=" in text and not e.m.MODE_FILE.exists()
    e.close()


def test_quiet_run_is_faulted_s2_shape():
    """s2 11-03: calls stop before minute 10; Strata goes away (on-demand idle stop: gate 'not answering', no call
    held); LDR's spinning thread ignores the terminate. Fires 30 min after the last call, exit 86, faulted.json complete."""
    e = Env(lambda m: {"calls": m < 10, "gate": "closed" if m >= 12 else "open",
                       "reason": "Strata is not answering" if m >= 12 else None, "strata_up": m < 12}, obeys=False)
    code, text = e.run("t-stuck", "--watchdog-min", "30")
    assert code == 86, (code, text[-800:])
    assert e.fired_min is not None and 29.95 <= e.fired_min - e.last_call_min <= 30.3, (e.fired_min, e.last_call_min)
    f = json.loads((e.out / "faulted.json").read_text())
    assert f["reason"].startswith("watchdog: no model call for 30.0 min"), f["reason"]
    assert f["rc"] == 86 and f["watchdog_min"] == 30 and f["research_id"] == "r1"
    assert 29.9 <= f["idle_min"] <= 30.1 and f["held_min_not_counted"] == 0, f
    assert f["last_call"]["id"] == e.n == 10 and f["last_call_end"], f
    assert f["stopped_by_api"] is False and 119 <= f["waited_s"] <= 125 and f["terminate"]["http"] == 200, f
    assert f["ldr"]["pid"] == os.getpid() and f["ldr"]["rss_mb"] > 0 and f["ldr"]["top_threads"], f["ldr"]
    assert f["gate"]["reason"] == "Strata is not answering" and f["ldr_status"]["status"] == "in_progress"
    assert f["proxy_calls_since_start"] == 10
    for name in ("marks.json", "samples.json", "research.json", "research-logs.json"):
        assert (e.out / name).exists(), name
    assert not (e.out / "summary.json").exists()
    assert json.loads((e.out / "marks.json").read_text())["faulted"] is True
    assert not e.m.MODE_FILE.exists()                      # the capture stopped with the fault
    assert "WATCHDOG: no model call for 30 min" in text and "FAULTED" in text
    e.close()


def test_held_time_is_not_counted_in_the_loop():
    # calls to minute 5, a test lock minutes 10-70 (no call waiting), then open: fires 30 + 60 min after the last call
    e = Env(lambda m: {"calls": m < 5, "gate": "closed" if 10 <= m < 70 else "open",
                       "reason": TEST_REASON if 10 <= m < 70 else None})
    code, text = e.run("t-held", "--watchdog-min", "30")
    assert code == 86, (code, text[-800:])
    assert 89.95 <= e.fired_min - e.last_call_min <= 90.3, (e.fired_min, e.last_call_min)   # 30 counted + 60 held
    f = json.loads((e.out / "faulted.json").read_text())
    assert 59.9 <= f["held_min_not_counted"] <= 60.1 and 29.9 <= f["idle_min"] <= 30.1, f
    assert f["stopped_by_api"] is True and f["ldr_status_after"] == "suspended", f
    assert 89.9 <= f["wall_min_since_last_call"] <= 90.3, f["wall_min_since_last_call"]
    e.close()


def test_a_call_held_for_hours_never_fires():
    # a memory-relief / Jan hold with LDR's next call waiting at the gate, 3 h; then calls resume and the run completes
    e = Env(lambda m: {"calls": m < 5 or 200 <= m < 210, "gate": "closed" if 5 <= m < 200 else "open",
                       "reason": "paused: freeing memory (MemAvailable 18.9 GB): Strata restart" if 5 <= m < 200 else None,
                       "held": 1 if 6 <= m < 200 else 0, "complete": m >= 210})
    code, text = e.run("t-heldcall", "--watchdog-min", "30", "--max-minutes", "400")
    assert code is None, (code, text[-800:])
    assert (e.out / "summary.json").exists() and not (e.out / "faulted.json").exists() and e.ldr.terminated == 0
    e.close()


def test_off_without_the_option():
    os.environ.pop("WATCHDOG_MIN", None)
    e = Env(lambda m: {"calls": m < 5 or 95 <= m < 100, "complete": m >= 100})     # 90 quiet minutes
    code, text = e.run("t-off")
    assert code is None, (code, text[-800:])
    assert (e.out / "summary.json").exists() and "watchdog" not in json.loads((e.out / "marks.json").read_text())
    assert "idle=" not in text
    e.close()


if __name__ == "__main__":
    run_tests(globals())
