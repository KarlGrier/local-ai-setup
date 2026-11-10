#!/usr/bin/env python3
"""uptime.py --until HH:MM [--every 900] — round 5, phase 7: watch the daily Strata server on 127.0.0.1:8080.

Every `every` seconds (default 15 min): one small probe request (first-token latency after the idle time before it),
then one CSV row in logs/r5/uptime.csv: engine + server RSS, open file descriptors, engine/server log sizes, the CPU
time both used while idle since the last probe, VRAM used on the 5080, MemAvailable, and new error lines in the
logs. Stops by itself at --until (local time, today or tomorrow)."""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import time
from pathlib import Path

import requests

WS = Path("/home/USER/ai-speed-testing/strata-compare")
OUT = WS / "logs/r5/uptime.csv"
UUID = "GPU-UUID-RTX5080"
BASE = "http://127.0.0.1:8080"
ERR = re.compile(r"\bERR\b|error|Traceback|exception|watchdog|no progress|stall", re.I)
BENIGN = re.compile(r"no error|error-ish", re.I)


def pids():
    """(server.py, engine) - by process name too: other command lines (a monitor, a shell) can contain the patterns"""
    def find(pat, comm):
        for p in subprocess.run(["pgrep", "-f", pat], capture_output=True, text=True).stdout.split():
            try:
                if open(f"/proc/{p}/comm").read().strip().startswith(comm):
                    return int(p)
            except OSError:
                pass
        return None
    return find("serve/server.py --engine strata", "python"), find("strata --serve", "strata")


def rss_mib(pid):
    try:
        for ln in open(f"/proc/{pid}/status"):
            if ln.startswith("VmRSS:"):
                return int(ln.split()[1]) // 1024
    except OSError:
        return None


def fds(pid):
    try:
        return len(os.listdir(f"/proc/{pid}/fd"))
    except OSError:
        return None


def ticks(pid):
    try:
        v = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()
        return int(v[11]) + int(v[12])
    except OSError:
        return None


def logs(srv):
    """the server's log file (its stdout) and the engine log from the config"""
    out = []
    try:
        out.append(os.readlink(f"/proc/{srv}/fd/1"))
    except OSError:
        pass
    try:
        cmd = open(f"/proc/{srv}/cmdline").read().split("\0")
        cfg = json.load(open(cmd[cmd.index("--config") + 1]))
        out.append(cfg["log"])
    except (OSError, ValueError, KeyError, IndexError):
        pass
    return out


def gpu_procs():
    """the other processes on the 5080 (graphics and compute) as 'name:MiB;...' (e.g. Chrome's GPU process)"""
    out = subprocess.run(["nvidia-smi", "-i", UUID], capture_output=True, text=True).stdout
    procs = []
    for ln in out.splitlines():
        m = re.match(r"\|\s+\d+\s+\S+\s+\S+\s+(\d+)\s+([CG+]+)\s+(\S+)\s+(\d+)MiB", ln)
        if m and "strata" not in m.group(3):
            procs.append(f"{os.path.basename(m.group(3))}:{m.group(4)}")
    return ";".join(procs)


def search_probe():
    """the local SearXNG (the chat page's web search): one test query -> (results, ms, error)"""
    t0 = time.time()
    try:
        r = requests.get("http://127.0.0.1:8888/search", params={"q": "linux kernel latest stable release", "format": "json"},
                         timeout=30, proxies={"http": None, "https": None})
        d = r.json()
        return len(d.get("results") or []), int((time.time() - t0) * 1000), \
            ";".join(str(e[0]) for e in (d.get("unresponsive_engines") or []))
    except Exception as e:  # noqa: BLE001
        return 0, int((time.time() - t0) * 1000), repr(e)[:80].replace(",", ";")


