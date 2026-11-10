"""The staged bench2.py `run`: passes --watchdog-min ($WATCHDOG_MIN, default 30) to the client, moves the client's
faulted.json into the run folder, writes bench-fail.json with "faulted", and exits 86; a normal run and an ordinary
failure behave as before. The client is a fake (subprocess.run patched); WS / B point into scratch."""
import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _load import drop, load, run_tests, scratch  # noqa: E402

ARGV = ["bench2.py", "run", "shop-7e", "deep", "--ids", "s2", "--effort-all", "medium", "--effort-verify", "xhigh",
        "--label", "p7dx", "--model-profile", "flash-next"]


class FakeSub:
    STDOUT = subprocess.STDOUT

    def __init__(self, ws, behaviour):
        self.ws, self.behaviour, self.cmds = ws, behaviour, []

    def run(self, cmd, cwd=None, env=None, stdout=None, stderr=None):
        self.cmds.append(cmd)
        tag = cmd[3]
        res = self.ws / "results" / tag
        res.mkdir(parents=True, exist_ok=True)
        if self.behaviour == "hang":
            (res / "faulted.json").write_text(json.dumps({"reason": "watchdog: no model call for 30.0 min (held time not counted)"}))
            (res / "marks.json").write_text("{}")
            return subprocess.CompletedProcess(cmd, 86)
        if self.behaviour == "ok":
            (res / "summary.json").write_text("{}")
            return subprocess.CompletedProcess(cmd, 0)
        return subprocess.CompletedProcess(cmd, 1)              # an ordinary failure (e.g. LDR unreachable)


class RunFiles:
    @staticmethod
    def modelprofile_mismatch(*a, **k):
        return None


def setup(behaviour):
    d = scratch("wd-b2-")
    ws = d / "ws"
    b = ws / "results" / "bench2"
    (ws / "run").mkdir(parents=True)
    b.mkdir(parents=True)
    for name, val in (("ldr.profile", "deep"), ("ldr.efforts", "report=medium verify=xhigh"), ("ldr.items", "off"),
                      ("ldr.s2", "off"), ("ldr.quicklimits", "off"), ("ldr.fallback", "off"), ("night-ok", "")):
        (ws / "run" / name).write_text(val + "\n")
    (b / "questions-shop-7e.jsonl").write_text(json.dumps({"id": "s2", "kind": "open", "question": "Q?"}) + "\n")
    (b / "queue-plan.json").write_text("[]")
    m = load(f"bench2_rc_{behaviour}_{id(d)}", "bench2.py")
    m.WS, m.B, m.PY, m.NIGHT_OK = ws, b, "/nonexistent/python", ws / "run" / "night-ok"
    m.subprocess = FakeSub(ws, behaviour)
    m.runfiles = lambda: RunFiles
    return d, m, b / "runs" / "shop-7e-deep-p7dx" / "s2"


def run(m):
    old = sys.argv
    sys.argv = list(ARGV)
    os.environ.pop("BENCH2_PLAN", None)
    code = None
    try:
        with contextlib.redirect_stdout(io.StringIO()) as out:
            m.main()
    except SystemExit as e:
        code = e.code
    finally:
        sys.argv = old
    return code, out.getvalue()


def test_hang_exits_86_and_keeps_the_files():
    os.environ.pop("WATCHDOG_MIN", None)
    d, m, rd = setup("hang")
    code, text = run(m)
    assert code == 86, (code, text)
    assert (rd / "faulted.json").exists() and (rd / "marks.json").exists() and not (rd / "bench.json").exists()
    meta = json.loads((rd / "bench-fail.json").read_text())
    assert meta["rc"] == 86 and meta["faulted"].startswith("watchdog: no model call"), meta
    cmd = m.subprocess.cmds[0]
    assert cmd[cmd.index("--watchdog-min") + 1] == "30", cmd
    assert "FAULTED" in text
    drop(d)


def test_watchdog_min_from_env():
    for val, want in (("5", "5"), ("0", "0"), ("12.5", "12.5")):
        os.environ["WATCHDOG_MIN"] = val
        try:
            d, m, rd = setup("ok")
            code, _ = run(m)
            cmd = m.subprocess.cmds[0]
            assert code is None and cmd[cmd.index("--watchdog-min") + 1] == want, (val, cmd)
            drop(d)
        finally:
            os.environ.pop("WATCHDOG_MIN", None)


def test_normal_run_unchanged():
    d, m, rd = setup("ok")
    code, _ = run(m)
    assert code is None and (rd / "bench.json").exists() and not (rd / "bench-fail.json").exists()
    assert "faulted" not in json.loads((rd / "bench.json").read_text())
    drop(d)


def test_ordinary_failure_unchanged():
    d, m, rd = setup("fail")
    code, _ = run(m)
    assert code is None, code                                    # as before: bench2.py itself ends normally
    meta = json.loads((rd / "bench-fail.json").read_text())
    assert meta["rc"] == 1 and "faulted" not in meta and not (rd / "bench.json").exists()
    drop(d)


if __name__ == "__main__":
    run_tests(globals())
