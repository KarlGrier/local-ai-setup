#!/usr/bin/env python3
"""guard.py — round 9 (copy of round 7, copy of round 6) memory guard around ONE experimental run (engine CLI, server, test client + server...).

    guard.py LABEL -- CMD ARGS...          (or: guard.py LABEL --watch-pattern REGEX  to guard a process started elsewhere)

Runs CMD in its own process group and samples every 0.2 s:
  * MemAvailable (/proc/meminfo) — floor 20 GiB (GUARD_MEM_GIB)
  * free VRAM on the RTX 5080 (nvidia-smi stream, by UUID) — floor 300 MiB (GUARD_VRAM_MIB)
  * the process tree's RSS, swap used
If a floor is crossed for 3 consecutive samples (0.6 s) the whole process group gets SIGTERM (then SIGKILL after 10 s)
and the run is marked GUARD-STOP.  Load-time peaks are included (sampling starts before the child is started).
Writes bringup/out/logs/guard/LABEL.csv (every sample) and appends one summary line to bringup/out/logs/guard/summary.txt:
  label, exit code, duration, min MemAvailable (GiB) + when, min 5080 free (MiB) + when, max tree RSS, max swap used.

2026-10-16 (r21, the standing 8080 guard; measurement runs keep the defaults above):
  GUARD_VRAM_MODE  stop (default, as above) | warn60 (the first sample under the VRAM floor writes a warning - the
                   processes on the NVIDIA cards included - and Strata is stopped only after GUARD_VRAM_HOLD_S, default
                   60, straight seconds under it) | log (the VRAM floor is logged, never acted on).  The memory floor
                   (and the swap rule) stop as before in every mode.
  GUARD_FOLLOW_PORT  with --watch-pattern: keep guarding across engine restarts (the server restarts a stopped engine
                   on the next request): when the watched process is gone, find the pattern again; exit only once
                   nothing listens on this port.  The CSV then gets a row every 5 s (and every sample under a floor).
  Warnings and stops are appended to bringup/out/logs/guard/LABEL.events (and sent as a desktop notification when
  notify-send exists).
"""
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
GPU = os.environ.get("STRATA_MON_GPU", "GPU-UUID-RTX5080")
MEM_FLOOR = float(os.environ.get("GUARD_MEM_GIB", "20")) * 1024 ** 3
VRAM_FLOOR = float(os.environ.get("GUARD_VRAM_MIB", "300"))
# round 15 (your rule for the stand-in files): stop a run when swap in use grows by more than this many GiB over its
# start (GUARD_SWAP_GROW_GIB; unset = no swap rule, as before)
SWAP_GROW = float(os.environ.get("GUARD_SWAP_GROW_GIB", "0")) * 1024 ** 3
VRAM_MODE = os.environ.get("GUARD_VRAM_MODE", "stop")
if VRAM_MODE not in ("stop", "warn60", "log"):
    sys.exit(f"guard.py: GUARD_VRAM_MODE must be stop, warn60 or log, not {VRAM_MODE!r}")
VRAM_HOLD = float(os.environ.get("GUARD_VRAM_HOLD_S", "60"))
FOLLOW_PORT = os.environ.get("GUARD_FOLLOW_PORT")
OUT = WS / "bringup/out/logs/guard"
OUT.mkdir(parents=True, exist_ok=True)


def meminfo():
    d = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":", 1)
        d[k] = int(v.split()[0]) * 1024
    return d


def tree_rss(root):
    """RSS of `root` and all descendants (bytes)."""
    kids = {}
    for p in os.listdir("/proc"):
        if not p.isdigit():
            continue
        try:
            with open(f"/proc/{p}/stat") as f:
                ppid = int(f.read().rsplit(")", 1)[1].split()[1])
            kids.setdefault(ppid, []).append(int(p))
        except OSError:
            pass
    total, stack = 0, [root]
    while stack:
        q = stack.pop()
        try:
            for line in open(f"/proc/{q}/status"):
                if line.startswith("VmRSS"):
                    total += int(line.split()[1]) * 1024
                    break
        except OSError:
            pass
        stack.extend(kids.get(q, []))
    return total


GPU2 = os.environ.get("GUARD_GPU2", "GPU-UUID-RTX4060TI")   # the 4060 Ti (desktop): logged


