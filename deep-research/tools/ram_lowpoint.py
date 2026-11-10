#!/usr/bin/env python3
"""ram_lowpoint.py - what uses RAM at the low point of a research report stage (2026-10-19, the user's request).

Samples MemAvailable every 10 s until the given bench run ends (its bench.json appears). While the run's deep evidence
file says the report stage has started (the lead's "lead_answer" note), every new low writes a full snapshot:
/proc/meminfo, every process group's RSS (Strata's engine with its expert arena, parked chat-cache conversations and
shared/pinned buffers, Strata's server, LDR, both SearXNG instances, Jan, the proxy, the runner, the rest), so the
lowest point of the stage is the one left in the output file.

  ram_lowpoint.py RUN_DIR DEEP_OUT_DIR OUT.json
"""
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

run_dir, deep_dir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
ENGINE_LOG = Path("/home/USER/ai-speed-testing/strata-compare/logs/engine-Cstar18t.log")


def meminfo():
    m = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":", 1)
        m[k] = int(v.split()[0]) * 1024
    return m


def procs():
    out = []
    for p in os.listdir("/proc"):
        if not p.isdigit():
            continue
        try:
            st = Path(f"/proc/{p}/status").read_text()
            cmd = Path(f"/proc/{p}/cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").strip()
        except OSError:
            continue
        f = dict(re.findall(r"^(\w+):\s+(\d+) kB", st, re.M))
        rss = int(f.get("VmRSS", 0)) * 1024
        if rss:
            out.append({"pid": int(p), "cmd": cmd, "comm": Path(f"/proc/{p}/comm").read_text().strip() if Path(f"/proc/{p}/comm").exists() else "",
                        "rss": rss, "anon": int(f.get("RssAnon", 0)) * 1024, "file": int(f.get("RssFile", 0)) * 1024,
                        "shmem": int(f.get("RssShmem", 0)) * 1024})
    return out


GROUPS = [("Strata engine", lambda p: p["comm"] in ("strata", "strata-host")),
          ("Strata server", lambda p: "serve/server.py" in p["cmd"]),
          ("LDR (ldr-web)", lambda p: "ldr-web" in p["cmd"] or p["comm"] == "ldr-web"),
          ("SearXNG 8889 (LDR)", lambda p: "granian" in p["cmd"] and (":8889" in p["cmd"] or "deep-research/searxng" in p["cmd"])),
          ("SearXNG 8888 (chat page)", lambda p: "granian" in p["cmd"] and (":8888" in p["cmd"] or "websearch" in p["cmd"])),
          ("SearXNG (other granian)", lambda p: "granian" in p["cmd"]),
          ("Jan", lambda p: "Jan_0.8.6" in p["cmd"] or "/tmp/.mount_Jan" in p["cmd"] or p["comm"].lower().startswith("jan")),
          ("strata-proxy", lambda p: "strata-proxy.py" in p["cmd"]),
          ("research runner", lambda p: "research-runner.py" in p["cmd"]),
          ("bench client", lambda p: "ldr-client.py" in p["cmd"] or "bench2.py" in p["cmd"]),
          ("browser", lambda p: any(b in p["cmd"].lower() for b in ("brave", "chrome", "firefox"))),
          ]


def grouped(ps):
    g, used = {}, set()
    for name, test in GROUPS:
        sel = [p for p in ps if p["pid"] not in used and test(p)]
        used |= {p["pid"] for p in sel}
        if sel:
            g[name] = {"rss_gib": round(sum(p["rss"] for p in sel) / 2**30, 2), "procs": len(sel),
                       "anon_gib": round(sum(p["anon"] for p in sel) / 2**30, 2),
                       "shmem_gib": round(sum(p["shmem"] for p in sel) / 2**30, 2)}
    rest = sorted((p for p in ps if p["pid"] not in used), key=lambda p: -p["rss"])
    g["everything else"] = {"rss_gib": round(sum(p["rss"] for p in rest) / 2**30, 2), "procs": len(rest),
                            "top": [(p["comm"], round(p["rss"] / 2**30, 2)) for p in rest[:6]]}
    return g


def chat_cache_parked():
    """Parked chat-cache conversations since the engine's last start, from its log."""
    try:
        lines = ENGINE_LOG.read_text(errors="replace").splitlines()
    except OSError:
        return None
    start = max((i for i, l in enumerate(lines) if "participating threads" in l), default=0)
    parked = []   # (tokens, mib)
    for l in lines[start:]:
        m = re.search(r"chat cache: parked a conversation of (\d+) tokens \(\d+ checkpoints?, (\d+) MiB\)", l)
        if m:
            parked.append((int(m.group(1)), int(m.group(2)))); continue
        m = re.search(r"chat cache: (?:dropped a conversation|dropped an older copy) of (\d+) tokens", l)
        if m:
            t = int(m.group(1))
            for i, (tt, _) in enumerate(parked):
                if tt == t:
                    parked.pop(i); break
            continue
        m = re.search(r"chat cache: restored a conversation of (\d+) tokens", l)
        if m:
            t = int(m.group(1))
            for i, (tt, _) in enumerate(parked):
                if tt == t:
                    parked.pop(i); break
    return {"conversations": len(parked), "mib": sum(m for _, m in parked), "largest_mib": max((m for _, m in parked), default=0)}


def strata_metrics():
    try:
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        e = json.load(op.open("http://127.0.0.1:8080/metrics", timeout=5))["engine"]
        return {k: e.get(k) for k in ("arena_mib", "expert_cache_mib", "expert_slots", "kv_resident", "vram_free_mib")}
    except Exception:  # noqa: BLE001
        return None


def report_stage():
    ev = deep_dir / "evidence.jsonl"
    try:
        with open(ev, "rb") as f:
            return b'"kind": "lead_answer"' in f.read()
    except OSError:
        return False


low = None
while not (run_dir / "bench.json").exists():
    if report_stage():
        m = meminfo()
        av = m["MemAvailable"]
        if low is None or av < low:
            low = av
            ps = procs()
            snap = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "stage": "report" if not (deep_dir / "report-unverified.md").exists() else "citation check",
                    "meminfo_gib": {k: round(m[k] / 2**30, 2) for k in ("MemTotal", "MemAvailable", "MemFree", "Cached", "Buffers",
                                                                        "Shmem", "AnonPages", "Mlocked", "Unevictable", "Slab", "PageTables")},
                    "swap_used_gib": round((m["SwapTotal"] - m["SwapFree"]) / 2**30, 2),
                    "groups": grouped(ps), "strata_metrics": strata_metrics(), "chat_cache_parked": chat_cache_parked()}
            out.write_text(json.dumps(snap, indent=1))
    time.sleep(10)
print(f"done; lowest MemAvailable in the report stage: {low / 2**30:.2f} GiB" if low else "no report-stage sample")
