#!/usr/bin/env python3
"""uptime_monitor.py — round 6: a PASSIVE 48-hour watch of the Strata server on 127.0.0.1:8080.

It never sends a model request, never restarts, updates or reconfigures anything.  Every 15 minutes it reads:
  * GET /health, /status, /metrics?requests=all (the server's own records of YOUR requests: prompt tokens, reused
    tokens, prompt ms, decode ms, decode tok/s, finish) — new requests since the last sample go to requests.csv;
  * /proc: server and engine pid, their start times, RSS, open file descriptors, CPU time (idle CPU = CPU used over an
    interval in which no request ran), the log sizes; /proc/meminfo MemAvailable and swap;
  * nvidia-smi: free memory on the RTX 5080 and the RTX 4060 Ti.
One row per sample in samples.csv.  Identity = server pid + start time, engine pid + start time + executable sha256 +
config + model id; when it changes (restart, other model, other build) the change is written to events.log and the
current segment ends; a new segment starts with the new identity (still passive).  No server: a DOWN row.
Stops after --hours (default 48).  Stop by hand: kill $(cat logs/r6/uptime/monitor.pid)
"""
import argparse
import csv
import hashlib
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
OUT = WS / "logs/r6/uptime"
GPUS = {"5080": "GPU-UUID-RTX5080", "4060ti": "GPU-UUID-RTX4060TI"}
TICK = os.sysconf("SC_CLK_TCK")
BOOT = time.time() - float(open("/proc/uptime").read().split()[0])


