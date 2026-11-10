"""Test every checker against known-good and known-bad answers, plus the sandbox, the renderer, the statistics and
the privacy check.  `suite/run.sh selftest` prints one line per check and exits non-zero on any failure."""
from __future__ import annotations

import json
import sys

from .common import RESULTS, TMP, write_json
from . import mock_anthropic, mock_openrouter, privacy, sandbox, stats
from .cats import agentic, coding, freshness, honesty, instruct, longctx, math, research, tools, visual


def sandbox_checks():
    out = []
    probe = r'''
import os, socket, json, resource
r = {}
try:
    socket.create_connection(("1.1.1.1", 80), timeout=3); r["net"] = "OPEN"
except Exception as e:
    r["net"] = type(e).__name__
try:
    socket.getaddrinfo("example.com", 80); r["dns"] = "OPEN"
except Exception as e:
    r["dns"] = type(e).__name__
r["home"] = os.path.exists("/home")
try:
    open("/usr/x", "w"); r["usr_write"] = "OPEN"
except Exception as e:
    r["usr_write"] = type(e).__name__
try:
    b = bytearray(4 << 30); r["mem"] = "OPEN"
except MemoryError:
    r["mem"] = "MemoryError"
r["env"] = sorted(os.environ)
print(json.dumps(r))
'''
    res = sandbox.run_python_files({"probe.py": probe}, "probe.py", timeout_s=30)
    try:
        r = json.loads(res["stdout"].strip().splitlines()[-1])
    except (ValueError, IndexError):
        r = {}
    out.append(("sandbox: no network, no DNS, no /home, /usr read-only, memory capped, bare environment",
                r.get("net") not in (None, "OPEN") and r.get("dns") not in (None, "OPEN") and r.get("home") is False
                and r.get("usr_write") not in (None, "OPEN") and r.get("mem") == "MemoryError"
                and not any("KEY" in k or "ANTHROPIC" in k for k in r.get("env", [])), json.dumps(r)[:300]))
    loop = sandbox.run_python_files({"loop.py": "while True: pass\n"}, "loop.py", timeout_s=3)
    out.append(("sandbox: endless loop killed at the time limit", loop["timed_out"] and loop["wall_s"] < 15,
                f"wall {loop['wall_s']} s"))
    fork = sandbox.run_python_files({"fork.py": "import os\nwhile True:\n    try:\n        os.fork()\n    except OSError:\n        pass\n"},
                                    "fork.py", timeout_s=3)
    out.append(("sandbox: fork bomb contained and killed", fork["timed_out"] or fork["rc"] is not None, f"wall {fork['wall_s']} s"))
    left = list((TMP / "sbx").glob("py-*"))
    out.append(("sandbox: throwaway folders removed afterwards", not left, f"{len(left)} left"))
    return out


def stats_checks():
    out = []
    lo, hi = stats.wilson(10, 20)
    out.append(("stats: Wilson 10/20 = 29.9-70.1 %", abs(lo - 0.2993) < 1e-3 and abs(hi - 0.7007) < 1e-3, f"{lo:.4f}-{hi:.4f}"))
    a = {f"i{k}": {"runs": [1.0 if k < 10 else 0.0]} for k in range(20)}
    b = {f"i{k}": {"runs": [1.0 if k < 11 else 0.0]} for k in range(20)}
    r = stats.paired(a, b)
    out.append(("stats: one extra solved item out of 20 is 'within noise'", r["verdict"] == "within noise", json.dumps(r)))
    c = {f"i{k}": {"runs": [1.0]} for k in range(20)}
    d = {f"i{k}": {"runs": [0.0 if k < 12 else 1.0]} for k in range(20)}
    r2 = stats.paired(c, d)
    out.append(("stats: 12 of 20 items lost is a real difference", r2["verdict"] == "A higher" and r2["p"] < 0.01,
                json.dumps(r2)))
    multi = {f"i{k}": {"runs": [1.0, 0.0, 1.0]} for k in range(10)}
    s, lo2, hi2, how = stats.category_score(multi)
    out.append(("stats: 3 runs per item uses the bootstrap", how.startswith("bootstrap") and lo2 <= s <= hi2, f"{s:.3f} {lo2:.3f}-{hi2:.3f}"))
    return out


def resume_checks():
    """2026-10-13 (27b): a reply without usage and without an answer crashed the token split and ended the run; a
    resumed run took its spend from a stale meta.json."""
    import tempfile
    from pathlib import Path
    from . import common, runner, tokcount
    out = []
    try:
        sp = tokcount.Counter().split(None, "only reasoning, no answer", "", None)
        ok, det = sp["method"] == "estimate+no-usage" and sp["completion"] > 0 and sp["answer"] == 0, json.dumps(sp)
    except Exception as e:                                   # noqa: BLE001
        ok, det = False, f"{type(e).__name__}: {e}"
    out.append(("tokens: a reply without usage or answer text gets an estimate (no crash)", ok, det))
    with tempfile.TemporaryDirectory() as d:
        saved = common.RESULTS
        try:
            runner.label_dir.__globals__["RESULTS"] = Path(d)
            for i, c in enumerate((1.5, 2.25, None)):
                write_json(Path(d) / "x" / "answers" / "math" / f"m{i}.r0.json", {"cost_usd": c})
            a, b = runner._spent_before("x", {"cost_usd": 1.0}), runner._spent_before("x", {"cost_usd": 9.0})
        finally:
            runner.label_dir.__globals__["RESULTS"] = saved
    out.append(("resume: the spend so far is the larger of meta's and the saved answers' sum", a == 3.75 and b == 9.0,
                f"{a} {b}"))
    return out


def main() -> int:
    groups = [("coding", coding.selftest), ("math", math.selftest), ("instruct", instruct.selftest),
              ("tools", tools.selftest), ("honesty", honesty.selftest), ("freshness", freshness.selftest),
              ("longctx", longctx.selftest), ("agentic", agentic.selftest), ("visual", visual.selftest),
              ("sandbox", sandbox_checks), ("stats", stats_checks), ("privacy", privacy.selftest),
              ("claude-mock", mock_anthropic.selftest), ("openrouter-mock", mock_openrouter.selftest),
              ("research", research.selftest), ("research-loop", research.loop_selftest),
              ("resume", resume_checks)]
    total = failed = 0
    rows = []
    for name, fn in groups:
        try:
            res = fn()
        except Exception as e:                               # noqa: BLE001
            res = [(f"{name}: self-test crashed", False, f"{type(e).__name__}: {e}")]
        for check, ok, detail in res:
            total += 1
            failed += 0 if ok else 1
            rows.append({"group": name, "check": check, "ok": bool(ok), "detail": detail})
            print(f"{'PASS' if ok else 'FAIL'}  {check}" + ("" if ok else f"  -- {detail[:300]}"), flush=True)
    print(f"\nself-test: {total - failed}/{total} checks passed")
    write_json(RESULTS / "selftest.json", {"total": total, "failed": failed, "checks": rows})
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