def probe():
    t0 = time.time()
    ttft = None
    err = None
    try:
        with requests.post(f"{BASE}/v1/chat/completions", stream=True, timeout=600,
                           json={"model": "x", "stream": True, "max_tokens": 64, "reasoning_effort": "none",
                                 "messages": [{"role": "user", "content": "Reply with the single word OK."}]}) as r:
            if r.status_code != 200:
                err = f"HTTP {r.status_code}: {r.text[:200]}"
            for line in r.iter_lines():
                if line.startswith(b"data: ") and line != b"data: [DONE]":
                    ev = json.loads(line[6:])
                    if "error" in ev:
                        err = str(ev["error"])[:200]
                    for ch in ev.get("choices", []):
                        d = ch.get("delta", {})
                        if (d.get("content") or d.get("reasoning_content")) and ttft is None:
                            ttft = time.time() - t0
    except Exception as e:  # noqa: BLE001
        err = repr(e)[:200]
    return ttft, time.time() - t0, err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", required=True)
    ap.add_argument("--every", type=int, default=900)
    a = ap.parse_args()
    now = dt.datetime.now()
    hh, mm = map(int, a.until.split(":"))
    end = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if end <= now:
        end += dt.timedelta(days=1)
    new = not OUT.exists()
    f = open(OUT, "a", buffering=1)
    if new:
        f.write("time,idle_s,probe_ttft_s,probe_total_s,probe_error,server_pid,engine_pid,server_rss_mib,engine_rss_mib,"
                "server_fds,engine_fds,server_log_mib,engine_log_mib,idle_cpu_server_pct,idle_cpu_engine_pct,"
                "vram_used_mib,memavail_mib,new_error_lines,error_sample,other_5080_procs,search_results,search_ms,search_problems\n")
    hz = os.sysconf("SC_CLK_TCK")
    last = {"t": time.time(), "tick": {}, "sizes": {}}
    srv, eng = pids()
    for p in (srv, eng):
        if p:
            last["tick"][p] = ticks(p)
    for lg in logs(srv) if srv else []:
        last["sizes"][lg] = os.path.getsize(lg) if os.path.exists(lg) else 0
    while dt.datetime.now() < end:
        time.sleep(max(1, min(a.every, (end - dt.datetime.now()).total_seconds())))
        if dt.datetime.now() >= end:
            break
        srv, eng = pids()
        idle = time.time() - last["t"]
        cpu = {}
        for p in (srv, eng):
            t = ticks(p) if p else None
            t0 = last["tick"].get(p)
            cpu[p] = round(100.0 * (t - t0) / hz / idle, 3) if t is not None and t0 is not None else None
        ttft, total, err = probe()
        srv, eng = pids()
        errs, sample, sizes = 0, "", []
        for lg in logs(srv) if srv else []:
            sz = os.path.getsize(lg) if os.path.exists(lg) else 0
            sizes.append(round(sz / 1048576, 2))
            s0 = last["sizes"].get(lg, 0)
            if sz > s0:
                with open(lg, "rb") as fh:
                    fh.seek(s0)
                    for ln in fh.read().decode("utf-8", "replace").splitlines():
                        if ERR.search(ln) and not BENIGN.search(ln):
                            errs += 1
                            sample = sample or ln[:160].replace(",", ";")
            last["sizes"][lg] = sz
        vram = subprocess.run(["nvidia-smi", "-i", UUID, "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                              capture_output=True, text=True).stdout.strip()
        avail = next(int(ln.split()[1]) // 1024 for ln in open("/proc/meminfo") if ln.startswith("MemAvailable"))
        f.write(",".join(str(x) for x in [
            dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), round(idle), ttft and round(ttft, 3), round(total, 3),
            (err or "").replace(",", ";"), srv, eng, rss_mib(srv) if srv else None, rss_mib(eng) if eng else None,
            fds(srv) if srv else None, fds(eng) if eng else None, *(sizes + [None, None])[:2],
            cpu.get(srv), cpu.get(eng), vram, avail, errs, sample, gpu_procs(), *search_probe()]) + "\n")
        last["t"] = time.time()
        for p in (srv, eng):
            if p:
                last["tick"][p] = ticks(p)


if __name__ == "__main__":
    main()