class Vram:
    def __init__(self, uuid=GPU):
        self.free = None
        self.p = subprocess.Popen(["nvidia-smi", "-i", uuid, "--query-gpu=memory.free", "--format=csv,noheader,nounits",
                                   "-lms", "200"], stdout=subprocess.PIPE, text=True)
        threading.Thread(target=self.read, daemon=True).start()

    def read(self):
        for line in self.p.stdout:
            try:
                self.free = float(line.strip())
            except ValueError:
                pass

    def stop(self):
        self.p.terminate()


def gpu_processes():
    """What sits on the NVIDIA cards now: the Processes table of nvidia-smi (graphics and compute)."""
    try:
        txt = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=10).stdout
    except Exception as e:   # noqa: BLE001 - a warning must still be written
        return f"(nvidia-smi failed: {e})"
    rows = [l.strip("| ").rstrip() for l in txt.split("Processes:", 1)[-1].splitlines()
            if l.startswith("|") and l.split()[1:2] and l.split()[1].isdigit()]
    return "; ".join(" ".join(r.split()) for r in rows) or "(none listed)"


def event(label, text, notify=False):
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {label}: {text}"
    with open(OUT / f"{label}.events", "a") as f:
        f.write(line + "\n")
    print(f"guard.py {line}", file=sys.stderr, flush=True)
    if not notify or os.environ.get("GUARD_NOTIFY", "1") == "0":
        return
    try:
        subprocess.Popen(["notify-send", "-u", "critical", "Strata guard", text[:400]], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except OSError:
        pass


def find(watch):
    """The first process whose command line matches `watch`, not this guard - and, when the pattern starts with an
    absolute path (the engine binary), only a process running that binary: a shell, grep or editor whose command line
    merely mentions the pattern is never picked (r21: a test guard picked the calling shell and stopped it)."""
    exe = watch.split()[0] if watch.split() and watch.startswith("/") else None
    for x in subprocess.run(["pgrep", "-f", watch], capture_output=True, text=True).stdout.split():
        pid = int(x)
        if pid == os.getpid():
            continue
        if exe is not None:
            try:
                if os.readlink(f"/proc/{pid}/exe").removesuffix(" (deleted)") != exe:
                    continue
            except OSError:
                continue
        return pid
    return None


def alive(pid):
    """pid exists and is not a zombie (a stopped engine stays a zombie until its server reaps it)."""
    try:
        with open(f"/proc/{pid}/stat") as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


def listening(port):
    r = subprocess.run(["ss", "-Hltn", f"( sport = :{port} )"], capture_output=True, text=True)
    return bool(r.stdout.strip())


def main():
    label = sys.argv[1]
    argv = sys.argv[2:]
    watch = None
    if argv and argv[0] == "--watch-pattern":
        watch = argv[1]
    else:
        if argv and argv[0] == "--":
            argv = argv[1:]
    vr = Vram()
    vr2 = Vram(GPU2)
    mn_v2 = 1e18
    time.sleep(0.5)
    csv = open(OUT / f"{label}.csv", "w")
    csv.write("t,memavail_gib,vram_free_mib,tree_rss_gib,swap_used_gib\n")
    t0 = time.time()
    if watch is None:
        child = subprocess.Popen(argv, start_new_session=True)
        pid = child.pid
    else:
        pid = find(watch)
        child = None
    mn_mem, mn_mem_t, mn_v, mn_v_t, mx_rss, mx_swap = 1e18, 0, 1e18, 0, 0, 0
    m0 = meminfo()
    swap0 = m0["SwapTotal"] - m0["SwapFree"]
    bad, stopped = 0, None
    rc = None
    vlow_since = None          # warn60 / log: when the 5080 went under the VRAM floor (None = not under it)
    stopped_pids = set()       # follow mode: each engine is stopped at most once
    last_row = -1e9
    if FOLLOW_PORT:
        event(label, f"guarding {watch!r} on port {FOLLOW_PORT}: engine pid {pid}, VRAM mode {VRAM_MODE} "
                     f"(floor {VRAM_FLOOR:.0f} MiB, hold {VRAM_HOLD:.0f} s), memory floor {MEM_FLOOR/1024**3:.0f} GiB")
    while True:
        if child is not None:
            rc = child.poll()
            if rc is not None:
                break
        elif pid is None or not (alive(pid) if FOLLOW_PORT else os.path.exists(f"/proc/{pid}")):
            if not FOLLOW_PORT:
                break
            pid = find(watch)
            if pid is None:
                if not listening(FOLLOW_PORT):
                    event(label, f"nothing listens on port {FOLLOW_PORT} any more - guard ends")
                    break
                time.sleep(2)
                continue
            event(label, f"guarding the restarted engine, pid {pid}")
            vlow_since = None   # a new engine gets the full hold time (loading it lowers the free VRAM anyway)
        m = meminfo()
        avail = m["MemAvailable"]
        swap = m["SwapTotal"] - m["SwapFree"]
        rss = tree_rss(pid) if pid else 0
        v = vr.free if vr.free is not None else 1e9
        t = time.time() - t0
        under = avail < MEM_FLOOR or v < VRAM_FLOOR
        if not FOLLOW_PORT or under or t - last_row >= 5:
            csv.write(f"{t:.1f},{avail/1024**3:.2f},{v:.0f},{rss/1024**3:.2f},{swap/1024**3:.2f}\n")
            last_row = t
            if FOLLOW_PORT:
                csv.flush()
        if avail < mn_mem:
            mn_mem, mn_mem_t = avail, t
        if v < mn_v:
            mn_v, mn_v_t = v, t
        mx_rss, mx_swap = max(mx_rss, rss), max(mx_swap, swap)
        if vr2.free is not None:
            mn_v2 = min(mn_v2, vr2.free)
        vram_act = v < VRAM_FLOOR and VRAM_MODE == "stop"
        if VRAM_MODE != "stop":
            if v < VRAM_FLOOR:
                if vlow_since is None:
                    vlow_since = t
                    event(label, f"WARNING: RTX 5080 free VRAM {v:.0f} MiB < floor {VRAM_FLOOR:.0f} MiB"
                                 + (f"; Strata is stopped if it stays under for {VRAM_HOLD:.0f} s" if VRAM_MODE == "warn60"
                                    else " (log only)") + f". On the NVIDIA cards: {gpu_processes()}", notify=True)
                elif VRAM_MODE == "warn60" and t - vlow_since >= VRAM_HOLD:
                    vram_act = True
            elif vlow_since is not None:
                event(label, f"RTX 5080 free VRAM back above the floor ({v:.0f} MiB) after {t - vlow_since:.0f} s", notify=True)
                vlow_since = None
        mem_act = avail < MEM_FLOOR or (SWAP_GROW > 0 and swap - swap0 > SWAP_GROW)
        if mem_act or vram_act:
            bad = bad + 1 if mem_act or VRAM_MODE == "stop" else 3
            may_stop = pid is not None and (stopped is None if not FOLLOW_PORT else pid not in stopped_pids)
            if bad >= 3 and may_stop:
                stopped_pids.add(pid)
                why = (f"GUARD-STOP at {t:.1f}s (MemAvailable {avail/1024**3:.1f} GiB, 5080 free {v:.0f} MiB, swap +{(swap - swap0)/1024**3:.1f} GiB)"
                       + (f", VRAM under the floor for {t - vlow_since:.0f} s" if vram_act and vlow_since is not None else ""))
                stopped = stopped or why
                if FOLLOW_PORT or VRAM_MODE != "stop":
                    event(label, why + f". On the NVIDIA cards: {gpu_processes()}", notify=True)
                print(f"guard.py {label}: {why}", file=sys.stderr, flush=True)
                if child is not None:
                    os.killpg(pid, signal.SIGTERM)
                    try:
                        child.wait(10)
                    except subprocess.TimeoutExpired:
                        os.killpg(pid, signal.SIGKILL)
                else:   # a watched server: stop it (the server stops its engine)
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except OSError:
                        pass
        else:
            bad = 0
        time.sleep(0.2)
    vr.stop()
    vr2.stop()
    csv.close()
    dur = time.time() - t0
    line = (f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {label} exit={rc} {dur:.0f}s min_MemAvailable={mn_mem/1024**3:.1f}GiB"
            f"@{mn_mem_t:.0f}s min_5080_free={mn_v:.0f}MiB@{mn_v_t:.0f}s max_tree_RSS={mx_rss/1024**3:.1f}GiB "
            f"max_swap_used={mx_swap/1024**3:.2f}GiB min_4060Ti_free={mn_v2:.0f}MiB {stopped or 'ok'}")
    with open(OUT / "summary.txt", "a") as f:
        f.write(line + "\n")
    print(line, flush=True)
    sys.exit(rc if rc is not None else 0)


if __name__ == "__main__":
    main()
