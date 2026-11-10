"""Resource monitor: 1 Hz samples of RAM/swap, server RSS and disk reads, NVMe reads, CPU busy, plus two nvidia-smi
streams (memory/link state and dmon utilisation/PCIe throughput). Stops on SIGTERM.

    monitor.py --label C0 --pid-pattern 'strata --serve' --out logs/monitor-C0
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time


def find_pid(pattern: str) -> int | None:
    try:
        out = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True).stdout.split()
        pids = [int(p) for p in out if int(p) != os.getpid()]
        return max(pids, key=lambda p: rss_kb(p)) if pids else None
    except Exception:
        return None


def rss_kb(pid: int) -> int:
    try:
        for line in open(f"/proc/{pid}/status"):
            if line.startswith("VmRSS"):
                return int(line.split()[1])
    except OSError:
        pass
    return 0


def proc_io(pid: int) -> int:
    try:
        for line in open(f"/proc/{pid}/io"):
            if line.startswith("read_bytes"):
                return int(line.split()[1])
    except OSError:
        pass
    return -1


def nvme_read_sectors(dev="nvme0n1") -> int:
    for line in open("/proc/diskstats"):
        f = line.split()
        if f[2] == dev:
            return int(f[5])
    return -1


def cpu_busy() -> tuple[int, int]:
    f = [int(x) for x in open("/proc/stat").readline().split()[1:]]
    idle = f[3] + f[4]
    return sum(f) - idle, sum(f)


def mem() -> dict:
    m = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":", 1)
        m[k] = int(v.split()[0])
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid-pattern", required=True)
    ap.add_argument("--out", required=True, help="path prefix")
    ap.add_argument("--interval", type=float, default=1.0)
    a = ap.parse_args()
    stop = {"v": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.update(v=True))
    signal.signal(signal.SIGINT, lambda *_: stop.update(v=True))
    sel = ["-i", os.environ["STRATA_MON_GPU"]] if os.environ.get("STRATA_MON_GPU") else []   # round 5: one card only
    q = subprocess.Popen(["nvidia-smi", *sel, "--query-gpu=timestamp,memory.used,memory.total,utilization.gpu,"
                          "pcie.link.gen.current,pcie.link.width.current,power.draw,temperature.gpu,clocks.sm",
                          "--format=csv,noheader,nounits", "-lms", str(int(a.interval * 1000))],
                         stdout=open(a.out + ".gpu.csv", "w"), stderr=subprocess.DEVNULL)
    d = subprocess.Popen(["nvidia-smi", "dmon", *sel, "-s", "put", "-d", "1", "-o", "T"],
                         stdout=open(a.out + ".dmon.txt", "w"), stderr=subprocess.DEVNULL)
    f = open(a.out + ".sys.csv", "w", buffering=1)
    f.write("t,pid,rss_mib,memavail_mib,cached_mib,swapused_mib,proc_read_mib,nvme_read_mib,cpu_busy_pct\n")
    pid = None
    b0 = cpu_busy()
    while not stop["v"]:
        if pid is None or not os.path.exists(f"/proc/{pid}"):
            pid = find_pid(a.pid_pattern)
        m = mem()
        b1 = cpu_busy()
        busy = 100.0 * (b1[0] - b0[0]) / max(1, b1[1] - b0[1])
        b0 = b1
        f.write("%.1f,%s,%d,%d,%d,%d,%.1f,%.1f,%.1f\n" % (
            time.time(), pid or "", rss_kb(pid) // 1024 if pid else 0, m["MemAvailable"] // 1024, m["Cached"] // 1024,
            (m["SwapTotal"] - m["SwapFree"]) // 1024, proc_io(pid) / 2**20 if pid else -1,
            nvme_read_sectors() * 512 / 2**20, busy))
        time.sleep(a.interval)
    q.terminate()
    d.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
