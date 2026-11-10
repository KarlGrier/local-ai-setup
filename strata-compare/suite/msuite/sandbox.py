"""Run code a model wrote: a throwaway folder under tmp/suite, no network, a time limit, killed afterwards.

The sandbox is bubblewrap (bwrap, already installed; no root needed): new user / pid / net / ipc / uts namespaces,
the system's /usr read-only, the throwaway folder as /work (the only writable place besides a private /tmp), no /home,
no /etc, an empty environment.  Limits: wall clock (the whole process group is SIGKILLed at the deadline), address
space, CPU seconds, file size, process count.  stdout / stderr go to files outside the folder and are read back capped.
"""
from __future__ import annotations

import os
import resource
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path

from .common import TMP

BWRAP = "/usr/bin/bwrap"
PYTHON = "/usr/bin/python3"
OUT_CAP = 200_000            # characters kept from stdout / stderr each


def _user_tasks() -> int:
    """Threads count against RLIMIT_NPROC, so count every task (thread) of this user, not just processes."""
    uid, n = os.getuid(), 0
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                if os.stat(f"/proc/{d}").st_uid == uid:
                    n += len(os.listdir(f"/proc/{d}/task"))
            except OSError:
                pass
    return n


def new_workdir(kind: str) -> Path:
    d = TMP / "sbx" / f"{kind}-{uuid.uuid4().hex[:12]}"
    d.mkdir(parents=True)
    return d


def remove_workdir(d: Path):
    d = Path(d)
    if TMP in d.parents:           # never delete anything outside tmp/suite
        shutil.rmtree(d, ignore_errors=True)


def run(cmd: list[str], workdir: Path, timeout_s: float = 60, mem_mb: int = 2048, cpu_s: int | None = None,
        fsize_mb: int = 64, extra_ro: list[tuple[str, str]] = (), env: dict | None = None) -> dict:
    """Run `cmd` inside the sandbox with `workdir` mounted read-write at /work.  Returns rc, stdout, stderr,
    timed_out, wall_s."""
    workdir = Path(workdir).resolve()
    logs = TMP / "sbx-logs"
    logs.mkdir(parents=True, exist_ok=True)
    tag = uuid.uuid4().hex[:12]
    out_p, err_p = logs / f"{tag}.out", logs / f"{tag}.err"
    args = [BWRAP, "--die-with-parent", "--unshare-all", "--new-session", "--hostname", "sandbox",
            "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib", "--ro-bind", "/lib64", "/lib64",
            "--ro-bind", "/bin", "/bin", "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
            "--bind", str(workdir), "/work", "--chdir", "/work", "--clearenv",
            "--setenv", "PATH", "/usr/bin:/bin", "--setenv", "HOME", "/work", "--setenv", "LANG", "C.UTF-8",
            "--setenv", "PYTHONUTF8", "1", "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
            "--setenv", "PYTHONHASHSEED", "0"]
    for src, dst in extra_ro:
        args += ["--ro-bind", src, dst]
    for k, v in (env or {}).items():
        args += ["--setenv", k, v]
    args += ["--"] + cmd
    nproc = _user_tasks() + 512
    cpu = int(cpu_s or timeout_s * 2 + 5)

    def limits():
        resource.setrlimit(resource.RLIMIT_AS, (mem_mb << 20, mem_mb << 20))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 5))
        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize_mb << 20, fsize_mb << 20))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        try:
            resource.setrlimit(resource.RLIMIT_NPROC, (nproc, nproc))
        except (ValueError, OSError):
            pass

    t0 = time.monotonic()
    timed_out = False
    with open(out_p, "wb") as fo, open(err_p, "wb") as fe:
        p = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=fo, stderr=fe, start_new_session=True,
                             preexec_fn=limits)
        try:
            rc = p.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            rc = None
        finally:
            try:
                os.killpg(p.pid, signal.SIGKILL)      # whatever is left in the group, always
            except ProcessLookupError:
                pass
            if rc is None:
                try:
                    p.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
    wall = time.monotonic() - t0
    out = out_p.read_bytes()[:OUT_CAP * 2].decode("utf-8", "replace")[:OUT_CAP]
    err = err_p.read_bytes()[:OUT_CAP * 2].decode("utf-8", "replace")[:OUT_CAP]
    out_p.unlink(missing_ok=True)
    err_p.unlink(missing_ok=True)
    return {"rc": rc, "stdout": out, "stderr": err, "timed_out": timed_out, "wall_s": round(wall, 2)}


def run_python_files(files: dict[str, str], main: str, timeout_s: float = 60, mem_mb: int = 2048,
                     keep: bool = False) -> dict:
    """Write `files` into a fresh throwaway folder, run `python3 -I main` there, delete the folder."""
    d = new_workdir("py")
    try:
        for name, text in files.items():
            p = d / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        res = run([PYTHON, "-I", main], d, timeout_s=timeout_s, mem_mb=mem_mb)
        if keep:
            res["workdir"] = str(d)
        return res
    finally:
        if not keep:
            remove_workdir(d)
