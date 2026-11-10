#!/usr/bin/env python3
"""ldr_runfiles.py - two run/ files around LDR, shared by the research runner, bench2.py, bench2-queue.sh and
run-ldr.sh (staged 10-29 in staging/runner-bench; not installed). Standard library only. Every function takes the run
folder (and the profiles folder) as an argument, so tests use temp folders.

1. run/ldr.modelprofile - "<name> <first 12 hex digits of the file's sha256>", written by run-ldr.sh when it starts LDR
   (C3b). The runner and the bench queue compare it with the profile they want (LDR_MODEL_PROFILE, default flash-next)
   and restart LDR when it differs, like the other ldr.* stamps. No stamp = an LDR started before C3, i.e. with the
   built-in values, which are flash-next's: it fits flash-next and nothing else.

2. run/paid-run.json - whose LDR searches these are, for item 7's paid-search budget (paid_budget.py reads it for the
   client "ldr", search_route.py its "route" and paid_search.py its "cache"):
     {"kind": "research", "run": <job id>}                                    while a Jan job's research runs (runner)
     {"kind": "test", "run": "<runs folder>/<qid>", "route": "7b", "cache": true}   during an item 7 measurement (bench2.py)
   plus "writer", "pid", "pid_start" (the writer's start time, /proc/<pid>/stat field 22) and "written". Written
   atomically (temp file + rename, under run/paid-run.lock); the writer removes it at the end (finally). A file whose
   writer is gone (crash, SIGKILL) is stale: readers ignore it (paid_budget.py checks the pid the same way), and the
   runner (every tick) and run-ldr.sh (stop / restart) remove it. A hand-written file without a pid counts for 12 h.

CLI (bench2-queue.sh and run-ldr.sh):
  ldr_runfiles.py mp-check --want NAME [--run-dir D] [--profiles-dir P]  exit 0 = LDR runs it, 1 = differs (why on stdout)
  ldr_runfiles.py paid-show [--run-dir D]                                one line for run-ldr.sh status
  ldr_runfiles.py paid-clear --stale-only [--run-dir D]                  remove the file if its writer is gone
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")
RUN_DIR = WS / "run"
PROFILES_DIR = WS / "profiles"
DEFAULT_PROFILE = "flash-next"
STAMP = "ldr.modelprofile"
PAID_FILE = "paid-run.json"
PAID_LOCK = "paid-run.lock"
KINDS = ("test", "research")
NO_PID_MAX_AGE_S = 12 * 3600       # a file without a writer pid (written by hand) counts this long


# -- 1. the model profile stamp ---------------------------------------------------------------------------------------
def profile_path(name_or_path: str | None, profiles_dir: str | Path | None = None) -> Path:
    """As deep/modelprofile.py's profile_file(): a name -> profiles/<name>.env; a path (with '/' or ending in .env)
    as given."""
    n = (name_or_path or DEFAULT_PROFILE).strip() or DEFAULT_PROFILE
    if "/" in n or n.endswith(".env"):
        return Path(n).expanduser()
    return Path(profiles_dir or PROFILES_DIR) / f"{n}.env"


def stamp_for(name_or_path: str | None, profiles_dir: str | Path | None = None) -> str | None:
    """The line run-ldr.sh writes for this profile - `basename "$P_FILE" .env` and `sha256sum < "$P_FILE" | cut -c1-12`
    of the resolved file - or None when there is no such file."""
    try:
        p = profile_path(name_or_path, profiles_dir).resolve()
        data = p.read_bytes()
    except OSError:
        return None
    name = p.name[:-4] if p.name.endswith(".env") and p.name != ".env" else p.name
    return f"{name} {hashlib.sha256(data).hexdigest()[:12]}"


def stamp_have(run_dir: str | Path | None = None) -> str | None:
    try:
        return (Path(run_dir or RUN_DIR) / STAMP).read_text().strip() or None
    except OSError:
        return None


def modelprofile_mismatch(want: str | None, run_dir: str | Path | None = None,
                          profiles_dir: str | Path | None = None) -> str:
    """Why the running LDR's model profile is not `want` ("" = it is)."""
    want = (want or DEFAULT_PROFILE).strip() or DEFAULT_PROFILE
    have = stamp_have(run_dir)
    is_default = profile_path(want, profiles_dir) == profile_path(DEFAULT_PROFILE, profiles_dir)
    if have is None and is_default:
        return ""                                  # started before C3: the built-in values = flash-next's
    w = stamp_for(want, profiles_dir)
    if w is None:
        return f"model profile {want}: no file {profile_path(want, profiles_dir)}"
    if have is None:
        return f"model profile: LDR runs the built-in values (no {STAMP}), wanted {w}"
    if have == w:
        return ""
    if have.split()[0] == w.split()[0]:
        return f"model profile {w.split()[0]}: the file changed since LDR started ({have.split()[-1]} -> {w.split()[-1]})"
    return f"model profile {have} -> {w}"


# -- 2. run/paid-run.json ---------------------------------------------------------------------------------------------
def pid_start(pid) -> str | None:
    """A running process's start time (field 22 of /proc/<pid>/stat); None when it is gone or a zombie."""
    try:
        rest = Path(f"/proc/{int(pid)}/stat").read_text().rsplit(")", 1)[1].split()
    except (OSError, ValueError, TypeError, IndexError):
        return None
    if len(rest) < 20 or rest[0] in ("Z", "X", "x"):
        return None
    return rest[19]


