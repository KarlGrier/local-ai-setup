"""Unit tests: the staged ldr-client.py's Watchdog (fake clocks, a fake proxy capture file + gate snapshot in scratch),
last_record, proc_snapshot, and that the three exit-code constants agree."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _load import S, drop, load, run_tests, scratch  # noqa: E402

C = load("ldr_client_staged", "ldr-client.py")
B2 = load("bench2_staged", "bench2.py")
TEST_REASON = "a test holds the GPUs (gpu-test.lock)"


class Clock:
    def __init__(self):
        self.t, self.m = 1_793_700_000.0, 100.0

    def wall(self):
        return self.t

    def mono(self):
        return self.m


class Rig:
    """A Watchdog on a scratch capture file + gate snapshot; poll() = one 3 s client poll with the proxy's state."""

    def __init__(self, limit=30.0, calls_name="capture/calls.jsonl"):
        self.d = scratch("wd-unit-")
        self.calls = self.d / calls_name
        self.calls.parent.mkdir(parents=True, exist_ok=True)
        self.clockf = self.d / "research-clock.json"
        self.clk = Clock()
        self.n = 0
        self.g = {"gate": "open", "reason": None, "inflight": 0, "held": 0}
        self.stale = False
        self.write_gate()
        self.wd = C.Watchdog(limit, self.calls, self.clockf, mono=self.clk.mono, wall=self.clk.wall)

    def write_gate(self):
        upd = self.clk.t - (300 if self.stale else 0.5)
        self.clockf.write_text(json.dumps({"paused_total_s": 0, "updated": upd, **self.g}))

    def call(self):
        self.n += 1
        with open(self.calls, "a") as f:
            f.write(json.dumps({"id": self.n, "t0": self.clk.t - 4, "cls": "agent", "content": "x" * 40}) + "\n")

    def poll(self, step=3.0):
        self.clk.t += step
        self.clk.m += step
        self.write_gate()
        self.wd.observe()
        return self.wd.fired()

    def run(self, minutes, every_min=None, step=3.0):
        """poll for `minutes` (a call every `every_min` minutes if given); the minute it fired, else None"""
        polls = int(round(minutes * 60 / step))
        per = int(round(every_min * 60 / step)) if every_min else 0
        for i in range(1, polls + 1):
            if per and i % per == 0:
                self.call()
            if self.poll(step):
                return i * step / 60
        return None

    def close(self):
        drop(self.d)


def test_calls_keep_coming_never_fires():
    r = Rig()
    assert r.run(180, every_min=5) is None
    assert r.wd.idle_s < 5 * 60 + 1, r.wd.idle_s
    r.close()


def test_quiet_fires_at_the_limit():
    r = Rig()
    assert r.run(10, every_min=1) is None
    m = r.run(60)
    assert m is not None and 29.9 <= m <= 30.1, m
    assert r.wd.state == "idle" and r.wd.last_call_end is not None
    r.close()


def test_no_call_at_all_fires_from_the_start():
    r = Rig()
    m = r.run(60)
    assert m is not None and 29.9 <= m <= 30.1, m
    assert r.wd.last_call_end is None
    r.close()


def test_held_time_not_counted():
    for reason in (TEST_REASON, "paused: freeing memory (MemAvailable 18.2 GB): Strata restart",
                   "paused: night pause (resumes at 09:00)",
                   "yielding to another client (it used Strata 2 min ago; yield 5 min)"):
        r = Rig()
        r.call()
        assert r.run(10) is None                                  # 10 min quiet, gate open: counted
        r.g.update(gate="closed", reason=reason)                  # 60 min held, no call waiting: not counted
        assert r.run(60) is None, reason
        assert abs(r.wd.held_s - 3600) < 4 and abs(r.wd.idle_s - 600) < 4, (r.wd.held_s, r.wd.idle_s)
        r.g.update(gate="open", reason=None)
        m = r.run(30)
        assert m is not None and 19.9 <= m <= 20.1, (reason, m)    # 10 + 20 counted = 30, 90 min after the call
        r.close()


def test_a_held_call_is_not_idle():
    r = Rig()
    r.call()
    assert r.run(25) is None
    r.g.update(gate="closed", reason="paused: freeing memory (MemAvailable 18.0 GB): Strata restart", held=1)
    assert r.run(180) is None                                     # 3 h waiting at the gate
    assert r.wd.idle_s == 0
    r.g.update(gate="open", reason=None, held=0)
    assert r.run(29) is None                                      # the clock started again when the hold ended
    r.close()


def test_a_long_call_in_flight_is_not_idle():
    r = Rig()
    r.call()
    assert r.run(25) is None
    r.g.update(inflight=1)                                        # e.g. the report call, 50 min
    assert r.run(50) is None
    r.g.update(inflight=0)
    r.call()
    assert r.run(29) is None
    assert r.run(2) is not None
    r.close()


def test_strata_down_without_a_waiting_call_counts():
    """s2 11-03: Strata's on-demand launcher stopped it after the run went quiet - that is not a hold."""
    r = Rig()
    r.call()
    assert r.run(5) is None
    r.g.update(gate="closed", reason="Strata is not answering", held=0)
    m = r.run(60)
    assert m is not None and 24.9 <= m <= 25.1, m
    r.close()


