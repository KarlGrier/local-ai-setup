"""The staged bench2-queue.sh, whole loop, in a scratch sandbox. A test copy is made with five exact replacements (WS,
the release check, strata-compare's folder, MemAvailable, the Strata-restart pgrep line) - each must match once and no
/home/USER path may remain, else the test stops before running anything. Stubs: .venv/bin/python (bench2.py next / run
from a scenario; ldr_runfiles fits), run-ldr.sh, strata-ensure.sh, tagcheck.sh, services_check.py, research_common.py
(no Jan jobs), and notify-send / sleep / curl on PATH. No network, no LDR, no live file."""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _load import S, drop, run_tests, scratch  # noqa: E402

ROW_S2 = "shop-7e deep s2 medium p7dx xhigh setup,critic 7dx - -"
ROW_S1 = "shop-7e deep s1 medium p7dx xhigh setup,critic 7dx - -"
KEY_S2 = "shop-7e/deep/p7dx/s2"
KEY_S1 = "shop-7e/deep/p7dx/s1"

PY_STUB = r"""#!/bin/bash
SB=__SB__
echo "python $*" >> $SB/calls.log
[ "$1" = -I ] && exit 0                                   # ldr_runfiles.py mp-check: the model profile fits
if [ "$1" = tools/bench2.py ] && [ "$2" = next ]; then
  l=$(head -n 1 $SB/scenario/next); sed -i 1d $SB/scenario/next; echo "${l:-done}"; exit 0
fi
if [ "$1" = tools/bench2.py ] && [ "$2" = run ]; then
  SET=$3; PROF=$4; shift 4; ID=; LABEL=
  while [ $# -gt 0 ]; do case $1 in --ids) ID=$2; shift;; --label) LABEL=$2; shift;; esac; shift; done
  b=$(head -n 1 $SB/scenario/runs); sed -i 1d $SB/scenario/runs
  RD=$SB/results/bench2/runs/$SET-$PROF${LABEL:+-$LABEL}/$ID; mkdir -p $RD/capture
  echo "bench2 run $SET/$PROF/${LABEL:--}/$ID -> $b" >> $SB/calls.log
  case $b in
    ok) echo '{"rc": 0}' > $RD/bench.json; exit 0;;
    hang) echo '{"reason": "watchdog: no model call for 30.0 min (held time not counted)"}' > $RD/faulted.json
          echo '{"rc": 86}' > $RD/bench-fail.json; exit 86;;
    fail) echo '{"rc": 1}' > $RD/bench-fail.json; exit 0;;
  esac
fi
echo "UNEXPECTED python $*" >> $SB/calls.log; exit 3
"""

REPLACEMENTS = [
    ("WS=/home/USER/ai/deep-research; cd $WS", "WS=__SB__; cd $WS"),
    ("/home/USER/ai-speed-testing/strata-compare/work/r22/tagcheck.sh", "$WS/stub/tagcheck.sh"),
    ("SC=/home/USER/ai-speed-testing/strata-compare", "SC=$WS/stub/sc"),
    ("avail() { awk '/MemAvailable/{printf \"%d\", $2/1048576}' /proc/meminfo; }", "avail() { echo 50; }"),
    ('pgrep -f "(^|/)llama-server( |$)|strata --serve" > /dev/null || break', "break"),
]