def get(base, path, timeout=10):
    try:
        with urllib.request.urlopen(base + path, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        return {"_error": repr(e)[:200]}


def pgrep(pat):
    out = subprocess.run(["pgrep", "-f", pat], capture_output=True, text=True).stdout.split()
    return [int(p) for p in out if int(p) != os.getpid()]


def comm(pid):
    try:
        return open(f"/proc/{pid}/comm").read().strip()
    except OSError:
        return ""


def cmdline(pid):
    try:
        return open(f"/proc/{pid}/cmdline", "rb").read().split(b"\0")
    except OSError:
        return []


def find_procs(port):
    server = None
    for p in pgrep("serve/server.py"):
        c = [x.decode(errors="replace") for x in cmdline(p)]
        if comm(p).startswith("python") and "--port" in c and c[c.index("--port") + 1] == str(port):
            server = p
    engine = None
    if server:
        for p in pgrep("strata --serve"):
            try:
                ppid = int(open(f"/proc/{p}/stat").read().rsplit(")", 1)[1].split()[1])
            except OSError:
                continue
            if ppid == server and comm(p).startswith("strata"):
                engine = p
    return server, engine


def stat(pid):
    """(start wall time, cpu seconds) from /proc/pid/stat"""
    f = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()
    return BOOT + int(f[19]) / TICK, (int(f[11]) + int(f[12])) / TICK


def status_kb(pid, key):
    for line in open(f"/proc/{pid}/status"):
        if line.startswith(key):
            return int(line.split()[1])
    return 0


def nfds(pid):
    try:
        return len(os.listdir(f"/proc/{pid}/fd"))
    except OSError:
        return -1


_sha = {}


def sha_of(path):
    if path not in _sha:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        _sha[path] = h.hexdigest()[:16]
    return _sha[path]


def gpu_free():
    out = {}
    for name, uuid in GPUS.items():
        try:
            out[name] = int(subprocess.run(["nvidia-smi", "-i", uuid, "--query-gpu=memory.free",
                                            "--format=csv,noheader,nounits"], capture_output=True, text=True,
                                           timeout=20).stdout.strip())
        except Exception:  # noqa: BLE001
            out[name] = -1
    return out


def meminfo():
    d = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":", 1)
        d[k] = int(v.split()[0])
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=48.0)
    ap.add_argument("--every", type=float, default=900.0)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    globals()["OUT"] = Path(a.out)
    base = f"http://127.0.0.1:{a.port}"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "monitor.pid").write_text(str(os.getpid()))
    ev = open(OUT / "events.log", "a", buffering=1)
    sfile = OUT / "samples.csv"
    rfile = OUT / "requests.csv"
    scols = ["time", "segment", "state", "server_pid", "engine_pid", "engine_started", "rss_engine_mib", "rss_server_mib",
             "fds_engine", "fds_server", "engine_log_mib", "server_log_mib", "cpu_engine_s", "requests_in_interval",
             "idle_cpu_pct_engine", "busy_now", "memavail_gib", "swap_used_mib", "free_5080_mib", "free_4060ti_mib",
             "requests_total", "health"]
    rcols = ["segment", "time", "duration_s", "finish", "prompt_tokens", "reused", "prompt_ms", "prompt_tok_s",
             "output_tokens", "decode_ms", "decode_tok_s", "hit_rate"]
    new_s, new_r = not sfile.exists(), not rfile.exists()
    sw = csv.writer(open(sfile, "a", newline="", buffering=1))
    rw = csv.writer(open(rfile, "a", newline="", buffering=1))
    if new_s:
        sw.writerow(scols)
    if new_r:
        rw.writerow(rcols)
    t_end = time.time() + a.hours * 3600
    ev.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} START passive monitor pid {os.getpid()} for {a.hours} h, every "
             f"{a.every:.0f} s, {base} (GET /health /status /metrics only)\n")
    ident, segment, last_seen, prev_cpu, prev_t, prev_total = None, 0, 0.0, None, None, None
    while time.time() < t_end:
        now = time.time()
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        server, engine = find_procs(a.port)
        mi = meminfo()
        gf = gpu_free()
        if not server or not engine:
            if ident is not None:
                ev.write(f"{stamp} CHANGE server/engine gone (was {ident}); segment {segment} ends\n")
                ident = None
            sw.writerow([stamp, segment, "DOWN", server, engine] + [""] * 10 +
                        [round(mi["MemAvailable"] / 2**20, 2), (mi["SwapTotal"] - mi["SwapFree"]) // 1024,
                         gf["5080"], gf["4060ti"], "", ""])
            time.sleep(min(a.every, max(1, t_end - time.time())))
            continue
        h = get(base, "/health")
        m = get(base, "/metrics?requests=all")
        st = get(base, "/status")
        e_start, e_cpu = stat(engine)
        s_start, _ = stat(server)
        c = [x.decode(errors="replace") for x in cmdline(server)]
        cfg = c[c.index("--config") + 1] if "--config" in c else "?"
        exe = os.readlink(f"/proc/{engine}/exe")
        cur = (server, round(s_start), engine, round(e_start), sha_of(exe), cfg, h.get("model"))
        if cur != ident:
            if ident is not None:
                ev.write(f"{stamp} CHANGE identity {ident} -> {cur}; segment {segment} ends\n")
            segment += 1
            ident = cur
            ev.write(f"{stamp} SEGMENT {segment}: server pid {server} (started {time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(s_start))}), "
                     f"engine pid {engine} (started {time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(e_start))}), "
                     f"exe {exe} sha256 {sha_of(exe)}..., config {cfg}, model {h.get('model')}\n")
            prev_cpu, prev_t, prev_total = None, None, None
            last_seen = now - a.every if last_seen == 0 else last_seen
        reqs = [r for r in (m.get("requests") or []) if (r.get("time") or 0) > last_seen]
        for r in sorted(reqs, key=lambda r: r.get("time") or 0):
            pt = r.get("prompt_tokens") or 0
            ru = r.get("reused") or 0
            pms = r.get("prompt_ms")
            rw.writerow([segment, time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(r.get("time") or 0)), r.get("duration_s"),
                         r.get("finish"), pt, ru, pms, round((pt - ru) / (pms / 1000), 1) if pms else "",
                         r.get("output_tokens"), r.get("decode_ms"), r.get("decode_tok_s"), r.get("hit_rate")])
            last_seen = max(last_seen, r.get("time") or 0)
        total = (m.get("totals") or {}).get("requests")
        n_int = (total - prev_total) if (total is not None and prev_total is not None) else ""
        idle = ""
        if prev_cpu is not None and n_int == 0 and not st.get("busy"):
            idle = round(100 * (e_cpu - prev_cpu) / (now - prev_t), 3)
        logdir = WS / "logs"
        try:
            elog = json.load(open(cfg)).get("log", "")
            elog_mib = round(os.path.getsize(elog) / 2**20, 2) if elog and os.path.exists(elog) else ""
        except Exception:  # noqa: BLE001
            elog_mib = ""
        try:
            slog = open(WS / f"logs/run/strata-{a.port}.logpath").read().strip()
            slog_mib = round(os.path.getsize(slog) / 2**20, 2)
        except Exception:  # noqa: BLE001
            slog_mib = ""
        sw.writerow([stamp, segment, "busy" if st.get("busy") else "idle", server, engine,
                     time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(e_start)),
                     status_kb(engine, "VmRSS") // 1024, status_kb(server, "VmRSS") // 1024, nfds(engine), nfds(server),
                     elog_mib, slog_mib, round(e_cpu, 1), n_int, idle, bool(st.get("busy")),
                     round(mi["MemAvailable"] / 2**20, 2), (mi["SwapTotal"] - mi["SwapFree"]) // 1024, gf["5080"],
                     gf["4060ti"], total, h.get("status", h.get("_error"))])
        prev_cpu, prev_t, prev_total = e_cpu, now, total
        _ = logdir
        time.sleep(min(a.every, max(1, t_end - time.time())))
    ev.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} END after {a.hours} h\n")


if __name__ == "__main__":
    main()