def test_strata_down_with_a_waiting_call_is_not_idle():
    r = Rig()
    r.call()
    r.g.update(gate="closed", reason="Strata is not answering", held=1)   # a call waits for Strata's start
    assert r.run(90) is None
    r.close()


def test_stale_gate_snapshot_counts():
    """the proxy is down (snapshot not updated): its last inflight / held values are not believed"""
    r = Rig()
    r.call()
    r.g.update(inflight=1)
    r.stale = True
    m = r.run(60)
    assert m is not None and 29.9 <= m <= 30.1, m
    assert "no fresh gate snapshot" in r.wd.state
    r.close()


def test_call_log_fallback():
    r = Rig(calls_name="logs/llm-calls.jsonl")                    # what the client watches without a capture dir
    assert r.run(100, every_min=20) is None
    assert r.run(31) is not None
    r.close()


def test_one_poll_counts_at_most_two_minutes():
    r = Rig()
    r.call()
    assert not r.poll() and r.wd.idle_s == 0
    r.clk.m += 7200                                               # a 2-hour stall between two polls (or a resume)
    r.clk.t += 7200
    r.write_gate()
    r.wd.observe()
    assert r.wd.idle_s == 120 and not r.wd.fired(), r.wd.idle_s
    r.close()


def test_limit_zero_is_off():
    r = Rig(limit=0)
    assert r.run(120) is None
    r.close()


def test_short_limit_from_env():
    os.environ["WATCHDOG_MIN"] = "0.5"
    try:
        assert C._env_float("WATCHDOG_MIN", 0.0) == 0.5
        assert B2.watchdog_min() == 0.5
        r = Rig(limit=C._env_float("WATCHDOG_MIN", 0.0))
        m = r.run(5)
        assert m is not None and abs(m - 0.5) < 0.06, m
        r.close()
        os.environ["WATCHDOG_MIN"] = "bogus"
        assert C._env_float("WATCHDOG_MIN", 0.0) == 0.0 and B2.watchdog_min() == 30.0
        os.environ["WATCHDOG_MIN"] = "0"
        assert B2.watchdog_min() == 0.0
    finally:
        os.environ.pop("WATCHDOG_MIN", None)
    assert B2.watchdog_min() == 30.0 and C._env_float("WATCHDOG_MIN", 0.0) == 0.0


def test_last_record_reads_the_last_line_from_the_end():
    d = scratch("wd-last-")
    p = d / "calls.jsonl"
    assert C.last_record(p) is None
    p.write_text("")
    assert C.last_record(p) is None
    big = "y" * (3 << 20)                                          # a 3 MB captured call
    with open(p, "w") as f:
        for i, t0 in ((1, 100.5), (2, 200.25)):
            f.write(json.dumps({"id": i, "t0": t0, "messages": "s"}) + "\n")
        f.write(json.dumps({"id": 3, "t0": 1793767000.125, "messages": big}) + "\n")
    assert C.last_record(p) == {"id": 3, "t0": 1793767000.125}
    p.write_text(json.dumps({"id": 9, "t0": 5.5}))                  # one line, no newline
    assert C.last_record(p) == {"id": 9, "t0": 5.5}
    drop(d)


def test_proc_snapshot_finds_the_busy_thread():
    code = ("import threading, time\n"
            "def spin():\n    x = 0\n    while True:\n        x += 1\n"
            "threading.Thread(target=spin, name='spinner', daemon=True).start()\n"
            "time.sleep(20)\n")
    p = subprocess.Popen(["nice", "-n", "19", sys.executable, "-I", "-c", code])
    try:
        import time
        time.sleep(0.8)
        snap = C.proc_snapshot(p.pid, sample_s=0.6)
        assert snap["pid"] == p.pid and snap["rss_mb"] is not None and snap["threads"] >= 2, snap
        top = snap["top_threads"][0]
        assert top["cpu_pct"] >= 20 and top["state"] in ("R", "S"), snap      # niced: a busy PC gives it less
        assert "wchan" in top
    finally:
        p.kill()
        p.wait()
    gone = C.proc_snapshot(p.pid, sample_s=0.1)
    assert "error" in gone, gone


def test_exit_codes_and_gate_reason_agree():
    q = (S / "tools" / "bench2-queue.sh").read_text()
    m = re.search(r"^WD_RC=(\d+)", q, re.M)
    assert m and int(m.group(1)) == C.WATCHDOG_RC == B2.WATCHDOG_RC == 86, (m and m.group(1))
    proxy = Path("/home/USER/ai/deep-research/tools/strata-proxy.py").read_text()   # read only
    assert f'DOWN = "{C.GATE_DOWN}"' in proxy
    assert C.CLOCK_FILE == Path("/home/USER/ai/deep-research/run/research-clock.json")
    assert "PROXY_CLOCK_FILE=$RUN/research-clock.json" in Path("/home/USER/ai/deep-research/run-ldr.sh").read_text()


if __name__ == "__main__":
    run_tests(globals())