class Sandbox:
    def __init__(self, nexts, runs, faults=""):
        self.d = scratch("wd-queue-")
        sb = self.sb = self.d / "ws"
        for sub in ("run", "logs", "tmp", "tools", "results/bench2/runs", "scenario", "bin", ".venv/bin",
                    "stub/sc/configs/usability/bin"):
            (sb / sub).mkdir(parents=True, exist_ok=True)
        (sb / "run" / "night-ok").write_text("")
        (sb / "NOTES.md").write_text("")
        (sb / "calls.log").write_text("")
        (sb / "scenario" / "next").write_text("".join(x + "\n" for x in nexts))
        (sb / "scenario" / "runs").write_text("".join(x + "\n" for x in runs))
        if faults:
            (sb / "results" / "bench2" / "watchdog-faults.tsv").write_text(faults)
        q = (S / "tools" / "bench2-queue.sh").read_text()
        for old, new in REPLACEMENTS:
            assert q.count(old) == 1, f"the queue script changed: {old!r} found {q.count(old)} times"
            q = q.replace(old, new)
        q = q.replace("__SB__", str(sb))
        assert "/home/USER" not in q.replace(str(sb), ""), "a live path is left in the test copy"
        (self.d / "queue-test.sh").write_text(q)
        stubs = {
            ".venv/bin/python": PY_STUB.replace("__SB__", str(sb)),
            "run-ldr.sh": f'#!/bin/bash\necho "run-ldr $1" >> {sb}/calls.log\n',
            "stub/tagcheck.sh": "#!/bin/bash\nexit 0\n",
            "stub/sc/configs/usability/bin/strata-ensure.sh": "#!/bin/bash\nexit 0\n",
            "bin/notify-send": f'#!/bin/bash\necho "notify $*" >> {sb}/calls.log\n',
            "bin/sleep": f'#!/bin/bash\necho "sleep $*" >> {sb}/calls.log\n',
            "bin/curl": "#!/bin/bash\nexit 0\n",
            "tools/services_check.py": "import sys\nsys.exit(0)\n",
            "tools/research_common.py": "ACTIVE = ('starting', 'running', 'paused')\n\ndef all_jobs():\n    return []\n",
        }
        for rel, text in stubs.items():
            p = sb / rel
            p.write_text(text)
            p.chmod(0o755)

    def run(self, **env):
        e = {"PATH": f"{self.sb}/bin:/usr/bin:/bin", "HOME": str(self.d), "BENCH2_PLAN": "queue-plan-test.json",
             "LANG": "C.UTF-8", **env}
        r = subprocess.run(["/bin/bash", str(self.d / "queue-test.sh")], env=e, capture_output=True, text=True,
                           timeout=60, cwd=str(self.d))
        self.rc = r.returncode
        self.calls = (self.sb / "calls.log").read_text().splitlines()
        self.log = (self.sb / "logs" / "bench2-queue.log").read_text()
        self.notes = (self.sb / "NOTES.md").read_text()
        tsv = self.sb / "results" / "bench2" / "watchdog-faults.tsv"
        self.faults = [l.split("\t") for l in tsv.read_text().splitlines()] if tsv.exists() else []
        self.runs_dir = self.sb / "results" / "bench2" / "runs" / "shop-7e-deep-p7dx"
        assert not any(c.startswith("UNEXPECTED") for c in self.calls), self.calls
        return self

    def ldr(self):
        return [c for c in self.calls if c.startswith("run-ldr")]

    def faulted_dirs(self, qid="s2"):
        return sorted(p.name for p in self.runs_dir.glob(f"{qid}.faulted-*")) if self.runs_dir.exists() else []

    def close(self):
        drop(self.d)


def test_hang_once_then_requeued_on_a_fresh_ldr():
    q = Sandbox([ROW_S2, ROW_S2], ["hang", "ok"]).run()
    assert q.rc == 0, (q.rc, q.log)
    runs = [c for c in q.calls if c.startswith("bench2 run")]
    assert runs == [f"bench2 run {KEY_S2} -> hang", f"bench2 run {KEY_S2} -> ok"], runs
    # before run 1: stop + start (a fresh LDR per question); after the hang: stop; before run 2: stop + start
    assert q.ldr() == ["run-ldr stop", "run-ldr start", "run-ldr stop", "run-ldr stop", "run-ldr start"], q.ldr()
    i_hang = q.calls.index(f"bench2 run {KEY_S2} -> hang")
    assert q.calls[i_hang + 1:].index("run-ldr stop") < q.calls[i_hang + 1:].index("python tools/bench2.py next --wide")
    assert len(q.faults) == 1 and q.faults[0][0] == KEY_S2 and q.faults[0][2].startswith(
        "results/bench2/runs/shop-7e-deep-p7dx/s2.faulted-"), q.faults
    fd = q.faulted_dirs()
    assert len(fd) == 1 and (q.runs_dir / fd[0] / "faulted.json").exists() and (q.runs_dir / fd[0] / "capture").is_dir()
    assert (q.runs_dir / "s2" / "bench.json").exists() and not (q.runs_dir / "s2" / "faulted.json").exists()
    assert "FAULTED - watchdog: no model call for 30.0 min" in q.log and "requeued once" in q.log, q.log
    assert q.notes == "" and not any(c.startswith("notify") for c in q.calls)
    q.close()