def is_live(rec: dict, mtime: float | None, now: float | None = None) -> bool:
    """Its writer still runs (same pid and start time); a file without a pid: younger than NO_PID_MAX_AGE_S."""
    if "pid" in rec:
        st = pid_start(rec.get("pid"))
        return st is not None and str(rec.get("pid_start") or st) == st
    return mtime is not None and (time.time() if now is None else now) - mtime <= NO_PID_MAX_AGE_S


def paid_run_read(run_dir: str | Path | None = None) -> tuple[dict | None, float | None]:
    """(the record or None if unreadable / not an object, the file's mtime or None if there is no file)."""
    p = Path(run_dir or RUN_DIR) / PAID_FILE
    try:
        mtime = p.stat().st_mtime
        d = json.loads(p.read_text())
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError):
        try:
            return None, p.stat().st_mtime
        except OSError:
            return None, None
    return (d if isinstance(d, dict) else None), mtime


def paid_run_live(run_dir: str | Path | None = None) -> dict | None:
    rec, mtime = paid_run_read(run_dir)
    return rec if rec is not None and is_live(rec, mtime) else None


@contextmanager
def _locked(run_dir: Path):
    with open(run_dir / PAID_LOCK, "a") as lf:          # opened close-on-exec (Python's default): no child keeps it
        fcntl.flock(lf, fcntl.LOCK_EX)
        yield


def _same(rec: dict | None, want: dict) -> bool:
    return bool(rec) and all(rec.get(k) == v for k, v in want.items()) \
        and set(k for k in ("route", "cache") if k in rec) == set(k for k in ("route", "cache") if k in want)


def paid_run_write(kind: str, run: str, writer: str, run_dir: str | Path | None = None, route: str | None = None,
                   cache: bool | None = None, pid: int | None = None, only_if_changed: bool = False) -> dict | None:
    """Write run/paid-run.json atomically for this process (or `pid`). only_if_changed: leave an identical live file of
    the same writer process alone (returns None then). Raises ValueError on a bad record, OSError on a write error."""
    run_dir = Path(run_dir or RUN_DIR)
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, not {kind!r}")
    run = str(run or "").strip()
    if not run:
        raise ValueError("a paid run needs its run id")
    pid = os.getpid() if pid is None else int(pid)
    st = pid_start(pid)
    if st is None:
        raise ValueError(f"pid {pid} is not running")
    rec: dict = {"kind": kind, "run": run}
    if route:
        rec["route"] = str(route)
    if cache is not None:
        rec["cache"] = bool(cache)
    with _locked(run_dir):
        if only_if_changed:
            have, _ = paid_run_read(run_dir)
            if _same(have, {**rec, "pid": pid, "pid_start": st}):
                return None
        rec.update(writer=writer, pid=pid, pid_start=st, written=round(time.time(), 1))
        fd, tmp = tempfile.mkstemp(prefix=".paid-run.", suffix=".tmp", dir=run_dir)
        try:
            with os.fdopen(fd, "w") as f:
                f.write(json.dumps(rec) + "\n")
            os.chmod(tmp, 0o644)
            os.replace(tmp, run_dir / PAID_FILE)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    return rec


def paid_run_clear(run_dir: str | Path | None = None, pid: int | None = None, stale_only: bool = False) -> str:
    """Remove run/paid-run.json when it is this pid's (pid given, not stale_only) or stale (writer gone, unreadable, or
    without a pid and too old). A live file of another writer is kept. Returns what happened."""
    run_dir = Path(run_dir or RUN_DIR)
    if not (run_dir / PAID_FILE).exists():
        return "none"
    with _locked(run_dir):
        rec, mtime = paid_run_read(run_dir)
        if mtime is None:
            return "none"
        if rec is None:
            why = "unreadable"
        elif not is_live(rec, mtime):
            why = "stale"
        elif not stale_only and pid is not None and rec.get("pid") == int(pid):
            why = "own"
        else:
            return f"kept ({rec.get('writer', '?')} pid {rec.get('pid', '-')}: {rec.get('kind')} {rec.get('run')})"
        try:
            (run_dir / PAID_FILE).unlink()
        except FileNotFoundError:
            return "none"
        return f"removed ({why})"


def paid_run_text(run_dir: str | Path | None = None) -> str:
    rec, mtime = paid_run_read(run_dir)
    if mtime is None:
        return "none"
    if rec is None:
        return "unreadable (ignored)"
    route = f", route {rec['route']}" if rec.get("route") else ""
    cache = f", cache {'on' if rec['cache'] else 'off'}" if isinstance(rec.get("cache"), bool) else ""
    state = "live" if is_live(rec, mtime) else "STALE (ignored)"
    return f"{rec.get('kind')} {rec.get('run')}{route}{cache} ({rec.get('writer', '?')} pid {rec.get('pid', '-')}, {state})"


# -- CLI ------------------------------------------------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="ldr_runfiles.py", description=__doc__.split("\n\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("mp-check")
    c.add_argument("--want", default=None, help=f"profile name or path (default $LDR_MODEL_PROFILE, else {DEFAULT_PROFILE})")
    c.add_argument("--profiles-dir", default=str(PROFILES_DIR))
    for name in ("mp-check", "paid-show", "paid-clear"):
        p = c if name == "mp-check" else sp.add_parser(name)
        p.add_argument("--run-dir", default=str(RUN_DIR))
        if name == "paid-clear":
            p.add_argument("--stale-only", action="store_true", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "mp-check":
        why = modelprofile_mismatch(a.want or os.environ.get("LDR_MODEL_PROFILE"), a.run_dir, a.profiles_dir)
        if why:
            print(why)
        return 1 if why else 0
    if a.cmd == "paid-show":
        print(paid_run_text(a.run_dir))
        return 0
    print(paid_run_clear(a.run_dir, stale_only=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
