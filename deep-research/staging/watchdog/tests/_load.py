"""Shared helpers for the watchdog tests: load the STAGED tools as modules, scratch dirs under staging/watchdog/scratch,
a fake clock, a fake LDR / requests. No network (nothing is sent anywhere), no LDR, no live run/ or results/ file."""
import importlib.util
import json
import shutil
import sys
import tempfile
import time as _time
import traceback
from pathlib import Path

import requests

S = Path("/home/USER/ai/deep-research/staging/watchdog")
TOOLS = S / "tools"
SCRATCH = S / "scratch"


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.__file__.startswith(str(TOOLS)), mod.__file__
    return mod


def scratch(prefix: str) -> Path:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix, dir=SCRATCH))


def drop(p: Path) -> None:
    p = Path(p).resolve()
    assert str(p).startswith(str(SCRATCH) + "/"), p          # never anything outside the scratch dir
    shutil.rmtree(p, ignore_errors=True)


class FakeTime:
    """time.time / monotonic / sleep on a fake clock; sleep() runs the hooks (the fake proxy) after advancing."""

    def __init__(self, t0: float = 1_793_700_000.0):
        self.t, self.m, self.hooks = t0, 5_000.0, []

    def time(self):
        return self.t

    def monotonic(self):
        return self.m

    def sleep(self, s):
        self.t += s
        self.m += s
        for h in list(self.hooks):
            h(self)

    def __getattr__(self, name):                 # strftime, localtime, ...
        return getattr(_time, name)


class FakeResp:
    def __init__(self, code=200, obj=None, text=None):
        self.status_code, self._obj = code, obj
        self.text = text if text is not None else json.dumps(obj)

    def json(self):
        return self._obj

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class FakeLDR:
    """LDR's API as ldr-client uses it. status: what /status says; obeys: a terminate ends the research."""

    def __init__(self, obeys=True):
        self.status, self.obeys, self.calls, self.terminated = "in_progress", obeys, [], 0

    def api(self, method, path, **kw):
        self.calls.append((method, path))
        if path == "/api/start_research":
            return FakeResp(200, {"research_id": "r1"})
        if path.endswith("/status"):
            return FakeResp(200, {"status": self.status, "progress": 18})
        if path.startswith("/api/terminate/"):
            self.terminated += 1
            if self.obeys:
                self.status = "suspended"
            return FakeResp(200, {"status": "success"})
        if path.startswith("/api/report/"):
            return FakeResp(200, {"content": "# Report\n\nThe answer [1].\n\n## Sources\n[1] https://example.invalid/a\n"})
        if path.endswith("/logs"):
            return FakeResp(200, [])
        if path == "/api/research/r1":
            return FakeResp(200, {"id": "r1"})
        return FakeResp(404, {"error": path})


class FakeRequests:
    """The module-level `requests` of ldr-client: SearXNG health, Strata /metrics (down -> ConnectionError)."""
    RequestException = requests.RequestException
    ConnectionError = requests.ConnectionError

    def __init__(self):
        self.strata_up = True

    def get(self, url, timeout=None, **kw):
        if url.endswith("/healthz"):
            return FakeResp(200, {})
        if "/metrics?requests=all" in url:
            return FakeResp(200, {"requests": []})
        if url.endswith("/metrics"):
            if not self.strata_up:
                raise requests.ConnectionError("Strata down (fake)")
            return FakeResp(200, {"live": {"state": "idle", "queued": 0}})
        raise AssertionError(f"unexpected GET {url} (no network in tests)")


def run_tests(glb: dict) -> None:
    tests = [(n, f) for n, f in glb.items() if n.startswith("test_") and callable(f)]
    bad = 0
    for n, f in tests:
        try:
            f()
            print(f"  ok   {n}")
        except Exception:                                   # noqa: BLE001
            bad += 1
            print(f"  FAIL {n}\n" + traceback.format_exc())
    name = Path(sys.argv[0]).name
    if bad:
        print(f"FAIL: {name}: {bad} of {len(tests)} tests failed")
        sys.exit(1)
    print(f"ok: {name}: {len(tests)} tests passed")