def test_second_hang_stops_and_reports():
    q = Sandbox([ROW_S2, ROW_S2, ROW_S2], ["hang", "hang", "ok"]).run()
    assert q.rc == 0, (q.rc, q.log)                              # exit 0: Restart=on-failure does not restart it
    runs = [c for c in q.calls if c.startswith("bench2 run")]
    assert len(runs) == 2, runs                                 # not requeued a second time
    assert q.ldr()[-1] == "run-ldr stop"                         # the stuck LDR does not stay up
    assert len(q.faulted_dirs()) == 2 and not (q.runs_dir / "s2").exists()
    assert [f[0] for f in q.faults] == [KEY_S2, KEY_S2]
    assert "hung twice: not requeued - queue stopped" in q.log, q.log
    assert q.notes.count("BENCH QUEUE STOPPED (watchdog") == 1 and KEY_S2 in q.notes and "watchdog-faults.tsv" in q.notes
    assert sum(1 for c in q.calls if c.startswith("notify") and "critical" in c) == 1, q.calls
    assert (q.sb / "scenario" / "next").read_text().strip() == ROW_S2      # the third pick never happened
    q.close()


def test_started_again_after_two_hangs_refuses_the_run():
    tsv = "".join(f"{KEY_S2}\t2026-11-04 10:0{i}:00\tresults/bench2/runs/shop-7e-deep-p7dx/s2.faulted-10000{i}\n"
                  for i in (1, 2))
    q = Sandbox([ROW_S2], ["ok"], faults=tsv).run()
    assert q.rc == 0, (q.rc, q.log)
    assert not any(c.startswith("bench2 run") for c in q.calls) and q.ldr() == [], q.calls
    assert "hung twice before" in q.log and any(c.startswith("notify") for c in q.calls)
    q.close()


def test_normal_runs_unaffected():
    q = Sandbox([ROW_S1, ROW_S2], ["ok", "ok"]).run()
    assert q.rc == 0, (q.rc, q.log)
    assert q.faults == [] and q.notes == "" and q.faulted_dirs() == [] and q.faulted_dirs("s1") == []
    assert q.ldr() == ["run-ldr stop", "run-ldr start"] * 2, q.ldr()
    assert "FAULTED" not in q.log and "queue finished (queue-plan-test.json)" in q.log
    q.close()


def test_other_failures_are_not_watchdog_faults():
    q = Sandbox([ROW_S2, ROW_S2], ["fail", "ok"]).run()
    assert q.rc == 0, (q.rc, q.log)
    assert q.faults == [] and q.faulted_dirs() == []
    assert "not completed (rc 0); retry in 10 min" in q.log and "sleep 600" in q.calls, q.log
    q.close()


def test_hangs_are_counted_per_run():
    q = Sandbox([ROW_S1, ROW_S2, ROW_S1, ROW_S2], ["hang", "hang", "ok", "ok"]).run()
    assert q.rc == 0, (q.rc, q.log)
    assert sorted(f[0] for f in q.faults) == [KEY_S1, KEY_S2] and q.notes == ""
    assert (q.runs_dir / "s1" / "bench.json").exists() and (q.runs_dir / "s2" / "bench.json").exists()
    q.close()


if __name__ == "__main__":
    run_tests(globals())
